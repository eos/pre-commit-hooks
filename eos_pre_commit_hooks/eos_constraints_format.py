from __future__ import annotations

import argparse
from typing import Sequence

from eos_pre_commit_hooks.eos_yaml import layout, pipeline

def eos_constraints_format(filenames: Sequence[str], *, check: bool = False) -> int:
    retv = 0

    for filename in filenames:
        with open(filename, encoding='utf-8') as f:
            original = f.read()

        try:
            formatted = pipeline.format_text(original, filename=filename)
        except layout.FoldMarkerError as e:
            print(e)
            retv = 1
            continue

        if formatted == original:
            continue

        retv = 1
        print(f'{filename}: reformatted')

        if not check:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(formatted)

    return retv

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'filenames', nargs='*',
        help='Filenames pre-commit believes are changed.',
    )
    parser.add_argument(
        '--check', action='store_true',
        help="Report files that would change, but don't rewrite them.",
    )
    args = parser.parse_args(argv)

    return eos_constraints_format(args.filenames, check=args.check)


if __name__ == '__main__':
    raise SystemExit(main())
