import { atom, computed } from 'nanostores'

const keyFor = (sessionId: string | null | undefined): string => sessionId ?? ''

export const $providerWaitSessions = atom<Record<string, string>>({})

export function sessionProviderWait(sessionId: null | string) {
  return computed($providerWaitSessions, sessions => sessions[keyFor(sessionId)] ?? '')
}

export function setSessionProviderWait(sessionId: string | null | undefined, text: string): void {
  const key = keyFor(sessionId)
  const sessions = $providerWaitSessions.get()
  const nextText = text.trim()

  if (!nextText) {
    if (!(key in sessions)) {
      return
    }

    const next = { ...sessions }
    delete next[key]
    $providerWaitSessions.set(next)

    return
  }

  if (sessions[key] === nextText) {
    return
  }

  $providerWaitSessions.set({ ...sessions, [key]: nextText })
}

export function clearSessionProviderWait(sessionId: string | null | undefined): void {
  setSessionProviderWait(sessionId, '')
}

export function clearAllProviderWaits(): void {
  $providerWaitSessions.set({})
}

/** Only the core's explained wait/reconnect frames belong in Desktop's status
 * row. Generic kawaii spinner rewrites remain presentation noise.
 *
 * `retrying in` is the automatic provider-retry countdown the core publishes
 * before each backoff attempt (and once per second while it sleeps). Showing
 * it here is what makes a retried turn read as progress instead of a hang —
 * the error stays visible with an attempt count while the agent keeps trying,
 * and a successful attempt clears the row.
 *
 * `rate limited` / `provider overloaded` (⏱️) are the older backoff wording,
 * kept so a Desktop build can still surface waits from a runtime that predates
 * the countdown format (Desktop and its backend update on separate clocks). */
export function providerWaitText(text: string): string {
  const value = text.trim()

  return /^(?:⏳|⏱\uFE0F?|⚠\uFE0F?|↻)\s*(?:waiting on|retrying in|no (?:output|response)|model returned|rate limited|provider overloaded)/i.test(
    value
  )
    ? value
    : ''
}
