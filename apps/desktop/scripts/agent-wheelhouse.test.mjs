import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { test } from 'vitest'

import { ensureAgentWheelhouse, isWheelhouseFresh } from './agent-wheelhouse.mjs'

function tempRoot() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'af-wheels-test-'))
}

test('isWheelhouseFresh requires a key match and a non-empty archive', () => {
  const root = tempRoot()
  const zipPath = path.join(root, 'agent-wheels.zip')
  const sidecarPath = `${zipPath}.key`

  assert.equal(isWheelhouseFresh({ zipPath, sidecarPath, key: 'k' }), false, 'nothing on disk yet')

  fs.writeFileSync(zipPath, 'PK-not-really')
  assert.equal(isWheelhouseFresh({ zipPath, sidecarPath, key: 'k' }), false, 'no sidecar yet')

  fs.writeFileSync(sidecarPath, 'other')
  assert.equal(isWheelhouseFresh({ zipPath, sidecarPath, key: 'k' }), false, 'stale lock hash')

  fs.writeFileSync(sidecarPath, 'k\n')
  assert.equal(isWheelhouseFresh({ zipPath, sidecarPath, key: 'k' }), true, 'matching key')

  fs.writeFileSync(zipPath, '')
  assert.equal(isWheelhouseFresh({ zipPath, sidecarPath, key: 'k' }), false, 'empty archive is not reusable')
})

test('ensureAgentWheelhouse returns null when the checkout has no uv.lock', () => {
  const root = tempRoot()

  assert.equal(ensureAgentWheelhouse({ desktopRoot: root, repoRoot: root, logger: () => {} }), null)
})

test('ensureAgentWheelhouse reuses a wheelhouse that matches uv.lock', () => {
  const repoRoot = tempRoot()
  const desktopRoot = tempRoot()
  const lock = path.join(repoRoot, 'uv.lock')
  fs.writeFileSync(lock, 'version = 1\n')
  const zipPath = path.join(desktopRoot, 'build', 'agent-wheels.zip')
  fs.mkdirSync(path.dirname(zipPath), { recursive: true })
  fs.writeFileSync(zipPath, 'PK-zip-bytes')

  // Prime the sidecar exactly as a successful build would, then confirm the
  // reuse path returns the archive without invoking uv or pip.
  const { createHash } = require('node:crypto')
  const key = createHash('sha256').update(fs.readFileSync(lock)).digest('hex')
  fs.writeFileSync(`${zipPath}.key`, key)

  assert.equal(ensureAgentWheelhouse({ desktopRoot, repoRoot, logger: () => {} }), zipPath)
})
