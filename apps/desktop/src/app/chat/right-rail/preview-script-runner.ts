/**
 * PREVIEW SCRIPT RUNNER REGISTRY — the one way anything in the app reaches into
 * the preview pane's guest page, the script analog of preview-nav's handle
 * registry.
 *
 * A live browser pane registers its webview's `executeJavaScript` here, keyed
 * by tab id; `activePreviewScriptRunner` resolves the ACTIVE tab from the
 * store. Both guest-page features ride it — the tour tool (preview-tour.ts)
 * and the interaction tool (preview-act.ts) — so their heavy payloads stay out
 * of the pane component's static import graph and only load when used.
 */

import { $rightRailActiveTabId } from '@/store/layout'
import { $previewTabs, type PreviewTab } from '@/store/preview'

/** Runs JS source in the pane's guest page, resolving its completion value. */
export type PreviewScriptRunner = (code: string) => Promise<unknown>

const runners = new Map<string, PreviewScriptRunner>()

/** How long an action waits for a just-opened tab's pane to register.
 *  `desktop_preview` returns as soon as the TAB exists; the pane mounts and
 *  registers its runner a beat later. An agent that opens a page and drives it
 *  immediately is the normal case, not a race to blame on the model — but the
 *  wait is bounded, because a tab that will never have a page must fail. */
const RUNNER_WAIT_MS = 2_000
const RUNNER_POLL_MS = 50

/** Register a live preview's script runner; returns an idempotent unregister. */
export function registerPreviewScriptRunner(tabId: string, runner: PreviewScriptRunner): () => void {
  runners.set(tabId, runner)

  return () => {
    if (runners.get(tabId) === runner) {
      runners.delete(tabId)
    }
  }
}

/** The tab every preview-surface lookup resolves to: the active one, else the
 *  first — a lone freshly-opened tab is the intent even before selection lands. */
export function activePreviewTab(): null | PreviewTab {
  const tabs = $previewTabs.get()

  return tabs.find(t => t.id === $rightRailActiveTabId.get()) ?? tabs[0] ?? null
}

/** The ACTIVE preview tab's script runner. Null = no live page behind it. */
export function activePreviewScriptRunner(): PreviewScriptRunner | null {
  const tab = activePreviewTab()

  return (tab && runners.get(tab.id)) || null
}

/** The active tab's runner, waiting briefly for a newly-opened pane to register.
 *
 *  With no tab at all there is nothing mounting, so this answers immediately
 *  instead of idling — the common "the agent never opened anything" case stays
 *  fast. */
export async function waitForActivePreviewScriptRunner(
  timeoutMs = RUNNER_WAIT_MS
): Promise<PreviewScriptRunner | null> {
  const immediate = activePreviewScriptRunner()

  if (immediate) {
    return immediate
  }

  // Nothing is mounting: no tab at all, or a file preview that never hosts a
  // page. Both must fail now rather than idle for the whole wait.
  const tab = activePreviewTab()

  if (!tab || tab.target.kind === 'file') {
    return null
  }

  const deadline = Date.now() + timeoutMs

  while (Date.now() < deadline) {
    await new Promise(resolve => setTimeout(resolve, RUNNER_POLL_MS))

    const runner = activePreviewScriptRunner()

    if (runner) {
      return runner
    }
  }

  return null
}

/** Why a drive call found no page, phrased for what the tab actually holds.
 *
 *  A FILE preview is the standing false alarm: it has no guest document, so
 *  "no live page" reads as "browser automation is broken" when the right move
 *  is to read the file. Say which one it is. */
export function missingPreviewPageReason(): string {
  const tab = activePreviewTab()

  if (!tab) {
    return 'No live page is open in the in-app browser — open one with desktop_preview first.'
  }

  if (tab.target.kind === 'file') {
    return (
      `The active tab is a file preview (${tab.target.label}), which has no page to drive — ` +
      'read it with read_file. desktop_preview + drive_preview only drive web pages.'
    )
  }

  return `The "${tab.target.label}" tab has no live page behind it — open a URL with desktop_preview, then retry.`
}
