# Usage HUD

Always-visible desktop monitor for **Cursor** subscription usage (included pool + on-demand overage), **GitHub** Actions/billing, with hooks for future **Cloud Agents** and other providers.

## UX choice (why not the taskbar)

Windows taskbar buttons are a poor fit for multi-provider gauges, projections, and alerts — too little space and no rich text. This app uses:

1. **Glass HUD** — small frameless, translucent, always-on-top card (draggable; dodges the mouse).
2. **System tray** — color dot (green / amber / red), tooltip, balloon alerts when thresholds trip.
3. Optional: start with Windows (shortcut / Task Scheduler) so it stays up all day.

## Features

- Remaining included Cursor allowance + **on-demand $** spent / left
- GitHub Actions minutes (+ packages/storage when the API allows)
- Local history → **daily burn**, projected end-of-cycle overrun, “burning hot today” alerts
- Provider plugin shape so Cloud / others can plug in later (`USAGE_HUD_ENABLE_CLOUD=1` shows a stub)

## Setup (Windows)

```powershell
cd $env:USERPROFILE\Documents\cursor-usage-hud
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

Cursor auth is automatic if you are signed into the Cursor editor (reads `%APPDATA%\Cursor\User\globalStorage\state.vscdb`). No API key required for personal usage.

GitHub:

```powershell
# either
gh auth login
# or put a classic/fine-grained token with billing read in .env
copy .env.example .env
```

## Run

```powershell
usage-hud              # HUD + tray
usage-hud status       # one-shot table
usage-hud status --json
```

## Alerts (defaults)

| Rule | Default |
|------|---------|
| Included / primary metric | warn ≥ 85%, critical ≥ 95% |
| On-demand spend | warn ≥ 70%, critical ≥ 95% |
| Hot day | today's delta ≥ 2× rolling avg daily |
| Projection | warn if burn rate hits limit before cycle reset |

Override with env vars in `.env` (see `.env.example`).

## Privacy

- Session JWT never leaves your machine except toward `cursor.com` / `api.github.com` for usage reads.
- History lives in `%APPDATA%\usage-hud\history.json`.
- Keep the git remote **private** — do not commit `.env`.

## Disclaimer

Cursor dashboard endpoints used here are **unofficial** and may change. Numbers on [cursor.com/dashboard/spending](https://cursor.com/dashboard/spending) remain the source of truth.
