// Offline Python dependency wheelhouse (Windows packaging only)
// ---------------------------------------------------------------------------
// First launch installs the Python agent from a git checkout, then runs
// `uv sync --locked`, which pulls ~180 wheels from pypi.org. On a network that
// throttles Fastly/PyPI to ~10 KB/s that stage runs for hours (measured on a
// real machine: `openai` 1.1 MB took 9 minutes, `pywin32` 9.1 MB never landed),
// so the Windows installers carry the wheels themselves and install.ps1
// resolves entirely from local files via `-Wheelhouse`.
//
// The wheelhouse is derived from uv.lock, so it is cached on the lockfile's
// hash rather than the commit: ordinary rebuilds (same lock) reuse the zip, and
// a dependency bump regenerates it. Generating it needs PyPI, so it is a
// packaging-time cost, never a user-facing one.
//
// Build inputs are CPython 3.11 / win_amd64 only. That is exactly what the
// Windows installer's `uv` provisions (Install-Venv pins UV_PYTHON to 3.11),
// and it keeps the payload to the single ABI the install can use.

import crypto from "node:crypto"
import fs from "node:fs"
import os from "node:os"
import path from "node:path"
import { spawnSync } from "node:child_process"

const WINDOWS_PYTHON = "3.11"

// Every wheel `uv sync --extra all --locked` installs on win_amd64/cp311, plus
// the build backend, which uv resolves separately in build isolation and would
// otherwise reach for the network mid-install.
function requirementsFor(repoRoot, logger) {
  const outPath = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "af-wh-req-")), "requirements.txt")

  const exportResult = spawnSync(
    "uv",
    ["export", "--frozen", "--no-hashes", "--no-emit-project", "--extra", "all", "-o", outPath],
    { cwd: repoRoot, encoding: "utf8", shell: true },
  )

  if (exportResult.status !== 0) {
    throw new Error(
      `uv export failed: ${(exportResult.stderr || exportResult.stdout || "").trim() || exportResult.status}`,
    )
  }

  let body = fs.readFileSync(outPath, "utf8")

  // Build backend from [build-system].requires -- `uv sync` builds the project
  // in isolation, and with --no-index that resolution has to come from here too.
  const pyproject = fs.readFileSync(path.join(repoRoot, "pyproject.toml"), "utf8")
  const buildRequires = /\[build-system\][\s\S]*?requires\s*=\s*\[([^\]]*)\]/.exec(pyproject)
  if (buildRequires) {
    for (const entry of buildRequires[1].matchAll(/"([^"]+)"/g)) {
      body += `${entry[1]}\n`
    }
  }

  fs.writeFileSync(outPath, body)
  logger(`[agent-wheels] requirements: ${body.split("\n").filter(l => l && !l.startsWith("#")).length} entries`)

  return outPath
}

function downloadWheels(requirementsPath, destDir, logger) {
  fs.rmSync(destDir, { recursive: true, force: true })
  fs.mkdirSync(destDir, { recursive: true })

  // `python` here is the packaging machine's interpreter. It only drives pip's
  // resolver/downloader; --platform/--python-version/--abi pin the wheels it
  // fetches to the target ABI regardless of the interpreter doing the fetching.
  const result = spawnSync(
    "python",
    [
      "-m",
      "pip",
      "download",
      "-r",
      requirementsPath,
      "-d",
      destDir,
      "--only-binary=:all:",
      "--platform",
      "win_amd64",
      "--python-version",
      WINDOWS_PYTHON.replace(".", ""),
      "--implementation",
      "cp",
      "--abi",
      `cp${WINDOWS_PYTHON.replace(".", "")}`,
      "--no-deps",
    ],
    { stdio: "inherit", shell: true },
  )

  if (result.status !== 0) {
    throw new Error(`pip download failed (exit ${result.status})`)
  }

  const wheels = fs.readdirSync(destDir).filter(name => name.endsWith(".whl"))
  if (wheels.length === 0) {
    throw new Error("pip download produced no wheels")
  }

  const bytes = wheels.reduce((sum, name) => sum + fs.statSync(path.join(destDir, name)).size, 0)
  logger(`[agent-wheels] downloaded ${wheels.length} wheels (${(bytes / 1024 / 1024).toFixed(0)} MB)`)

  return wheels.length
}

function zipDirectory(sourceDir, zipPath) {
  fs.rmSync(zipPath, { force: true })

  // Compress-Archive is entry-by-entry slow on PowerShell 5.1; the .NET API
  // writes the archive directly. -NoProfile keeps a user profile script from
  // polluting the build log.
  const script = [
    "Add-Type -AssemblyName System.IO.Compression.FileSystem",
    `[System.IO.Compression.ZipFile]::CreateFromDirectory('${sourceDir}', '${zipPath}', [System.IO.Compression.CompressionLevel]::Optimal, $false)`,
  ].join("; ")

  const result = spawnSync("powershell", ["-NoProfile", "-NonInteractive", "-Command", script], {
    stdio: "inherit",
  })

  if (result.status !== 0 || !fs.existsSync(zipPath)) {
    throw new Error(`zip failed (exit ${result.status})`)
  }
}

/**
 * True when `zipPath` exists and its `.key` sidecar matches `key`.
 *
 * Exported so the cache contract (rebuild only when uv.lock changes) can be
 * tested without invoking uv or pip.
 */
export function isWheelhouseFresh({ zipPath, sidecarPath, key }) {
  try {
    return fs.readFileSync(sidecarPath, "utf8").trim() === key && fs.statSync(zipPath).size > 0
  } catch {
    return false
  }
}

/**
 * Ensure `build/agent-wheels.zip` exists and matches the current uv.lock.
 *
 * Returns the zip path, or null when the wheelhouse could not be produced (no
 * uv on PATH, no network at packaging time, ...). A missing wheelhouse is not a
 * packaging failure: install.ps1 falls back to PyPI exactly as before.
 */
export function ensureAgentWheelhouse({ desktopRoot, repoRoot, logger = console.log }) {
  const zipPath = path.join(desktopRoot, "build", "agent-wheels.zip")
  const sidecarPath = `${zipPath}.key`
  const lockPath = path.join(repoRoot, "uv.lock")

  if (!fs.existsSync(lockPath)) {
    logger("[agent-wheels] no uv.lock; skipping bundled wheelhouse")

    return null
  }

  const key = crypto.createHash("sha256").update(fs.readFileSync(lockPath)).digest("hex")

  if (isWheelhouseFresh({ zipPath, sidecarPath, key })) {
    logger(`[agent-wheels] reusing ${path.basename(zipPath)} for uv.lock ${key.slice(0, 12)}`)

    return zipPath
  }

  let stagingDir = null
  try {
    logger("[agent-wheels] building wheelhouse from uv.lock (needs PyPI; cached until the lock changes)")
    stagingDir = fs.mkdtempSync(path.join(os.tmpdir(), "af-wheels-"))

    const requirements = requirementsFor(repoRoot, logger)
    downloadWheels(requirements, path.join(stagingDir, "wheels"), logger)
    fs.mkdirSync(path.dirname(zipPath), { recursive: true })
    zipDirectory(path.join(stagingDir, "wheels"), zipPath)

    const mb = (fs.statSync(zipPath).size / 1024 / 1024).toFixed(0)
    logger(`[agent-wheels] wrote ${zipPath} (${mb} MB)`)
    fs.writeFileSync(sidecarPath, key)

    return zipPath
  } catch (error) {
    logger(`[agent-wheels] could not build the wheelhouse: ${error.message}`)
    logger("[agent-wheels] installer will fall back to PyPI for Python dependencies")
    // electron-builder fails the packaging step when an extraResources source
    // is missing, so leave a valid (wheel-less) archive behind. install.ps1
    // recognises it has no .whl files and falls back to PyPI.
    writePlaceholderZip(zipPath, stagingDir, error.message)
    fs.rmSync(sidecarPath, { force: true })

    return null
  } finally {
    if (stagingDir) {
      fs.rmSync(stagingDir, { recursive: true, force: true })
    }
  }
}

function writePlaceholderZip(zipPath, stagingDir, reason) {
  const dir = path.join(stagingDir || os.tmpdir(), "placeholder")

  try {
    fs.mkdirSync(dir, { recursive: true })
    fs.writeFileSync(path.join(dir, "no-wheels.txt"), `wheelhouse generation failed: ${reason}\n`)
    fs.mkdirSync(path.dirname(zipPath), { recursive: true })
    zipDirectory(dir, zipPath)
  } catch {
    // Nothing further to do -- a missing archive just fails the packaging step
    // with electron-builder's own message.
  }
}
