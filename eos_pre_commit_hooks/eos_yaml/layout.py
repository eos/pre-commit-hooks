from __future__ import annotations

FOLD_OPEN = '# {{{'
FOLD_CLOSE = '# }}}'

class FoldMarkerError(Exception):
    """Raised with file/line context when `# {{{`/`# }}}` imbalance is ambiguous."""

def _is_blank(line: str) -> bool:
    return not line.strip()

def _is_comment(line: str) -> bool:
    """A `#`-comment starting in column 0."""
    return line.startswith('#')

def _is_key(line: str) -> bool:
    """A constraint entry's own key: column 0, neither blank nor a comment."""
    return bool(line) and not line[0].isspace() and not _is_comment(line)

def _is_fold_open(line: str) -> bool:
    return line.lstrip().startswith('#') and '{{{' in line

def _is_fold_close(line: str) -> bool:
    return line.lstrip().startswith('#') and '}}}' in line

def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())

def _chunk_starts(lines: list[str]) -> list[int]:
    """Index of the first line of every top-level entry, header comments included.

    An entry's header is the run of column-0 comment lines glued to its key with no
    blank line in between; a `# }}}` closes the fold above it and so is never part
    of one.
    """
    starts = []

    for index, line in enumerate(lines):
        if not _is_key(line):
            continue

        start = index
        while start > 0 and _is_comment(lines[start - 1]) and not _is_fold_close(lines[start - 1]):
            start -= 1

        starts.append(start)

    return starts

def normalize_blank_lines(text: str) -> str:
    """Collapse/expand blank-line runs between top-level constraint entries to
    exactly one. CONSTRAINTS-FORMAT.md §2."""
    lines = text.splitlines(keepends=True)
    starts = _chunk_starts(lines)

    if len(starts) < 2:
        return text

    pieces = [''.join(lines[:starts[0]])]

    for position, start in enumerate(starts):
        followed = position + 1 < len(starts)
        chunk = lines[start:starts[position + 1] if followed else len(lines)]

        if followed:
            while _is_blank(chunk[-1]):
                chunk.pop()
            chunk.append('\n')

        pieces.append(''.join(chunk))

    return ''.join(pieces)

def _fold_marker_error(filename: str, index: int, reason: str) -> FoldMarkerError:
    return FoldMarkerError(f'{filename}:{index + 1}: unbalanced fold markers: {reason}')

def check_and_repair_fold_markers(text: str, filename: str = '<unknown>') -> str:
    """Validate/repair vim foldmarker nesting; raise FoldMarkerError if ambiguous.
    CONSTRAINTS-FORMAT.md §5.

    Every injection is recorded first and applied only once the whole file has been
    scanned, so a raise leaves `text` untouched.
    """
    lines = text.splitlines(keepends=True)
    injections: list[tuple[int, str]] = []
    opens: list[tuple[int, int]] = []
    previous: tuple[str, int] | None = None

    for index, line in enumerate(lines):
        if _is_fold_open(line):
            indent = _indent(line)
            pending = [entry for entry in opens if entry[1] >= indent]

            if len(pending) > 1:
                raise _fold_marker_error(filename, index,
                                         'more than one fold is still open here')

            if pending:
                injections.append((index, ' ' * pending[0][1] + FOLD_CLOSE + '\n'))
                opens.remove(pending[0])

            opens.append((index, indent))
            previous = ('open', index)
        elif _is_fold_close(line):
            if opens:
                opens.pop()
                previous = ('close', index)
                continue

            if previous is None:
                point = 0
            elif previous[0] == 'close':
                point = previous[1] + 1
            else:
                raise _fold_marker_error(filename, index,
                                         'no unambiguous place for the missing "# {{{"')

            injections.append((point, ' ' * _indent(line) + FOLD_OPEN + '\n'))
            previous = ('repaired', index)

    if len(opens) > 1:
        raise _fold_marker_error(filename, opens[0][0],
                                 'more than one fold is still open at end of file')

    if opens:
        injections.append((len(lines), ' ' * opens[0][1] + FOLD_CLOSE + '\n'))

    if not injections:
        return text

    if injections[-1][0] == len(lines) and not lines[-1].endswith('\n'):
        lines[-1] += '\n'

    pending_at: dict[int, list[str]] = {}
    for index, marker in injections:
        pending_at.setdefault(index, []).append(marker)

    repaired: list[str] = []
    for index, line in enumerate(lines):
        repaired.extend(pending_at.get(index, ()))
        repaired.append(line)
    repaired.extend(pending_at.get(len(lines), ()))

    return ''.join(repaired)
