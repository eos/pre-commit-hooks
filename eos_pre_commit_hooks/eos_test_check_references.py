from __future__ import annotations

import argparse
import math
import os
import re
import subprocess
from typing import Sequence

def eos_test_check_references(
        filenames: Sequence[str],
        *,
        enforce_all: bool = False,
) -> int:
    retv = 0
    filenames_filtered = set(filenames)

    # each check is a tuple of regular expression and error message, designed to catch typical mistakes
    checks = [
        (
            re.compile(r'\[[a-zA-Z0-9][a-zA-Z0-9+-]*[0-9]{4}\]'),
            'needs a colon and a final letter after year to be a correctly formatted reference'
        ),
        (
            re.compile(r'\[[a-zA-Z0-9][a-zA-Z0-9+-]*[0-9]{4}[A-Z]\]'),
            'needs a colon to be a correctly formatted reference'
        ),
        (
            re.compile(r'\[[a-zA-Z0-9][a-zA-Z0-9+-]*:[0-9]{4}\]'),
            'needs a final letter to be a correctly formatted reference'
        ),
    ]

    # regexp for correctly formed reference
    # See eos/utils/reference-name.cc
    good_reference_regexp = re.compile(r'\[[a-zA-Z0-9][a-zA-Z0-9+-]*:[0-9]{4}[A-Z]\]')

    # Read in all references from references.yaml
    known_refs = set()
    with open("eos/references.yaml") as f:
        for line in f:
            known_refs.update(good_reference_regexp.findall(line))


    for filename in filenames_filtered:
        with open(filename) as f:
            for lineno, line in enumerate(f):
                for regexp, msg in checks:
                    if m := regexp.search(line):
                        print(f'{filename} line {lineno+1}: {m.group()} {msg}')
                        retv = 1
                for found_ref in good_reference_regexp.findall(line):
                    if found_ref not in known_refs:
                        print(f'{filename} line {lineno+1}: Reference {found_ref} not found in references.yaml')
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

    return eos_test_check_references(
        args.filenames,
        enforce_all=args.enforce_all,
    )


if __name__ == '__main__':
    raise SystemExit(main())
