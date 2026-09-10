"""Local snapshot history for burn-rate projections."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from usage_hud.models import BurnProjection, ProviderSnapshot


class HistoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.is_file():
            self._write({"samples": []})

    def _read(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"samples": []}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def record(self, snapshots: list[ProviderSnapshot]) -> None:
        data = self._read()
        samples: list[dict[str, Any]] = data.setdefault("samples", [])
        for snap in snapshots:
            if not snap.ok:
                continue
            entry = {
                "ts": snap.fetched_at.astimezone(timezone.utc).isoformat(),
                "provider_id": snap.provider_id,
                "cycle_end": snap.cycle_end.isoformat() if snap.cycle_end else None,
                "metrics": [
                    {
                        "key": m.key,
                        "used": m.used,
                        "limit": m.limit,
                        "percent_used": m.resolved_percent(),
                        "unit": m.unit,
                    }
                    for m in snap.metrics
                ],
            }
            samples.append(entry)
        # Keep ~14 days at 2-min cadence ≈ 10k; trim to last 4000 samples.
        if len(samples) > 4000:
            data["samples"] = samples[-4000:]
        self._write(data)

    def projections(
        self,
        snapshots: list[ProviderSnapshot],
        burn_multiplier: float,
    ) -> list[BurnProjection]:
        data = self._read()
        samples = data.get("samples") or []
        out: list[BurnProjection] = []
        now = datetime.now(timezone.utc)

        for snap in snapshots:
            if not snap.ok or not snap.metrics:
                continue
            for metric in snap.metrics:
                if metric.limit is None:
                    continue
                series = [
                    s
                    for s in samples
                    if s.get("provider_id") == snap.provider_id
                    and any(m.get("key") == metric.key for m in s.get("metrics") or [])
                ]
                if len(series) < 2:
                    out.append(
                        BurnProjection(
                            provider_id=snap.provider_id,
                            metric_key=metric.key,
                            used_today=0.0,
                            avg_daily=0.0,
                            projected_cycle_end=None,
                            days_left=None,
                            will_exhaust=False,
                            note="collecting history…",
                        )
                    )
                    continue

                def used_at(sample: dict[str, Any]) -> float:
                    for m in sample.get("metrics") or []:
                        if m.get("key") == metric.key:
                            return float(m.get("used") or 0)
                    return 0.0

                def ts(sample: dict[str, Any]) -> datetime:
                    return datetime.fromisoformat(sample["ts"])

                first = series[0]
                last = series[-1]
                t0, t1 = ts(first), ts(last)
                elapsed_days = max((t1 - t0).total_seconds() / 86400.0, 1e-6)
                delta = max(0.0, used_at(last) - used_at(first))
                avg_daily = delta / elapsed_days

                # Today: from midnight UTC or first sample today.
                day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                today_samples = [s for s in series if ts(s) >= day_start]
                if today_samples:
                    used_today = max(0.0, used_at(today_samples[-1]) - used_at(today_samples[0]))
                else:
                    used_today = 0.0

                days_left = None
                projected = None
                will_exhaust = False
                if snap.cycle_end:
                    days_left = max(
                        0.0,
                        (snap.cycle_end.astimezone(timezone.utc) - now).total_seconds()
                        / 86400.0,
                    )
                    projected = metric.used + avg_daily * days_left
                    if metric.limit is not None and projected >= metric.limit:
                        will_exhaust = True

                hot = avg_daily > 0 and used_today >= burn_multiplier * max(avg_daily, 1e-9)

                note = ""
                if hot:
                    note = "today burning hot"
                elif will_exhaust:
                    note = "on track to exhaust before reset"
                elif avg_daily > 0:
                    note = f"~{avg_daily:.1f}/day"

                out.append(
                    BurnProjection(
                        provider_id=snap.provider_id,
                        metric_key=metric.key,
                        used_today=used_today,
                        avg_daily=avg_daily,
                        projected_cycle_end=projected,
                        days_left=days_left,
                        will_exhaust=will_exhaust,
                        note=note,
                    )
                )
        return out
