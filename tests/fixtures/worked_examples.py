from __future__ import annotations
from eos_pre_commit_hooks.eos_yaml.model import FieldSpec, AlignmentPlan

# --- Small example: spec §4.1, at label_gap=1, column_gap=1 ----------------------
# Under those defaults the renderer reproduces the spec's §4.1 illustration exactly,
# so this fixture IS that illustration rather than a re-derivation of it. (An earlier
# draft of this plan had the comma placed after the column padding instead of against
# its value, which did not match; DESIGN.md §3.1 now states the rule the examples use.)

SMALL_FIELDS = [
    FieldSpec(key='observables', kind='vector', indent=0, cells=['"foo"', '"bar"', '"baz"']),
    FieldSpec(key='means', kind='vector', indent=0, cells=['+1.0e-4', '-1.0', '+0.3']),
]
SMALL_OBSERVABLE_CELLS = ['"foo"', '"bar"', '"baz"']

SMALL_PLAN = AlignmentPlan(
    value_column=15,                 # absolute: indent 0 + 'observables:' 12 + gap 1 + '[ ' 2
    pad=[1, 7],
    column_widths=[7, 5, 5],
    wrap_w=None,
    included=[0, 1],
    excluded=[],
)

# Byte-for-byte the illustration in spec 4.1: the comma sits against its value and
# the column padding follows it, not the other way round.
SMALL_EXPECTED_TEXT = (
    'observables: [ "foo",   "bar", "baz" ]\n'
    'means:       [ +1.0e-4, -1.0,  +0.3  ]\n'
)

# --- Big example: spec §4.2 real data (B-to-D-l-nu.yaml, Belle:2015A, N=10) -------
# Cell strings taken from the *current, unformatted* real file (already
# round-trip-safe canonical floats — this file happens to already use the target
# float style). `kinematics` is included as a vector field for completeness (its
# cells are ~34 chars each — this is what the §4.4 cap must exclude); `covariance`
# is a matrix field. `options` is deliberately identical on every column here,
# exactly as in the real file.

BIG_OBSERVABLE_CELL = '"B->Dlnu::BR"'
BIG_N = 10

BIG_FIELDS = [
    FieldSpec(key='observables', kind='vector', cells=[BIG_OBSERVABLE_CELL] * BIG_N),
    FieldSpec(key='options', kind='vector', cells=['{ l: e, q: d }'] * BIG_N),
    FieldSpec(key='kinematics', kind='vector', cells=[
        '{ q2_min: +10.44, q2_max: +11.63 }',
        '{ q2_min:  +9.26, q2_max: +10.44 }',
        '{ q2_min:  +8.07, q2_max:  +9.26 }',
        '{ q2_min:  +6.89, q2_max:  +8.07 }',
        '{ q2_min:  +5.71, q2_max:  +6.89 }',
        '{ q2_min:  +4.52, q2_max:  +5.71 }',
        '{ q2_min:  +3.34, q2_max:  +4.52 }',
        '{ q2_min:  +2.15, q2_max:  +3.34 }',
        '{ q2_min:  +0.97, q2_max:  +2.15 }',
        '{ q2_min:  +0.01, q2_max:  +0.97 }',
    ]),
    FieldSpec(key='means', kind='vector', cells=[
        '+4.154e-05', '+6.106e-04', '+1.255e-03', '+1.635e-03', '+1.901e-03',
        '+2.758e-03', '+3.524e-03', '+4.216e-03', '+4.371e-03', '+4.050e-03',
    ]),
    FieldSpec(key='covariance', kind='matrix', rows=[
        ['+1.912e-09', '+1.726e-10', '+3.427e-10', '+4.424e-10', '+5.041e-10',
         '+7.320e-10', '+9.624e-10', '+1.096e-09', '+1.049e-09', '+8.840e-10'],
        ['+1.726e-10', '+1.478e-08', '+1.811e-09', '+2.383e-09', '+2.738e-09',
         '+3.977e-09', '+5.166e-09', '+5.959e-09', '+5.903e-09', '+5.209e-09'],
        ['+3.427e-10', '+1.811e-09', '+2.863e-08', '+4.849e-09', '+5.579e-09',
         '+8.101e-09', '+1.051e-08', '+1.215e-08', '+1.214e-08', '+1.075e-08'],
        ['+4.424e-10', '+2.383e-09', '+4.849e-09', '+3.786e-08', '+7.398e-09',
         '+1.071e-08', '+1.387e-08', '+1.602e-08', '+1.603e-08', '+1.425e-08'],
        ['+5.041e-10', '+2.738e-09', '+5.579e-09', '+7.398e-09', '+4.355e-08',
         '+1.241e-08', '+1.606e-08', '+1.860e-08', '+1.873e-08', '+1.678e-08'],
        ['+7.320e-10', '+3.977e-09', '+8.101e-09', '+1.071e-08', '+1.241e-08',
         '+6.176e-08', '+2.334e-08', '+2.709e-08', '+2.731e-08', '+2.440e-08'],
        ['+9.624e-10', '+5.166e-09', '+1.051e-08', '+1.387e-08', '+1.606e-08',
         '+2.334e-08', '+8.585e-08', '+3.533e-08', '+3.555e-08', '+3.156e-08'],
        ['+1.096e-09', '+5.959e-09', '+1.215e-08', '+1.602e-08', '+1.860e-08',
         '+2.709e-08', '+3.533e-08', '+1.022e-07', '+4.194e-08', '+3.744e-08'],
        ['+1.049e-09', '+5.903e-09', '+1.214e-08', '+1.603e-08', '+1.873e-08',
         '+2.731e-08', '+3.555e-08', '+4.194e-08', '+1.005e-07', '+3.887e-08'],
        ['+8.840e-10', '+5.209e-09', '+1.075e-08', '+1.425e-08', '+1.678e-08',
         '+2.440e-08', '+3.156e-08', '+3.744e-08', '+3.887e-08', '+8.132e-08'],
    ]),
]

# Structural facts about BIG_FIELDS that STEP-5's plan_alignment(BIG_FIELDS, ...)
# must reproduce (see STEP-5.md for the full assertion list) — NOT a full
# AlignmentPlan literal, because the exact column_widths/value_column depend on
# label_gap/column_gap/cap_slack, which are implementation defaults (DESIGN.md §3.1,
# §3.3), not spec-mandated numbers:
BIG_EXPECTED_INCLUDED = [0, 1, 3, 4]   # observables, options, means, covariance
BIG_EXPECTED_EXCLUDED = [2]            # kinematics
BIG_EXPECTED_KEYS = ['observables', 'options', 'means', 'covariance']
BIG_EXPECTED_WRAP_W = None   # at the 240-column budget all ten cells fit one line
BIG_EXPECTED_WRAP_W_AT_150 = 5   # ceil(10/5) = 2 sub-lines, break after cell index 4

# Verbatim text the issue author hand-formatted and hand-verified (spec §4.2) — kept
# for structural comparison only, NOT as a byte-exact target. See DESIGN.md §3.1.
BIG_HAND_FORMATTED_TEXT = '''\
B^0->D^+e^-nu::BRs@Belle:2015A:
  type: MultivariateGaussian(Covariance)
  observables:    [ "B->Dlnu::BR",  "B->Dlnu::BR",  "B->Dlnu::BR",  "B->Dlnu::BR",  "B->Dlnu::BR",
                    "B->Dlnu::BR",  "B->Dlnu::BR",  "B->Dlnu::BR",  "B->Dlnu::BR",  "B->Dlnu::BR"   ]
  options:        [ { l: e, q: d }, { l: e, q: d }, { l: e, q: d }, { l: e, q: d }, { l: e, q: d },
                    { l: e, q: d }, { l: e, q: d }, { l: e, q: d }, { l: e, q: d }, { l: e, q: d }  ]
  kinematics:
        - { q2_min: +10.44, q2_max: +11.63 }
        - { q2_min:  +9.26, q2_max: +10.44 }
        ...
  means:          [ +4.154e-05,     +6.106e-04,     +1.255e-03,     +1.635e-03,     +1.901e-03,
                    +2.758e-03,     +3.524e-03,     +4.216e-03,     +4.371e-03,     +4.050e-03      ]
  covariance:   [ [ +1.912e-09,     +1.726e-10,     +3.427e-10,     +4.424e-10,     +5.041e-10,
                    +7.320e-10,     +9.624e-10,     +1.096e-09,     +1.049e-09,     +8.840e-10      ],
                  [ +1.726e-10,     +1.478e-08,     +1.811e-09,     +2.383e-09,     +2.738e-09,
                    +3.977e-09,     +5.166e-09,     +5.959e-09,     +5.903e-09,     +5.209e-09      ],
                   ...
                  [ +8.840e-10,     +5.209e-09,     +1.075e-08,     +1.425e-08,     +1.678e-08,
                    +2.440e-08,     +3.156e-08,     +3.744e-08,     +3.887e-08,     +8.132e-08      ]
                ]
'''

# The corresponding *current, unformatted* real-file text (2-space-reindented from
# eos/constraints/experimental/B-to-D-l-nu.yaml lines 8-39 — original is 4-space
# indented; STEP-7's end-to-end fixtures should use the ACTUAL 4-space original,
# this copy is only for STEP-5/6 unit-test convenience) is intentionally not
# duplicated here — STEP-7 reads the real file directly (see STEP-7.md).
