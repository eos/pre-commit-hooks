from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

Notation = Literal['fixed', 'scientific']


@dataclass
class FieldSpec:
    """One constraint-entry key's already-rendered cell content.

    `cells`/`rows` hold final display strings (e.g. "+1.234e-05", "'B->Dlnu::BR'",
    "{ l: e, q: d }") produced by floats.py/strings.py — this module and everything
    downstream of it never sees a raw float or a ruamel node.
    """
    key: str
    kind: Literal['vector', 'matrix']
    cells: list[str] = field(default_factory=list)        # vector: N cells
    rows: list[list[str]] = field(default_factory=list)   # matrix: N rows of N cells


@dataclass
class AlignmentPlan:
    """Output of alignment.plan_alignment(); input to render.render_group()."""
    value_column: int
    key_pad: dict[str, int]
    column_widths: list[int]
    wrap_w: Optional[int]
    included: list[str]
    excluded: list[str]
    column_gap: int = 1        # the gap `value_column` was computed with; render.py reuses it
