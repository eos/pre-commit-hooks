from __future__ import annotations

import io

from dataclasses import dataclass

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.scalarstring import ScalarString

from . import alignment, floats, layout, render, strings
from .model import FieldSpec

INDENT = 2
MIXTURE = 'Mixture'
COMPONENTS = 'components'
OBSERVABLES = 'observables'
REFERENCE_KEYS = (OBSERVABLES, 'means', 'covariance')

class _Rendered(str):
    """A scalar whose final text is already decided; ruamel emits it verbatim."""

def _represent_rendered(representer, data):
    return representer.represent_scalar('tag:yaml.org,2002:float', str(data))

def _new_yaml() -> YAML:
    yaml = YAML(typ='rt')
    yaml.preserve_quotes = True
    yaml.width = 1 << 20
    yaml.indent(mapping=INDENT, sequence=2 * INDENT, offset=INDENT)
    yaml.brace_single_entry_mapping_in_flow_sequence = True
    yaml.representer.add_representer(_Rendered, _represent_rendered)

    return yaml

_YAML = _new_yaml()

# --- node classification ----------------------------------------------------------

def _is_sequence(node) -> bool:
    return isinstance(node, (CommentedSeq, list))

def _is_float(node) -> bool:
    return isinstance(node, float)

def _is_number(node) -> bool:
    return isinstance(node, (int, float)) and not isinstance(node, bool)

def _is_flow(node) -> bool:
    return bool(getattr(node, 'fa', None) and node.fa.flow_style())

def _is_cell(node, flow_parent: bool = False) -> bool:
    """A scalar, or a flow mapping whose own values are all scalars.

    A mapping nested in a flow sequence carries no flow style of its own — it
    inherits its parent's — so `flow_parent` stands in for it.
    """
    if isinstance(node, (CommentedMap, dict)):
        return (_is_flow(node) or flow_parent) and not any(
            _is_sequence(value) or isinstance(value, dict) for value in node.values()
        )

    return not _is_sequence(node)

def _notation(value):
    """Fixed or scientific, from the exponent marker ruamel kept from the source."""
    return floats.detect_notation('e' if getattr(value, '_exp', None) else '')

# --- scalar canonicalization ------------------------------------------------------

def _entry_floats(node):
    """Every float anywhere below `node`, for the entry-wide exponent width."""
    if isinstance(node, (CommentedMap, dict)):
        for value in node.values():
            yield from _entry_floats(value)
    elif _is_sequence(node):
        for item in node:
            yield from _entry_floats(item)
    elif _is_float(node):
        yield node

@dataclass
class _Scope:
    """One sequence field's shared float format: the fractional-digit width to pad
    every element to, per notation, and the notation an integer element takes on."""
    widths: dict[str, int]
    promote: str | None

def _field_scope(value) -> _Scope:
    """The float format one sequence field's elements share.

    A matrix field's rows share the one scope; numbers inside a flow-mapping cell sit
    outside it and keep their natural form. Spec §3.1.
    """
    values = []

    for item in value:
        if _is_float(item):
            values.append(item)
        elif _is_sequence(item):
            values.extend(element for element in item if _is_float(element))

    widths = {}
    for notation in ('fixed', 'scientific'):
        selected = [element for element in values if _notation(element) == notation]
        if selected:
            widths[notation] = floats.mantissa_width(selected, notation)

    notations = {_notation(element) for element in values}
    promote = 'scientific' if notations == {'scientific'} else 'fixed' if values else None

    return _Scope(widths=widths, promote=promote)

def _with_plain_keys(node: CommentedMap) -> CommentedMap:
    """`node` with every quoted key replaced by its plain text. Spec §3.2."""
    if not any(isinstance(key, ScalarString) for key in node):
        return node

    plain = CommentedMap()
    for key, value in node.items():
        plain[str(key)] = value

    for attribute in ('_yaml_comment', '_yaml_format'):
        if hasattr(node, attribute):
            setattr(plain, attribute, getattr(node, attribute))

    return plain

def _canonicalize(node, exponent_width: int, scope: _Scope | None = None):
    """Rewrite every scalar below `node` into its final form. Spec §3.1, §3.2."""
    if isinstance(node, CommentedMap):
        node = _with_plain_keys(node)
        for key in node:
            value = node[key]
            node[key] = _canonicalize(
                value, exponent_width, _field_scope(value) if _is_sequence(value) else None)

        return node

    if _is_sequence(node):
        for index, item in enumerate(node):
            inherited = scope if _is_number(item) or _is_sequence(item) else None
            node[index] = _canonicalize(item, exponent_width, inherited)

        return node

    if _is_number(node):
        notation = _notation(node) if _is_float(node) else scope and scope.promote

        # an integer outside a float-valued field stays integral
        if notation is None:
            return node

        width = scope.widths.get(notation, 1) if scope else 1

        return _Rendered(floats.format_float(node, notation, exponent_width, width))

    if isinstance(node, str) and not isinstance(node, _Rendered):
        return strings.quote(str(node))

    return node

# --- ruamel-rendered text ---------------------------------------------------------

def _dump(value) -> str:
    buffer = io.StringIO()
    _YAML.dump(value, buffer)

    return buffer.getvalue()

def _dump_scalar(value) -> str:
    """One cell's rendered text: no key, no `- ` marker, no trailing newline."""
    if isinstance(value, (CommentedMap, dict)) and not _is_flow(value):
        flow = CommentedMap(value)
        flow.fa.set_flow_style()
        value = flow

    text = _dump(CommentedSeq([value])).strip()

    return text[2:] if text.startswith('- ') else text

def _key_line(key) -> str:
    """The `key:` line for a mapping whose value starts on the following lines."""
    holder = CommentedMap()
    holder[key] = None

    return _dump(holder).rstrip('\n')

def _indented(text: str, indent: int) -> list[str]:
    return [' ' * indent + line if line else '' for line in text.splitlines()]

def _key_lines(mapping, key, indent: int) -> list[str]:
    """One ordinary `key: value` block, dumped by ruamel and re-indented."""
    holder = CommentedMap()
    holder[key] = mapping[key]

    return _indented(_dump(holder), indent)

# --- comments ---------------------------------------------------------------------

def _token_lines(token) -> list[str]:
    return [' ' * token.start_mark.column + line if line else '' for line in
            token.value.splitlines()]

def _pre_comment_lines(mapping, key) -> list[str]:
    slot = mapping.ca.items.get(key)
    tokens = slot[1] if slot else None
    lines = []

    for token in tokens or ():
        lines.extend(_token_lines(token))

    return lines

def _detach_value_comments(node) -> None:
    """Drop the second copy ruamel keeps, on the value itself, of a key's own comment."""
    if isinstance(node, CommentedMap):
        for key in node:
            slot = node.ca.items.get(key)
            attached = getattr(node[key], 'ca', None)

            if (slot and slot[2] is not None and attached and attached.comment
                    and attached.comment[0] is slot[2]):
                attached.comment[0] = None

            _detach_value_comments(node[key])
    elif _is_sequence(node):
        for item in node:
            _detach_value_comments(item)

def _post_comment(mapping, key) -> tuple[str | None, list[str]]:
    """The key's own end-of-line comment, if any, and the full lines that follow it."""
    slot = mapping.ca.items.get(key)
    token = slot[2] if slot else None

    if token is None:
        return None, []

    if token.value.startswith('\n'):
        return None, token.value[1:].splitlines()

    head, _, rest = token.value.partition('\n')

    return head.strip(), rest.splitlines()

def _own_comments(node):
    """`node`'s own comment slots, without creating them where they are absent."""
    return getattr(node, '_yaml_comment', None)

def _last_element_line(node) -> int | None:
    """The source line a sequence's last element starts on."""
    if not _is_sequence(node) or not node:
        return None

    position = getattr(node, 'lc', None) and node.lc.data.get(len(node) - 1)

    return position[0] if position else None

def _end_lines(node) -> list[str]:
    """The comment run that follows a value's whole block in the source.

    ruamel parks it on the innermost node the block ends in, so a key rendered by
    the aligned grid — which never reaches ruamel's emitter — has to carry it here.
    A token on the last element's own line annotates that element, and is hoisted by
    `_element_comment_lines` instead.
    """
    lines = []

    if isinstance(node, (CommentedMap, dict)):
        for value in node.values():
            lines.extend(_end_lines(value))
    elif _is_sequence(node):
        for item in node:
            lines.extend(_end_lines(item))

    own = _own_comments(node)
    last = _last_element_line(node)

    for token in (own.end if own else None) or ():
        if token.start_mark.line != last:
            lines.extend(_token_lines(token))

    return lines

def _leading_lines(node) -> list[str]:
    """A comment run on a mapping's own first line, below the key it belongs to."""
    own = _own_comments(node)
    lines = []

    for token in ((own.comment or [None, None])[1] if own else None) or ():
        lines.extend(_token_lines(token))

    return lines

def _element_comment_lines(node, indent: int) -> list[str]:
    """Comments a sequence attaches to its own elements, hoisted above the key.

    A canonical wrap width moves the elements out from under such a comment, so the
    note is kept but not its position within the field.
    """
    own = _own_comments(node)
    lines = []
    tokens = []

    for index in sorted(own.items if own else {}):
        for slot in own.items[index]:
            tokens.extend([slot] if not isinstance(slot, list) else slot)

    tokens.extend(token for token in (own.end if own else None) or ()
                  if token.start_mark.line == _last_element_line(node))

    for token in tokens:
        if token is not None:
            lines.extend(' ' * indent + line.strip()
                         for line in token.value.splitlines() if line.strip())

    for item in node if _is_sequence(node) else ():
        if _is_sequence(item):
            lines.extend(_element_comment_lines(item, indent))

    return lines

def _append_comments(lines: list[str], eol: str | None, following: list[str]) -> None:
    """Attach `eol` to the block just emitted, or above it where that would not parse."""
    if eol:
        if len(lines) == 1 or lines[0].endswith(':'):
            lines[0] += '  ' + eol
        else:
            lines.insert(0, ' ' * (len(lines[0]) - len(lines[0].lstrip())) + eol)

    lines.extend(following)

# --- alignment groups -------------------------------------------------------------

def _field_spec(key: str, value, arity: int) -> FieldSpec | None:
    """A vector or matrix FieldSpec for `value`, or None if it is not a candidate."""
    if not _is_sequence(value) or len(value) != arity:
        return None

    flow = _is_flow(value)

    if all(_is_cell(item, flow) for item in value):
        return FieldSpec(key=key, kind='vector', cells=[_dump_scalar(item) for item in value])

    if all(_is_sequence(row) and all(_is_cell(cell, flow or _is_flow(row)) for cell in row)
           for row in value):
        return FieldSpec(key=key, kind='matrix',
                         rows=[[_dump_scalar(cell) for cell in row] for row in value])

    return None

def _runs(keys: list[str], specs: dict) -> list[list[str]]:
    """Maximal runs of adjacent candidate keys. Spec §4 step 1."""
    runs: list[list[str]] = [[]]

    for key in keys:
        if specs.get(key) is None:
            runs.append([])
        else:
            runs[-1].append(key)

    return [run for run in runs if run]

def _arity(entry) -> tuple[int, list[str]]:
    """The entry's arity and its rendered `observables` cells. Spec §2."""
    value = entry.get(OBSERVABLES) if isinstance(entry, (CommentedMap, dict)) else None

    if not _is_sequence(value):
        return 0, []

    flow = _is_flow(value)
    cells = ([_dump_scalar(item) for item in value]
             if all(_is_cell(item, flow) for item in value) else [])

    return len(value), cells

# --- assembly ---------------------------------------------------------------------

def _entry_lines(entry, indent: int, arity: int | None = None,
                 observable_cells: list[str] | None = None) -> list[str]:
    """One constraint entry's body, key by key, in the entry's own key order."""
    if arity is None:
        arity, observable_cells = _arity(entry)

    keys = list(entry)
    specs = {key: _field_spec(key, entry[key], arity) for key in keys} if arity > 1 else {}
    plans = {}

    for run in _runs(keys, specs):
        plan = alignment.plan_alignment(
            [specs[key] for key in run],
            observable_cells or [''] * arity,
            indent=indent,
            reference_keys=REFERENCE_KEYS,
        )
        plans.update(dict.fromkeys(run, plan))

    mixture = entry.get('type') == MIXTURE
    lines = []

    for key in keys:
        lines.extend(_pre_comment_lines(entry, key))

        hoisted = []

        if key in plans:
            spec, plan = specs[key], plans[key]
            hoisted = _element_comment_lines(entry[key], indent)
            block = (render.render_group([spec], plan, indent) if key in plan.included
                     else render.render_self_aligned(spec, indent))
            block += _end_lines(entry[key])
        elif mixture and key == COMPONENTS and _is_sequence(entry[key]):
            block = _component_lines(entry[key], key, indent, arity, observable_cells)
        else:
            block = _key_lines(entry, key, indent)

        _append_comments(block, *_post_comment(entry, key))
        lines.extend(hoisted + block)

    return lines

def _component_lines(components, key: str, indent: int, arity: int,
                     observable_cells: list[str] | None) -> list[str]:
    """A `Mixture` entry's components, each aligned against its own fields. Spec §6."""
    lines = [' ' * indent + key + ':']

    for component in components:
        if not isinstance(component, CommentedMap):
            lines.extend(_indented(_dump(CommentedSeq([component])), indent + INDENT))
            continue

        block = _entry_lines(component, indent + 2 * INDENT, arity, observable_cells)
        first = next((number for number, line in enumerate(block)
                      if line.strip() and not line.lstrip().startswith('#')), 0)
        block[first] = ' ' * (indent + INDENT) + '- ' + block[first][indent + 2 * INDENT:]
        lines.extend(block)

    return lines

def _document_lines(data: CommentedMap) -> list[str]:
    lines = []

    for token in (data.ca.comment or [None, None])[1] or ():
        lines.extend(_token_lines(token))

    for key in data:
        lines.extend(_pre_comment_lines(data, key))
        entry = data[key]

        if isinstance(entry, CommentedMap) and entry:
            block = [_key_line(key)] + _leading_lines(entry) + _entry_lines(entry, INDENT)
        else:
            block = _key_lines(data, key, 0)

        _append_comments(block, *_post_comment(data, key))
        lines.extend(block)

    for token in (data.ca.end if _own_comments(data) else None) or ():
        lines.extend(_token_lines(token))

    return lines

def _reindent_comments(text: str) -> str:
    """Pull every indented full-line comment onto the indent of the key below it."""
    lines = text.split('\n')
    indent = 0

    for index in range(len(lines) - 1, -1, -1):
        stripped = lines[index].strip()

        if not stripped:
            continue

        if stripped.startswith('#'):
            if lines[index] != stripped:
                lines[index] = ' ' * indent + stripped
        else:
            indent = len(lines[index]) - len(lines[index].lstrip())

    return '\n'.join(lines)

def format_text(text: str, filename: str = '<unknown>') -> str:
    """The canonical form of one constraints file. See the project's style spec.

    Raises `layout.FoldMarkerError` when the file's fold markers are unbalanced in a
    way that has no unambiguous repair; the caller must then leave the file alone.
    """
    data = _YAML.load(text)

    if isinstance(data, CommentedMap):
        data = _with_plain_keys(data)
        _detach_value_comments(data)
        for key in data:
            data[key] = _canonicalize(data[key], floats.entry_exponent_width(
                list(_entry_floats(data[key]))))
        formatted = '\n'.join(_document_lines(data))
    elif data is None:
        formatted = text
    else:
        formatted = _dump(data)

    if formatted and not formatted.endswith('\n'):
        formatted += '\n'

    formatted = _reindent_comments(formatted)
    formatted = layout.normalize_blank_lines(formatted)

    return layout.check_and_repair_fold_markers(formatted, filename)
