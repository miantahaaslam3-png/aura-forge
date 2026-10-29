import { contextBridge, ipcRenderer, webFrame, webUtils } from 'electron'

// Which translucency the OS can back. Asked synchronously because the renderer
// needs it before its first paint, and answered by main because deciding it
// needs `os.release()` — a sandboxed preload may only require electron, events,
// timers and url, so importing node:os here throws before contextBridge runs
// and takes the ENTIRE bridge down with it (window.auraForgeDesktop undefined =>
// "Desktop IPC bridge is unavailable"). No reply means no glass, which degrades
// to an ordinary opaque window rather than a page thinned over nothing.
const translucencySupport = ipcRenderer.sendSync('auraforge:translucency:support')
const hudWindowing = ipcRenderer.sendSync('auraforge:hud:windowing')
const hudNativeDrag = hudWindowing?.nativeDrag === true

contextBridge.exposeInMainWorld('auraForgeDesktop', {
  glassSupported: translucencySupport?.glass === true,
  translucencySupported: translucencySupport?.translucency === true,
  getConnection: profile => ipcRenderer.invoke('auraforge:connection', profile),
  // Registry-scoped backend resolution: { connectionId, profile } → descriptor.
  getConnectionFor: payload => ipcRenderer.invoke('auraforge:connection:for', payload),
  getProfileRoutes: profiles => ipcRenderer.invoke('auraforge:plugin-profile-routes', profiles),
  revalidateConnection: () => ipcRenderer.invoke('auraforge:connection:revalidate'),
  touchBackend: profile => ipcRenderer.invoke('auraforge:backend:touch', profile),
  getGatewayWsUrl: profile => ipcRenderer.invoke('auraforge:gateway:ws-url', profile),
  // Registry-scoped fresh WS URL: { connectionId, profile } → result shape of
  // getGatewayWsUrl, minted against that connection's backend.
  getGatewayWsUrlFor: payload => ipcRenderer.invoke('auraforge:gateway:ws-url-for', payload),
  // Union agent roster across every registered connection.
  getAgentRoster: () => ipcRenderer.invoke('auraforge:agents:roster'),
  openSessionWindow: (sessionId, opts) => ipcRenderer.invoke('auraforge:window:openSession', sessionId, opts),
  openSessionInTerminal: (sessionId, opts) => ipcRenderer.invoke('auraforge:window:openInTerminal', sessionId, opts),
  openWindow: () => ipcRenderer.invoke('auraforge:window:openInstance'),
  openBrowserWindow: tabId => ipcRenderer.invoke('auraforge:window:openBrowser', tabId),
  onBrowserPopoutClosed: callback => {
    const listener = (_event, tabId) => callback(tabId)
    ipcRenderer.on('auraforge:browser-popout:closed', listener)

    return () => ipcRenderer.removeListener('auraforge:browser-popout:closed', listener)
  },
  claimAmbientCue: key => ipcRenderer.invoke('auraforge:ambient:claim', key),
  wakeIndicator: {
    getState: () => ipcRenderer.invoke('auraforge:wake-indicator:get'),
    setState: state => ipcRenderer.send('auraforge:wake-indicator:set', state),
    onState: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('auraforge:wake-indicator:state', listener)

      return () => ipcRenderer.removeListener('auraforge:wake-indicator:state', listener)
    }
  },
  petOverlay: {
    // Main renderer → main process: window lifecycle + drag. `request` is
    // `{ bounds, screen }`; resolves with the screen bounds it actually used.
    open: request => ipcRenderer.invoke('auraforge:pet-overlay:open', request),
    close: () => ipcRenderer.invoke('auraforge:pet-overlay:close'),
    setBounds: bounds => ipcRenderer.send('auraforge:pet-overlay:set-bounds', bounds),
    setIgnoreMouse: ignore => ipcRenderer.send('auraforge:pet-overlay:ignore-mouse', ignore),
    // Flip the overlay focusable (and focus it) while the composer needs keys.
    setFocusable: focusable => ipcRenderer.send('auraforge:pet-overlay:set-focusable', focusable),
    // Main renderer → overlay (forwarded by main): push the latest pet state.
    pushState: payload => ipcRenderer.send('auraforge:pet-overlay:state', payload),
    // Overlay → main renderer (forwarded by main): pop back in / composer submit.
    control: payload => ipcRenderer.send('auraforge:pet-overlay:control', payload),
    // Overlay subscribes to state pushes.
    onState: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('auraforge:pet-overlay:state', listener)

      return () => ipcRenderer.removeListener('auraforge:pet-overlay:state', listener)
    },
    // Main renderer subscribes to overlay control messages.
    onControl: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('auraforge:pet-overlay:control', listener)

      return () => ipcRenderer.removeListener('auraforge:pet-overlay:control', listener)
    }
  },
  // HUD mode: the chrome-free floating chat. A full app renderer (own gateway)
  // sized as a floating bar, so it mounts the real composer. Main owns the
  // window; `onChanged` keeps every window's toggle truthful.
  hud: {
    nativeDrag: hudNativeDrag,
    windowing: {
      clientPlacement: hudWindowing?.clientPlacement !== false,
      controlDrag: hudWindowing?.controlDrag === true,
      nativeDrag: hudNativeDrag,
      solid: hudWindowing?.solid === true,
      workspaceTransfer: hudWindowing?.workspaceTransfer === true
    },
    open: request => ipcRenderer.invoke('auraforge:hud:open', request),
    close: () => ipcRenderer.invoke('auraforge:hud:close'),
    setIgnoreMouse: ignore => ipcRenderer.send('auraforge:hud:ignore-mouse', ignore),
    beginMove: () => ipcRenderer.send('auraforge:hud:begin-move'),
    endMove: () => ipcRenderer.send('auraforge:hud:end-move'),
    moveBy: delta => ipcRenderer.send('auraforge:hud:move-by', delta),
    setWorkspaceTransfer: transferring => ipcRenderer.send('auraforge:hud:workspace-transfer', transferring),
    setBounds: bounds => ipcRenderer.send('auraforge:hud:set-bounds', bounds),
    resetLayout: () => ipcRenderer.invoke('auraforge:hud:reset-layout'),
    // Whether the band covers the window below the bar. Main pairs it with the
    // user's translucency setting to decide the native frost (macOS vibrancy /
    // Windows 11 DWM backdrop) — see hudFrostFor.
    setFrost: showing => ipcRenderer.invoke('auraforge:hud:frost', showing),
    // The HUD tells main which session it is on; main hands that back to the
    // app window when the HUD closes, so the app can re-home onto it.
    setSession: sessionId => ipcRenderer.send('auraforge:hud:session', sessionId),
    onGoto: callback => {
      const listener = (_event, sessionId) => callback(sessionId)
      ipcRenderer.on('auraforge:hud:goto', listener)

      return () => ipcRenderer.removeListener('auraforge:hud:goto', listener)
    },
    onChanged: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('auraforge:hud:changed', listener)

      return () => ipcRenderer.removeListener('auraforge:hud:changed', listener)
    },
    // Linux only, and silent elsewhere: where the cursor is, in page
    // coordinates, or null when it has left the window. Stands in for the
    // mousemove that `setIgnoreMouseEvents(true, { forward: true })` delivers on
    // macOS and Windows but not here.
    onCursor: callback => {
      const listener = (_event, point) => callback(point)
      ipcRenderer.on('auraforge:hud:cursor', listener)

      return () => ipcRenderer.removeListener('auraforge:hud:cursor', listener)
    },
    // Main's game-overlay watch: whether a fullscreen app (a game) is under
    // the HUD, so the renderer can step back to the low-opacity overlay
    // treatment while one owns the screen.
    onGameOverlay: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('auraforge:hud:game-overlay', listener)

      return () => ipcRenderer.removeListener('auraforge:hud:game-overlay', listener)
    }
  },
  // Quick Entry: the global-hotkey mini composer window. Main owns the OS
  // shortcut + the persisted preference; the quick window only captures text
  // and hands it back, and the primary renderer submits it through the normal
  // prompt path.
  quickEntry: {
    getSettings: () => ipcRenderer.invoke('auraforge:quick-entry:settings:get'),
    setSettings: patch => ipcRenderer.invoke('auraforge:quick-entry:settings:set', patch),
    submit: payload => ipcRenderer.send('auraforge:quick-entry:submit', payload),
    dismiss: () => ipcRenderer.send('auraforge:quick-entry:dismiss'),
    // Primary renderer → main → quick window: gateway connection state + the
    // recent-session options the target picker offers. Main caches the latest
    // payload so a freshly spawned quick window starts from truth.
    pushState: payload => ipcRenderer.send('auraforge:quick-entry:state', payload),
    // Quick window subscribes to those pushes.
    onState: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('auraforge:quick-entry:state', listener)

      return () => ipcRenderer.removeListener('auraforge:quick-entry:state', listener)
    },
    // Main → primary renderer: a submit captured by the quick window.
    onSubmit: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('auraforge:quick-entry:submit', listener)

      return () => ipcRenderer.removeListener('auraforge:quick-entry:submit', listener)
    },
    // Main → quick window: you were just summoned (reset draft + refocus).
    onShown: callback => {
      const listener = () => callback()
      ipcRenderer.on('auraforge:quick-entry:shown', listener)

      return () => ipcRenderer.removeListener('auraforge:quick-entry:shown', listener)
    }
  },
  getBootProgress: () => ipcRenderer.invoke('auraforge:boot-progress:get'),
  getConnectionConfig: profile => ipcRenderer.invoke('auraforge:connection-config:get', profile),
  saveConnectionConfig: payload => ipcRenderer.invoke('auraforge:connection-config:save', payload),
  applyConnectionConfig: payload => ipcRenderer.invoke('auraforge:connection-config:apply', payload),
  testConnectionConfig: payload => ipcRenderer.invoke('auraforge:connection-config:test', payload),
  // Opt-in OS-keychain encryption for stored gateway secrets (default off —
  // see secret-storage-policy.ts). get never touches the OS keychain.
  getSecretStorageEncryption: () => ipcRenderer.invoke('auraforge:secret-storage:get'),
  setSecretStorageEncryption: (on: boolean) => ipcRenderer.invoke('auraforge:secret-storage:set', on),
  // v2 multi-connection registry: named agent sources (local / remote / cloud / ssh).
  connections: {
    list: () => ipcRenderer.invoke('auraforge:connections:list'),
    save: payload => ipcRenderer.invoke('auraforge:connections:save', payload),
    remove: id => ipcRenderer.invoke('auraforge:connections:remove', id),
    setPrimary: id => ipcRenderer.invoke('auraforge:connections:set-primary', id),
    setLaunchMode: mode => ipcRenderer.invoke('auraforge:connections:set-launch-mode', mode),
    setLastUsed: id => ipcRenderer.invoke('auraforge:connections:set-last-used', id),
    test: id => ipcRenderer.invoke('auraforge:connections:test', id),
    updateManaged: id => ipcRenderer.invoke('auraforge:connections:update-managed', id),
    // Fan out `hermes update` to every eligible registered connection.
    // Optional excludeIds skips rows the caller updates through another path.
    updateAll: options => ipcRenderer.invoke('auraforge:connections:update-all', options),
    // Registry lifecycle push (main → renderer): a connection was removed or
    // materially edited, so secondaries scoped to it must be disposed (and,
    // for edits, re-dialed at the new target).
    onChanged: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('auraforge:connections:changed', listener)

      return () => ipcRenderer.removeListener('auraforge:connections:changed', listener)
    }
  },
  sshConfigHosts: () => ipcRenderer.invoke('auraforge:ssh-config:hosts'),
  sshResolveHost: host => ipcRenderer.invoke('auraforge:ssh-config:resolve', host),
  probeConnectionConfig: remoteUrl => ipcRenderer.invoke('auraforge:connection-config:probe', remoteUrl),
  oauthLoginConnectionConfig: remoteUrl => ipcRenderer.invoke('auraforge:connection-config:oauth-login', remoteUrl),
  oauthLogoutConnectionConfig: remoteUrl => ipcRenderer.invoke('auraforge:connection-config:oauth-logout', remoteUrl),
  // Aura Forge Cloud: one portal login powers discovery + silent per-agent sign-in
  // (cloud-auto-discovery Phase 3).
  cloud: {
    status: () => ipcRenderer.invoke('auraforge:cloud:status'),
    login: () => ipcRenderer.invoke('auraforge:cloud:login'),
    logout: () => ipcRenderer.invoke('auraforge:cloud:logout'),
    discover: org => ipcRenderer.invoke('auraforge:cloud:discover', org),
    agentSignIn: dashboardUrl => ipcRenderer.invoke('auraforge:cloud:agent-sign-in', dashboardUrl)
  },
  profile: {
    get: () => ipcRenderer.invoke('auraforge:profile:get'),
    remember: name => ipcRenderer.invoke('auraforge:profile:remember', name),
    set: name => ipcRenderer.invoke('auraforge:profile:set', name)
  },
  api: request => ipcRenderer.invoke('auraforge:api', request),
  notify: payload => ipcRenderer.invoke('auraforge:notify', payload),
  requestMicrophoneAccess: () => ipcRenderer.invoke('auraforge:requestMicrophoneAccess'),
  readWindowBelow: () => ipcRenderer.invoke('auraforge:window:readBelow'),
  readFileDataUrl: filePath => ipcRenderer.invoke('auraforge:readFileDataUrl', filePath),
  readFileDataUrlForAttach: filePath => ipcRenderer.invoke('auraforge:readFileDataUrlForAttach', filePath),
  dataUrlReadMax: {
    get: () => ipcRenderer.invoke('auraforge:data-url-read-max:get'),
    set: maxMb => ipcRenderer.invoke('auraforge:data-url-read-max:set', maxMb)
  },
  readFileText: filePath => ipcRenderer.invoke('auraforge:readFileText', filePath),
  readPluginSource: (filePath: string) => ipcRenderer.invoke('auraforge:readPluginSource', filePath),
  selectPaths: options => ipcRenderer.invoke('auraforge:selectPaths', options),
  selectSavePath: options => ipcRenderer.invoke('auraforge:selectSavePath', options),
  writeClipboard: text => ipcRenderer.invoke('auraforge:writeClipboard', text),
  readClipboard: () => ipcRenderer.invoke('auraforge:readClipboard'),
  saveGatewayFile: payload => ipcRenderer.invoke('auraforge:saveGatewayFile', payload),
  saveImageFromUrl: url => ipcRenderer.invoke('auraforge:saveImageFromUrl', url),
  contextMenuEdit: command => ipcRenderer.invoke('auraforge:context-menu:edit', command),
  contextMenuCopyImage: () => ipcRenderer.invoke('auraforge:context-menu:copy-image'),
  contextMenuSpellcheck: action => ipcRenderer.invoke('auraforge:context-menu:spellcheck', action),
  contextMenuGuestAddWord: payload => ipcRenderer.invoke('auraforge:context-menu:guest-add-word', payload),
  onContextMenuSpellcheck: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('auraforge:context-menu-spellcheck', listener)

    return () => ipcRenderer.removeListener('auraforge:context-menu-spellcheck', listener)
  },
  saveImageBuffer: (data, ext) => ipcRenderer.invoke('auraforge:saveImageBuffer', { data, ext }),
  saveClipboardImage: () => ipcRenderer.invoke('auraforge:saveClipboardImage'),
  getPathForFile: file => {
    try {
      return webUtils.getPathForFile(file) || ''
    } catch {
      return ''
    }
  },
  normalizePreviewTarget: (target, baseDir) => ipcRenderer.invoke('auraforge:normalizePreviewTarget', target, baseDir),
  watchPreviewFile: url => ipcRenderer.invoke('auraforge:watchPreviewFile', url),
  watchDirectory: dir => ipcRenderer.invoke('auraforge:watchDirectory', dir),
  stopPreviewFileWatch: id => ipcRenderer.invoke('auraforge:stopPreviewFileWatch', id),
  setActiveWork: payload => ipcRenderer.send('auraforge:active-work', payload),
  setTitleBarTheme: payload => ipcRenderer.send('auraforge:titlebar-theme', payload),
  setNativeTheme: mode => ipcRenderer.send('auraforge:native-theme', mode),
  setTranslucency: payload => ipcRenderer.send('auraforge:translucency', payload),
  setKeepAwake: on => ipcRenderer.send('auraforge:keep-awake', on),
  setDisableF12: blocked => ipcRenderer.send('auraforge:devtools:disable-f12', blocked),
  setPreviewShortcutActive: active => ipcRenderer.send('auraforge:previewShortcutActive', Boolean(active)),
  openExternal: url => ipcRenderer.invoke('auraforge:openExternal', url),
  openPreviewInBrowser: url => ipcRenderer.invoke('auraforge:openPreviewInBrowser', url),
  reachPreviewUrl: url => ipcRenderer.invoke('auraforge:preview:reach', url),
  setActiveConnectionRoute: route => ipcRenderer.send('auraforge:connection:active-route', route),
  fetchLinkTitle: url => ipcRenderer.invoke('auraforge:fetchLinkTitle', url),
  resolveFavicon: url => ipcRenderer.invoke('auraforge:resolveFavicon', url),
  sanitizeWorkspaceCwd: cwd => ipcRenderer.invoke('auraforge:workspace:sanitize', cwd),
  settings: {
    getDefaultProjectDir: () => ipcRenderer.invoke('auraforge:setting:defaultProjectDir:get'),
    setDefaultProjectDir: dir => ipcRenderer.invoke('auraforge:setting:defaultProjectDir:set', dir),
    pickDefaultProjectDir: () => ipcRenderer.invoke('auraforge:setting:defaultProjectDir:pick')
  },
  zoom: {
    // Current zoom of this window, as { level, percent }.
    get: () => ipcRenderer.invoke('auraforge:zoom:get'),
    // Synchronous zoom factor (1 = 100%). Coordinate math needs it in the
    // same tick as the event it converts, so no IPC round-trip here.
    factor: () => webFrame.getZoomFactor(),
    setPercent: percent => ipcRenderer.send('auraforge:zoom:set-percent', percent),
    // Fires on every zoom change, including the Ctrl/Cmd +/-/0 shortcuts,
    // so the settings UI can stay in sync with the keyboard.
    onChanged: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('auraforge:zoom:changed', listener)

      return () => ipcRenderer.removeListener('auraforge:zoom:changed', listener)
    }
  },
  revealLogs: () => ipcRenderer.invoke('auraforge:logs:reveal'),
  getRecentLogs: () => ipcRenderer.invoke('auraforge:logs:recent'),
  // Fire-and-forget: persists a renderer error-boundary catch (with component
  // stack) to desktop.log so crashes survive the window (#79428).
  reportRendererError: report => ipcRenderer.send('auraforge:logs:renderer-error', report),
  readDir: dirPath => ipcRenderer.invoke('auraforge:fs:readDir', dirPath),
  gitRoot: startPath => ipcRenderer.invoke('auraforge:fs:gitRoot', startPath),
  revealPath: targetPath => ipcRenderer.invoke('auraforge:fs:reveal', targetPath),
  openDir: dirPath => ipcRenderer.invoke('auraforge:fs:openDir', dirPath),
  desktopPluginsRoot: () => ipcRenderer.invoke('auraforge:fs:desktopPluginsRoot'),
  logsRoot: () => ipcRenderer.invoke('auraforge:fs:logsRoot'),
  agentPluginsRoot: () => ipcRenderer.invoke('auraforge:fs:agentPluginsRoot'),
  renamePath: (targetPath, newName) => ipcRenderer.invoke('auraforge:fs:rename', targetPath, newName),
  writeTextFile: (filePath, content) => ipcRenderer.invoke('auraforge:fs:writeText', filePath, content),
  trashPath: targetPath => ipcRenderer.invoke('auraforge:fs:trash', targetPath),
  git: {
    worktreeList: repoPath => ipcRenderer.invoke('auraforge:git:worktreeList', repoPath),
    worktreeAdd: (repoPath, options) => ipcRenderer.invoke('auraforge:git:worktreeAdd', repoPath, options),
    worktreeRemove: (repoPath, worktreePath, options) =>
      ipcRenderer.invoke('auraforge:git:worktreeRemove', repoPath, worktreePath, options),
    branchSwitch: (repoPath, branch) => ipcRenderer.invoke('auraforge:git:branchSwitch', repoPath, branch),
    branchList: repoPath => ipcRenderer.invoke('auraforge:git:branchList', repoPath),
    baseBranchList: repoPath => ipcRenderer.invoke('auraforge:git:baseBranchList', repoPath),
    repoStatus: repoPath => ipcRenderer.invoke('auraforge:git:repoStatus', repoPath),
    fileDiff: (repoPath, filePath) => ipcRenderer.invoke('auraforge:git:fileDiff', repoPath, filePath),
    scanRepos: (roots, options) => ipcRenderer.invoke('auraforge:git:scanRepos', roots, options),
    review: {
      list: (repoPath, scope, baseRef) => ipcRenderer.invoke('auraforge:git:review:list', repoPath, scope, baseRef),
      diff: (repoPath, filePath, scope, baseRef, staged) =>
        ipcRenderer.invoke('auraforge:git:review:diff', repoPath, filePath, scope, baseRef, staged),
      stage: (repoPath, filePath) => ipcRenderer.invoke('auraforge:git:review:stage', repoPath, filePath),
      unstage: (repoPath, filePath) => ipcRenderer.invoke('auraforge:git:review:unstage', repoPath, filePath),
      revert: (repoPath, filePath) => ipcRenderer.invoke('auraforge:git:review:revert', repoPath, filePath),
      revParse: (repoPath, ref) => ipcRenderer.invoke('auraforge:git:review:revParse', repoPath, ref),
      commit: (repoPath, message, push) => ipcRenderer.invoke('auraforge:git:review:commit', repoPath, message, push),
      commitContext: repoPath => ipcRenderer.invoke('auraforge:git:review:commitContext', repoPath),
      push: repoPath => ipcRenderer.invoke('auraforge:git:review:push', repoPath),
      shipInfo: repoPath => ipcRenderer.invoke('auraforge:git:review:shipInfo', repoPath),
      prList: (repoPath, branches, numbers) =>
        ipcRenderer.invoke('auraforge:git:review:prList', repoPath, branches, numbers),
      fetchPrComment: (repoPath, url) => ipcRenderer.invoke('auraforge:git:review:fetchPrComment', repoPath, url),
      createPr: repoPath => ipcRenderer.invoke('auraforge:git:review:createPr', repoPath)
    }
  },
  terminal: {
    cwd: id => ipcRenderer.invoke('auraforge:terminal:cwd', id),
    dispose: id => ipcRenderer.invoke('auraforge:terminal:dispose', id),
    resize: (id, size) => ipcRenderer.invoke('auraforge:terminal:resize', id, size),
    start: options => ipcRenderer.invoke('auraforge:terminal:start', options),
    write: (id, data) => ipcRenderer.invoke('auraforge:terminal:write', id, data),
    onData: (id, callback) => {
      const channel = `auraforge:terminal:${id}:data`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    },
    onExit: (id, callback) => {
      const channel = `auraforge:terminal:${id}:exit`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    }
  },
  onClosePreviewRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('auraforge:close-preview-requested', listener)

    return () => ipcRenderer.removeListener('auraforge:close-preview-requested', listener)
  },
  onPreviewNav: callback => {
    const listener = (_event, command) => callback(command)
    ipcRenderer.on('auraforge:preview-nav', listener)

    return () => ipcRenderer.removeListener('auraforge:preview-nav', listener)
  },
  onOpenFolderRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('auraforge:open-folder-requested', listener)

    return () => ipcRenderer.removeListener('auraforge:open-folder-requested', listener)
  },
  onOpenUpdatesRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('auraforge:open-updates', listener)

    return () => ipcRenderer.removeListener('auraforge:open-updates', listener)
  },
  onDeepLink: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('auraforge:deep-link', listener)

    return () => ipcRenderer.removeListener('auraforge:deep-link', listener)
  },
  signalDeepLinkReady: () => ipcRenderer.invoke('auraforge:deep-link-ready'),
  probePluginRepo: payload => ipcRenderer.invoke('auraforge:plugin:probe', payload),
  installDesktopPlugin: payload => ipcRenderer.invoke('auraforge:plugin:installDesktop', payload),
  onWindowStateChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('auraforge:window-state-changed', listener)

    return () => ipcRenderer.removeListener('auraforge:window-state-changed', listener)
  },
  onFocusSession: callback => {
    const listener = (_event, sessionId) => callback(sessionId)
    ipcRenderer.on('auraforge:focus-session', listener)

    return () => ipcRenderer.removeListener('auraforge:focus-session', listener)
  },
  onNotificationAction: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('auraforge:notification-action', listener)

    return () => ipcRenderer.removeListener('auraforge:notification-action', listener)
  },
  onNotificationActivate: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('auraforge:notification-activate', listener)

    return () => ipcRenderer.removeListener('auraforge:notification-activate', listener)
  },
  onPreviewFileChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('auraforge:preview-file-changed', listener)

    return () => ipcRenderer.removeListener('auraforge:preview-file-changed', listener)
  },
  onBackendExit: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('auraforge:backend-exit', listener)

    return () => ipcRenderer.removeListener('auraforge:backend-exit', listener)
  },
  // Soft gateway-mode apply finished tearing down the primary backend. Renderer
  // should wipe session lists + re-dial without a window reload.
  onConnectionApplied: callback => {
    const listener = () => callback()
    ipcRenderer.on('auraforge:connection:applied', listener)

    return () => ipcRenderer.removeListener('auraforge:connection:applied', listener)
  },
  onPowerResume: callback => {
    const listener = () => callback()
    ipcRenderer.on('auraforge:power-resume', listener)

    return () => ipcRenderer.removeListener('auraforge:power-resume', listener)
  },
  // AC ↔ battery transitions; renderers slow their backstop polls on battery.
  getOnBattery: () => ipcRenderer.invoke('auraforge:power-battery:get'),
  onBatteryChanged: callback => {
    const listener = (_event, onBattery) => callback(Boolean(onBattery))
    ipcRenderer.on('auraforge:power-battery', listener)

    return () => ipcRenderer.removeListener('auraforge:power-battery', listener)
  },
  onBootProgress: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('auraforge:boot-progress', listener)

    return () => ipcRenderer.removeListener('auraforge:boot-progress', listener)
  },
  // First-launch bootstrap progress -- emitted by the install.ps1 stage
  // runner in main.ts (apps/desktop/electron/bootstrap-runner.ts).
  // Renderer's install overlay subscribes to live events and queries the
  // current snapshot via getBootstrapState() to recover after a devtools
  // reload mid-bootstrap.
  getBootstrapState: () => ipcRenderer.invoke('auraforge:bootstrap:get'),
  continueBootstrapLocal: () => ipcRenderer.invoke('auraforge:bootstrap:continue-local'),
  resetBootstrap: () => ipcRenderer.invoke('auraforge:bootstrap:reset'),
  repairBootstrap: () => ipcRenderer.invoke('auraforge:bootstrap:repair'),
  cancelBootstrap: () => ipcRenderer.invoke('auraforge:bootstrap:cancel'),
  onBootstrapEvent: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('auraforge:bootstrap:event', listener)

    return () => ipcRenderer.removeListener('auraforge:bootstrap:event', listener)
  },
  getVersion: () => ipcRenderer.invoke('auraforge:version'),
  getRemoteDisplayReason: () => ipcRenderer.invoke('auraforge:get-remote-display-reason'),
  uninstall: {
    summary: () => ipcRenderer.invoke('auraforge:uninstall:summary'),
    run: mode => ipcRenderer.invoke('auraforge:uninstall:run', { mode })
  },
  updates: {
    check: () => ipcRenderer.invoke('auraforge:updates:check'),
    apply: opts => ipcRenderer.invoke('auraforge:updates:apply', opts),
    getBranch: () => ipcRenderer.invoke('auraforge:updates:branch:get'),
    setBranch: name => ipcRenderer.invoke('auraforge:updates:branch:set', name),
    onProgress: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('auraforge:updates:progress', listener)

      return () => ipcRenderer.removeListener('auraforge:updates:progress', listener)
    }
  },
  themes: {
    fetchMarketplace: id => ipcRenderer.invoke('auraforge:vscode-theme:fetch', id),
    searchMarketplace: query => ipcRenderer.invoke('auraforge:vscode-theme:search', query)
  },
  // Find-in-page (Ctrl/Cmd+F): delegates to Electron's
  // webContents.findInPage on the IPC sender's window so a Cmd+F pressed
  // in a secondary session window searches THAT window, not the primary.
  // `onFoundInPage` returns the unsubscribe fn; the renderer wires it via
  // `initFindInPageListener` in store/find-in-page.ts and tears it down
  // when the FindBar unmounts.
  findInPage: (query, options) => ipcRenderer.invoke('auraforge:find-in-page', query, options),
  stopFindInPage: () => ipcRenderer.invoke('auraforge:stop-find-in-page'),
  onFoundInPage: callback => {
    const listener = (_event, result) => callback(result)
    ipcRenderer.on('auraforge:found-in-page', listener)

    return () => ipcRenderer.removeListener('auraforge:found-in-page', listener)
  },
  // Main-process `before-input-event` forwards Ctrl/Cmd+F here so renderer
  // can open the FindBar even when the GTK compositor has already grabbed
  // the chord at the windowing layer (#81727).
  onOpenFindBarRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('auraforge:open-find-bar', listener)

    return () => ipcRenderer.removeListener('auraforge:open-find-bar', listener)
  }
})
