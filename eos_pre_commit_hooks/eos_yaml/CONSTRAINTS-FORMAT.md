# The canonical form of `eos/constraints/**/*.yaml`

This describes what a formatted constraints file looks like, and nothing about how it
is produced. Two properties hold over every rule below and take precedence wherever a
rule would seem to conflict with them:

- **The data does not change.** Every scalar reads back as the same value and the same
  type, every float bit-for-bit, and the structure and key order are untouched.
- **The form is settled.** Formatting an already-formatted file changes nothing.

## 1. Terms

- **Entry** — one top-level mapping in the file, e.g. everything under
  `B^0->D^+e^-nu::BRs@Belle:2015A:`.
- **Cell** — one element of a sequence, rendered as a single-line token: a scalar, or a
  flow mapping such as `{q2_min: +10.44, q2_max: +11.63}`.
- **Arity `N`** — the number of `observables` in the entry.
- **Vector field** — a key whose value is a sequence of `N` cells (`observables`,
  `means`, `kinematics`, `options`).
- **Matrix field** — a key whose value is `N` rows of `N` cells (`covariance`,
  `correlations`).
- **Alignment group** — the vector and matrix fields of one entry that are laid out as
  a single table (§6). An entry with `N == 1` has no group; there is nothing to align.

## 2. Layout

- **Indentation** is 2 spaces per level.
- **Exactly one blank line** separates consecutive entries. There are no blank lines
  inside an entry.
- **Key order** is as authored, both within an entry and between entries.
- **No line exceeds 240 characters**, except a comment line, which is never reflowed.
  The limit governs alignment groups; a sequence field that is not part of one (§6) is
  emitted on one line however long it is.

## 3. Numbers

A float is written with a **mandatory sign**, `+` or `-`, and always at least one
fractional digit: `+5.0e+00`, never `+5e+00`; `+100.0`, never `+100`.

- **Digits.** The shortest decimal that reads back as the same double, extended by
  trailing zeros to the rule below.
- **Common mantissa width.** Every element of one sequence field carries the same
  number of fractional digits — the largest any of them needs. A matrix field is one
  such scope spanning all of its rows, so a column is uniform all the way down. Where
  a field mixes fixed-point and scientific notation the width is counted per notation.
  Standalone scalars (`mean:`, `theta:`) and numbers inside a flow-mapping cell
  (`kinematics`' `q2_min`) belong to no field scope and keep their shortest form.
- **Notation** — fixed-point or scientific — is as authored, never re-derived from the
  magnitude.
- **Exponents** use a lowercase `e`, a mandatory sign, and two zero-padded digits:
  `+4.05e-05`. If any float in the entry needs three digits, every float in that entry
  uses three. The width is a minimum, never a truncation.
- **Integers** stay integers, unsigned: `dof: 5`, `physical-limit: 0`. The one
  exception is an integer that is an element of a sequence field which also holds
  floats — a covariance's `0`, a correlation matrix's diagonal `1`. Those are written
  as floats, in that field's notation and mantissa width, so the column reads
  uniformly. A field holding no float at all stays integral throughout.

## 4. Strings and keys

- **String values are single-quoted**, or double-quoted when the value itself contains
  an apostrophe: `'B->Dlnu::BR'`, `"B->K^*ll::P'_5"`.
- **Keys are never quoted**, including keys containing an apostrophe and every nested
  key (`q2_min`, `hi`, `form-factors`).
- **Flow mappings carry no padding inside their braces**: `{l: 'e', q: 'd'}`.

## 5. Comments and fold markers

Comments are kept verbatim and stay with what they annotate, re-indented to the key
they sit above. Two positions cannot be kept and move by the smallest amount that
still parses:

- a comment on a key's own line, where the value is laid out starting on that same
  line, moves to the line **above** the key;
- a comment attached to a single **element** of a sequence moves to the lines **above
  that field's key**, in element order, since the element it followed no longer sits
  where it did.

Vim fold markers (`# {{{`, `# }}}`) are comments like any other and are kept. A
formatted file has them balanced.

## 6. The aligned grid

The fields of an alignment group form one table. Column `i` has a single width — the
widest cell at that index across every vector field and every row of every matrix
field — and every field's first cell begins in the same character column, reached by
padding after `key:`. A comma sits directly against its own cell; the padding follows
the comma.

A matrix field's **inner** bracket is the one that lands on that column; its outer
bracket takes the two columns to the left, each further row repeats only the inner
bracket beneath the first, and the outer bracket closes alone on its own line:

```yaml
Some::Constraint@Author:2020A:
  type: 'MultivariateGaussian(Covariance)'
  observables:  [ 'foo',    'bar',    'baz',    'quux'   ]
  kinematics:
    - {q2_min: +1.0, q2_max: +2.0}
    - {q2_min: +2.0, q2_max: +3.0}
    - {q2_min: +3.0, q2_max: +4.0}
    - {q2_min: +4.0, q2_max: +5.5}
  means:        [ +1.0e-04, -1.0,     +0.3,     +12.0    ]
  covariance: [ [ +1.0e-08, +0.0e+00, +0.0e+00, +0.0e+00 ],
                [ +0.0e+00, +1.0e-08, +0.0e+00, +0.0e+00 ],
                [ +0.0e+00, +0.0e+00, +1.0e-08, +0.0e+00 ],
                [ +0.0e+00, +0.0e+00, +0.0e+00, +1.0e-08 ]
              ]
```

**Which fields take part.** A field joins the group when its widest cell fits the
group's width cap, which is `max(15, w)` plus two characters of slack, where `w` is the
widest cell of `observables`, `means` and `covariance`. Those three are the fields the
alignment exists for, so each contributes to the cap and none can be excluded by it —
except that `observables` is dropped when its own cells are too wide to leave room for
three columns on a line, in which case the cap comes from the remaining two. A field
that does not join — `kinematics` above, and `options` where its cells run wide — is
emitted as a block sequence with its cells exactly as they come, aligned against
nothing: one cell per line for a vector field, one bracketed row per line for a matrix
field. A matrix field whose rows are not all `N` cells long never joins either.

**Wrapping.** When the group's lines would exceed the budget, every field breaks at the
same cell index, chosen so the cells spread evenly over as few lines as the budget
allows. Continuation lines carry no bracket and start at the shared column, and the
columns hold across the break — cell `j` of every line shares a width with cells
`j + W`, `j + 2W`, and so on. Shown at a narrow budget, since the real one rarely
forces a break:

```yaml
  observables: [ 'foo',    'bar',
                 'baz',    'quux' ]
  means:       [ +1.0e-04, -1.0,
                 +0.3,     +12.0  ]
```

## 7. Mixture entries

In a `type: Mixture` entry the entry's own fields and **every component's** `means` and
`covariance` form a single group, so a column indexes the same observable everywhere in
the entry. The group therefore spans two indentation levels, and the shared column is
an absolute one: a component's `means:` at indent 6 puts its first cell in the same
character column as the entry's `observables:` at indent 2.

```yaml
  observables:      [ 'ubenue::Re{cVL}',       'ubenue::Re{cVR}',       ...
  kinematics:       [ {},                      {},                      ...
  components:
    - means:        [ +0.239210427429589030,   +0.745753385482569400,   ...
      covariance: [ [ +0.00413002621593829000, -0.00332498388430227560, ...
```

A component's field joins on the same terms as any other (§6): right arity, cells
within the cap, rows not ragged. One that fails is emitted on its own and leaves the
rest of the group untouched.
