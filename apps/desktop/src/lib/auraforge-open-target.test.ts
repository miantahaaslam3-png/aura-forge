import { describe, expect, it } from 'vitest'

import {
  normalizeHermesOpenString,
  pathFromHermesDeepLink,
  pathFromOpenDeepLink,
  resolveAuraForgeOpenPath
} from './auraforge-open-target'

describe('normalizeHermesOpenString', () => {
  it('accepts hash-router paths and strips a leading hash', () => {
    expect(normalizeHermesOpenString('/index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizeHermesOpenString('#/index-network/intent/1')).toBe('/index-network/intent/1')
  })

  it('maps plugin-scoped auraforge:// deep links to the same path', () => {
    expect(normalizeHermesOpenString('auraforge://index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizeHermesOpenString('auraforge://index-network/intent/1?focus=true')).toBe(
      '/index-network/intent/1?focus=true'
    )
  })

  it('maps auraforge://open/… deep links by stripping the open host', () => {
    expect(normalizeHermesOpenString('auraforge://open/index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizeHermesOpenString('auraforge://open/settings/plugins')).toBe('/settings/plugins')
  })

  it('rejects reserved hermes kinds and unsafe paths', () => {
    expect(normalizeHermesOpenString('auraforge://blueprint/morning-brief')).toBeNull()
    expect(normalizeHermesOpenString('auraforge://plugin/install')).toBeNull()
    expect(normalizeHermesOpenString('https://example.com/x')).toBeNull()
    expect(normalizeHermesOpenString('/../etc/passwd')).toBeNull()
    expect(normalizeHermesOpenString('index-network')).toBeNull()
  })
})

describe('resolveAuraForgeOpenPath', () => {
  it('merges structured path + params', () => {
    expect(resolveAuraForgeOpenPath({ path: '/index-network/intent/1', params: { focus: 'true' } })).toBe(
      '/index-network/intent/1?focus=true'
    )
  })

  it('resolves href the same as a bare string', () => {
    expect(resolveAuraForgeOpenPath({ href: 'auraforge://index-network/intent/1' })).toBe('/index-network/intent/1')
  })
})

describe('pathFromHermesDeepLink', () => {
  it('builds the navigate path from a plugin-scoped deep-link payload', () => {
    expect(pathFromHermesDeepLink('index-network', 'intent/1')).toBe('/index-network/intent/1')
  })

  it('builds the navigate path from auraforge://open/… payloads', () => {
    expect(pathFromOpenDeepLink('index-network/intent/1')).toBe('/index-network/intent/1')
    expect(pathFromHermesDeepLink('open', 'agent/42')).toBe('/agent/42')
  })

  it('ignores reserved kinds', () => {
    expect(pathFromHermesDeepLink('blueprint', 'morning-brief')).toBeNull()
    expect(pathFromHermesDeepLink('plugin', 'install')).toBeNull()
  })
})
