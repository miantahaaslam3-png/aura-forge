import { describe, expect, it } from 'vitest'

import { decodeTextDataUrl, isMissingReadFileTextHandler } from './preview-text-fallback'

describe('isMissingReadFileTextHandler', () => {
  it('recognizes the bare missing-handler message', () => {
    expect(isMissingReadFileTextHandler(new Error("No handler registered for 'auraforge:readFileText'"))).toBe(true)
  })

  it('recognizes the message the way Electron wraps it over IPC', () => {
    expect(
      isMissingReadFileTextHandler(
        new Error(
          "Error invoking remote method 'auraforge:readFileText': Error: No handler registered for 'auraforge:readFileText'"
        )
      )
    ).toBe(true)
  })

  it('recognizes an older preload that never exposed the call', () => {
    expect(isMissingReadFileTextHandler(new TypeError('bridge().readFileText is not a function'))).toBe(true)
  })

  it('leaves real read failures alone so they surface', () => {
    for (const message of [
      'EACCES: permission denied, open \u0027C:\\secret.txt\u0027',
      'ENOENT: no such file or directory, open \u0027C:\\gone.txt\u0027',
      'Error invoking remote method \u0027auraforge:readFileText\u0027: Error: File is too large to preview'
    ]) {
      expect(isMissingReadFileTextHandler(new Error(message))).toBe(false)
    }
  })

  it('treats non-Error throwables as text', () => {
    expect(isMissingReadFileTextHandler("No handler registered for 'auraforge:readFileText'")).toBe(true)
    expect(isMissingReadFileTextHandler(undefined)).toBe(false)
  })
})

describe('decodeTextDataUrl', () => {
  it('decodes a base64 data URL and reports the mime type', () => {
    const { bytes, mimeType } = decodeTextDataUrl(`data:text/plain;base64,${btoa('hello\nworld')}`)

    expect(mimeType).toBe('text/plain')
    expect(new TextDecoder().decode(bytes)).toBe('hello\nworld')
  })

  it('decodes a percent-encoded data URL', () => {
    const { bytes, mimeType } = decodeTextDataUrl('data:text/plain,hello%20world')

    expect(mimeType).toBe('text/plain')
    expect(new TextDecoder().decode(bytes)).toBe('hello world')
  })

  it('rejects a payload that is not a data URL', () => {
    expect(() => decodeTextDataUrl('')).toThrow(/Unreadable file data URL/)
  })
})
