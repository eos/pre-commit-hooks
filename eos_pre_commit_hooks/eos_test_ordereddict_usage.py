from __future__ import annotations

import argparse
import math
import os
import re
import subprocess
from typing import Sequence

def eos_test_ordereddict_usage(
        filenames: Sequence[str],
        *,
        enforce_all: bool = False,
) -> int:
    # Find all .py files that are also in the list of files pre-commit tells
    # us about
    retv = 0
    filenames_filtered = set(filenames)

    checks = [ re.compile(r'^import collections.OrderedDict'),
               re.compile(r'^from collections import .*OrderedDict'),
    ]
    msg = 'Since Python 3.7, the regular dict class is guaranteed to preserve insertion order so OrderedDict (likely) is not needed'

    for filename in filenames_filtered:
        if not filename.endswith('.py'):
            pass

        with open(filename) as f:
            for lineno, line in enumerate(f):
                for regexp in checks:
                    if regexp.search(line):
                        print(f'{filename} line {lineno+1}: {msg}')
                        retv = 1

    return retv


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'filenames', nargs='*',
        help='Filenames pre-commit believes are changed.',
    )
    parser.add_argument(
        '--enforce-all', action='store_true',
        help='Enforce all files are checked, not just staged files.',
    )
    args = parser.parse_args(argv)

    return eos_test_ordereddict_usage(
        args.filenames,
        enforce_all=args.enforce_all,
    )


if __name__ == '__main__':
    raise SystemExit(main())
