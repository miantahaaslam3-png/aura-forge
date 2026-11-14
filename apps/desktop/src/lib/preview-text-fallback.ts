/**
 * PREVIEW TEXT FALLBACK — reading a text file when the Electron shell under this
 * renderer predates the dedicated `readFileText` IPC.
 *
 * Desktop and its shell normally ship together, but a renderer from a new
 * install can meet a main process from the previous one: the app was still
 * running while the installer replaced the app on disk, or a packaged build's
 * asar was partially swapped. The renderer is the half that knows it is new, so
 * it owns the compatibility rung — on a *missing handler* it re-reads the same
 * bytes through `readFileDataUrl`, which every shell has had for far longer.
 *
 * Any other failure is a real failure (permissions, a deleted file, a binary
 * read) and must surface: a silent empty preview would hide the actual error.
 */

/** True when `error` means "this shell has no readFileText IPC at all". */
export function isMissingReadFileTextHandler(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? '')

  return (
    /No handler registered for ['"]?auraforge:readFileText/i.test(message) ||
    /readFileText (?:is )?not a function/i.test(message)
  )
}

/** Decode a `data:` URL into bytes + mime type (base64 or percent-encoded). */
export function decodeTextDataUrl(dataUrl: string): { bytes: Uint8Array; mimeType?: string } {
  const [, metadata = '', data = ''] = String(dataUrl || '').match(/^data:([^,]*),(.*)$/) || []

  if (!metadata && !data) {
    throw new Error('Unreadable file data URL')
  }

  const base64 = metadata.includes(';base64')
  const mimeType = metadata.replace(/;base64$/, '') || undefined
  const raw = base64 ? atob(data) : decodeURIComponent(data)

  return { bytes: Uint8Array.from(raw, ch => ch.charCodeAt(0)), mimeType }
}
