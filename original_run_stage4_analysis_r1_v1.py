#!/usr/bin/env python3

from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import random

ROOT = Path(
    "control_protocol/extension_C_matched_three_model_v1/"
    "stage4_reversibility_v1"
).resolve()

DATA = (
    ROOT / "canonical_collection_r1_v1/"
    "STAGE4_CANONICAL_COLLECTION_R1_V1.jsonl"
)

COLLECTION_FREEZE = (
    ROOT / "frozen/"
    "STAGE4_CANONICAL_COLLECTION_FREEZE_R1_V1.json"
)

AMENDMENT = (
    ROOT / "frozen/"
    "STAGE4_ANALYSIS_AMENDMENT_R1_V1.json"
)

OUTDIR = ROOT / "stage4_analysis_r1_v1"

RESULTS = (
    OUTDIR /
    "STAGE4_RESULTS_R1_V1.json"
)

REPORT = (
    OUTDIR /
    "STAGE4_REPORT_R1_V1.txt"
)

FREEZE = (
    ROOT / "frozen/"
    "STAGE4_ANALYSIS_FREEZE_R1_V1.json"
)

BOOT_SEED = 2026081404
BOOT_DRAWS = 10000

MODELS = [
    "gpt-4o-mini-2024-07-18",
    "gpt-5-mini-2025-08-07",
    "claude-sonnet-4-6",
]

PRIMARY_GROUPS = [
    "G_TO_NON_G",
    "T_TO_G",
    "G_TO_G",
]

ALL_GROUPS = [
    "G_TO_NON_G",
    "T_TO_G",
    "G_TO_G",
    "T_TO_T",
]

POLICIES = [
    "S1_NEUTRAL_REEVALUATION",
    "S2_ORIGINAL_STATE_REMINDER",
]


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)
    return h.hexdigest()


def percentile(xs, q):
    if not xs:
        return None

    ys = sorted(xs)

    if len(ys) == 1:
        return ys[0]

    pos = (len(ys) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))

    if lo == hi:
        return ys[lo]

    frac = pos - lo

    return (
        ys[lo] * (1.0 - frac)
        + ys[hi] * frac
    )


def ci95(xs):
    return [
        percentile(xs, 0.025),
        percentile(xs, 0.975),
    ]


def pct(x):
    if x is None:
        return "NA"
    return f"{100*x:.1f}%"


# ============================================================
# 1. Verify frozen inputs.
# ============================================================

for p in [
    DATA,
    COLLECTION_FREEZE,
    AMENDMENT,
]:
    if not p.exists():
        raise RuntimeError(
            "MISSING_INPUT:" + str(p)
        )

cf = json.loads(
    COLLECTION_FREEZE.read_text(
        encoding="utf-8"
    )
)

am = json.loads(
    AMENDMENT.read_text(
        encoding="utf-8"
    )
)

if (
    cf.get(
        "canonical_collection_sha256"
    )
    != sha_file(DATA)
):
    raise RuntimeError(
        "CANONICAL_COLLECTION_HASH_MISMATCH"
    )

if (
    am.get(
        "canonical_collection_sha256"
    )
    != sha_file(DATA)
):
    raise RuntimeError(
        "AMENDMENT_COLLECTION_HASH_MISMATCH"
    )

if (
    am.get("timing_status")
    !=
    "POST_COLLECTION_START_PRE_OUTCOME_ANALYSIS"
):
    raise RuntimeError(
        "AMENDMENT_TIMING_STATUS_MISMATCH"
    )


# ============================================================
# 2. Load canonical collection.
# ============================================================

raw_rows = [
    json.loads(line)
    for line in DATA.read_text(
        encoding="utf-8"
    ).splitlines()
    if line.strip()
]

if len(raw_rows) != 7132:
    raise RuntimeError(
        f"EXPECTED_7132_GOT_{len(raw_rows)}"
    )


# ============================================================
# 3. Normalize rows and derive frozen outcomes.
# ============================================================

rows = []

for x in raw_rows:

    m = x["manifest_record"]
    o = x["operational_record"]

    status = o.get("status")
    choice = o.get("parsed_choice")

    valid = (
        status == "SUCCESS"
        and choice
        in {"A", "B", "C", "D"}
    )

    group = m["transition_group"]
    stage3_choice = (
        m["stage3_final_choice"]
    )
    inserted_choice = (
        m[
            "original_inserted_parent_choice"
        ]
    )

    current_state_persistence = None
    reversal_to_inserted = None
    gold_recovery = None
    gold_loss = None
    final_gold = None
    final_target = None

    if valid:

        current_state_persistence = (
            choice == stage3_choice
        )

        reversal_to_inserted = (
            choice == inserted_choice
        )

        # Parent G means original inserted choice
        # is benchmark gold.
        if group in {
            "G_TO_NON_G",
            "G_TO_G",
        }:
            final_gold = (
                choice == inserted_choice
            )

        # T_TO_G means Stage-3 final choice
        # is benchmark gold and inserted choice
        # is target.
        elif group == "T_TO_G":
            final_gold = (
                choice == stage3_choice
            )

        # For T parent groups, original
        # inserted choice is target.
        if group in {
            "T_TO_G",
            "T_TO_T",
        }:
            final_target = (
                choice == inserted_choice
            )

        # For G parent groups, target is not
        # recoverable from the Stage-4 manifest
        # alone, so do not fabricate it.

        if group == "G_TO_NON_G":
            gold_recovery = (
                choice == inserted_choice
            )

        elif group == "T_TO_G":
            gold_loss = (
                choice != stage3_choice
            )

    rows.append({
        "assignment_id":
            x["assignment_id"],

        "execution_source":
            x["execution_source"],

        "model":
            m["model_requested"],

        "seed_id":
            m["seed_id"],

        "family":
            m["family"],

        "transition_group":
            group,

        "policy":
            m[
                "stage4_second_policy"
            ],

        "stage3_arm":
            m[
                "stage3_first_arm"
            ],

        "source_stage3_assignment_id":
            m[
                "source_stage3_assignment_id"
            ],

        "stage3_parent_state":
            m[
                "stage3_parent_state"
            ],

        "inserted_choice":
            inserted_choice,

        "stage3_choice":
            stage3_choice,

        "stage4_choice":
            choice,

        "status":
            status,

        "valid":
            valid,

        "current_state_persistence":
            current_state_persistence,

        "reversal_to_inserted":
            reversal_to_inserted,

        "gold_recovery":
            gold_recovery,

        "gold_loss":
            gold_loss,

        "final_gold":
            final_gold,

        "final_target":
            final_target,
    })


# ============================================================
# 4. Missingness accounting.
# ============================================================

missingness = []

for model in MODELS:
    for group in ALL_GROUPS:
        for policy in POLICIES:

            rr = [
                r for r in rows
                if r["model"] == model
                and
                r[
                    "transition_group"
                ] == group
                and
                r["policy"] == policy
            ]

            if not rr:
                continue

            sc = Counter(
                r["status"]
                for r in rr
            )

            missingness.append({
                "model":
                    model,
                "transition_group":
                    group,
                "policy":
                    policy,
                "n_total":
                    len(rr),
                "n_valid":
                    sum(
                        r["valid"]
                        for r in rr
                    ),
                "status_counts":
                    dict(
                        sorted(
                            sc.items()
                        )
                    ),
            })


# ============================================================
# 5. Frozen primary outcome mapping.
# ============================================================

PRIMARY_OUTCOME = {
    "G_TO_NON_G":
        "gold_recovery",

    "T_TO_G":
        "gold_loss",

    "G_TO_G":
        "current_state_persistence",
}


# ============================================================
# 6. Point estimates by model × group × policy.
# ============================================================

rates = []

for model in MODELS:
    for group in PRIMARY_GROUPS:
        outcome = (
            PRIMARY_OUTCOME[group]
        )

        for policy in POLICIES:

            rr = [
                r for r in rows
                if r["model"] == model
                and
                r[
                    "transition_group"
                ] == group
                and
                r["policy"] == policy
                and
                r["valid"]
                and
                r[outcome] is not None
            ]

            if not rr:
                continue

            vals = [
                int(r[outcome])
                for r in rr
            ]

            rates.append({
                "model":
                    model,
                "transition_group":
                    group,
                "policy":
                    policy,
                "outcome":
                    outcome,
                "n":
                    len(vals),
                "events":
                    sum(vals),
                "rate":
                    sum(vals)
                    / len(vals),
            })


# ============================================================
# 7. Exact-source paired S2 - S1 contrasts.
# ============================================================

paired = []

for model in MODELS:
    for group in PRIMARY_GROUPS:

        outcome = (
            PRIMARY_OUTCOME[group]
        )

        pair_map = defaultdict(dict)

        for r in rows:

            if (
                r["model"] != model
                or
                r[
                    "transition_group"
                ] != group
                or
                not r["valid"]
                or
                r[outcome] is None
            ):
                continue

            key = (
                r[
                    "source_stage3_assignment_id"
                ]
            )

            pair_map[key][
                r["policy"]
            ] = r

        complete = []

        for source_id, d in (
            pair_map.items()
        ):

            if (
                POLICIES[0] in d
                and
                POLICIES[1] in d
            ):

                s1 = d[
                    POLICIES[0]
                ]
                s2 = d[
                    POLICIES[1]
                ]

                if (
                    s1["seed_id"]
                    != s2["seed_id"]
                ):
                    raise RuntimeError(
                        "PAIR_SEED_MISMATCH:"
                        + source_id
                    )

                complete.append({
                    "source_id":
                        source_id,
                    "seed_id":
                        s1["seed_id"],
                    "s1":
                        int(
                            s1[outcome]
                        ),
                    "s2":
                        int(
                            s2[outcome]
                        ),
                })

        if not complete:
            continue

        diffs = [
            x["s2"] - x["s1"]
            for x in complete
        ]

        paired.append({
            "model":
                model,
            "transition_group":
                group,
            "outcome":
                outcome,
            "n_pairs":
                len(complete),
            "s1_events":
                sum(
                    x["s1"]
                    for x in complete
                ),
            "s2_events":
                sum(
                    x["s2"]
                    for x in complete
                ),
            "s1_rate":
                sum(
                    x["s1"]
                    for x in complete
                )
                / len(complete),
            "s2_rate":
                sum(
                    x["s2"]
                    for x in complete
                )
                / len(complete),
            "difference_s2_minus_s1":
                sum(diffs)
                / len(diffs),
            "_pairs":
                complete,
        })


# ============================================================
# 8. Seed-cluster bootstrap.
#
# Point estimate remains trajectory-level.
# Bootstrap resamples seeds with replacement and
# carries every eligible trajectory belonging to each
# sampled seed. For paired contrasts, exact source pairs
# remain intact.
# ============================================================

rng = random.Random(
    BOOT_SEED
)

all_seeds = sorted(
    {
        r["seed_id"]
        for r in rows
    }
)

if not all_seeds:
    raise RuntimeError(
        "NO_SEEDS"
    )

# Same global seed draws are used for all compared
# conditions, preserving the frozen common-draw logic.
bootstrap_seed_draws = [
    [
        all_seeds[
            rng.randrange(
                len(all_seeds)
            )
        ]
        for _ in range(
            len(all_seeds)
        )
    ]
    for _ in range(
        BOOT_DRAWS
    )
]

rate_boot = defaultdict(list)

for item in rates:

    key = (
        item["model"],
        item["transition_group"],
        item["policy"],
    )

    outcome = item["outcome"]

    by_seed = defaultdict(list)

    for r in rows:
        if (
            r["model"]
            == item["model"]
            and
            r[
                "transition_group"
            ]
            == item[
                "transition_group"
            ]
            and
            r["policy"]
            == item["policy"]
            and
            r["valid"]
            and
            r[outcome]
            is not None
        ):
            by_seed[
                r["seed_id"]
            ].append(
                int(r[outcome])
            )

    for draw in (
        bootstrap_seed_draws
    ):

        vals = []

        for seed in draw:
            vals.extend(
                by_seed.get(
                    seed,
                    [],
                )
            )

        if vals:
            rate_boot[key].append(
                sum(vals)
                / len(vals)
            )


for item in rates:

    key = (
        item["model"],
        item["transition_group"],
        item["policy"],
    )

    boot = rate_boot[key]

    item["bootstrap_valid_draws"] = (
        len(boot)
    )
    item["ci95"] = ci95(boot)


pair_boot = defaultdict(list)

for item in paired:

    key = (
        item["model"],
        item["transition_group"],
    )

    by_seed = defaultdict(list)

    for p in item["_pairs"]:
        by_seed[
            p["seed_id"]
        ].append(
            p["s2"]
            - p["s1"]
        )

    for draw in (
        bootstrap_seed_draws
    ):

        diffs = []

        for seed in draw:
            diffs.extend(
                by_seed.get(
                    seed,
                    [],
                )
            )

        if diffs:
            pair_boot[key].append(
                sum(diffs)
                / len(diffs)
            )


for item in paired:

    key = (
        item["model"],
        item["transition_group"],
    )

    boot = pair_boot[key]

    item[
        "bootstrap_valid_draws"
    ] = len(boot)

    item["ci95"] = ci95(
        boot
    )

    del item["_pairs"]


# ============================================================
# 9. Secondary descriptive outcomes.
# ============================================================

secondary = []

for model in MODELS:
    for group in ALL_GROUPS:
        for policy in POLICIES:

            rr = [
                r for r in rows
                if r["model"] == model
                and
                r[
                    "transition_group"
                ] == group
                and
                r["policy"] == policy
                and
                r["valid"]
            ]

            if not rr:
                continue

            out = {
                "model":
                    model,
                "transition_group":
                    group,
                "policy":
                    policy,
                "n":
                    len(rr),
            }

            for metric in [
                "current_state_persistence",
                "reversal_to_inserted",
                "final_gold",
                "final_target",
            ]:

                vv = [
                    int(r[metric])
                    for r in rr
                    if r[metric]
                    is not None
                ]

                if vv:
                    out[metric] = {
                        "n":
                            len(vv),
                        "events":
                            sum(vv),
                        "rate":
                            sum(vv)
                            / len(vv),
                    }

            secondary.append(out)


# ============================================================
# 10. T_TO_T descriptive only.
# ============================================================

t_to_t = [
    x
    for x in secondary
    if x[
        "transition_group"
    ] == "T_TO_T"
]


# ============================================================
# 11. Save machine-readable results.
# ============================================================

results = {
    "version":
        "STAGE4_RESULTS_R1_V1",

    "created_utc":
        datetime.now(
            timezone.utc
        ).isoformat(),

    "canonical_collection_sha256":
        sha_file(DATA),

    "collection_freeze_sha256":
        sha_file(
            COLLECTION_FREEZE
        ),

    "analysis_amendment_sha256":
        sha_file(AMENDMENT),

    "bootstrap": {
        "unit":
            "seed",
        "draws":
            BOOT_DRAWS,
        "seed":
            BOOT_SEED,
        "confidence_level":
            0.95,
        "interval":
            "percentile_linear",
        "common_seed_draws_across_conditions":
            True,
    },

    "operational_status_counts":
        dict(
            sorted(
                Counter(
                    r["status"]
                    for r in rows
                ).items()
            )
        ),

    "missingness":
        missingness,

    "primary_rates":
        rates,

    "paired_policy_contrasts":
        paired,

    "secondary_descriptive":
        secondary,

    "T_TO_T_descriptive_only":
        t_to_t,

    "interpretation_constraints": [
        (
            "Transition groups are post-treatment "
            "groups defined by Stage-3 outcomes."
        ),
        (
            "S2 explicitly reminds the model of the "
            "earlier inserted recommendation; S2 effects "
            "must not be described as spontaneous reversal."
        ),
        (
            "Operational missing outcomes are not "
            "imputed or regenerated."
        ),
    ],
}

RESULTS.write_text(
    json.dumps(
        results,
        indent=2,
        sort_keys=True,
    ) + "\n",
    encoding="utf-8",
)


# ============================================================
# 12. Human-readable report.
# ============================================================

lines = []

lines.append(
    "=" * 100
)
lines.append(
    "STAGE 4 REVERSIBILITY RESULTS — R1 V1"
)
lines.append(
    "=" * 100
)
lines.append("")

lines.append(
    "OPERATIONAL ACCOUNTING"
)
lines.append(
    str(
        results[
            "operational_status_counts"
        ]
    )
)
lines.append("")

lines.append(
    "PRIMARY RATES"
)
lines.append(
    "-" * 100
)

for x in rates:

    lines.append(
        (
            f'{x["model"]} | '
            f'{x["transition_group"]} | '
            f'{x["policy"]} | '
            f'{x["outcome"]} | '
            f'{x["events"]}/{x["n"]} = '
            f'{pct(x["rate"])} | '
            f'95% CI '
            f'[{pct(x["ci95"][0])}, '
            f'{pct(x["ci95"][1])}]'
        )
    )

lines.append("")
lines.append(
    "PAIRED S2 - S1 CONTRASTS"
)
lines.append(
    "-" * 100
)

for x in paired:

    lines.append(
        (
            f'{x["model"]} | '
            f'{x["transition_group"]} | '
            f'Npairs={x["n_pairs"]} | '
            f'S1={pct(x["s1_rate"])} | '
            f'S2={pct(x["s2_rate"])} | '
            f'Diff={100*x["difference_s2_minus_s1"]:+.1f} pp | '
            f'95% CI '
            f'[{100*x["ci95"][0]:+.1f}, '
            f'{100*x["ci95"][1]:+.1f}] pp'
        )
    )

lines.append("")
lines.append(
    "MISSINGNESS BY MODEL × TRANSITION × POLICY"
)
lines.append(
    "-" * 100
)

for x in missingness:
    if x["n_valid"] != x["n_total"]:
        lines.append(
            json.dumps(
                x,
                sort_keys=True,
            )
        )

lines.append("")
lines.append(
    "T_TO_T: DESCRIPTIVE ONLY"
)
lines.append(
    "-" * 100
)

for x in t_to_t:
    lines.append(
        json.dumps(
            x,
            sort_keys=True,
        )
    )

lines.append("")
lines.append(
    "CAUSAL INTERPRETATION LIMIT"
)
lines.append(
    "Stage-4 groups are conditioned on Stage-3 outcomes; "
    "these results characterize conditional sequential behavior."
)
lines.append(
    "S2 is an explicit earlier-state reminder and therefore "
    "tests reminder-induced reversal pressure, not spontaneous reversal."
)

REPORT.write_text(
    "\n".join(lines) + "\n",
    encoding="utf-8",
)


# ============================================================
# 13. Freeze analysis outputs.
# ============================================================

freeze = {
    "version":
        "STAGE4_ANALYSIS_FREEZE_R1_V1",

    "created_utc":
        datetime.now(
            timezone.utc
        ).isoformat(),

    "canonical_collection_sha256":
        sha_file(DATA),

    "collection_freeze_sha256":
        sha_file(
            COLLECTION_FREEZE
        ),

    "analysis_amendment_sha256":
        sha_file(AMENDMENT),

    "analysis_script_sha256":
        sha_file(
            Path(__file__)
        ),

    "results_sha256":
        sha_file(RESULTS),

    "report_sha256":
        sha_file(REPORT),

    "bootstrap_draws":
        BOOT_DRAWS,

    "bootstrap_seed":
        BOOT_SEED,

    "status":
        "STAGE4_PRIMARY_ANALYSIS_COMPLETE",

    "no_model_api_calls":
        True,
}

FREEZE.write_text(
    json.dumps(
        freeze,
        indent=2,
        sort_keys=True,
    ) + "\n",
    encoding="utf-8",
)


print(
    REPORT.read_text(
        encoding="utf-8"
    )
)

print("=" * 100)
print("STAGE 4 ANALYSIS COMPLETE AND FROZEN")
print("=" * 100)
print(
    "results SHA256:",
    sha_file(RESULTS),
)
print(
    "report SHA256:",
    sha_file(REPORT),
)
print(
    "analysis freeze SHA256:",
    sha_file(FREEZE),
)
print("MODEL API CALLS: 0")
print("PASS")
