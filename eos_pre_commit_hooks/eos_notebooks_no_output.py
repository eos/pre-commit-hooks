from __future__ import annotations

import argparse
import json
from typing import Sequence

def eos_notebooks_no_output(filenames: Sequence[str], *, fix: bool = False) -> int:
    retv = 0

    for filename in filenames:
        with open(filename, encoding='utf-8') as f:
            try:
                notebook = json.load(f)
            except json.JSONDecodeError as e:
                print(f'{filename}: not valid JSON: {e}')
                retv = 1
                continue

        cells = notebook.get('cells')
        if not isinstance(cells, list):
            print(f'{filename}: no cell list; not a notebook in nbformat 4')
            retv = 1
            continue

        stale = []
        for number, cell in enumerate(cells, start=1):
            if not isinstance(cell, dict) or cell.get('cell_type') != 'code':
                continue

            if cell.get('outputs') or cell.get('execution_count') is not None:
                stale.append((number, cell))

        if not stale:
            continue

        retv = 1
        for number, cell in stale:
            count = cell.get('execution_count')
            prompt = '[ ]' if count is None else f'[{count}]'
            print(f'{filename} cell {number}: {prompt} carries {len(cell.get("outputs", []))} '
                  'stored output(s); notebooks are committed unexecuted')

        if fix:
            for _, cell in stale:
                cell['execution_count'] = None
                cell['outputs'] = []

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(notebook, f, indent=1, sort_keys=True, ensure_ascii=False)
                f.write('\n')

            print(f'{filename}: cleared')

    return retv


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'filenames', nargs='*',
        help='Filenames pre-commit believes are changed.',
    )
    parser.add_argument(
        '--fix', action='store_true',
        help='Clear the stored outputs instead of only reporting them.',
    )
    args = parser.parse_args(argv)

    return eos_notebooks_no_output(args.filenames, fix=args.fix)


if __name__ == '__main__':
    raise SystemExit(main())
