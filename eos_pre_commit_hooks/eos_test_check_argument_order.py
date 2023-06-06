from __future__ import annotations

import argparse
import math
import os
import re
import subprocess
from typing import Sequence

def eos_test_check_argument_order(
        filenames: Sequence[str],
        *,
        enforce_all: bool = False,
) -> int:
    # Find all _TEST.cc files that are also in the list of files pre-commit tells
    # us about
    retv = 0
    filenames_filtered = set(filenames)

    # each check is a tuple of regular expression and error message
    checks = [
        (
            re.compile(r'TEST_CHECK_NEARLY_EQUAL\(\s*[+-]?[0-9]+[.]?[0-9]*([e][+-]?[0-9]+)?\s*,'),
            'TEST_CHECK_NEARLY_EQUAL() expects arguments in the order: actual value, expected value, tolerance'
        ),
        (
            re.compile(r'TEST_CHECK_RELATIVE_ERROR\(\s*[+-]?[0-9]+[.]?[0-9]*([e][+-]?[0-9]+)?\s*,'),
            'TEST_CHECK_RELATIVE_ERROR() expects arguments in the order: actual value, expected value, tolerance'
        ),
        (
            re.compile(r'TEST_CHECK_RELATIVE_ERROR_C\(\s*[+-]?[0-9]+[.]?[0-9]*([e][+-]?[0-9]+)?\s*,'),
            'TEST_CHECK_RELATIVE_ERROR_C() expects arguments in the order: actual value, expected value, tolerance'
        ),
    ]

    for filename in filenames_filtered:
        if not filename.endswith('_TEST.cc'):
            pass

        with open(filename) as f:
            for lineno, line in enumerate(f):
                for regexp, msg in checks:
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

    return eos_test_check_argument_order(
        args.filenames,
        enforce_all=args.enforce_all,
    )


if __name__ == '__main__':
    raise SystemExit(main())
