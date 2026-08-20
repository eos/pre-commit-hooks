from __future__ import annotations

import ast
import io
import pathlib

import pytest
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.scalarstring import DoubleQuotedScalarString, SingleQuotedScalarString

from eos_pre_commit_hooks.eos_yaml import strings
from eos_pre_commit_hooks.eos_yaml.strings import quote

SINGLE_QUOTED = [
    'B->Dlnu::BR',
    'common systematic',
    'B->D::f+(q2)@BSZ2015',
    '',
]

DOUBLE_QUOTED = [
    "it's",
    "'",
    "the Wilson coefficients' scale",
    "'quoted'",
]

@pytest.mark.parametrize('value', SINGLE_QUOTED)
def test_values_without_an_apostrophe_are_single_quoted(value):
    assert type(quote(value)) is SingleQuotedScalarString

@pytest.mark.parametrize('value', DOUBLE_QUOTED)
def test_values_with_an_apostrophe_are_double_quoted(value):
    assert type(quote(value)) is DoubleQuotedScalarString

@pytest.mark.parametrize('value', SINGLE_QUOTED + DOUBLE_QUOTED)
def test_the_string_value_is_preserved(value):
    assert str(quote(value)) == value

@pytest.mark.parametrize('value', SINGLE_QUOTED + DOUBLE_QUOTED)
def test_round_trip_through_ruamel(value):
    yaml = YAML(typ='rt')
    stream = io.StringIO()
    yaml.dump(CommentedMap([('observable', quote(value))]), stream)
    text = stream.getvalue()

    assert yaml.load(text)['observable'] == value

@pytest.mark.parametrize(('value', 'expected'), [
    ('B->Dlnu::BR', "observable: 'B->Dlnu::BR'\n"),
    ("it's", 'observable: "it\'s"\n'),
])
def test_dumped_text_uses_the_expected_quote_character(value, expected):
    stream = io.StringIO()
    YAML(typ='rt').dump(CommentedMap([('observable', quote(value))]), stream)

    assert stream.getvalue() == expected

def test_module_imports_nothing_it_must_not():
    tree = ast.parse(pathlib.Path(strings.__file__).read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or '').split('.')[0])

    assert imported == {'__future__', 'ruamel'}
