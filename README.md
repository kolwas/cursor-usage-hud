# Usage HUD

Always-visible compact usage chip for **every detected AI subscription**. Windows + Linux/KDE.

## What it tracks

Auto-discovers from Cursor session + OpenCode `auth.json`:

| Provider | Source |
|----------|--------|
| Cursor | local editor session |
| GitHub Copilot | OpenCode OAuth |
| OpenCode Go | `opencode-go` / `opencode` API key → `/zen/go/v1/usage` |
| OpenAI / ChatGPT | OpenCode OAuth (when connected) |
| Claude | Claude Desktop log + `~/.claude.json` plan metadata — local files only |

New logins in OpenCode appear on the next refresh. Zen credit balance has no public API yet — Go windows show when the account is entitled.

## Claude: how the limits actually work

A Claude subscription has **no monthly meter and no daily meter** — every limit is a
*rolling window*, and the HUD shows one gauge per window:

| Gauge | Window | Opens | Resets |
|-------|--------|-------|--------|
| `5h` | session, all models | with your first message after the previous window closed | 5 h after it opened |
| `7d` | weekly, all models | at the start of the weekly cycle | rolls once a week |

So "used 40%" on `5h` does not mean 40% of a day — it means 40% of the current
five-hour session window, and the details panel tells you when it refills
(`5h 40% · resets in 2h10m`). Hitting 100% on `5h` pauses you until that reset;
the weekly gauge is the one worth pacing, which is what the `+/−d` badge does.

Max plans also have a separate Opus-only weekly window. It is not in any local
file, so this HUD does not show it — check it in Claude itself.

### Where the numbers come from — local files only

This provider reads **no credentials and makes no network call**. Two files:

1. **`plan-usage-history.json`** (`%APPDATA%\Claude`, `~/.config/Claude`) — the percent
   per window that Claude Desktop logs for itself. It carries no reset timestamps, so
   window ends are *estimated* from the sample series and marked `reset est.`:
   the window start is the last reset visible in the log (a drop in utilization, or the
   last zero before usage appeared). An all-zero series means no window is running, and
   a window that should already have rolled is left unknown rather than guessed forward.
2. **`~/.claude.json` → `oauthAccount`** — account profile, no secrets: e-mail,
   `userRateLimitTier` (shown as `Claude Max 5x`) and `hasExtraUsageEnabled`
   (which tells you whether the weekly cap is a hard stop or bills as extra usage).

The log is only written **while the Claude Desktop app runs**. Anything older than
20 minutes is shown as `stale Nh` with no reset time instead of being passed off as
current, and with no log at all the Claude row states that rather than showing a number.

An account token would give exact reset times from Anthropic's account API. Reading that
token and sending it anywhere is deliberately out of scope here — accuracy is traded for
keeping the HUD entirely local.

Not paying for Claude? Tray → **Providers** → uncheck, or `USAGE_HUD_DISABLE=anthropic`.

## Default UX

A small **chip** stays on an **idle monitor** (not the one under your mouse):

`Cur 12% +18d · Cop 1% +99d+`

- Click chip → details (flees on hover unless Alt+drag pinned)
- **Tray icon click** → **pinned details** (does not flee; click chip to collapse)
- Tray right-click → subscription breakdown, **Providers** on/off, Hide chip
- **Right-click chip → Hide** (60m / 180m / day / forever)
- Alt+drag → pin chip position

### Providers (pay only)

Hide models you do not pay for:

- Tray → **Providers** (checkboxes; saved under state dir `providers.json`)
- Or env: `USAGE_HUD_DISABLE=openai,anthropic,opencode-go`

### KDE / Plasma

1. Panel needs a **System Tray** (Status Notifier) widget — Qt uses SNI; no extra Plasma applet.
2. Same binary: `pip install -e . && usage-hud`
3. Autostart: copy `packaging/usage-hud.desktop` to `~/.config/autostart/` and set `Exec=` to your venv, e.g. `/home/YOU/.../cursor-usage-hud/.venv/bin/usage-hud`
4. Auth: `~/.config/Cursor/.../state.vscdb`, `~/.local/share/opencode/auth.json`
5. State: `~/.local/share/usage-hud/` (`providers.json`, snooze, history)
6. Wayland + X11 OK via Qt; multi-monitor idle chip uses Qt screens API.
7. If the tray icon is missing: right-click panel → Add Widgets → System Tray; ensure Usage HUD is not in the “hidden” entries.

## Setup

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
# Linux:   source .venv/bin/activate
pip install -e .
usage-hud
```

### Auth

- **Cursor** — local `state.vscdb` (Linux: `~/.config/Cursor/...`)
- **Copilot** — OpenCode `~/.local/share/opencode/auth.json`

## CLI

```bash
usage-hud status
usage-hud status --json
```

## Config

See `.env.example`. History:

- Windows: `%APPDATA%\usage-hud\`
- Linux: `~/.local/share/usage-hud/`
