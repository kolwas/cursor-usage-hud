"""The one small record every scene prop is described with."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Prop:
    """A thing in a raven scene, as plain numbers so a frame is just data.

    ``a`` and ``b`` are the main parameters (for a dropped prop: how far it
    is above its resting place, negative = higher; for a flying thing: its x
    and y); ``extra`` carries the rest. What they mean is defined by the
    painter of that ``kind`` in raven_art.
    """

    kind: str
    a: float = 0.0
    b: float = 0.0
    extra: tuple[float, ...] = ()
