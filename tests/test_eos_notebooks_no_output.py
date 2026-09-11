from __future__ import annotations

import json

import pytest

from eos_pre_commit_hooks.eos_notebooks_no_output import main

def code(source, execution_count=None, outputs=()):
    return {
        'cell_type': 'code',
        'execution_count': execution_count,
        'metadata': {},
        'outputs': list(outputs),
        'source': source,
    }

def markdown(source):
    return {'cell_type': 'markdown', 'metadata': {}, 'source': source}

def notebook(*cells):
    return {'cells': list(cells), 'metadata': {}, 'nbformat': 4, 'nbformat_minor': 2}

DISPLAY_DATA = {
    'data': {'text/plain': ['<Figure size 640x600 with 2 Axes>']},
    'metadata': {},
    'output_type': 'display_data',
}

@pytest.fixture
def write(tmp_path):
    def write(content, name='example.ipynb'):
        path = tmp_path / name
        path.write_text(json.dumps(content, indent=1, sort_keys=True) + '\n')
        return str(path)
    return write

def test_cleared_notebook_passes(write):
    path = write(notebook(markdown('# Title'), code('import eos'), code('eos.Parameters()')))

    assert main([path]) == 0

def test_notebook_without_code_cells_passes(write):
    assert main([write(notebook(markdown('# Title')))]) == 0

def test_stored_output_fails(write, capsys):
    path = write(notebook(code('import eos'), code('figure.draw()', 13, [DISPLAY_DATA])))

    assert main([path]) == 1
    assert 'cell 2: [13] carries 1 stored output(s)' in capsys.readouterr().out

def test_prompt_number_without_output_fails(write, capsys):
    """nbsphinx's 'auto' rule trips on a bare prompt number too."""
    path = write(notebook(code('import eos', execution_count=1)))

    assert main([path]) == 1
    assert 'cell 1: [1] carries 0 stored output(s)' in capsys.readouterr().out

def test_markdown_cells_are_ignored(write):
    assert main([write(notebook(markdown('# Title'), code('import eos')))]) == 0

def test_every_offending_cell_is_reported(write, capsys):
    path = write(notebook(code('a', 1, [DISPLAY_DATA]), code('b'), code('c', 3, [DISPLAY_DATA])))

    assert main([path]) == 1

    out = capsys.readouterr().out
    assert 'cell 1: [1]' in out
    assert 'cell 3: [3]' in out
    assert 'cell 2' not in out

def test_fix_clears_outputs_and_leaves_source_alone(write):
    path = write(notebook(markdown('# Title'), code('figure.draw()', 13, [DISPLAY_DATA])))

    assert main([path, '--fix']) == 1
    assert main([path]) == 0

    cells = json.loads(open(path, encoding='utf-8').read())['cells']
    assert cells[0] == markdown('# Title')
    assert cells[1]['source'] == 'figure.draw()'
    assert cells[1]['execution_count'] is None
    assert cells[1]['outputs'] == []

def test_fix_leaves_a_clean_notebook_byte_identical(write):
    path = write(notebook(markdown('# Title'), code('import eos')))
    before = open(path, encoding='utf-8').read()

    assert main([path, '--fix']) == 0
    assert open(path, encoding='utf-8').read() == before

def test_invalid_json_fails(tmp_path, capsys):
    path = tmp_path / 'broken.ipynb'
    path.write_text('{"cells": [')

    assert main([str(path)]) == 1
    assert 'not valid JSON' in capsys.readouterr().out

def test_json_without_cells_fails(write, capsys):
    assert main([write({'metadata': {}})]) == 1
    assert 'not a notebook in nbformat 4' in capsys.readouterr().out

def test_several_files_are_all_reported(write, capsys):
    clean = write(notebook(code('import eos')), name='clean.ipynb')
    dirty = write(notebook(code('a', 1, [DISPLAY_DATA])), name='dirty.ipynb')

    assert main([clean, dirty]) == 1

    out = capsys.readouterr().out
    assert 'dirty.ipynb' in out
    assert 'clean.ipynb' not in out
