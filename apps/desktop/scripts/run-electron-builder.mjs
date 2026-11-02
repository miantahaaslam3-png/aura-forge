// Resolve electronDist at runtime (#38673, #47917): electron-builder 26.8.x can
// re-unpack a broken Electron.app; reusing the installed dist dodges that.
// npm workspace hoisting is non-deterministic — require.resolve finds electron
// wherever it landed. Dist present → -c.electronDist=<abs>/dist; absent → let
// electron-builder fetch via @electron/get (electronVersion + ELECTRON_MIRROR).

import fs from "node:fs"
import path from "node:path"
import { spawnSync } from "node:child_process"
import { createRequire } from "node:module"
import { fileURLToPath } from "node:url"

const require = createRequire(import.meta.url)

const here = path.dirname(fileURLToPath(import.meta.url))
const desktopRoot = path.resolve(here, "..")
const repoRoot = path.resolve(desktopRoot, "..", "..")

// ---------------------------------------------------------------------------
// Repo source archive (Windows only)
// ---------------------------------------------------------------------------
// First launch installs the Python agent from a git checkout. On a network that
// throttles github.com to a few KB/s and resets the connection, that clone can
// never finish (real report: repository stage failed after 10 minutes with
// "Failed to download repository"), so the Windows installer carries the tree
// itself and install.ps1 -SourceArchive extracts it instead.
//
// Regenerated only when HEAD moves; `git archive HEAD` means the archive always
// matches the commit stamped into install-stamp.json.
function ensureAgentSourceArchive() {
  const zipPath = path.join(desktopRoot, "build", "agent-source.zip")
  const sidecarPath = `${zipPath}.commit`

  if (!fs.existsSync(path.join(repoRoot, ".git"))) {
    console.warn("[agent-source] no git checkout; skipping bundled source archive")

    return
  }

  const head = spawnSync("git", ["rev-parse", "HEAD"], { cwd: repoRoot, encoding: "utf8" })

  if (head.status !== 0) {
    console.warn("[agent-source] could not resolve HEAD; skipping bundled source archive")

    return
  }

  const commit = head.stdout.trim()

  if (
    fs.existsSync(zipPath) &&
    fs.existsSync(sidecarPath) &&
    fs.readFileSync(sidecarPath, "utf8").trim() === commit
  ) {
    console.log(`[agent-source] reusing ${path.basename(zipPath)} for ${commit.slice(0, 12)}`)

    return
  }

  console.log(`[agent-source] archiving ${commit.slice(0, 12)} -> ${zipPath}`)
  fs.mkdirSync(path.dirname(zipPath), { recursive: true })

  const archive = spawnSync("git", ["archive", "--format=zip", "-o", zipPath, "HEAD"], {
    cwd: repoRoot,
    stdio: "inherit",
  })

  if (archive.status !== 0) {
    console.warn("[agent-source] git archive failed; installer will fall back to cloning")

    return
  }

  fs.writeFileSync(sidecarPath, commit)
}

function electronDistDir() {
  try {
    return path.join(path.dirname(require.resolve("electron/package.json")), "dist")
  } catch {
    return null
  }
}

function distBinary(dist) {
  if (process.platform === "darwin") {
    return path.join(dist, "Electron.app", "Contents", "MacOS", "Electron")
  }
  if (process.platform === "win32") {
    return path.join(dist, "electron.exe")
  }
  return path.join(dist, "electron")
}

function electronBuilderCli() {
  const pkgJson = require.resolve("electron-builder/package.json")
  const bin = require(pkgJson).bin
  const rel = typeof bin === "string" ? bin : bin["electron-builder"]
  return path.join(path.dirname(pkgJson), rel)
}

const dist = electronDistDir()
const args = []
if (dist && fs.existsSync(distBinary(dist))) {
  args.push(`-c.electronDist=${dist}`)
} else {
  console.warn(
    "[run-electron-builder] no local electron dist; electron-builder will fetch " +
      "via @electron/get (electronVersion + ELECTRON_MIRROR)."
  )
}
args.push(...process.argv.slice(2))

if (process.platform === "win32") {
  ensureAgentSourceArchive()
}

const result = spawnSync(process.execPath, [electronBuilderCli(), ...args], {
  stdio: "inherit",
})
if (result.error) {
  console.error(`[run-electron-builder] spawn failed: ${result.error.message}`)
  process.exit(1)
}
process.exit(result.status == null ? 1 : result.status)
