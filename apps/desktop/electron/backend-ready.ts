import fs from 'node:fs'

// `hermes serve` announces HERMES_BACKEND_READY; the legacy `hermes dashboard`
// backend announces HERMES_DASHBOARD_READY. Accept either so the desktop spawn
// works against both the headless backend and old/dashboard runtimes.
const _READY_RE = /^HERMES_(?:BACKEND|DASHBOARD)_READY port=(\d+)/m

// The announcement clock starts the instant the backend process is spawned —
// before uvicorn binds its socket. On a cold install the child must first
// compile and import the whole `auraforge_cli.main` → `web_server` → FastAPI/
// uvicorn chain, and on Windows real-time AV (Defender) scans every freshly
// written `.pyc`. That pre-bind cost can run 30-60s on a slow disk, so a tight
// 45s deadline kills a *healthy but still-starting* backend and respawns it,
// piling up orphaned processes (issue #50209). A roomier default absorbs the
// cold-start cost; a warm start still announces in well under a second.
const DEFAULT_PORT_ANNOUNCE_TIMEOUT_MS = 90_000
// Never trust a deadline tighter than the warm-start path needs; floor at 45s
// (the historical default) so a malformed override can't reintroduce the loop.
const MIN_PORT_ANNOUNCE_TIMEOUT_MS = 45_000

/**
 * Resolve the port-announcement deadline. Honors the
 * HERMES_DESKTOP_PORT_ANNOUNCE_TIMEOUT_MS env override (for users on slow
 * disks / aggressive AV who need an even longer cold-start window), clamped
 * to a sane floor so a bad value can't make boot flakier than the default.
 */
function resolvePortAnnounceTimeoutMs(env = process.env) {
  const parsed = Number(env.HERMES_DESKTOP_PORT_ANNOUNCE_TIMEOUT_MS)

  if (Number.isFinite(parsed) && parsed > 0) {
    return Math.max(MIN_PORT_ANNOUNCE_TIMEOUT_MS, Math.round(parsed))
  }

  return DEFAULT_PORT_ANNOUNCE_TIMEOUT_MS
}

/**
 * Watch a child process's stdout for the `HERMES_(BACKEND|DASHBOARD)_READY
 * port=<N>` line that web_server.py prints after uvicorn binds its socket.
 *
 * Returns the parsed port. Rejects if:
 *   - the child exits before emitting the line
 *   - the child emits an `error` event
 *   - no line arrives within the timeout
 *
 * The default timeout is cold-start tolerant (see
 * DEFAULT_PORT_ANNOUNCE_TIMEOUT_MS) because the clock starts before the
 * backend has even bound its port. Pass an explicit `timeoutMs` to override.
 *
 * A single `cleanup()` tears down every listener (data/exit/error/timeout)
 * on every terminal path — resolve, reject, or timeout — so repeated
 * backend spawns don't leak listener slots on the child.
 */
function waitForDashboardPort(child, timeoutMs = resolvePortAnnounceTimeoutMs(), describeOutputTail = () => '') {
  return new Promise((resolve, reject) => {
    let buf = ''
    let done = false

    function cleanup() {
      if (done) {
        return
      }

      done = true
      clearTimeout(timer)
      child.stdout.off('data', onData)
      child.off('exit', onExit)
      child.off('error', onError)
    }

    function onData(chunk) {
      buf += chunk.toString()
      let nl

      while ((nl = buf.indexOf('\n')) !== -1) {
        const line = buf.slice(0, nl)
        buf = buf.slice(nl + 1)
        const m = line.match(_READY_RE)

        if (m) {
          cleanup()
          resolve(parseInt(m[1], 10))

          return
        }
      }
    }

    function onExit(code, signal) {
      cleanup()
      reject(new Error(`Aura Forge backend: exited before port announcement (${signal || code})${describeOutputTail()}`))
    }

    function onError(err) {
      cleanup()
      reject(err)
    }

    const timer = setTimeout(() => {
      cleanup()
      reject(new Error(`Timed out waiting for Aura Forge backend port announcement (${timeoutMs}ms)`))
    }, timeoutMs)

    child.stdout.on('data', onData)
    child.on('exit', onExit)
    child.on('error', onError)
  })
}

function readDashboardReadyFile(readyFile: fs.PathOrFileDescriptor) {
  if (!readyFile) {
    return null
  }

  try {
    const parsed = JSON.parse(fs.readFileSync(readyFile, 'utf8'))
    const port = Number(parsed?.port)

    return Number.isInteger(port) && port > 0 ? port : null
  } catch {
    return null
  }
}

function waitForDashboardReadyFile(
  readyFile,
  child,
  timeoutMs = resolvePortAnnounceTimeoutMs(),
  describeOutputTail = () => ''
) {
  return new Promise((resolve, reject) => {
    let done = false
    let interval = null

    function cleanup() {
      if (done) {
        return
      }

      done = true
      clearTimeout(timer)

      if (interval) {
        clearInterval(interval)
      }

      child.off('exit', onExit)
      child.off('error', onError)
    }

    function check() {
      const port = readDashboardReadyFile(readyFile)

      if (port) {
        cleanup()
        resolve(port)
      }
    }

    function onExit(code, signal) {
      cleanup()
      reject(new Error(`Aura Forge backend: exited before port announcement (${signal || code})${describeOutputTail()}`))
    }

    function onError(err) {
      cleanup()
      reject(err)
    }

    const timer = setTimeout(() => {
      cleanup()
      reject(new Error(`Timed out waiting for Aura Forge backend port announcement (${timeoutMs}ms)`))
    }, timeoutMs)

    child.on('exit', onExit)
    child.on('error', onError)
    interval = setInterval(check, 50)

    if (typeof interval.unref === 'function') {
      interval.unref()
    }

    check()
  })
}

function waitForDashboardPortAnnouncement(
  child,
  options: {
    /** Returns a formatted stdout/stderr tail suffix for exit errors (#93608). */
    describeOutputTail?: () => string
    readyFile?: fs.PathOrFileDescriptor | null
    timeoutMs?: number
  } = {}
) {
  const timeoutMs = options.timeoutMs ?? resolvePortAnnounceTimeoutMs()
  const describeOutputTail = options.describeOutputTail ?? (() => '')

  if (options.readyFile) {
    return waitForDashboardReadyFile(options.readyFile, child, timeoutMs, describeOutputTail)
  }

  return waitForDashboardPort(child, timeoutMs, describeOutputTail)
}

// A fresh install's FIRST local boot is the coldest one the machine will ever
// do: the venv was created seconds ago, so every import compiles bytecode for
// the first time while real-time AV inspects the new `.pyc` files. The standard
// 45s readiness ceiling is sized for a warm tree and lands too close to that
// cold spawn — a post-install boot measured ~28s, and any extra stall turned a
// healthy install into "backend did not become ready", killing the child the
// user had just waited minutes for. Same reasoning as the cold-start
// port-announcement budget above (#50209).
const FIRST_LOCAL_BOOT_READY_TIMEOUT_MS = 180_000
// How long after an install completes still counts as "first boot". Retries
// inside this window reuse a tree that is by then warm, so the wider budget is
// harmless there.
const FIRST_BOOT_GRACE_MS = 30 * 60_000

/**
 * Readiness budget for a local backend spawn: extended only while this process
 * is running the boot that immediately followed a first-run install. Absent /
 * stale `bootstrapCompletedAt` (or no install in this process) returns
 * undefined so the caller keeps the standard 45s default — a genuinely stuck
 * backend must still fail fast on every later boot.
 */
function resolveLocalReadyTimeoutMs(
  options: { bootstrapCompletedAt?: null | number; now?: number } = {}
): number | undefined {
  const completedAt = Number(options.bootstrapCompletedAt) || 0

  if (!completedAt) {
    return undefined
  }

  const now = options.now ?? Date.now()

  if (now - completedAt >= FIRST_BOOT_GRACE_MS) {
    return undefined
  }

  return FIRST_LOCAL_BOOT_READY_TIMEOUT_MS
}

export {
  DEFAULT_PORT_ANNOUNCE_TIMEOUT_MS,
  FIRST_BOOT_GRACE_MS,
  FIRST_LOCAL_BOOT_READY_TIMEOUT_MS,
  MIN_PORT_ANNOUNCE_TIMEOUT_MS,
  readDashboardReadyFile,
  resolveLocalReadyTimeoutMs,
  resolvePortAnnounceTimeoutMs,
  waitForDashboardPort,
  waitForDashboardPortAnnouncement,
  waitForDashboardReadyFile
}
