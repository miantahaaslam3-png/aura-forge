import { isTimeoutError } from './with-timeout'

/**
 * Boot-progress phases in which Electron main is ACTIVELY bringing the local
 * backend up (see `startHermes()` in `electron/main.ts`). While one of these is
 * the latest reported phase, "getConnection() has not answered yet" means
 * "the backend is still starting", not "the backend is gone".
 */
const MID_BOOT_PHASES = new Set([
  'backend.ready',
  'backend.port',
  'backend.resolve',
  'backend.runtime',
  'backend.spawn',
  'backend.wait',
  'runtime.external'
])

/**
 * How long a mid-boot phase may go without a fresh progress update before the
 * renderer stops trusting it. Main refreshes `timestamp` on every phase, so a
 * stale snapshot means the boot stopped reporting — most likely wedged — and
 * the user deserves the recovery overlay rather than an endless spinner.
 */
export const BACKEND_BOOT_STALL_BUDGET_MS = 10 * 60_000

export interface BackendBootSnapshot {
  error?: null | string
  phase?: string
  running?: boolean
  timestamp?: number
}

export interface BackendBootWaitInput {
  /** `getBootstrapState().active` — the first-launch installer is running. */
  bootstrapActive: boolean
  /** Absolute epoch ms after which waiting stops no matter what. */
  deadline: number
  /** The error that ended the last `getConnection()` attempt. */
  error: unknown
  now: number
  /** Latest `getBootProgress()` snapshot, or null when it could not be read. */
  progress: BackendBootSnapshot | null
  stallBudgetMs?: number
}

/**
 * Whether a failed backend-wait attempt should be retried instead of surfaced.
 *
 * Only our OWN budget may expire (`TimeoutError`) — a real rejection from main
 * is main's verdict and must reach the recovery overlay/retry classifier. A
 * timeout is tolerated while a first-launch install is still running (it can be
 * hours long on a slow link) or while main is still mid-boot, which includes
 * the ~30s spawn that follows the installer and used to land right on the
 * renderer's 45s ceiling — the "backend timed out" report from a fresh install
 * that then needed a full app restart.
 */
export function shouldKeepWaitingForBackendBoot(input: BackendBootWaitInput): boolean {
  if (!isTimeoutError(input.error)) {
    return false
  }

  if (input.now >= input.deadline) {
    return false
  }

  if (input.bootstrapActive) {
    return true
  }

  const progress = input.progress

  if (!progress) {
    return false
  }

  // Main stamps every failure with `error` + `running:false`. Never wait out a
  // failure that main has already reported.
  if (progress.error) {
    return false
  }

  if (progress.running === false) {
    return false
  }

  if (!progress.phase || !MID_BOOT_PHASES.has(progress.phase)) {
    return false
  }

  const stallBudgetMs = input.stallBudgetMs ?? BACKEND_BOOT_STALL_BUDGET_MS

  return input.now - (progress.timestamp ?? 0) <= stallBudgetMs
}
