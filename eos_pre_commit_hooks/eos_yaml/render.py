from __future__ import annotations

from .model import AlignmentPlan, FieldSpec

def _chunk(cells: list[str], width: int) -> list[list[str]]:
    """The cells of one row, split into the sub-lines the plan's wrap width allows."""
    return [cells[start:start + width] for start in range(0, len(cells), width)] or [cells]

def _cells(
        chunk: list[str], plan: AlignmentPlan, offset: int, tail: bool, closer: str,
) -> str:
    """One sub-line's cells: a comma follows its cell directly, padding follows the comma.

    Keeping the comma against the value it belongs to — rather than out past the
    column padding — is what the spec's §4.1 and §4.2 examples do.
    """
    columns = len(plan.column_widths)
    parts = []

    for index, cell in enumerate(chunk):
        width = plan.column_widths[(offset + index) % columns]

        if index < len(chunk) - 1:
            parts.append(cell + ',' + ' ' * (width - len(cell) + plan.column_gap))
        elif tail:
            parts.append(cell.ljust(width) + ' ' * plan.column_gap + closer)
        else:
            parts.append(cell + ',')

    return ''.join(parts)

def _row(cells: list[str], plan: AlignmentPlan, head: str, closer: str) -> list[str]:
    """One row of cells: `head` opens it, continuation sub-lines carry no bracket."""
    width = plan.wrap_w or len(cells)
    chunks = _chunk(cells, width)
    continuation = ' ' * plan.value_column
    lines = []

    for number, chunk in enumerate(chunks):
        last = number == len(chunks) - 1
        lines.append(
            (head if number == 0 else continuation)
            + _cells(chunk, plan, number * width, last, closer)
        )

    return lines

def _head(field: FieldSpec, pad: int) -> str:
    """The key, its padding, and the bracket-work up to the field's first cell."""
    brackets = '[ ' if field.kind == 'vector' else '[ [ '

    return ' ' * field.indent + field.key + ':' + ' ' * pad + brackets

def _render_field(field: FieldSpec, plan: AlignmentPlan, pad: int) -> list[str]:
    if field.kind == 'vector':
        return _row(field.cells, plan, _head(field, pad), ']')

    # The inner `[` of every row sits at the vector fields' bracket column; the outer
    # `[` two columns to its left, and the lone closing `]` under it.
    inner = ' ' * (plan.value_column - 2) + '[ '
    lines = []

    for number, row in enumerate(field.rows):
        last = number == len(field.rows) - 1
        head = _head(field, pad) if number == 0 else inner
        lines.extend(_row(row, plan, head, ']' if last else '],'))

    lines.append(' ' * (plan.value_column - 4) + ']')

    return lines

def render_group(fields: list[FieldSpec], plan: AlignmentPlan) -> list[str]:
    """Emit the aligned text lines for one alignment group. Spec §4 steps 5-7.
    See STEP-6.md.

    `plan.pad` and `plan.included` are indexed by position in `fields`, so a group
    holding several same-named fields addresses each of them separately (§6)."""
    lines = []

    for index, field in enumerate(fields):
        if index in plan.included:
            lines.extend(_render_field(field, plan, plan.pad[index]))

    return lines

def render_self_aligned(field: FieldSpec) -> list[str]:
    """Emit a cap-excluded field's own lines, self-aligned only against its own
    rows (e.g. `kinematics`). Spec §4.4. See STEP-6.md."""
    lines = [' ' * field.indent + field.key + ':']
    marker = ' ' * (field.indent + 2) + '- '

    if field.kind == 'vector':
        lines.extend(marker + cell for cell in field.cells)
    else:
        lines.extend(marker + '[ ' + ', '.join(row) + ' ]' for row in field.rows)

    return lines
