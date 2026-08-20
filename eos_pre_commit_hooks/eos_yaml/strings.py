from __future__ import annotations

from ruamel.yaml.scalarstring import DoubleQuotedScalarString, SingleQuotedScalarString

def quote(value: str):
    """Single-quote `value`, unless it contains an apostrophe (then double-quote).

    Returns a ruamel.yaml ScalarString subclass instance (SingleQuotedScalarString
    or DoubleQuotedScalarString) — the caller dumps it with ruamel, which handles
    any necessary escaping itself. Spec §3.2/§7.4. See STEP-3.md.
    """
    if "'" in value:
        return DoubleQuotedScalarString(value)

    return SingleQuotedScalarString(value)
