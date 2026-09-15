# Aura Forge CLI Reference

Live sources when anything looks stale: `auraforge --help`, `auraforge <command> --help`,
https://auraforge-agent.nousresearch.com/docs/reference/cli-commands

### Global Flags

```
auraforge [flags] [command]        (no subcommand = interactive chat)

  --version, -V             Show version
  -z, --oneshot PROMPT      One-shot: print ONLY the final response (for scripts/pipes)
  -m MODEL  --provider P    Model/provider override for this invocation
  -t, --toolsets LIST       Comma-separated toolsets for this invocation
  --resume, -r SESSION      Resume session by ID or title
  --continue, -c [NAME]     Resume by name, or most recent session
  --worktree, -w            Isolated git worktree mode (parallel agents)
  --skills, -s SKILL        Preload skills (comma-separate or repeat)
  --profile, -p NAME        Use a named profile
  --yolo                    Skip dangerous command approval
  --tui / --cli             Force the Ink TUI / classic REPL
  --ignore-rules            Skip AGENTS.md/SOUL.md/memory/skill injection
  --safe-mode               Disable ALL customizations (troubleshooting)
  --pass-session-id         Include session ID in system prompt
```

### Chat

```
auraforge chat [flags]
  -q, --query TEXT          Single query, non-interactive
  --image PATH              Attach a local image to a single query
  -Q, --quiet               Suppress banner, spinner, tool previews
  --checkpoints             Enable filesystem checkpoints (/rollback)
  --max-turns N             Cap tool-calling iterations
  --source TAG              Session source tag (default: cli)
```
(plus the global flags above)

### Configuration

```
auraforge setup [section]      Wizard (model|tts|terminal|gateway|tools|agent)
auraforge model                Interactive model/provider picker
auraforge fallback [add|remove|list]  Fallback provider chain
auraforge config [show|edit|get|set|unset|path|env-path|check|migrate]
auraforge login / logout       OAuth sign-in / clear stored auth
auraforge doctor [--fix]       Check dependencies and config
auraforge status [--all]       Component status
```

### Tools & Skills

```
auraforge tools [list|enable NAME|disable NAME]   Per-platform toolsets (curses UI with no args)

auraforge skills list|browse|search QUERY|inspect ID
auraforge skills install ID    Hub identifier OR a direct https://…/SKILL.md URL
auraforge skills config        Enable/disable skills per platform
auraforge skills check|update|uninstall|publish PATH
auraforge skills tap add REPO  Add a GitHub repo as a skill source
auraforge bundles              Skill bundles (one /<name> alias loads several skills)
```

### MCP Servers

```
auraforge mcp add NAME (--url or --command) | remove | list | test NAME
auraforge mcp catalog | install NAME     Curated catalog install
auraforge mcp configure NAME             Toggle tool selection
auraforge mcp serve                      Run Aura Forge as an MCP server
```
Details (transport, tool discovery, catalog): `references/native-mcp.md`.

### Gateway (Messaging Platforms)

```
auraforge gateway run|install|start|stop|restart|status|setup
```

20+ platforms: Telegram, Discord, Slack, WhatsApp (Baileys + Business Cloud API), iMessage (Photon — `auraforge photon setup`), Signal, Email, SMS, Matrix, Mattermost, Teams, LINE, SimpleX, ntfy, Google Chat, Home Assistant, DingTalk, Feishu, WeCom, Weixin, API Server, Webhooks. Open WebUI connects via the API Server adapter. Most adapters ship under `plugins/platforms/`.
Docs: https://auraforge-agent.nousresearch.com/docs/user-guide/messaging/

### Sessions

```
auraforge sessions list|browse|rename ID TITLE|delete ID|export OUT|prune|stats
```

### Cron / Webhooks

```
auraforge cron list|create SCHED|edit ID|pause|resume|run ID|remove|status
    Schedules: '30m', 'every 2h', '0 9 * * *', ISO timestamp
auraforge webhook subscribe NAME|list|remove NAME|test NAME
```
Webhook payloads/routes: `references/webhooks.md`.

### Profiles

```
auraforge profile list|create NAME (--clone|--clone-all|--clone-from)|use|show|delete
auraforge profile rename A B | alias NAME | export NAME | import FILE
```

### Credentials & Pools

```
auraforge auth                 Interactive credential manager
auraforge auth add [PROVIDER]  Add OAuth or API-key credential (nous, openai-codex, qwen-oauth, …)
auraforge auth list|remove P IDX|reset PROVIDER|status
```
Multiple credentials per provider form a pool that rotates automatically and skips exhausted keys.

### Other

```
auraforge desktop / gui        Native desktop app
auraforge dashboard            Web admin panel + embedded chat (--stop / --status)
auraforge proxy                OpenAI-compatible local proxy backed by an OAuth provider
auraforge portal               Quick setup / sign in via Nous Portal
auraforge kanban <verb>        Multi-agent work-queue board
auraforge project              Named multi-folder workspaces
auraforge skin list|use|set    Switch/tweak skins (see references/themes.md)
auraforge pets <verb>          Pet mascots (see references/petdex.md)
auraforge memory setup|status|off|reset   Memory provider
auraforge secrets bitwarden|onepassword   External secret stores
auraforge moa                  Mixture-of-Agents slots
auraforge hooks / security / backup / import / checkpoints / console
auraforge logs [-f] [errors]   View agent/error logs
auraforge send                 One-off message through a gateway platform
auraforge pairing / plugins / insights / journey / computer-use
auraforge acp                  ACP server (IDE integration)
auraforge completion bash|zsh|fish
auraforge update / uninstall / claw migrate
```

Plugin- and provider-supplied subcommands (e.g. `auraforge photon setup`) only appear once their plugin is installed/active.

### Where to Find Things

| Looking for... | Location |
|---|---|
| Config options | `auraforge config edit` · [Configuration docs](https://auraforge-agent.nousresearch.com/docs/user-guide/configuration) |
| Tools / toolsets | `auraforge tools list` · [Tools reference](https://auraforge-agent.nousresearch.com/docs/reference/tools-reference) |
| Skills catalog | `auraforge skills browse` · [Skills catalog](https://auraforge-agent.nousresearch.com/docs/reference/skills-catalog) |
| Provider setup | `auraforge model` · [Providers guide](https://auraforge-agent.nousresearch.com/docs/integrations/providers) |
| Env variables | `auraforge config env-path` · [Env vars reference](https://auraforge-agent.nousresearch.com/docs/reference/environment-variables) |
| Gateway logs | `~/.auraforge/logs/gateway.log` (or `auraforge logs`) |
| Sessions | `auraforge sessions browse` (reads state.db) |
