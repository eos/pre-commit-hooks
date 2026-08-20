from __future__ import annotations

import pathlib
import shutil

import pytest
from ruamel.yaml import YAML

from eos_pre_commit_hooks.eos_constraints_format import main
from eos_pre_commit_hooks.eos_yaml import layout, pipeline

FIXTURES = pathlib.Path(__file__).parent / 'fixtures' / 'e2e'
NAMES = ['B-to-D-l-nu', 'B-to-K-ll', 'dispersive-bounds', 'wet-constraints']

@pytest.fixture(params=NAMES)
def fixture(request):
    """One real constraints file's text, copied verbatim from `eos/constraints/**`."""
    return (FIXTURES / f'{request.param}.input.yaml').read_text()

@pytest.fixture
def formatted(fixture):
    return pipeline.format_text(fixture)

def load(text):
    return YAML(typ='safe').load(text)

def leaves(node, path=''):
    """Every leaf scalar below `node`, keyed by a path built from sorted keys."""
    if isinstance(node, dict):
        for key in sorted(node, key=str):
            yield from leaves(node[key], f'{path}/{key}')
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from leaves(item, f'{path}[{index}]')
    else:
        yield path, node

def comments(text):
    """Every comment in the file, in order. No `#` appears inside a scalar here."""
    return [line[line.index('#'):].strip() for line in text.split('\n') if '#' in line]

def entry_lines(text):
    """The index of every top-level constraint key line."""
    return [index for index, line in enumerate(text.split('\n'))
            if line.strip() and not line[0].isspace() and not line.startswith('#')]

# --- Part F: the five per-fixture assertions --------------------------------------

def test_output_is_valid_yaml(formatted):
    assert load(formatted) is not None

def test_every_leaf_scalar_survives(fixture, formatted):
    before, after = list(leaves(load(fixture))), list(leaves(load(formatted)))

    assert [path for path, _ in before] == [path for path, _ in after]

    for (path, original), (_, result) in zip(before, after):
        assert type(original) is type(result), path
        assert original == result, path

def test_floats_are_bit_identical(fixture, formatted):
    before = {path: value for path, value in leaves(load(fixture)) if isinstance(value, float)}
    after = dict(leaves(load(formatted)))

    assert before, 'the fixture is expected to hold floats'

    for path, value in before.items():
        assert isinstance(after[path], float), path
        assert after[path] == value, path

def test_formatting_is_idempotent(formatted):
    assert pipeline.format_text(formatted) == formatted

def test_blank_lines_separate_entries(formatted):
    lines = formatted.split('\n')

    assert '\n\n\n' not in formatted

    indices = entry_lines(formatted)
    for start, following in zip(indices, indices[1:]):
        assert any(not lines[index].strip() for index in range(start, following)), lines[start]

def test_fold_markers_stay_balanced(formatted):
    assert layout.check_and_repair_fold_markers(formatted) == formatted

def test_every_comment_survives(fixture, formatted):
    """Section headers and fold markers between entries included: ruamel parks
    those on the innermost node the preceding entry ends in."""
    assert comments(formatted) == comments(fixture)

# --- comments in the places ruamel puts them somewhere unexpected ------------------

LEADING = '''\
Some::Constraint@Author:2020A:
    # This result assumes tp = 30.261001
    type: Gaussian
    observable: 'Some::Observable'
    mean: 1.0
'''

ELEMENTS = '''\
Some::Constraint@Author:2020A:
    type: MultivariateGaussian(Covariance)
    observables: [
        'A', 'B',  # no C
        'D', 'E'
    ]
    means: [1.0, 2.0, 3.0, 4.0]
    covariance: [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
'''

INTEGERS = '''\
Some::Constraint@Author:2020A:
    type: MultivariateGaussian
    observables: ['A', 'B']
    means: [0.48, 0.85]
    sigma-stat-hi: [0.19, 0.18]
    sigma-stat-lo: [0.19, 0.18]
    sigma-sys: [0, 0]
    correlations:
      - [1, 0]
      - [0, 1]
    dof: 2
'''

def test_integers_in_a_float_field_become_floats():
    lines = pipeline.format_text(INTEGERS).split('\n')

    # `correlations` holds only integers, so it keeps them; so does a lone scalar
    assert any(line.startswith('  correlations: [ [ 1,') for line in lines)
    assert '  dof: 2' in lines

def test_integers_take_the_fields_own_float_format():
    text = pipeline.format_text(INTEGERS.replace('- [1, 0]', '- [1, 0.5]'))

    assert '+1.0' in text and '+0.0' in text and '+0.5' in text

def test_an_entrys_first_line_comment_survives():
    assert '# This result assumes tp = 30.261001' in pipeline.format_text(LEADING)

def test_element_comments_are_hoisted_above_the_key():
    lines = pipeline.format_text(ELEMENTS).split('\n')

    assert lines[lines.index('  # no C') + 1].startswith('  observables:')

# --- The reference file's own layout ----------------------------------------------

def test_reference_entry_matches_the_worked_example():
    """Spec §4.2's entry: one shared grid, `kinematics` out of it, no wrap at 240."""
    text = pipeline.format_text((FIXTURES / 'B-to-D-l-nu.input.yaml').read_text())
    lines = text.split('\n')
    start = lines.index('B^0->D^+e^-nu::BRs@Belle:2015A:')
    entry = lines[start:start + 40]

    means = next(line for line in entry if line.startswith('  means:'))
    covariance = next(line for line in entry if line.startswith('  covariance:'))
    observables = next(line for line in entry if line.startswith('  observables:'))

    # every field's first cell starts in one column; `covariance`'s *inner* bracket
    # is the one that lands there, its outer bracket two columns to the left
    assert means.index('[ ') + 2 == covariance.index('[ [ ') + 4 == observables.index('[ ') + 2

    # all ten cells fit one line at 240 columns, so every field is a single line and
    # each covariance row is one line ending in the comma that separates the rows
    assert means.count(',') == 9 and means.rstrip().endswith(']')
    assert observables.count(',') == 9 and observables.rstrip().endswith(']')
    assert covariance.count(',') == 10 and covariance.rstrip().endswith('],')

    assert '  kinematics:' in entry
    assert entry[entry.index('  kinematics:') + 1].startswith('    - {q2_min:')
    assert '+4.050e-03' in text and '+7.320e-10' in text
    assert max(len(line) for line in entry) <= 240

# --- Part D: the command line -----------------------------------------------------

def test_cli_rewrites_a_file_once(tmp_path):
    target = tmp_path / 'B-to-D-l-nu.yaml'
    shutil.copy(FIXTURES / 'B-to-D-l-nu.input.yaml', target)

    assert main([str(target)]) == 1
    assert target.read_text() != (FIXTURES / 'B-to-D-l-nu.input.yaml').read_text()
    assert main([str(target), '--check']) == 0

def test_cli_check_leaves_the_file_alone(tmp_path):
    target = tmp_path / 'B-to-D-l-nu.yaml'
    shutil.copy(FIXTURES / 'B-to-D-l-nu.input.yaml', target)
    original = target.read_text()

    assert main([str(target), '--check']) == 1
    assert target.read_text() == original

def test_cli_reports_unbalanced_fold_markers(tmp_path, capsys):
    target = tmp_path / 'broken.yaml'
    target.write_text('# }}}\n# }}}\nfoo:\n  bar: 1\n')
    original = target.read_text()

    assert main([str(target)]) == 1
    assert target.read_text() == original
    assert 'fold markers' in capsys.readouterr().out
