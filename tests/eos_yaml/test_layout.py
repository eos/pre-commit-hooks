from __future__ import annotations

import ast
import pathlib

import pytest

from eos_pre_commit_hooks.eos_yaml import layout
from eos_pre_commit_hooks.eos_yaml.layout import (
    FoldMarkerError,
    check_and_repair_fold_markers,
    normalize_blank_lines,
)

# --- Part A: blank-line normalization --------------------------------------------

ENTRY_A = (
    'A^0->B^-e^-nu::BR@Exp:2015A:\n'
    '  type: Gaussian\n'
    '  mean: +1.0e+00\n'
)

ENTRY_B = (
    'A^0->B^-e^-nu::BR@Exp:2015B:\n'
    '  type: Gaussian\n'
    '  mean: +2.0e+00\n'
)

HEADER = (
    '#########\n'
    '# Belle #\n'
    '#########\n'
    '#\n'
    '# 2015\n'
    '#\n'
)

PREAMBLE = '# vim: set fdm=marker :\n\n'

DATED_HEADER = '#\n# 2019\n#\n# {{{\n'

BLANK_LINE_CASES = {
    'stacked with no blank line':
        (ENTRY_A + ENTRY_B, ENTRY_A + '\n' + ENTRY_B),
    'already separated by one blank line':
        (ENTRY_A + '\n' + ENTRY_B, ENTRY_A + '\n' + ENTRY_B),
    'separated by two blank lines':
        (ENTRY_A + '\n\n' + ENTRY_B, ENTRY_A + '\n' + ENTRY_B),
    'separated by five blank lines':
        (ENTRY_A + '\n' * 5 + ENTRY_B, ENTRY_A + '\n' + ENTRY_B),
    'second entry carrying a comment header':
        (ENTRY_A + HEADER + ENTRY_B, ENTRY_A + '\n' + HEADER + ENTRY_B),
    'comment header already separated by three blank lines':
        (ENTRY_A + '\n\n\n' + HEADER + ENTRY_B, ENTRY_A + '\n' + HEADER + ENTRY_B),
    'file preamble ahead of the first entry':
        (PREAMBLE + ENTRY_A + ENTRY_B, PREAMBLE + ENTRY_A + '\n' + ENTRY_B),
    'file preamble ahead of a comment header':
        (PREAMBLE + HEADER + ENTRY_A + ENTRY_B, PREAMBLE + HEADER + ENTRY_A + '\n' + ENTRY_B),
    'a single entry':
        (PREAMBLE + ENTRY_A, PREAMBLE + ENTRY_A),
    'no entry at all':
        (PREAMBLE, PREAMBLE),
    'a fold closing above the next entry':
        (ENTRY_A + '# }}}\n' + DATED_HEADER + ENTRY_B,
         ENTRY_A + '# }}}\n\n' + DATED_HEADER + ENTRY_B),
    'trailing blank lines after the last entry':
        (ENTRY_A + ENTRY_B + '\n\n', ENTRY_A + '\n' + ENTRY_B + '\n\n'),
    'no trailing newline on the last line':
        (ENTRY_A + ENTRY_B.rstrip('\n'), ENTRY_A + '\n' + ENTRY_B.rstrip('\n')),
}

@pytest.mark.parametrize('name', list(BLANK_LINE_CASES))
def test_normalize_blank_lines(name):
    text, expected = BLANK_LINE_CASES[name]

    assert normalize_blank_lines(text) == expected

@pytest.mark.parametrize('name', list(BLANK_LINE_CASES))
def test_normalize_blank_lines_is_idempotent(name):
    once = normalize_blank_lines(BLANK_LINE_CASES[name][0])

    assert normalize_blank_lines(once) == once

@pytest.mark.parametrize('name', list(BLANK_LINE_CASES))
def test_the_file_preamble_is_left_untouched(name):
    text = BLANK_LINE_CASES[name][0]

    if text.startswith(PREAMBLE):
        assert normalize_blank_lines(text).startswith(PREAMBLE)

def test_no_blank_line_is_inserted_inside_a_comment_header():
    text = normalize_blank_lines(ENTRY_A + HEADER + ENTRY_B)

    assert HEADER + ENTRY_B in text

def test_entry_content_is_preserved_line_for_line():
    text = ENTRY_A + '\n\n\n' + HEADER + ENTRY_B
    kept = [line for line in normalize_blank_lines(text).splitlines() if line.strip()]

    assert kept == [line for line in text.splitlines() if line.strip()]

# --- Part B: fold-marker balance and repair --------------------------------------

def block(*lines: str) -> str:
    return ''.join(line + '\n' for line in lines)

BALANCED = {
    'a single fold':
        block('# {{{', 'a: 1', '# }}}'),
    'two sequential folds':
        block('# {{{', 'a: 1', '# }}}', '', '# {{{', 'b: 2', '# }}}'),
    'a genuinely nested, deeper-indented fold':
        block('# {{{', 'a: 1', '  # {{{', '  b: 2', '  # }}}', '# }}}'),
    'no fold marker at all':
        block('a: 1', 'b: 2'),
    'an empty file':
        '',
}

REPAIRED = {
    'a missing close before the next open': (
        block('# {{{', 'a: 1', '# {{{', 'b: 2', '# }}}'),
        block('# {{{', 'a: 1', '# }}}', '# {{{', 'b: 2', '# }}}'),
    ),
    'a missing close at end of file': (
        block('# {{{', 'a: 1'),
        block('# {{{', 'a: 1', '# }}}'),
    ),
    'a missing close at end of a file without a trailing newline': (
        block('# {{{') + 'a: 1',
        block('# {{{', 'a: 1', '# }}}'),
    ),
    'a missing open at the top of the file': (
        block('a: 1', '# }}}'),
        block('# {{{', 'a: 1', '# }}}'),
    ),
    'a missing open after the previous fold closed': (
        block('# {{{', 'a: 1', '# }}}', 'b: 2', '# }}}'),
        block('# {{{', 'a: 1', '# }}}', '# {{{', 'b: 2', '# }}}'),
    ),
}

AMBIGUOUS = {
    'two unmatched closes in a row':
        (block('# }}}', '# }}}'), 2),
    'two unmatched closes with content in between':
        (block('a: 1', '# }}}', 'b: 2', '# }}}'), 4),
    'two folds still open at end of file':
        (block('# {{{', '  # {{{', 'a: 1'), 1),
    'three opens where only one can be closed unambiguously':
        (block('# {{{', '  # {{{', '# {{{', 'a: 1'), 3),
}

@pytest.mark.parametrize('name', list(BALANCED))
def test_balanced_text_is_returned_unchanged(name):
    text = BALANCED[name]

    assert check_and_repair_fold_markers(text, 'balanced.yaml') == text

@pytest.mark.parametrize('name', list(REPAIRED))
def test_an_unambiguous_imbalance_is_repaired(name):
    text, expected = REPAIRED[name]

    assert check_and_repair_fold_markers(text, 'broken.yaml') == expected

@pytest.mark.parametrize('name', list(REPAIRED))
def test_a_repair_is_itself_balanced(name):
    once = check_and_repair_fold_markers(REPAIRED[name][0], 'broken.yaml')

    assert check_and_repair_fold_markers(once, 'broken.yaml') == once

@pytest.mark.parametrize('name', list(AMBIGUOUS))
def test_an_ambiguous_imbalance_raises(name):
    text, line = AMBIGUOUS[name]

    with pytest.raises(FoldMarkerError) as raised:
        check_and_repair_fold_markers(text, 'ambiguous.yaml')

    assert 'ambiguous.yaml' in str(raised.value)
    assert f':{line}:' in str(raised.value)

@pytest.mark.parametrize('name', list(AMBIGUOUS))
def test_an_ambiguous_imbalance_leaves_the_text_untouched(name):
    text = AMBIGUOUS[name][0]
    original = str(text)

    with pytest.raises(FoldMarkerError):
        check_and_repair_fold_markers(text, 'ambiguous.yaml')

    assert text == original

def test_the_default_filename_appears_in_the_message():
    with pytest.raises(FoldMarkerError) as raised:
        check_and_repair_fold_markers(block('# }}}', '# }}}'))

    assert '<unknown>' in str(raised.value)

def test_a_modeline_is_not_mistaken_for_a_fold_marker():
    text = block('# vim: set fdm=marker :', 'a: 1')

    assert check_and_repair_fold_markers(text, 'modeline.yaml') == text

# --- Part B: a real, already balanced corpus file ---------------------------------

# eos/constraints/experimental/B-to-K-ll.yaml, lines 1-58: one fold opening at
# line 9 and closing at line 58.
CORPUS_EXCERPT = (
    '# vim: set fdm=marker :\n'
    '\n'
    '#########\n'
    '# BaBar #\n'
    '#########\n'
    '#\n'
    '# 2012\n'
    '#\n'
    '# {{{\n'
    'B^+->K^+mu^+mu^-::BR[1.00,6.00]@BaBar:2012A:\n'
    '    type: Gaussian\n'
    '    observable: B->Kll::BR\n'
    '    kinematics: {q2_min: 1, q2_max: 6}\n'
    '    options: {l: mu, q: u, tag: BFS2004}\n'
    '    mean: 1.36e-07\n'
    '    sigma-stat: {hi: 2.7e-08, lo: -2.4e-08}\n'
    '    sigma-sys: {hi: 3e-09, lo: -3e-09}\n'
    'B^+->K^+mu^+mu^-::BR[2.00,4.30]@BaBar:2012A:\n'
    '    type: Gaussian\n'
    '    observable: B->Kll::BR\n'
    '    kinematics: {q2_min: 2, q2_max: 4.3}\n'
    '    options: {l: mu, q: u, tag: BFS2004}\n'
    '    mean: 0.49e-07\n'
    '    sigma-stat: {hi: 1.5e-08, lo: -1.3e-08}\n'
    '    sigma-sys: {hi: 1e-09, lo: -1e-09}\n'
    'B^+->K^+mu^+mu^-::BR[4.30,8.12]@BaBar:2012A:\n'
    '    type: Gaussian\n'
    '    observable: B->Kll::BR\n'
    '    kinematics: {q2_min: 4.3, q2_max: 8.12}\n'
    '    options: {l: mu, q: u, tag: BFS2004}\n'
    '    mean: 0.94e-07\n'
    '    sigma-stat: {hi: 2.0e-08, lo: -1.9e-08}\n'
    '    sigma-sys: {hi: 2e-09, lo: -2e-09}\n'
    'B^+->K^+mu^+mu^-::BR[10.11,12.89]@BaBar:2012A:\n'
    '    type: Gaussian\n'
    '    observable: B->Kll::BR\n'
    '    kinematics: {q2_min: 10.11, q2_max: 12.89}\n'
    '    options: {l: mu, q: u, tag: BFS2004}\n'
    '    mean: 0.90e-07\n'
    '    sigma-stat: {hi: 2.0e-08, lo: -1.9e-08}\n'
    '    sigma-sys: {hi: 4e-09, lo: -4e-09}\n'
    'B^+->K^+mu^+mu^-::BR[14.21,16.00]@BaBar:2012A:\n'
    '    type: Gaussian\n'
    '    observable: B->Kll::BR\n'
    '    kinematics: {q2_min: 14.21, q2_max: 16}\n'
    '    options: {l: mu, q: u, tag: GP2004}\n'
    '    mean: 4.9e-08\n'
    '    sigma-stat: {hi: 1.5e-08, lo: -1.4e-08}\n'
    '    sigma-sys: {hi: 2e-09, lo: -2e-09}\n'
    'B^+->K^+mu^+mu^-::BR[16.00,22.86]@BaBar:2012A:\n'
    '    type: Gaussian\n'
    '    observable: B->Kll::BR\n'
    '    kinematics: {q2_min: 16, q2_max: 22.86}\n'
    '    options: {l: mu, q: u, tag: GP2004}\n'
    '    mean: 6.7e-08\n'
    '    sigma-stat: {hi: 2.3e-08, lo: -2.1e-08}\n'
    '    sigma-sys: {hi: 5e-09, lo: -5e-09}\n'
    '# }}}\n'
)

def test_a_real_corpus_file_is_returned_byte_for_byte():
    text = CORPUS_EXCERPT

    assert check_and_repair_fold_markers(text, 'B-to-K-ll.yaml') == text

def test_the_corpus_excerpt_is_the_expected_shape():
    lines = CORPUS_EXCERPT.splitlines()

    assert lines[8] == '# {{{'
    assert lines[57] == '# }}}'

# --- Module hygiene ---------------------------------------------------------------

def test_module_imports_nothing_it_must_not():
    tree = ast.parse(pathlib.Path(layout.__file__).read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or '').split('.')[0])

    assert imported == {'__future__'}
