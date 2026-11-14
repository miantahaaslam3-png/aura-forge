import { beforeEach, describe, expect, it, vi } from 'vitest'

import { $rightRailActiveTabId } from '@/store/layout'
import { closeRightRail, openPreview, type PreviewTarget } from '@/store/preview'

import { registerPreviewScriptRunner } from './preview-script-runner'
import { runPreviewTour } from './preview-tour'

function urlTarget(url: string): PreviewTarget {
  return { kind: 'url', label: 'Browser', source: url, url }
}

describe('runPreviewTour (tour_tool)', () => {
  // URL targets share the singleton Browser tab id, so anything a test
  // registers would answer the next one.
  let cleanups: Array<() => void> = []

  const openBrowserTab = () => {
    openPreview(urlTarget('https://example.com'), 'tool-result')

    return $rightRailActiveTabId.get()!
  }

  beforeEach(() => {
    vi.useRealTimers()

    for (const cleanup of cleanups) {
      cleanup()
    }

    cleanups = []
    closeRightRail()
    window.localStorage.clear()
  })

  it('names a file preview as a file instead of calling the page missing', async () => {
    openPreview(
      {
        kind: 'file',
        label: 'notes.txt',
        path: '/Users/dev/notes.txt',
        previewKind: 'text',
        source: 'file:///Users/dev/notes.txt',
        url: 'file:///Users/dev/notes.txt'
      },
      'file-browser'
    )

    const result = await runPreviewTour({ kind: 'targets' })

    expect(result.success).toBe(false)
    expect(result.error).toContain('file preview')
    expect(result.error).toContain('read_file')
  })

  it('waits for a just-opened pane to register instead of reporting it absent', async () => {
    const tabId = openBrowserTab()

    setTimeout(() => {
      cleanups.push(registerPreviewScriptRunner(tabId, async () => JSON.stringify({ success: true, targets: [] })))
    }, 120)

    expect(await runPreviewTour({ kind: 'targets' })).toMatchObject({ success: true })
  })
})
