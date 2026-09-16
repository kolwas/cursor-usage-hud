# Przepiórka (Usage HUD)

Always-visible desktop chip for every AI coding subscription you pay for — Cursor, GitHub
Copilot, Claude, OpenAI/ChatGPT, OpenCode Go. Windows + Linux/KDE. One line per gauge, a
pie-clock for time-to-reset, a tiny timeline for "will I run out before it renews".

## What it tracks

Auto-discovers from the Cursor editor session and OpenCode's `auth.json` — nothing to
configure to get started, only to hide what you don't use (see [Providers](#providers--turn-things-off)).

| Provider | Source | Reaches the network? |
|----------|--------|-----------------------|
| Cursor | local editor session (`state.vscdb`) | yes — its own `cursor.com/api/usage-summary` |
| GitHub Copilot | OpenCode OAuth (`auth.json`) | yes — its own `api.github.com/copilot_internal/user` |
| OpenCode Go | `opencode-go` / `opencode` API key | yes — its own `/zen/go/v1/usage` |
| OpenAI / ChatGPT | OpenCode OAuth (when connected) | yes — its own account-usage endpoint |
| Claude | Claude Desktop log + `~/.claude.json` plan metadata | **no** — see below |

Each provider only ever talks to *that vendor's own* API, using a token the corresponding app
(Cursor, OpenCode) already stored on this machine — usage-hud does not introduce a new place
where a credential is typed in, and never sends any token to a third party. New logins in
OpenCode appear on the next refresh. Zen credit balance has no public API yet — Go windows
show once the account is entitled.

## Privacy & credentials

**Claude is the one provider that reads no token and makes no network call at all.** It is
built from two local files only:

1. `plan-usage-history.json` — the percent-per-window log Claude Desktop writes for itself.
2. `~/.claude.json` → `oauthAccount` — account profile fields (e-mail, plan tier, an
   extra-usage flag). No token lives in that block; only account metadata does.

Deliberately: Anthropic's account API would give exact reset times, but that needs the OAuth
token Claude Code stores locally, and reading that token and sending it anywhere was ruled
out for this tool — accuracy is traded for staying entirely local. See
[Claude: how the limits actually work](#claude-how-the-limits-actually-work) for the detail.

For the other providers, the credential model is: usage-hud reads the token *that app already
wrote to disk* (Cursor's session in `state.vscdb`, OpenCode's in `auth.json`) and sends it
only to that same vendor's own usage endpoint — the same round trip the vendor's own app
already makes. No token is logged, written to `usage-hud`'s own state files, or sent anywhere
other than the vendor it came from. `git log` and the working tree carry **no credentials,
account values, or personal identifiers** — verified before every publish.

## Configuration

Everything is an environment variable, loaded from a `.env` file next to the source (copy
`.env.example` → `.env`) or from the real environment. All are optional; sane defaults ship
with the tool.

### Display

| Variable | Default | Meaning |
|---|---|---|
| `USAGE_HUD_MODE` | `chip` | `chip` = always-visible chip; `quiet` = tray only (icon + tooltip + alerts) |
| `USAGE_HUD_QUIET` | off | Back-compat shorthand for `USAGE_HUD_MODE=quiet` |
| `USAGE_HUD_OPACITY` | `0.94` | Chip window opacity, clamped `0.35`–`1.0` |
| `USAGE_HUD_REFRESH_SECONDS` | `180` | How often every provider is re-fetched (minimum 30) |
| `USAGE_HUD_POPUP_SECONDS` | `12` | How long a tray notification stays up (minimum 4) |
| `USAGE_HUD_PRESENTATION` | off | Force presentation-mode chip hiding (also auto-detected) |

### Alerts

| Variable | Default | Meaning |
|---|---|---|
| `USAGE_HUD_ALERT_INCLUDED_PCT` | `85` | WARN threshold for a plan/included gauge (CRITICAL is fixed at 95%) |
| `USAGE_HUD_ALERT_ONDEMAND_PCT` | `70` | WARN threshold for pay-as-you-go spend gauges |
| `USAGE_HUD_ALERT_BURN_MULTIPLIER` | `2.0` | "Burning hot today" fires when today's usage is this many × the average daily rate |

### Providers — turn things off

Only pay for some of these? Hide the rest — either from the running app or before it ever starts:

- **Tray → Providers** — checkboxes, persisted to `providers.json` in the state dir; takes
  effect on the next refresh without a restart.
- **`USAGE_HUD_DISABLE`** — comma-separated provider IDs, e.g.
  `USAGE_HUD_DISABLE=openai,anthropic,opencode-go`. IDs: `cursor`, `copilot`, `opencode-go`,
  `openai`, `anthropic`, `cloud`.

A disabled provider is never fetched, never shown, and — for Claude specifically — its local
files are simply not read.

### Paths & advanced overrides

| Variable | Default | Meaning |
|---|---|---|
| `USAGE_HUD_STATE_DIR` | `%APPDATA%\usage-hud` / `~/.local/share/usage-hud` | Where history/snooze/provider-prefs are written |
| `CURSOR_STATE_DB` | auto-detected | Path to Cursor's `state.vscdb` |
| `CURSOR_SESSION_TOKEN` | — | Skip the state-DB lookup and supply a session token/JWT directly |
| `OPENCODE_AUTH_JSON` | `~/.local/share/opencode/auth.json` | Path to OpenCode's auth store |
| `OPENCODE_ANTIGRAVITY_JSON` | `~/.config/opencode/antigravity-accounts.json` | Enables the optional cloud-stub gauge when present |
| `GITHUB_COPILOT_TOKEN` | — | Skip the OpenCode auth lookup for Copilot and supply a token directly |
| `CLAUDE_DESKTOP_DIR` | auto-detected | Claude Desktop's user-data folder (holds `plan-usage-history.json`) |
| `CLAUDE_JSON` | `~/.claude.json` | Path to Claude's account-profile file |
| `USAGE_HUD_ENABLE_CLOUD` | off | Show the placeholder cloud-credits gauge |
| `GITHUB_TOKEN` / `GITHUB_LOGIN` | — | Read by a GitHub Actions/storage billing provider that exists in the code but is **not currently wired into auto-discovery** — set only if you re-enable it yourself in `providers/registry.py` |

## Claude: how the limits actually work

A Claude subscription has **no monthly meter and no daily meter** — every limit is a
*rolling window*, and the HUD shows one gauge per window:

| Gauge | Window | Opens | Resets |
|-------|--------|-------|--------|
| `5h` | session, all models | with your first message after the previous window closed | 5 h after it opened |
| `7d` | weekly, all models | at the start of the weekly cycle | rolls once a week |

So "used 40%" on `5h` does not mean 40% of a day — it means 40% of the current five-hour
session window. Hitting 100% on `5h` pauses you until that reset; the weekly gauge is the one
worth pacing, which is what the prediction timeline and `+/−d` badge are for.

Max plans also have a separate Opus-only weekly window. It is not in any local file, so this
HUD does not show it — check it in Claude itself.

### Where the numbers come from — local files only

1. **`plan-usage-history.json`** (`%APPDATA%\Claude`, `~/.config/Claude`) — the percent per
   window that Claude Desktop logs for itself. It carries no reset timestamps, so window ends
   are *estimated* from the sample series and marked `reset est.`: the window start is the
   last reset visible in the log (a drop in utilization, or the last zero before usage
   appeared). An all-zero series means no window is running, and a window that should already
   have rolled is left unknown rather than guessed forward.
2. **`~/.claude.json` → `oauthAccount`** — account profile, no secrets: e-mail,
   `userRateLimitTier` (shown as `Claude Max 5x`) and `hasExtraUsageEnabled` (tells you
   whether the weekly cap is a hard stop or bills as extra usage).

The log is only written **while the Claude Desktop app runs**. Anything older than 20 minutes
is shown as `stale Nh` with no reset time instead of being passed off as current, and with no
log at all the Claude row states that rather than showing a number.

A freshly-reset window is not trusted for a prediction either: the burn-rate projection waits
for roughly 10% of a window's own length to elapse (a floor of one hour) before it will call
an "overrun" — a couple of percent used in the first minutes of a 7-day window would otherwise
extrapolate into an alarming but meaningless "exhausts today".

## Default UX

A small **chip** stays on an **idle monitor** (not the one under your mouse), one line per
gauge:

```
Cur Incl  🥧 25d  11%  +16d
Cur API   🥧 25d  70%  -24d
Cla 5h    🥧 3h14m  9%
Cla 7d    🥧 6d     2%
```

- Pie wedge = time left in that window; its **color follows usage severity**, not time — a
  clock winding down on a near-full gauge reads as alarming even with hours still on the clock.
- The `+16d`/`-24d` badge is a burn-rate prediction (days before/after renewal at the current
  pace) with a tiny timeline underneath it: track = the whole billing cycle, filled = elapsed
  so far, dot = where that pace lands.
- Click chip → details (flees on hover unless Alt+drag pinned)
- **Tray icon click** → **pinned details** (does not flee; click chip to collapse)
- Tray right-click → subscription breakdown, **Providers** on/off, Hide chip
- **Right-click chip → Hide** (60m / 180m / day / forever)
- Alt+drag → pin chip position

### KDE / Plasma

1. Panel needs a **System Tray** (Status Notifier) widget — Qt uses SNI; no extra Plasma applet.
2. Same binary: `pip install -e . && usage-hud`
3. Icon (once, so `Icon=przepiorka` in the .desktop file resolves):
   `mkdir -p ~/.local/share/icons/hicolor/256x256/apps && cp src/usage_hud/assets/przepiorka.png ~/.local/share/icons/hicolor/256x256/apps/przepiorka.png && gtk-update-icon-cache ~/.local/share/icons/hicolor 2>/dev/null`
4. Autostart: copy `packaging/przepiorka.desktop` to `~/.config/autostart/` and set `Exec=` to
   your venv, e.g. `/home/YOU/.../cursor-usage-hud/.venv/bin/usage-hud`
5. Auth: `~/.config/Cursor/.../state.vscdb`, `~/.local/share/opencode/auth.json`
6. State: `~/.local/share/usage-hud/` (`providers.json`, snooze, history)
7. Wayland + X11 OK via Qt; multi-monitor idle chip uses Qt's screens API.
8. If the tray icon is missing: right-click panel → Add Widgets → System Tray; make sure
   Przepiórka isn't in the "hidden" entries.

## Setup

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
# Linux:   source .venv/bin/activate
pip install -e .
usage-hud
```

## CLI

```bash
usage-hud status
usage-hud status --json
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

No network access or local credentials are needed to run the test suite — everything is
exercised against synthetic `ProviderSnapshot`/`Metric` fixtures.

## License

MIT — see `LICENSE`.
