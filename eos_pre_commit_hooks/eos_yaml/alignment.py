from __future__ import annotations

import math

from .model import AlignmentPlan, FieldSpec

def _rows(field: FieldSpec) -> list[list[str]]:
    """The rows of cells a field contributes to the shared grid."""
    return [field.cells] if field.kind == 'vector' else field.rows

def _natural_cell_width(field: FieldSpec) -> int:
    """The field's widest rendered cell, before any column padding."""
    return max((len(cell) for row in _rows(field) for cell in row), default=0)

def _is_ragged(field: FieldSpec, arity: int) -> bool:
    """A matrix field whose rows do not all hold `arity` cells. §6."""
    return field.kind == 'matrix' and any(len(row) != arity for row in field.rows)

def _bracket_prefix_len(field: FieldSpec) -> int:
    """The bracket-work between a field's padding and its first cell: `[ ` or `[ [ `."""
    return 2 if field.kind == 'vector' else 4

def _value_column(field: FieldSpec, label_gap: int) -> int:
    """The absolute column this field alone would put its first cell in."""
    return field.indent + len(field.key + ':') + label_gap + _bracket_prefix_len(field)

def _column_widths(fields: list[FieldSpec], wrap_w: int) -> list[int]:
    """One shared width per wrap column; cells `j`, `j + W`, `j + 2W`, ... share one."""
    widths = [0] * wrap_w

    for field in fields:
        for row in _rows(field):
            for index, cell in enumerate(row):
                position = index % wrap_w
                widths[position] = max(widths[position], len(cell))

    return widths

def _worst_case_width(value_column: int, widths: list[int], column_gap: int) -> int:
    """The longest line the group can emit at this wrap width, plus a safety margin."""
    return value_column + sum(widths) + len(widths) * (1 + column_gap) + 1

def _three_column_width(
        key: str, max_line_width: int, indent: int, label_gap: int, column_gap: int,
) -> int:
    """The widest cell that still leaves room for three columns on one line.

    A reference field wider than this cannot set the grid's columns without
    squeezing the group down to one or two cells per line. §6.
    """
    fixed = (indent + len('[ ') + len(' ]') + len(key) + 1 + label_gap
             + 2 * (1 + column_gap))

    return (max_line_width - fixed) // 3

def _reference_width(
        fields: list[FieldSpec], reference_keys: tuple[str, ...], observable_cells: list[str],
        max_line_width: int, label_gap: int, column_gap: int,
) -> tuple[int, list[int]]:
    """The cell width the cap is measured against, and any reference fields dropped.

    Every field named in `reference_keys` contributes its own width, so the cap is
    wide enough for all of them at once and none can be excluded by it — §6's
    `max(15, obslenmax, meanslenmax)`. A reference too wide to leave three columns per
    line contributes nothing and is dropped from the group instead. With no candidates
    present the width comes from `observable_cells`, preserving the behaviour of a
    caller that names none.
    """
    dropped: list[int] = []
    widths: list[int] = []

    for index, field in enumerate(fields):
        if field.key not in reference_keys:
            continue

        width = _natural_cell_width(field)

        if width > _three_column_width(
                field.key, max_line_width, field.indent, label_gap, column_gap):
            dropped.append(index)
        else:
            widths.append(width)

    if not reference_keys:
        return max(len(cell) for cell in observable_cells), dropped

    return max(widths, default=0), dropped

def plan_alignment(
        fields: list[FieldSpec],
        observable_cells: list[str],
        max_line_width: int = 240,
        label_gap: int = 1,
        column_gap: int = 1,
        cap_slack: int = 2,
        reference_keys: tuple[str, ...] = (),
) -> AlignmentPlan:
    """Group vector/matrix fields, apply the width cap (with `cap_slack`),
    compute column widths and wrap width. CONSTRAINTS-FORMAT.md §2, §6.

    `fields` is one alignment group's fields, in the order they are emitted; the
    caller has already established the shared arity, which is `len(observable_cells)`.
    Each field carries its own indent, so a group may span two indent levels (§6).

    `reference_keys` names the fields that may set the cap (the caller supplies them
    so this module stays free of corpus field names). A reference too wide to leave
    three columns per line is dropped from the group and the next candidate takes over.
    """
    arity = len(observable_cells)
    assert arity > 1 and fields, 'a group needs at least one field and an arity above one'

    reference, dropped = _reference_width(
        fields, reference_keys, observable_cells, max_line_width, label_gap, column_gap,
    )
    cap = max(15, reference)
    threshold = cap + cap_slack
    too_wide = set(dropped)

    keep = [
        index not in too_wide
        and _natural_cell_width(field) <= threshold
        and not _is_ragged(field, arity)
        for index, field in enumerate(fields)
    ]
    included = [index for index, kept in enumerate(keep) if kept]
    excluded = [index for index, kept in enumerate(keep) if not kept]

    if not included:
        return AlignmentPlan(
            value_column=0,
            pad=[0] * len(fields),
            column_widths=[],
            wrap_w=None,
            included=[],
            excluded=excluded,
            column_gap=column_gap,
        )

    members = [fields[index] for index in included]
    value_column = max(_value_column(field, label_gap) for field in members)
    pad = [
        value_column - _value_column(field, 0) if kept else 0
        for field, kept in zip(fields, keep)
    ]

    # The widest wrap that fits the budget, then as few cells per line as that many
    # lines allow — an even split reads better and can only shorten the lines further.
    widest = 1
    for candidate in range(arity, 0, -1):
        widths = _column_widths(members, candidate)
        if _worst_case_width(value_column, widths, column_gap) <= max_line_width:
            widest = candidate
            break

    wrap_w = math.ceil(arity / math.ceil(arity / widest))

    return AlignmentPlan(
        value_column=value_column,
        pad=pad,
        column_widths=_column_widths(members, wrap_w),
        wrap_w=None if wrap_w >= arity else wrap_w,
        included=included,
        excluded=excluded,
        column_gap=column_gap,
    )
