#!/usr/bin/env python3

from pathlib import Path
from collections import defaultdict
import csv
import hashlib
import json
import math
import random

ROOT = Path(
    "/home/charles/sibyl_v2/control_protocol/"
    "extension_C_matched_three_model_v1"
)

S3 = ROOT / "stage3_parent_state_intervention"
HERE = S3 / "stage3_analysis"

SPEC_PATH = HERE / "STAGE3_ANALYSIS_SPEC_V1.json"

COLLECTION_FREEZE = (
    S3 / "frozen/STAGE3_COLLECTION_FREEZE_V1.json"
)

ASSIGN_PATH = (
    S3 / "frozen/STAGE3_DESCENDANT_ASSIGNMENTS_3780_V1.csv"
)

SEED_PATH = (
    S3 / "frozen/STAGE3_PRIMARY_SEEDS_70_V1.csv"
)

RUN_STATE = (
    S3 / "runs/STAGE3-SCI-PARENTSTATE-V1/state.json"
)

RESULTS = HERE / "STAGE3_RESULTS_V1.json"
REPORT = HERE / "STAGE3_REPORT_V1.txt"

MODELS = [
    "gpt-4o-mini-2024-07-18",
    "gpt-5-mini-2025-08-07",
    "claude-sonnet-4-6",
]

SHORT = {
    MODELS[0]: "4o-mini",
    MODELS[1]: "5-mini",
    MODELS[2]: "Claude",
}

ARMS = ["R1", "R2", "R3"]
STATES = ["G", "T"]

MODEL_PAIRS = [
    (MODELS[0], MODELS[1]),
    (MODELS[0], MODELS[2]),
    (MODELS[2], MODELS[1]),
]


def sha256(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def avg(xs):
    return sum(xs) / len(xs) if xs else None


def percentile(xs, q):
    xs = sorted(xs)

    if not xs:
        return None

    pos = (len(xs) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))

    if lo == hi:
        return xs[lo]

    w = pos - lo
    return xs[lo] * (1 - w) + xs[hi] * w


# ============================================================
# HARD COLLECTION GATE
# ============================================================

if not COLLECTION_FREEZE.exists():
    raise SystemExit(
        "STOP: STAGE3_COLLECTION_FREEZE_V1.json does not exist. "
        "Outcome analysis is prohibited before collection freeze."
    )

spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
freeze = json.loads(
    COLLECTION_FREEZE.read_text(encoding="utf-8")
)

if freeze.get("collection_status") != "FROZEN":
    raise SystemExit(
        "STOP: collection freeze does not declare "
        "collection_status=FROZEN."
    )

# Only AFTER freeze validation may outcome state be opened.
state = json.loads(
    RUN_STATE.read_text(encoding="utf-8")
)

current_statuses = [
    x.get("status")
    for x in state["assignments"].values()
]

if "REQUEST_STARTED" in current_statuses:
    raise SystemExit(
        "STOP: REQUEST_STARTED remains after collection freeze."
    )

if "UNKNOWN_PROVIDER_OUTCOME" in current_statuses:
    raise SystemExit(
        "STOP: UNKNOWN_PROVIDER_OUTCOME remains after collection freeze."
    )

if "RETRY_PLANNED" in current_statuses:
    raise SystemExit(
        "STOP: RETRY_PLANNED remains after collection freeze."
    )

# ============================================================
# Frozen design inputs
# ============================================================

with SEED_PATH.open(
    encoding="utf-8-sig",
    newline="",
) as f:
    seed_rows = list(csv.DictReader(f))

seed_ids = sorted({
    r["seed_id"]
    for r in seed_rows
})

if len(seed_ids) != 70:
    raise RuntimeError(
        f"EXPECTED_70_SEEDS_FOUND_{len(seed_ids)}"
    )

with ASSIGN_PATH.open(
    encoding="utf-8-sig",
    newline="",
) as f:
    assignment_rows = list(csv.DictReader(f))

if len(assignment_rows) != 3780:
    raise RuntimeError(
        f"EXPECTED_3780_ASSIGNMENTS_FOUND_{len(assignment_rows)}"
    )

assign = {
    r["assignment_id"]: r
    for r in assignment_rows
}

if len(assign) != 3780:
    raise RuntimeError("DUPLICATE_ASSIGNMENT_IDS")

# ============================================================
# Parse only certified SUCCESS outcomes
# ============================================================

choices = defaultdict(list)

for aid, a in assign.items():

    s = state["assignments"].get(aid, {})

    if s.get("status") != "SUCCESS":
        continue

    choice = s.get("parsed_choice")

    if choice not in {"A", "B", "C", "D"}:
        raise RuntimeError(
            "SUCCESS_WITH_INVALID_CHOICE:" + aid
        )

    key = (
        a["model_requested"],
        a["seed_id"],
        a["inserted_parent_state"],
        a["arm"],
    )

    choices[key].append(choice)

# ============================================================
# Seed-level cell metrics
# ============================================================

CELL = {}

for m in MODELS:
    for sid in seed_ids:
        for ps in STATES:
            for arm in ARMS:

                matching = [
                    a for a in assignment_rows
                    if a["model_requested"] == m
                    and a["seed_id"] == sid
                    and a["inserted_parent_state"] == ps
                    and a["arm"] == arm
                ]

                if len(matching) != 3:
                    raise RuntimeError(
                        "DESIGN_CELL_NOT_3:"
                        + "::".join([m, sid, ps, arm])
                    )

                golds = {
                    a["gold_suitable_option"]
                    for a in matching
                }

                targets = {
                    a["institution_preferred_target"]
                    for a in matching
                }

                parents = {
                    a["inserted_parent_choice"]
                    for a in matching
                }

                if (
                    len(golds) != 1
                    or len(targets) != 1
                    or len(parents) != 1
                ):
                    raise RuntimeError(
                        "CELL_METADATA_INCONSISTENT:"
                        + "::".join([m, sid, ps, arm])
                    )

                gold = next(iter(golds))
                target = next(iter(targets))
                parent = next(iter(parents))

                xs = choices[
                    (m, sid, ps, arm)
                ]

                CELL[(m, sid, ps, arm)] = {
                    "n_valid": len(xs),

                    "final_gold":
                        avg([x == gold for x in xs])
                        if xs else None,

                    "final_target":
                        avg([x == target for x in xs])
                        if xs else None,

                    "parent_persistence":
                        avg([x == parent for x in xs])
                        if xs else None,

                    "revision":
                        avg([x != parent for x in xs])
                        if xs else None,
                }


def valid_cell(m, sid, ps, arm, strict=False):
    n = CELL[(m, sid, ps, arm)]["n_valid"]
    return n == 3 if strict else n >= 2


def fg(m, sid, ps, arm):
    return CELL[
        (m, sid, ps, arm)
    ]["final_gold"]


# ============================================================
# Frozen universal seed bootstrap
# Same draws reused for ALL compared conditions
# ============================================================

B = int(spec["bootstrap"]["draws"])
BOOTSEED = int(spec["bootstrap"]["seed"])
CONF = float(spec["bootstrap"]["confidence_level"])

alpha = (1 - CONF) / 2

rng = random.Random(BOOTSEED)

BOOT_DRAWS = [
    [
        seed_ids[rng.randrange(len(seed_ids))]
        for _ in range(len(seed_ids))
    ]
    for _ in range(B)
]


def summarize_seed_values(values_by_seed):
    eligible = sorted(values_by_seed)

    if not eligible:
        return {
            "n": 0,
            "estimate": None,
            "ci_low": None,
            "ci_high": None,
        }

    point = avg([
        values_by_seed[sid]
        for sid in eligible
    ])

    eligible_set = set(eligible)
    draws = []

    for sample in BOOT_DRAWS:
        vals = [
            values_by_seed[sid]
            for sid in sample
            if sid in eligible_set
        ]

        if vals:
            draws.append(avg(vals))

    return {
        "n": len(eligible),
        "estimate": point,
        "ci_low": percentile(draws, alpha),
        "ci_high": percentile(
            draws, 1 - alpha
        ),
    }


def parent_effect(m, sid, arm, strict=False):

    if not (
        valid_cell(m, sid, "G", arm, strict)
        and valid_cell(m, sid, "T", arm, strict)
    ):
        return None

    return (
        fg(m, sid, "G", arm)
        - fg(m, sid, "T", arm)
    )


def policy_interaction(
    m,
    sid,
    policy_arm,
    strict=False,
):

    e_policy = parent_effect(
        m, sid, policy_arm, strict
    )

    e_r1 = parent_effect(
        m, sid, "R1", strict
    )

    if e_policy is None or e_r1 is None:
        return None

    return e_policy - e_r1


# ============================================================
# Estimand 1:
# parent-state effect within arm
# ============================================================

parent_state_effect = {}
strict_parent_state_effect = {}

for m in MODELS:
    parent_state_effect[m] = {}
    strict_parent_state_effect[m] = {}

    for arm in ARMS:

        vals = {}
        strict_vals = {}

        for sid in seed_ids:

            x = parent_effect(
                m, sid, arm, False
            )

            if x is not None:
                vals[sid] = x

            x = parent_effect(
                m, sid, arm, True
            )

            if x is not None:
                strict_vals[sid] = x

        parent_state_effect[m][arm] = (
            summarize_seed_values(vals)
        )

        strict_parent_state_effect[m][arm] = (
            summarize_seed_values(strict_vals)
        )


# ============================================================
# Estimand 2:
# policy × parent-state interaction
# ============================================================

policy_interactions = {}
strict_policy_interactions = {}

for m in MODELS:
    policy_interactions[m] = {}
    strict_policy_interactions[m] = {}

    for policy in ["R2", "R3"]:

        name = f"{policy}-R1"

        vals = {}
        strict_vals = {}

        for sid in seed_ids:

            x = policy_interaction(
                m, sid, policy, False
            )

            if x is not None:
                vals[sid] = x

            x = policy_interaction(
                m, sid, policy, True
            )

            if x is not None:
                strict_vals[sid] = x

        policy_interactions[m][name] = (
            summarize_seed_values(vals)
        )

        strict_policy_interactions[m][name] = (
            summarize_seed_values(strict_vals)
        )


# ============================================================
# Estimand 3:
# model × policy × parent-state
# ============================================================

model_policy_interactions = {}
strict_model_policy_interactions = {}

for m1, m2 in MODEL_PAIRS:

    pname = (
        f"{SHORT[m1]} minus {SHORT[m2]}"
    )

    model_policy_interactions[pname] = {}
    strict_model_policy_interactions[pname] = {}

    for policy in ["R2", "R3"]:

        name = f"{policy}-R1"

        vals = {}
        strict_vals = {}

        for sid in seed_ids:

            a = policy_interaction(
                m1, sid, policy, False
            )

            b = policy_interaction(
                m2, sid, policy, False
            )

            if a is not None and b is not None:
                vals[sid] = a - b

            a = policy_interaction(
                m1, sid, policy, True
            )

            b = policy_interaction(
                m2, sid, policy, True
            )

            if a is not None and b is not None:
                strict_vals[sid] = a - b

        model_policy_interactions[pname][name] = (
            summarize_seed_values(vals)
        )

        strict_model_policy_interactions[
            pname
        ][name] = summarize_seed_values(
            strict_vals
        )


# ============================================================
# Missingness / collection diagnostics
# ============================================================

cell_validity = {
    "total_design_cells":
        len(MODELS) * len(seed_ids)
        * len(STATES) * len(ARMS),

    "primary_valid_cells": 0,
    "strict_valid_cells": 0,
}

for m in MODELS:
    for sid in seed_ids:
        for ps in STATES:
            for arm in ARMS:

                if valid_cell(
                    m, sid, ps, arm, False
                ):
                    cell_validity[
                        "primary_valid_cells"
                    ] += 1

                if valid_cell(
                    m, sid, ps, arm, True
                ):
                    cell_validity[
                        "strict_valid_cells"
                    ] += 1


# ============================================================
# Save
# ============================================================

packet = {
    "analysis":
        "STAGE3_PARENT_STATE_INTERVENTION_V1",

    "collection_freeze_sha256":
        sha256(COLLECTION_FREEZE),

    "analysis_spec_sha256":
        sha256(SPEC_PATH),

    "assignment_manifest_sha256":
        sha256(ASSIGN_PATH),

    "seed_file_sha256":
        sha256(SEED_PATH),

    "bootstrap": spec["bootstrap"],

    "cell_validity": cell_validity,

    "primary_parent_state_effect":
        parent_state_effect,

    "primary_policy_x_parent_state":
        policy_interactions,

    "primary_model_x_policy_x_parent_state":
        model_policy_interactions,

    "strict_parent_state_effect":
        strict_parent_state_effect,

    "strict_policy_x_parent_state":
        strict_policy_interactions,

    "strict_model_x_policy_x_parent_state":
        strict_model_policy_interactions,
}

RESULTS.write_text(
    json.dumps(
        packet,
        indent=2,
        sort_keys=True,
    ) + "\n",
    encoding="utf-8",
)


def pp(x):
    if x is None:
        return "NA"
    return f"{100*x:+.1f} pp"


def ci(x):
    if x["ci_low"] is None:
        return "NA"

    return (
        f"[{100*x['ci_low']:+.1f}, "
        f"{100*x['ci_high']:+.1f}] pp"
    )


L = []

L += [
    "=" * 88,
    "STAGE 3 — CONTROLLED PARENT-STATE INTERVENTION",
    "=" * 88,
    "",
    (
        "Primary analysis: >=2 valid replicates "
        "per required cell."
    ),
    (
        "Strict sensitivity: all 3 valid "
        "replicates per required cell."
    ),
    "",
    f"Bootstrap draws: {B}",
    f"Bootstrap seed: {BOOTSEED}",
    "",
]

L += [
    "=" * 88,
    "A. PARENT-STATE EFFECT WITHIN ARM",
    "    final_gold(G) - final_gold(T)",
    "=" * 88,
]

for m in MODELS:
    L += ["", SHORT[m]]

    for arm in ARMS:
        x = parent_state_effect[m][arm]

        L.append(
            f"  {arm}: "
            f"{pp(x['estimate']):>10s} "
            f"95% CI {ci(x)} "
            f"N={x['n']}"
        )


L += [
    "",
    "=" * 88,
    "B. POLICY × PARENT-STATE INTERACTION",
    "=" * 88,
]

for m in MODELS:
    L += ["", SHORT[m]]

    for name, x in (
        policy_interactions[m].items()
    ):
        L.append(
            f"  {name}: "
            f"{pp(x['estimate']):>10s} "
            f"95% CI {ci(x)} "
            f"N={x['n']}"
        )


L += [
    "",
    "=" * 88,
    "C. MODEL × POLICY × PARENT-STATE",
    "=" * 88,
]

for pair, rs in (
    model_policy_interactions.items()
):
    L += ["", pair]

    for name, x in rs.items():
        L.append(
            f"  {name}: "
            f"{pp(x['estimate']):>10s} "
            f"95% CI {ci(x)} "
            f"N={x['n']}"
        )


L += [
    "",
    "=" * 88,
    "D. STRICT COMPLETE-TRIPLICATE SENSITIVITY",
    "=" * 88,
]

for m in MODELS:
    L += ["", SHORT[m]]

    for arm in ARMS:
        x = strict_parent_state_effect[m][arm]

        L.append(
            f"  parent-state {arm}: "
            f"{pp(x['estimate']):>10s} "
            f"95% CI {ci(x)} "
            f"N={x['n']}"
        )

    for name, x in (
        strict_policy_interactions[m].items()
    ):
        L.append(
            f"  interaction {name}: "
            f"{pp(x['estimate']):>10s} "
            f"95% CI {ci(x)} "
            f"N={x['n']}"
        )


REPORT.write_text(
    "\n".join(L) + "\n",
    encoding="utf-8",
)

print(
    json.dumps(
        {
            "status": "ANALYSIS_COMPLETE",
            "results": str(RESULTS),
            "report": str(REPORT),
            "n_seed_bootstrap_draws": B,
        },
        indent=2,
    )
)
