import pathlib
p = pathlib.Path('apps/desktop/src/app/settings/billing/use-charge-poller.ts')
t = p.read_text()
old = """      return timeoutOutcome(observed.status?.ok ? (observed.status.portal_url ?? opts.portalUrl) : opts.portalUrl)
  }
}"""
new = """      return timeoutOutcome(observed.status?.ok ? (observed.status.portal_url ?? opts.portalUrl) : opts.portalUrl)
    default:
      throw new Error(`Unhandled settlement kind: ${(settlement as any).kind}`)
  }
}"""
assert old in t, 'pattern not found'
p.write_text(t.replace(old, new))
print('patched')