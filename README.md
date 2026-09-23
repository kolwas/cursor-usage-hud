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
| GitHub (Actions/storage billing) | a token you configure — **off by default** | yes — its own `api.github.com` billing endpoints |

GitHub Actions/storage billing is not an AI service and, unlike everything above, has no local
session file to auto-detect — it only appears once you type a token into **Settings → Services**
(or set `GITHUB_TOKEN` yourself). Nothing short of that activates it.

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

**Settings dialog** — the easy path, no file editing: tray icon → right-click → **Settings…**,
or right-click the chip itself → **Settings…**. Two tabs:

- **General** — refresh interval, chip opacity, popup duration, display mode (always-visible
  chip vs. tray-only), and the three alert thresholds.
- **Services** — one box per provider: an enable/disable checkbox, a plain-language
  detected/not-detected line, and (GitHub only) the token/login fields it actually needs.
  Claude/Anthropic deliberately has no credential field here — see
  [Privacy & credentials](#privacy--credentials).

Saving applies immediately (no restart) and writes to `settings.json` in the state dir — never
into the repo, never into `.env`.

Everything below is the same configuration as **environment variables** instead — useful for a
fixed/scripted install, or to check into your own dotfiles. Loaded from a `.env` file next to
the source (copy `.env.example` → `.env`) or the real environment. An explicit environment
variable always wins over whatever the Settings dialog last saved. All are optional; sane
defaults ship with the tool.

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

- **Settings → Services** (or the tray's **Providers** submenu — same checkboxes, same file) —
  persisted to `providers.json` in the state dir; takes effect on the next refresh without a
  restart.
- **`USAGE_HUD_DISABLE`** — comma-separated provider IDs, e.g.
  `USAGE_HUD_DISABLE=openai,anthropic,opencode-go`. IDs: `cursor`, `copilot`, `opencode-go`,
  `openai`, `anthropic`, `github`, `cloud`.

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
| `GITHUB_TOKEN` / `GITHUB_LOGIN` | — | Activates the GitHub Actions/storage billing row (off unless set — see [What it tracks](#what-it-tracks)); same fields as Settings → Services → GitHub |

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
- The small bar next to the percent is exactly that percent, filled that far, colored by
  severity — nothing else to decode. A richer burn-timeline chart (cycle progress plus a flag
  for the projected exhaustion date) exists too, but only in the expanded/flyout view next to
  the words that explain it — cramming two encodings into one 38x10px chip icon never read
  clearly no matter how it was drawn.
- The `+16d`/`-24d` badge is the burn-rate prediction itself (days before/after renewal at the
  current pace); a row that's genuinely on track to run out (or whose pace just spiked) gets
  its whole line tinted, not just that one badge.
- Click chip → details (flees on hover unless Alt+drag pinned)
- **Tray icon click** → **pinned details** (does not flee; click chip to collapse)
- **Right-click chip → Details / Hide / Settings…**
- Tray right-click → subscription breakdown, **Providers** on/off, Hide chip, **Settings…**
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
