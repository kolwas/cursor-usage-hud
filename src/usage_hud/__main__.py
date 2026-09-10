"""CLI entrypoints."""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="usage-hud", description="Desktop usage HUD")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("gui", help="Launch HUD + tray (default)")
    p_status = sub.add_parser("status", help="Print one-shot usage to stdout")
    p_status.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    cmd = args.cmd or "gui"

    if cmd == "status":
        from usage_hud.config import Settings
        from usage_hud.providers.cloud import CloudStubProvider
        from usage_hud.providers.cursor import CursorProvider
        from usage_hud.providers.github import GitHubProvider

        settings = Settings.load()
        providers = [CursorProvider(), GitHubProvider(settings)]
        if settings.enable_cloud_stub:
            providers.append(CloudStubProvider())
        snaps = [p.fetch() for p in providers]
        if args.json:
            payload = []
            for s in snaps:
                payload.append(
                    {
                        "provider": s.provider_id,
                        "title": s.title,
                        "ok": s.ok,
                        "error": s.error,
                        "message": s.message,
                        "cycle_end": s.cycle_end.isoformat() if s.cycle_end else None,
                        "metrics": [
                            {
                                "key": m.key,
                                "label": m.label,
                                "used": m.used,
                                "limit": m.limit,
                                "remaining": m.resolved_remaining(),
                                "percent": m.resolved_percent(),
                                "unit": m.unit,
                                "detail": m.detail,
                            }
                            for m in s.metrics
                        ],
                    }
                )
            print(json.dumps(payload, indent=2))
            return

        for s in snaps:
            print(f"== {s.title} ==")
            if not s.ok:
                print(f"  ERROR: {s.error}")
                continue
            for m in s.metrics:
                pct = m.resolved_percent()
                pct_txt = f"{pct:.1f}%" if pct is not None else "n/a"
                rem = m.resolved_remaining()
                rem_txt = f" left={rem:g}{m.unit}" if rem is not None else ""
                print(f"  {m.label}: {m.used:g}{m.unit}/{m.limit}{m.unit if m.limit is not None else ''} ({pct_txt}){rem_txt}")
                if m.detail:
                    print(f"    {m.detail}")
            if s.message:
                print(f"  {s.message}")
            if s.cycle_end:
                print(f"  cycle ends {s.cycle_end.isoformat()}")
            print()
        return

    from usage_hud.app import run

    raise SystemExit(run())


if __name__ == "__main__":
    main()
