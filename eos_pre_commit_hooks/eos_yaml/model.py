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

    `indent` is the absolute column the field's own key starts at, so one group can
    span two indent levels (CONSTRAINTS-FORMAT.md §7).
    """
    key: str
    kind: Literal['vector', 'matrix']
    cells: list[str] = field(default_factory=list)        # vector: N cells
    rows: list[list[str]] = field(default_factory=list)   # matrix: N rows of N cells
    indent: int = 2


@dataclass
class AlignmentPlan:
    """Output of alignment.plan_alignment(); input to render.render_group().

    `pad`, `included` and `excluded` are indexed by position in the `fields` list
    the plan was made from: a Mixture group holds one `means` per component, so a
    key name cannot address a single field.
    """
    value_column: int          # absolute, every field's own indent included
    pad: list[int]             # parallel to `fields`; 0 where a field is excluded
    column_widths: list[int]
    wrap_w: Optional[int]
    included: list[int]
    excluded: list[int]
    column_gap: int = 1        # the gap `value_column` was computed with; render.py reuses it
