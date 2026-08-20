from __future__ import annotations

import ast
import math
import pathlib

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from eos_pre_commit_hooks.eos_yaml import floats
from eos_pre_commit_hooks.eos_yaml.floats import (
    detect_notation,
    entry_exponent_width,
    format_float,
    mantissa_width,
    required_exponent_width,
)

NOTATIONS = st.sampled_from(['fixed', 'scientific'])
WIDTHS = st.sampled_from([2, 3])
FINITE = st.floats(allow_nan=False, allow_infinity=False)

@pytest.mark.parametrize(('value', 'notation', 'width', 'expected'), [
    (1.36e-07, 'scientific', 2, '+1.36e-07'),
    (-2.4e-08, 'scientific', 2, '-2.4e-08'),
    (0.1349768, 'fixed', 2, '+0.1349768'),
    (0.0, 'fixed', 2, '+0.0'),
    (-0.0, 'fixed', 2, '-0.0'),
    (1.5e-123, 'scientific', 3, '+1.5e-123'),
    (1.5e-7, 'scientific', 3, '+1.5e-007'),
])
def test_format_float_worked_examples(value, notation, width, expected):
    assert format_float(value, notation, width) == expected

@pytest.mark.parametrize(('raw_text', 'expected'), [
    ('1.36e-07', 'scientific'),
    ('0.1349768', 'fixed'),
    ('1.36E-07', 'scientific'),
    ('+4.05e+12', 'scientific'),
    ('-0.0', 'fixed'),
])
def test_detect_notation_worked_examples(raw_text, expected):
    assert detect_notation(raw_text) == expected

@pytest.mark.parametrize(('value', 'expected'), [
    (1.5e-7, 2),
    (1.5e-123, 3),
    (0.0, 2),
    (-0.0, 2),
    (1e99, 2),
    (1e100, 3),
    (1e-99, 2),
    (1e-100, 3),
])
def test_required_exponent_width_worked_examples(value, expected):
    assert required_exponent_width(value) == expected

@pytest.mark.parametrize(('values', 'expected'), [
    ([4.154e-05, 1.5e-123], 3),
    ([4.154e-05, 6.106e-04], 2),
    ([], 2),
    ([1.5e-123], 3),
    ([6.106e-04], 2),
    ([1.5e-123, 4.154e-05], 3),
    ([1e99, 1e-99], 2),
    ([1e99, 1e-100], 3),
])
def test_entry_exponent_width(values, expected):
    assert entry_exponent_width(values) == expected

@pytest.mark.parametrize(('notation', 'expected'), [
    ('fixed', '-0.0'),
    ('scientific', '-0.0e+00'),
])
def test_negative_zero_keeps_its_sign(notation, expected):
    assert format_float(-0.0, notation) == expected
    assert math.copysign(1.0, float(format_float(-0.0, notation))) == -1.0

@pytest.mark.parametrize(('notation', 'expected'), [
    ('fixed', '+0.0'),
    ('scientific', '+0.0e+00'),
])
def test_positive_zero_keeps_its_sign(notation, expected):
    assert format_float(0.0, notation) == expected
    assert math.copysign(1.0, float(format_float(0.0, notation))) == 1.0

@pytest.mark.parametrize(('value', 'notation', 'expected'), [
    (1e-7, 'scientific', '+1.0e-07'),
    (5.0, 'scientific', '+5.0e+00'),
    (100.0, 'fixed', '+100.0'),
    (5.0, 'fixed', '+5.0'),
])
def test_mantissa_always_keeps_a_fractional_digit(value, notation, expected):
    assert format_float(value, notation) == expected

@pytest.mark.parametrize(('value', 'expected'), [
    (1.5e-123, '+1.5e-123'),
    (1e300, '+1.0e+300'),
])
def test_exponent_width_is_a_minimum_never_a_truncation(value, expected):
    assert format_float(value, 'scientific', 2) == expected

@pytest.mark.parametrize('value', [math.inf, -math.inf, math.nan])
@pytest.mark.parametrize('notation', ['fixed', 'scientific'])
def test_non_finite_input_is_rejected(value, notation):
    with pytest.raises(ValueError):
        format_float(value, notation)
    with pytest.raises(ValueError):
        required_exponent_width(value)

def test_unknown_notation_is_rejected():
    with pytest.raises(ValueError):
        format_float(1.0, 'engineering')

@settings(max_examples=1000)
@given(value=FINITE, notation=NOTATIONS, width=WIDTHS)
def test_formatting_round_trips_bit_exactly(value, notation, width):
    text = format_float(value, notation, width)

    assert float(text) == value
    assert math.copysign(1.0, float(text)) == math.copysign(1.0, value)

@settings(max_examples=1000)
@given(value=FINITE, notation=NOTATIONS, width=WIDTHS)
def test_sign_is_mandatory(value, notation, width):
    assert format_float(value, notation, width)[0] in '+-'

@settings(max_examples=1000)
@given(value=FINITE, width=WIDTHS)
def test_scientific_exponent_has_the_requested_width(value, width):
    _, _, exponent = format_float(value, 'scientific', width).partition('e')

    assert exponent[0] in '+-'
    assert exponent[1:].isdigit()
    assert len(exponent[1:]) == max(width, required_exponent_width(value))

@settings(max_examples=1000)
@given(value=FINITE, width=WIDTHS)
def test_scientific_mantissa_has_exactly_one_leading_digit(value, width):
    mantissa, _, _ = format_float(value, 'scientific', width).partition('e')

    assert mantissa[0] in '+-'
    assert mantissa[2] == '.'
    assert mantissa[1].isdigit()
    assert len(mantissa) >= 4

@settings(max_examples=1000)
@given(value=FINITE, width=WIDTHS)
def test_fixed_notation_carries_no_exponent(value, width):
    text = format_float(value, 'fixed', width)

    assert 'e' not in text and 'E' not in text
    assert '.' in text

@settings(max_examples=1000)
@given(value=FINITE, notation=NOTATIONS, width=WIDTHS)
def test_formatting_is_idempotent(value, notation, width):
    once = format_float(value, notation, width)

    assert format_float(value, detect_notation(once), width) == once

@settings(max_examples=1000)
@given(value=FINITE, notation=NOTATIONS, width=WIDTHS)
def test_reparsing_the_output_formats_identically(value, notation, width):
    once = format_float(value, notation, width)

    assert format_float(float(once), detect_notation(once), width) == once

VALUE_LISTS = st.lists(FINITE, min_size=1, max_size=8)
PADDINGS = st.integers(min_value=0, max_value=20)

def fractional_digits(text: str) -> str:
    mantissa, _, _ = text.partition('e')
    _, _, fraction = mantissa.partition('.')

    return fraction

@pytest.mark.parametrize(('value', 'notation', 'padding', 'expected'), [
    (4.05e-03, 'scientific', 3, '+4.050e-03'),
    (5.0, 'scientific', 3, '+5.000e+00'),
    (0.5, 'fixed', 4, '+0.5000'),
    (0.1349768, 'fixed', 3, '+0.1349768'),
])
def test_mantissa_padding_worked_examples(value, notation, padding, expected):
    assert format_float(value, notation, 2, padding) == expected

@pytest.mark.parametrize(('values', 'notation', 'expected'), [
    ([4.154e-05, 4.05e-03], 'scientific', 3),
    ([5.0, 1.0], 'scientific', 1),
    ([0.011, 0.0029], 'fixed', 4),
    ([0.1349768], 'fixed', 7),
    ([1.5, 1.25, 1.125], 'fixed', 3),
    ([1.3e-05], 'scientific', 1),
    ([1.3e-05], 'fixed', 6),
    ([0.0], 'fixed', 1),
    ([0.0], 'scientific', 1),
    ([-0.0], 'fixed', 1),
    ([], 'fixed', 1),
    ([], 'scientific', 1),
])
def test_mantissa_width_is_the_max_over_shortest_forms(values, notation, expected):
    assert mantissa_width(values, notation) == expected

def test_mantissa_width_default_is_the_unpadded_behaviour():
    assert format_float(4.05e-03, 'scientific', 2, 1) == format_float(4.05e-03, 'scientific')

@settings(max_examples=1000)
@given(value=FINITE, notation=NOTATIONS, width=WIDTHS, padding=PADDINGS)
def test_padding_never_changes_the_parsed_value(value, notation, width, padding):
    text = format_float(value, notation, width, padding)
    natural = len(fractional_digits(format_float(value, notation, width)))

    assert float(text) == value
    assert math.copysign(1.0, float(text)) == math.copysign(1.0, value)
    assert len(fractional_digits(text)) == max(padding, natural)

@settings(max_examples=1000)
@given(values=VALUE_LISTS, notation=NOTATIONS, width=WIDTHS)
def test_field_width_makes_fractional_digit_counts_uniform(values, notation, width):
    shared = mantissa_width(values, notation)
    counts = {len(fractional_digits(format_float(value, notation, width, shared)))
              for value in values}

    assert counts == {shared}

@settings(max_examples=1000)
@given(values=VALUE_LISTS, notation=NOTATIONS, width=WIDTHS)
def test_padding_is_idempotent_at_field_scope(values, notation, width):
    shared = mantissa_width(values, notation)
    once = [format_float(value, notation, width, shared) for value in values]
    reparsed = [float(text) for text in once]
    again = mantissa_width(reparsed, notation)

    assert again == shared
    assert [format_float(value, notation, width, again) for value in reparsed] == once

def test_module_imports_nothing_it_must_not():
    tree = ast.parse(pathlib.Path(floats.__file__).read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or '').split('.')[0])

    assert imported == {'__future__', 'math', 'decimal', 'model'}
