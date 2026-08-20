from __future__ import annotations

import ast
import inspect
import math
import pathlib

import pytest

from eos_pre_commit_hooks.eos_yaml import alignment
from eos_pre_commit_hooks.eos_yaml.alignment import _three_column_width, plan_alignment
from eos_pre_commit_hooks.eos_yaml.model import FieldSpec
from tests.fixtures.worked_examples import (
    BIG_EXPECTED_EXCLUDED,
    BIG_EXPECTED_INCLUDED,
    BIG_EXPECTED_KEYS,
    BIG_EXPECTED_WRAP_W,
    BIG_EXPECTED_WRAP_W_AT_150,
    BIG_FIELDS,
    BIG_N,
    BIG_OBSERVABLE_CELL,
    SMALL_FIELDS,
    SMALL_OBSERVABLE_CELLS,
    SMALL_PLAN,
)

def keys(fields, indices):
    """The keys of `fields` at `indices`, so an index-keyed plan reads as names."""
    return [fields[index].key for index in indices]

# --- Part A: the two worked examples ---------------------------------------------

def test_small_example_matches_its_plan_exactly():
    assert plan_alignment(SMALL_FIELDS, SMALL_OBSERVABLE_CELLS) == SMALL_PLAN

def test_big_example_matches_structurally():
    plan = plan_alignment(BIG_FIELDS, [BIG_OBSERVABLE_CELL] * BIG_N)

    assert plan.included == BIG_EXPECTED_INCLUDED
    assert keys(BIG_FIELDS, plan.included) == BIG_EXPECTED_KEYS
    assert plan.excluded == BIG_EXPECTED_EXCLUDED
    assert plan.wrap_w == BIG_EXPECTED_WRAP_W
    assert len(plan.column_widths) == BIG_N

def test_the_big_example_wraps_at_the_narrower_budget():
    """The layout the spec's §4.2 illustration was hand-derived at."""
    plan = plan_alignment(BIG_FIELDS, [BIG_OBSERVABLE_CELL] * BIG_N, max_line_width=150)

    assert plan.wrap_w == BIG_EXPECTED_WRAP_W_AT_150
    assert len(plan.column_widths) == BIG_EXPECTED_WRAP_W_AT_150

def test_no_wrap_is_needed_for_the_small_example():
    plan = plan_alignment(SMALL_FIELDS, SMALL_OBSERVABLE_CELLS)

    assert plan.wrap_w is None
    assert len(plan.column_widths) == len(SMALL_OBSERVABLE_CELLS)

def test_planning_is_a_pure_function():
    once = plan_alignment(BIG_FIELDS, [BIG_OBSERVABLE_CELL] * BIG_N)
    again = plan_alignment(BIG_FIELDS, [BIG_OBSERVABLE_CELL] * BIG_N)

    assert once == again

# --- Part B: the §4.4 cap ---------------------------------------------------------

CAP_N = 4
REFERENCE_KEYS = ('observables', 'means', 'covariance')
SHORT_OBSERVABLES = ['x' * 10] * CAP_N          # cap = max(15, 10) = 15, threshold = 17
LONG_OBSERVABLES = ['x' * 20] * CAP_N           # cap = 20, threshold = 22

def _uniform(key, width, arity=CAP_N):
    return FieldSpec(key=key, kind='vector', cells=['y' * width] * arity)

CAP_CASES = {
    'the 15-character floor dominates, field exactly at the threshold':
        (SHORT_OBSERVABLES, 17, True),
    'the 15-character floor dominates, field one character over':
        (SHORT_OBSERVABLES, 18, False),
    'the widest observable dominates, field exactly at the threshold':
        (LONG_OBSERVABLES, 22, True),
    'the widest observable dominates, field one character over':
        (LONG_OBSERVABLES, 23, False),
}

@pytest.mark.parametrize('name', list(CAP_CASES))
def test_cap_boundary(name):
    observables, width, expected = CAP_CASES[name]
    fields = [
        FieldSpec(key='observables', kind='vector', cells=observables),
        _uniform('candidate', width),
    ]

    plan = plan_alignment(fields, observables)

    assert ('candidate' in keys(fields, plan.included)) is expected
    assert ('candidate' in keys(fields, plan.excluded)) is not expected
    assert keys(fields, plan.included)[0] == 'observables'

def test_a_field_excluded_by_the_cap_sets_no_column_width():
    observables = SHORT_OBSERVABLES
    fields = [
        FieldSpec(key='observables', kind='vector', cells=observables),
        _uniform('kinematics', 34),
    ]

    plan = plan_alignment(fields, observables)

    assert keys(fields, plan.excluded) == ['kinematics']
    assert plan.column_widths == [10] * CAP_N
    assert plan.pad == [plan.pad[0], 0]

def test_every_field_excluded_leaves_an_empty_grid():
    observables = ['x' * 5] * 3
    fields = [_uniform('kinematics', 34, arity=3)]

    plan = plan_alignment(fields, observables)

    assert plan.included == []
    assert keys(fields, plan.excluded) == ['kinematics']
    assert plan.value_column == 0
    assert plan.pad == [0]
    assert plan.column_widths == []
    assert plan.wrap_w is None

# --- Part C: raggedness (spec §5) -------------------------------------------------

def test_a_ragged_matrix_field_is_excluded():
    observables = ['"obs"'] * 3
    ragged = FieldSpec(key='covariance', kind='matrix', rows=[
        ['+1.0e+00', '+2.0e+00', '+3.0e+00'],
        ['+2.0e+00', '+4.0e+00'],
        ['+3.0e+00', '+6.0e+00', '+9.0e+00'],
    ])
    fields = [FieldSpec(key='observables', kind='vector', cells=observables), ragged]

    plan = plan_alignment(fields, observables)

    assert keys(fields, plan.included) == ['observables']
    assert keys(fields, plan.excluded) == ['covariance']
    assert plan.column_widths == [5, 5, 5]
    assert plan.pad == [1, 0]

def test_a_square_matrix_of_the_wrong_arity_is_excluded():
    observables = ['"obs"'] * 3
    wrong = FieldSpec(key='correlations', kind='matrix', rows=[['+1.0', '+0.5']] * 2)
    fields = [FieldSpec(key='observables', kind='vector', cells=observables), wrong]

    plan = plan_alignment(fields, observables)

    assert keys(fields, plan.included) == ['observables']
    assert keys(fields, plan.excluded) == ['correlations']

# --- Part D: wrapping -------------------------------------------------------------

# One 'means:' field alone at indent 2: value_column = 2 + len('means:') + label_gap
# + 2 = 11, so the worst-case line is 11 + W * width + W * 2 + 1 = 12 + W * (width + 2).
# These cases state the budget they were derived against instead of relying on the
# default.
BUDGET = 150
WRAP_OBSERVABLES = ['x' * 20] * 6               # cap = 20, threshold = 22

def test_the_default_budget_is_the_one_the_spec_settled_on():
    assert inspect.signature(plan_alignment).parameters['max_line_width'].default == 240

def test_a_group_that_fits_exactly_does_not_wrap():
    fields = [_uniform('means', 21, arity=6)]   # 12 + 6 * 23 = 150, exactly the budget

    plan = plan_alignment(fields, WRAP_OBSERVABLES, max_line_width=BUDGET)

    assert plan.wrap_w is None
    assert plan.column_widths == [21] * 6

def test_a_group_one_character_too_wide_wraps():
    fields = [_uniform('means', 22, arity=6)]   # 12 + 6 * 24 = 156, one cell too many

    plan = plan_alignment(fields, WRAP_OBSERVABLES, max_line_width=BUDGET)

    # The widest fit is 5 cells per line (12 + 5 * 24 = 132); two lines then even out
    # to ceil(6 / 2) = 3.
    assert plan.wrap_w == 3
    assert plan.column_widths == [22] * 3

def test_the_wrap_width_is_balanced_across_the_sub_lines():
    observables = ['x' * 31] * 4                # cap = 31, threshold = 33
    fields = [_uniform('means', 33, arity=4)]   # 12 + 4 * 35 = 152 > 150 > 12 + 3 * 35

    plan = plan_alignment(fields, observables, max_line_width=BUDGET)

    assert plan.wrap_w == math.ceil(4 / 2)
    assert plan.column_widths == [33] * 2

def test_wrap_columns_are_shared_across_sub_lines():
    observables = ['x' * 40] * 6                # cap = 40, threshold = 42
    fields = [FieldSpec(key='means', kind='vector', cells=[
        'y' * 42, 'y' * 30, 'y' * 30, 'y' * 41, 'y' * 30, 'y' * 30,
    ])]

    plan = plan_alignment(fields, observables, max_line_width=BUDGET)

    # Wrapped at 3, cell 0 shares its column with cell 3, cell 1 with cell 4, and so
    # on; only the widest of each pair sets the width.
    assert plan.wrap_w == 3
    assert plan.column_widths == [42, 30, 30]

def test_an_over_wide_single_cell_still_yields_one_cell_per_line():
    observables = ['x' * 200] * 3               # cap = 200, so nothing is excluded
    fields = [_uniform('means', 200, arity=3)]

    plan = plan_alignment(fields, observables)

    assert plan.wrap_w == 1
    assert plan.column_widths == [200]

# --- Part E: group shapes ---------------------------------------------------------

def test_a_matrix_only_group_needs_no_vector_field():
    observables = ['"obs"'] * 3
    fields = [FieldSpec(key='covariance', kind='matrix', rows=[
        ['+1.912e-09', '+1.726e-10', '+3.427e-10'],
        ['+1.726e-10', '+1.478e-08', '+1.811e-09'],
        ['+3.427e-10', '+1.811e-09', '+2.863e-08'],
    ])]

    plan = plan_alignment(fields, observables)

    assert keys(fields, plan.included) == ['covariance']
    assert plan.excluded == []
    assert plan.value_column == 2 + len('covariance:') + 1 + 4
    assert plan.pad == [1]
    assert plan.column_widths == [10, 10, 10]
    assert plan.wrap_w is None

def test_included_and_excluded_keep_their_original_order():
    observables = ['"obs"'] * 3
    fields = [
        _uniform('observables', 5, arity=3),
        _uniform('wide_a', 30, arity=3),
        _uniform('means', 8, arity=3),
        _uniform('wide_b', 30, arity=3),
        _uniform('covariance', 8, arity=3),
    ]

    plan = plan_alignment(fields, observables)

    assert keys(fields, plan.included) == ['observables', 'means', 'covariance']
    assert keys(fields, plan.excluded) == ['wide_a', 'wide_b']

def test_a_matrix_field_borrows_two_columns_from_its_own_padding():
    observables = ['"obs"'] * 3
    fields = [
        _uniform('means', 8, arity=3),
        FieldSpec(key='means_too', kind='matrix', rows=[['+1.0e+00'] * 3] * 3),
    ]

    plan = plan_alignment(fields, observables)

    assert plan.value_column == 2 + len('means_too:') + 1 + 4
    assert plan.pad[1] == 1
    assert plan.pad[0] == plan.value_column - 2 - len('means:') - 2

# --- Part F: a group spanning two indent levels (spec §6) -------------------------

def test_two_indent_levels_share_one_absolute_value_column():
    """A Mixture entry's own fields sit at indent 2, its components' at indent 6."""
    observables = ["'obs'"] * 5
    fields = [
        FieldSpec('observables', 'vector', cells=observables, indent=2),
        FieldSpec('covariance', 'matrix', rows=[['+1.0e+00'] * 5] * 5, indent=6),
    ]

    plan = plan_alignment(fields, observables, reference_keys=REFERENCE_KEYS)

    assert plan.included == [0, 1]
    assert plan.value_column == 6 + len('covariance:') + 1 + 4

    # each field's own first cell lands in that one column, counted from column zero
    assert 2 + len('observables:') + plan.pad[0] + len('[ ') == plan.value_column
    assert 6 + len('covariance:') + plan.pad[1] + len('[ [ ') == plan.value_column

    assert all(pad >= 1 for pad in plan.pad)

def test_the_deeper_field_can_be_the_one_that_sets_the_column():
    fields = [
        FieldSpec('observables', 'vector', cells=["'obs'"] * 3, indent=2),
        FieldSpec('means', 'vector', cells=['+1.0e+00'] * 3, indent=6),
    ]

    plan = plan_alignment(fields, fields[0].cells, reference_keys=REFERENCE_KEYS)

    # 'observables:' at indent 2 reaches column 17, 'means:' at indent 6 only 15
    assert plan.value_column == 2 + len('observables:') + 1 + 2
    assert plan.pad == [1, 3]

def test_one_ragged_component_leaves_its_siblings_in_the_group():
    """Spec §6: membership stays per field, so a name cannot address the group."""
    observables = ["'obs'"] * 3
    fields = [
        FieldSpec('observables', 'vector', cells=observables, indent=2),
        FieldSpec('means', 'vector', cells=['+1.0e+00'] * 3, indent=6),
        FieldSpec('covariance', 'matrix', rows=[['+1.0e+00'] * 3] * 3, indent=6),
        FieldSpec('means', 'vector', cells=['+2.0e+00'] * 3, indent=6),
        FieldSpec('covariance', 'matrix', rows=[['+2.0e+00'] * 2] * 3, indent=6),
    ]

    plan = plan_alignment(fields, observables, reference_keys=REFERENCE_KEYS)

    assert plan.included == [0, 1, 2, 3]
    assert plan.excluded == [4]

# --- Part G: module hygiene -------------------------------------------------------

def test_module_imports_nothing_it_must_not():
    tree = ast.parse(pathlib.Path(alignment.__file__).read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or '').split('.')[0])

    assert imported == {'__future__', 'math', 'model'}

def test_no_field_name_is_hard_coded():
    source = pathlib.Path(alignment.__file__).read_text()

    for name in ('observables', 'kinematics', 'covariance', 'correlations', 'options'):
        assert f"'{name}'" not in source and f'"{name}"' not in source

def _observables(width, arity=4):
    """An observables field whose cells are exactly `width` characters wide."""
    return FieldSpec(key='observables', kind='vector',
                     cells=["'" + 'x' * (width - 2) + "'"] * arity)

@pytest.mark.parametrize('budget, expected', [(150, 42), (240, 72)])
def test_three_column_width_matches_the_specified_arithmetic(budget, expected):
    # (budget - indent 2 - '[ ' 2 - ' ]' 2 - 'observables: ' 13 - two ', ' 4) // 3
    assert _three_column_width('observables', budget, 2, 1, 1) == expected

@pytest.mark.parametrize('budget, width', [(150, 12), (150, 41), (150, 42),
                                           (240, 43), (240, 63), (240, 72)])
def test_a_narrow_reference_field_stays_in_the_group(budget, width):
    fields = [_observables(width), FieldSpec('means', 'vector', cells=['+1.0e+00'] * 4)]
    plan = plan_alignment(fields, fields[0].cells, max_line_width=budget,
                          reference_keys=REFERENCE_KEYS)

    assert keys(fields, plan.included) == ['observables', 'means']
    assert plan.excluded == []

@pytest.mark.parametrize('budget, width', [(150, 43), (150, 63), (150, 90),
                                           (240, 73), (240, 90)])
def test_a_reference_field_too_wide_for_three_columns_is_dropped(budget, width):
    fields = [_observables(width), FieldSpec('means', 'vector', cells=['+1.0e+00'] * 4)]
    plan = plan_alignment(fields, fields[0].cells, max_line_width=budget,
                          reference_keys=REFERENCE_KEYS)

    assert keys(fields, plan.excluded) == ['observables']
    assert keys(fields, plan.included) == ['means']

def test_the_next_reference_sets_the_cap_once_the_first_is_dropped():
    # observables is dropped, so the cap comes from means (8 chars) and not from the
    # 63-char observable names -- which would otherwise widen every numeric column.
    fields = [
        _observables(63),
        FieldSpec('means', 'vector', cells=['+1.0e+00'] * 4),
        FieldSpec('kinematics', 'vector', cells=['{ q2_min: +1.0, q2_max: +2.0 }'] * 4),
    ]
    plan = plan_alignment(fields, fields[0].cells, max_line_width=150,
                          reference_keys=REFERENCE_KEYS)

    assert keys(fields, plan.included) == ['means']
    assert keys(fields, plan.excluded) == ['observables', 'kinematics']
    assert plan.column_widths == [8, 8, 8, 8]

def test_naming_no_reference_keys_keeps_the_original_behaviour():
    fields = [_observables(63), FieldSpec('means', 'vector', cells=['+1.0e+00'] * 4)]

    assert plan_alignment(fields, fields[0].cells).included == [0, 1]


# --- the cap spans every reference field, not just observables --------------------

def test_the_cap_is_wide_enough_for_every_reference_field():
    # means is wider than observables, so it sets the cap and cannot be excluded by it.
    fields = [
        FieldSpec('observables', 'vector', cells=["'" + 'x' * 10 + "'"] * 4),
        _uniform('means', 23),
    ]
    plan = plan_alignment(fields, fields[0].cells, reference_keys=REFERENCE_KEYS)

    assert keys(fields, plan.included) == ['observables', 'means']
    assert plan.excluded == []

def test_a_reference_field_is_never_excluded_by_the_cap_it_sets():
    for width in (16, 23, 30, 42):
        fields = [
            FieldSpec('observables', 'vector', cells=["'x'"] * 4),
            _uniform('means', width),
        ]
        plan = plan_alignment(fields, fields[0].cells,
                              reference_keys=REFERENCE_KEYS)

        assert plan.excluded == [], f'means at width {width} was excluded'

def test_a_non_reference_field_is_still_capped_against_the_widest_reference():
    # kinematics is not a reference, so a cell wider than the cap still excludes it.
    fields = [
        FieldSpec('observables', 'vector', cells=["'" + 'x' * 10 + "'"] * 4),
        _uniform('means', 12),
        _uniform('kinematics', 34),
    ]
    plan = plan_alignment(fields, fields[0].cells, reference_keys=REFERENCE_KEYS)

    assert keys(fields, plan.included) == ['observables', 'means']
    assert keys(fields, plan.excluded) == ['kinematics']

def test_covariance_is_a_reference_and_so_never_excluded_by_the_cap():
    # modest means, full-precision covariance: the pairing that used to eject the matrix
    fields = [
        FieldSpec('observables', 'vector', cells=["'" + 'x' * 10 + "'"] * 4),
        _uniform('means', 12),
        FieldSpec('covariance', 'matrix', rows=[['y' * 23] * 4] * 4),
    ]
    plan = plan_alignment(fields, fields[0].cells, reference_keys=REFERENCE_KEYS)

    assert keys(fields, plan.included) == ['observables', 'means', 'covariance']
    assert plan.excluded == []

def test_the_floor_is_fifteen():
    fields = [
        FieldSpec('observables', 'vector', cells=["'x'"] * 4),
        _uniform('candidate', 17),
    ]

    plan = plan_alignment(fields, fields[0].cells, reference_keys=REFERENCE_KEYS)

    assert 'candidate' in keys(fields, plan.included)

    wider = [fields[0], _uniform('candidate', 18)]
    plan = plan_alignment(wider, fields[0].cells, reference_keys=REFERENCE_KEYS)

    assert 'candidate' in keys(wider, plan.excluded)
