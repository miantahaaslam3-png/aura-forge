import { describe, expect, it } from 'vitest'

import { BACKEND_BOOT_STALL_BUDGET_MS, shouldKeepWaitingForBackendBoot } from './backend-boot-wait'
import { TimeoutError } from './with-timeout'

const NOW = 1_000_000

const timeout = new TimeoutError('Timed out connecting to Aura Forge backend')

function input(overrides: Partial<Parameters<typeof shouldKeepWaitingForBackendBoot>[0]> = {}) {
  return {
    bootstrapActive: false,
    deadline: NOW + 60_000,
    error: timeout as unknown,
    now: NOW,
    progress: { error: null, phase: 'backend.wait', running: true, timestamp: NOW - 1_000 },
    ...overrides
  }
}

describe('shouldKeepWaitingForBackendBoot', () => {
  it('keeps waiting while the first-launch installer is still running', () => {
    expect(
      shouldKeepWaitingForBackendBoot(
        input({
          bootstrapActive: true,
          progress: { error: null, phase: 'bootstrap.install', running: true, timestamp: NOW - 1_000 }
        })
      )
    ).toBe(true)
  })

  it('keeps waiting through the backend spawn that follows the installer', () => {
    // The reported first-launch race: the installer is done, the fresh backend
    // is still starting, and the renderer budget expires in that window.
    expect(
      shouldKeepWaitingForBackendBoot(
        input({ progress: { error: null, phase: 'backend.wait', running: true, timestamp: NOW - 1_000 } })
      )
    ).toBe(true)
    expect(
      shouldKeepWaitingForBackendBoot(
        input({ progress: { error: null, phase: 'backend.spawn', running: true, timestamp: NOW } })
      )
    ).toBe(true)
  })

  it('surfaces a real rejection from main instead of retrying it', () => {
    expect(
      shouldKeepWaitingForBackendBoot(input({ error: new Error('Aura Forge backend did not become ready: timeout') }))
    ).toBe(false)
  })

  it('stops once main reports a boot failure', () => {
    expect(
      shouldKeepWaitingForBackendBoot(
        input({
          progress: { error: 'backend exited before ready', phase: 'backend.error', running: false, timestamp: NOW }
        })
      )
    ).toBe(false)
  })

  it('stops when nothing is booting (idle / init phase)', () => {
    expect(
      shouldKeepWaitingForBackendBoot(
        input({ progress: { error: null, phase: 'idle', running: false, timestamp: NOW } })
      )
    ).toBe(false)
    expect(
      shouldKeepWaitingForBackendBoot(
        input({ progress: { error: null, phase: 'init', running: true, timestamp: NOW } })
      )
    ).toBe(false)
    expect(shouldKeepWaitingForBackendBoot(input({ progress: null }))).toBe(false)
  })

  it('stops when the boot stopped reporting progress for the stall budget', () => {
    expect(
      shouldKeepWaitingForBackendBoot(
        input({
          progress: {
            error: null,
            phase: 'backend.wait',
            running: true,
            timestamp: NOW - BACKEND_BOOT_STALL_BUDGET_MS - 1
          }
        })
      )
    ).toBe(false)
  })

  it('stops at the overall deadline even while an install is running', () => {
    expect(shouldKeepWaitingForBackendBoot(input({ bootstrapActive: true, deadline: NOW }))).toBe(false)
  })
})
