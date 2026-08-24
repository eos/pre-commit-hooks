from __future__ import annotations

import math
from decimal import Decimal

from .model import Notation

def _decompose(value: float) -> tuple[bool, str, int]:
    """Sign, shortest round-tripping digits, and the decimal exponent of the first."""
    if not math.isfinite(value):
        raise ValueError(f'expected a finite value, got {value!r}')

    negative = math.copysign(1.0, value) < 0.0
    # repr() gives the shortest digit string that round-trips; normalize() drops
    # its trailing zeros without changing the value it denotes.
    _, digit_tuple, exponent = Decimal(repr(abs(value))).normalize().as_tuple()
    digits = ''.join(str(digit) for digit in digit_tuple)

    return negative, digits, int(exponent) + len(digits) - 1

def _natural_fraction(value: float, notation: Notation) -> str:
    """The fractional digits of `value`'s shortest round-tripping form in `notation`."""
    _, digits, exponent = _decompose(value)

    if notation == 'scientific':
        return digits[1:] or '0'

    if notation == 'fixed':
        if exponent >= 0:
            return digits[exponent + 1:] or '0'
        return '0' * (-exponent - 1) + digits

    raise ValueError(f"expected notation 'fixed' or 'scientific', got {notation!r}")

def format_float(
        value: float,
        notation: Notation,
        exponent_width: int = 2,
        mantissa_width: int = 1,
) -> str:
    """Canonical round-trip string for `value`. CONSTRAINTS-FORMAT.md §3.

    The result is a pure function of the four arguments and always carries an
    explicit sign. Both widths are minima, never truncations: an exponent needing
    more digits keeps them all rather than round-tripping to a different double, and
    a mantissa needing more fractional digits likewise keeps all of them. Padding
    the fraction with trailing zeros cannot change the parsed value.
    """
    negative, digits, exponent = _decompose(value)
    sign = '-' if negative else '+'
    fraction = _natural_fraction(value, notation).ljust(mantissa_width, '0')

    if notation == 'scientific':
        width = max(exponent_width, len(str(abs(exponent))))
        return f'{sign}{digits[0]}.{fraction}e{"-" if exponent < 0 else "+"}{abs(exponent):0{width}d}'

    integer = digits[:exponent + 1].ljust(exponent + 1, '0') if exponent >= 0 else '0'

    return f'{sign}{integer}.{fraction}'

def detect_notation(raw_text: str) -> Notation:
    """Was `raw_text` (the original scalar's source text) fixed-point or scientific?"""
    return 'scientific' if 'e' in raw_text or 'E' in raw_text else 'fixed'

def required_exponent_width(value: float) -> int:
    """2, unless |decimal exponent| >= 100, in which case 3. §3."""
    _, _, exponent = _decompose(value)

    return 3 if abs(exponent) >= 100 else 2

def entry_exponent_width(values: list[float]) -> int:
    """Scan every float in one constraint entry; 3 if any needs it, else 2."""
    return 3 if any(required_exponent_width(value) == 3 for value in values) else 2

def mantissa_width(values: list[float], notation: Notation) -> int:
    """Fractional digits shared by every element of one sequence field. §3.

    The max over the values' shortest round-tripping forms, floored at 1 — the
    mandatory fractional digit means no shortest form ever contributes 0.
    """
    return max((len(_natural_fraction(value, notation)) for value in values), default=1)
