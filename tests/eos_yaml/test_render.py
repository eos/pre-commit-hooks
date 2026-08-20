from __future__ import annotations

import ast
import pathlib

from eos_pre_commit_hooks.eos_yaml import render
from eos_pre_commit_hooks.eos_yaml.model import AlignmentPlan, FieldSpec
from eos_pre_commit_hooks.eos_yaml.render import render_group, render_self_aligned
from tests.fixtures.worked_examples import (
    BIG_EXPECTED_EXCLUDED,
    BIG_EXPECTED_INCLUDED,
    BIG_EXPECTED_WRAP_W_AT_150,
    BIG_FIELDS,
    BIG_HAND_FORMATTED_TEXT,
    SMALL_EXPECTED_TEXT,
    SMALL_FIELDS,
    SMALL_PLAN,
)

# --- Part A: the small worked example ---------------------------------------------

def test_small_example_renders_exactly():
    lines = render_group(SMALL_FIELDS, SMALL_PLAN, indent=0)

    assert '\n'.join(lines) + '\n' == SMALL_EXPECTED_TEXT

def test_rendering_is_a_pure_function():
    once = render_group(SMALL_FIELDS, SMALL_PLAN, indent=0)
    again = render_group(SMALL_FIELDS, SMALL_PLAN, indent=0)

    assert once == again

def test_only_included_fields_are_rendered():
    fields = SMALL_FIELDS + [FieldSpec('kinematics', 'vector', cells=['{ x: 1 }'] * 3)]
    lines = render_group(fields, SMALL_PLAN, indent=0)

    assert '\n'.join(lines) + '\n' == SMALL_EXPECTED_TEXT

# --- Part B: inner/outer bracket placement ----------------------------------------

BRACKET_FIELDS = [
    FieldSpec('means', 'vector', cells=['+1.000e+00', '+2.000e+00', '+3.000e+00']),
    FieldSpec('covariance', 'matrix', rows=[['+1.000e-01'] * 3] * 3),
]
BRACKET_PLAN = AlignmentPlan(
    value_column=16,                                 # 'covariance:' 11 + gap 1 + '[ [ ' 4
    key_pad={'means': 8, 'covariance': 1},
    column_widths=[10, 10, 10],
    wrap_w=None,
    included=['means', 'covariance'],
    excluded=[],
)

def _brackets(line):
    """The column of every `[` on a line, left to right."""
    return [column for column, character in enumerate(line) if character == '[']

def test_a_matrix_inner_bracket_aligns_with_a_vector_bracket():
    vector, matrix_first, matrix_second, matrix_third, closing = render_group(
        BRACKET_FIELDS, BRACKET_PLAN, indent=2)

    outer, inner = _brackets(matrix_first)

    assert _brackets(vector) == [inner]
    assert outer == inner - 2

    # continuation rows repeat the inner bracket only; the closer sits under the outer
    assert _brackets(matrix_second) == [inner]
    assert _brackets(matrix_third) == [inner]
    assert closing == ' ' * outer + ']'

def test_matrix_cells_start_at_the_value_column():
    lines = render_group(BRACKET_FIELDS, BRACKET_PLAN, indent=2)

    for line in lines[:-1]:
        assert line.index('+') == 2 + BRACKET_PLAN.value_column

def test_matrix_rows_are_comma_separated_and_the_last_one_is_not():
    lines = render_group(BRACKET_FIELDS, BRACKET_PLAN, indent=2)

    assert [line[-2:] for line in lines[1:4]] == ['],', '],', ' ]']
    assert lines[-1].strip() == ']'

# --- Part C: wrapping --------------------------------------------------------------

WRAP_FIELDS = [
    FieldSpec('observables', 'vector', cells=['"foo"', '"bar"', '"baz"', '"snafu"']),
    FieldSpec('means', 'vector', cells=['+1.0e-4', '-1.0', '+0.3', '-0.003']),
]
WRAP_PLAN = AlignmentPlan(
    value_column=15,
    key_pad={'observables': 1, 'means': 7},
    column_widths=[7, 7],
    wrap_w=2,
    included=['observables', 'means'],
    excluded=[],
)

def test_a_wrapped_group_breaks_after_the_same_cell_index_in_every_field():
    observables_first, observables_second, means_first, means_second = render_group(
        WRAP_FIELDS, WRAP_PLAN, indent=0)

    # the comma sits against its value; the column padding follows it
    assert observables_first == 'observables: [ "foo",   "bar",'
    assert observables_second == ' ' * 15 + '"baz",   "snafu" ]'
    assert means_first == 'means:       [ +1.0e-4, -1.0,'
    assert means_second == ' ' * 15 + '+0.3,    -0.003  ]'

def test_wrapped_continuation_lines_start_at_the_value_column():
    lines = render_group(WRAP_FIELDS, WRAP_PLAN, indent=4)

    for line in lines[1::2]:
        assert line.startswith(' ' * (4 + WRAP_PLAN.value_column))
        assert line[4 + WRAP_PLAN.value_column] != ' '
        assert '[' not in line

def test_a_matrix_row_wraps_like_a_vector_field():
    fields = [FieldSpec('covariance', 'matrix', rows=[['+1.0e-01'] * 4] * 2)]
    plan = AlignmentPlan(
        value_column=16,
        key_pad={'covariance': 1},
        column_widths=[8, 8],
        wrap_w=2,
        included=['covariance'],
        excluded=[],
    )
    first, second, third, fourth, closing = render_group(fields, plan, indent=2)

    assert _brackets(first) == [14, 16]
    assert _brackets(third) == [16]
    for continuation in (second, fourth):
        assert '[' not in continuation
        assert continuation.startswith(' ' * (2 + plan.value_column))
        assert continuation[2 + plan.value_column] != ' '
    assert second.endswith('],')
    assert fourth.endswith(' ]')
    assert closing == ' ' * 14 + ']'

# --- Part D: structural check against the hand-formatted big example ---------------

BIG_PLAN = AlignmentPlan(
    value_column=16,                                 # 'covariance:' 11 + gap 1 + '[ [ ' 4
    key_pad={'observables': 2, 'options': 6, 'means': 8, 'covariance': 1},
    column_widths=[14] * BIG_EXPECTED_WRAP_W_AT_150,
    wrap_w=BIG_EXPECTED_WRAP_W_AT_150,
    included=BIG_EXPECTED_INCLUDED,
    excluded=BIG_EXPECTED_EXCLUDED,
)

def _split_cells(text):
    """The top-level, comma-separated cells of one rendered sub-line."""
    cells, depth, current = [], 0, ''

    for character in text:
        depth += {'{': 1, '}': -1}.get(character, 0)
        if character == ',' and depth == 0:
            cells.append(current.strip())
            current = ''
        else:
            current += character

    if current.strip():
        cells.append(current.strip())

    return cells

def _sub_lines(lines):
    """Every field's cells, sub-line by sub-line, keyed by field name."""
    fields, current = {}, None

    for line in lines:
        text = line.strip()
        head, separator, tail = text.partition(':')

        if separator and head.replace('-', '').replace('_', '').isalnum() and '{' not in head:
            current = head
            text = tail.strip()

        while text.startswith('['):
            text = text[1:].strip()

        text = text.rstrip(',').rstrip(']').rstrip(',').strip()

        if current is None or not text or text == '...':
            continue

        fields.setdefault(current, []).append(_split_cells(text))

    return fields

def test_the_big_example_matches_the_hand_formatted_layout_structurally():
    rendered = _sub_lines(render_group(BIG_FIELDS, BIG_PLAN, indent=2))
    expected = _sub_lines(BIG_HAND_FORMATTED_TEXT.split('\n'))

    assert list(rendered) == BIG_EXPECTED_INCLUDED
    assert 'kinematics' not in rendered

    for key in ('observables', 'options', 'means'):
        assert rendered[key] == expected[key], key

    # the fixture elides all but the first two and the last of the ten matrix rows
    assert len(rendered['covariance']) == 2 * len(BIG_FIELDS[-1].rows)
    assert rendered['covariance'][:4] == expected['covariance'][:4]
    assert rendered['covariance'][-2:] == expected['covariance'][-2:]

def test_the_big_example_stays_inside_the_line_budget():
    lines = render_group(BIG_FIELDS, BIG_PLAN, indent=2)

    assert max(len(line) for line in lines) <= 240
    assert all(line == line.rstrip() for line in lines)

# --- Part E: self-aligned fields ---------------------------------------------------

def test_a_kinematics_shaped_field_renders_as_a_block_sequence():
    field = FieldSpec('kinematics', 'vector', cells=[
        '{ q2_min: +10.44, q2_max: +11.63 }',
        '{ q2_min:  +9.26, q2_max: +10.44 }',
    ])
    lines = render_self_aligned(field, indent=2)

    assert lines == [
        '  kinematics:',
        '    - { q2_min: +10.44, q2_max: +11.63 }',
        '    - { q2_min:  +9.26, q2_max: +10.44 }',
    ]

def test_a_self_aligned_matrix_field_puts_one_row_per_line():
    field = FieldSpec('correlations', 'matrix', rows=[['+1.0', '+0.5'], ['+0.5', '+1.0']])

    assert render_self_aligned(field, indent=0) == [
        'correlations:',
        '  - [ +1.0, +0.5 ]',
        '  - [ +0.5, +1.0 ]',
    ]

# --- Part F: module hygiene --------------------------------------------------------

def test_render_imports_only_the_model():
    tree = ast.parse(pathlib.Path(render.__file__).read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or '').split('.')[0])

    assert imported == {'__future__', 'model'}

def test_no_field_name_is_hard_coded():
    source = pathlib.Path(render.__file__).read_text()

    for name in ('observables', 'kinematics', 'covariance', 'correlations', 'options'):
        assert f"'{name}'" not in source and f'"{name}"' not in source
