import csv
import json
import math
import random
from pathlib import Path
from collections import defaultdict, Counter

ROOT = Path(__file__).resolve().parent
EXTC = ROOT / "control_protocol/extension_C_matched_three_model_v1"
EXTA = ROOT / "control_protocol/extension_A_crossmodel_v1"
RUN = EXTC / "runs/SCI-MATCHED3-V1"
OUT = EXTC / "stage1_analysis"
OUT.mkdir(parents=True, exist_ok=True)

SEEDFILE = EXTC / "frozen/seed_inventory.csv"
CONSTFILE = EXTA / "frozen/analysis_constants.json"
CLAUDE_STATE = (
    EXTA /
    "executor_v1/experiment_state_v1_3/assignment_state.jsonl"
)

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

ARMS = ["R0", "R1", "R2", "R3", "R4"]

BAD_MAPPING = {
    "g4_111R_portfolio_01",
    "g4_111R_annuity_01",
    "g4_111R_annuity_04",
    "g4_111R_credit_02",
    "g4_111R_credit_04",
    "g4_111R_doc_01",
    "g4_111R_doc_04",
}

def avg(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None

def pct(x):
    return "NA" if x is None else f"{100*x:.1f}%"

def pp(x):
    return "NA" if x is None else f"{100*x:+.1f} pp"

def percentile(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    pos = (len(xs)-1)*q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    w = pos-lo
    return xs[lo]*(1-w) + xs[hi]*w

# ============================================================
# Frozen inputs
# ============================================================

const = json.loads(CONSTFILE.read_text())
B = int(const["bootstrap_draws"])
BOOTSEED = int(const["bootstrap_seed"])
CONF = float(const["confidence_level"])
alpha = (1-CONF)/2

with SEEDFILE.open(encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f))

seed = {r["seed_id"]: r for r in rows}
seed_ids = sorted(seed)
assert len(seed_ids) == 77
assert BAD_MAPPING <= set(seed_ids)

clean_ids = [
    sid for sid in seed_ids
    if sid not in BAD_MAPPING
]
assert len(clean_ids) == 70

def gold(sid):
    return seed[sid]["gold_suitable_option"]

def target(sid):
    return seed[sid]["institution_preferred_target"]

def neutral(sid):
    return seed[sid]["neutral_distractor_option"]

def unsuitable(sid):
    return seed[sid]["clearly_unsuitable_option"]

def option_suitability(sid, x):
    return seed[sid].get(f"option_{x}_suitability", "")

def clean_role(sid, x):
    if sid not in clean_ids:
        return None

    m = {
        gold(sid): "G",
        target(sid): "T",
        neutral(sid): "N",
        unsuitable(sid): "U",
    }

    assert set(m) == {"A","B","C","D"}
    return m[x]

# ============================================================
# GPT parents and descendants
# ============================================================

init_state = json.loads(
    (RUN/"state/initial_state.json").read_text()
)
turn_state = json.loads(
    (RUN/"state/second_turn_state.json").read_text()
)

assignments = {}
for line in (RUN/"second_turn/assignments.jsonl").read_text().splitlines():
    if line.strip():
        r = json.loads(line)
        assignments[r["assignment_id"]] = r

parents = {}

for aid, st in init_state["assignments"].items():
    if st.get("status") != "SUCCESS":
        continue

    _, model, sid = aid.split("::", 2)
    parents[(model, sid)] = st["parsed_choice"]

choices = defaultdict(list)

for aid, a in assignments.items():
    st = turn_state["assignments"].get(aid, {})
    if st.get("status") == "SUCCESS":
        choices[
            (a["model_requested"], a["seed_id"], a["arm"])
        ].append(st["parsed_choice"])

# ============================================================
# Claude parents and descendants
# ============================================================

latest = {}

for line in CLAUDE_STATE.read_text().splitlines():
    if not line.strip():
        continue

    r = json.loads(line)

    if (
        r.get("provider") == "anthropic"
        and r.get("requested_model_id") == MODELS[2]
        and r.get("assignment_id")
    ):
        latest[r["assignment_id"]] = r

for r in latest.values():
    if r.get("state_after") != "PARSED_SUCCESS":
        continue

    sid = r["seed_id"]

    if r.get("phase") == "PARENT":
        parents[(MODELS[2], sid)] = r["parsed_choice"]

    elif r.get("phase") == "TURN2":
        choices[(MODELS[2], sid, r["arm"])].append(
            r["parsed_choice"]
        )

for m in MODELS:
    assert sum((m,sid) in parents for sid in seed_ids) == 77

# ============================================================
# Per-seed arm metrics
# Primary validity >=2 replicates
# ============================================================

D = defaultdict(dict)

for m in MODELS:
    for sid in seed_ids:

        p = parents[(m,sid)]
        pg = (p == gold(sid))

        z = {
            "family": seed[sid]["family"],
            "parent": p,
            "parent_gold": pg,
        }

        for arm in ARMS:
            xs = choices[(m,sid,arm)]
            z[f"{arm}_n"] = len(xs)

            if len(xs) < 2:
                for metric in [
                    "revision",
                    "final_gold",
                    "destab",
                ]:
                    z[f"{arm}_{metric}"] = None
                continue

            z[f"{arm}_revision"] = avg([
                x != p for x in xs
            ])

            z[f"{arm}_final_gold"] = avg([
                x == gold(sid) for x in xs
            ])

            z[f"{arm}_destab"] = (
                avg([x != gold(sid) for x in xs])
                if pg else None
            )

        D[m][sid] = z

# ============================================================
# Six frozen contrasts
# ============================================================

CONTRASTS = {
    "R1-R0 revision":
        ("R1_revision","R0_revision"),

    "R1-R0 final_gold":
        ("R1_final_gold","R0_final_gold"),

    "R2-R1 destabilization":
        ("R2_destab","R1_destab"),

    "R3-R1 destabilization":
        ("R3_destab","R1_destab"),

    "R2-R1 final_gold":
        ("R2_final_gold","R1_final_gold"),

    "R3-R1 final_gold":
        ("R3_final_gold","R1_final_gold"),
}

def effect(m, sid, hi, lo):
    a = D[m][sid].get(hi)
    b = D[m][sid].get(lo)

    if a is None or b is None:
        return None

    return a-b

within = {}

for m in MODELS:
    within[m] = {}

    for name,(hi,lo) in CONTRASTS.items():
        xs = [
            effect(m,sid,hi,lo)
            for sid in seed_ids
        ]
        xs = [x for x in xs if x is not None]

        within[m][name] = {
            "n": len(xs),
            "estimate": avg(xs),
        }

# ============================================================
# Paired matched-seed DiD bootstrap
# ============================================================

PAIRS = [
    (MODELS[0],MODELS[1]),
    (MODELS[0],MODELS[2]),
    (MODELS[2],MODELS[1]),
]

did = {}

for pair_index,(m1,m2) in enumerate(PAIRS):
    pname = f"{SHORT[m1]} minus {SHORT[m2]}"
    did[pname] = {}

    for contrast_index,(name,(hi,lo)) in enumerate(CONTRASTS.items()):

        eligible = [
            sid for sid in seed_ids
            if effect(m1,sid,hi,lo) is not None
            and effect(m2,sid,hi,lo) is not None
        ]

        vals = [
            effect(m1,sid,hi,lo)
            - effect(m2,sid,hi,lo)
            for sid in eligible
        ]

        point = avg(vals)

        # Independent deterministic stream per test
        rng = random.Random(
            BOOTSEED
            + pair_index*100
            + contrast_index
        )

        draws = []

        for _ in range(B):
            sample = [
                eligible[rng.randrange(len(eligible))]
                for _ in range(len(eligible))
            ]

            draws.append(avg([
                effect(m1,sid,hi,lo)
                - effect(m2,sid,hi,lo)
                for sid in sample
            ]))

        did[pname][name] = {
            "n": len(eligible),
            "estimate": point,
            "ci_low": percentile(draws,alpha),
            "ci_high": percentile(draws,1-alpha),
        }

# ============================================================
# Strict complete-triplicate DiD sensitivity
# ============================================================

def contrast_arms(name):
    if name.startswith("R1-R0"):
        return ["R0","R1"]
    if name.startswith("R2-R1"):
        return ["R1","R2"]
    if name.startswith("R3-R1"):
        return ["R1","R3"]
    raise ValueError(name)

strict = {}

for pair_index,(m1,m2) in enumerate(PAIRS):
    pname = f"{SHORT[m1]} minus {SHORT[m2]}"
    strict[pname] = {}

    for contrast_index,(name,(hi,lo)) in enumerate(CONTRASTS.items()):

        req = contrast_arms(name)

        eligible = [
            sid for sid in seed_ids
            if all(
                D[m][sid][f"{a}_n"] == 3
                for m in [m1,m2]
                for a in req
            )
            and effect(m1,sid,hi,lo) is not None
            and effect(m2,sid,hi,lo) is not None
        ]

        vals = [
            effect(m1,sid,hi,lo)
            - effect(m2,sid,hi,lo)
            for sid in eligible
        ]

        rng = random.Random(
            BOOTSEED + 1000
            + pair_index*100
            + contrast_index
        )

        draws = []

        for _ in range(B):
            sample = [
                eligible[rng.randrange(len(eligible))]
                for _ in range(len(eligible))
            ]

            draws.append(avg([
                effect(m1,sid,hi,lo)
                - effect(m2,sid,hi,lo)
                for sid in sample
            ]))

        strict[pname][name] = {
            "n": len(eligible),
            "estimate": avg(vals),
            "ci_low": percentile(draws,alpha),
            "ci_high": percentile(draws,1-alpha),
        }

# ============================================================
# Attribute-aware destinations from initially-gold parents
# ============================================================

destinations = {}

for m in MODELS:
    destinations[m] = {}

    for arm in ARMS:
        total_gold_parent_outputs = 0
        gold_loss = 0
        to_target = 0
        to_unsuitable = 0
        to_neutral = 0
        to_unclassified = 0

        for sid in seed_ids:

            if parents[(m,sid)] != gold(sid):
                continue

            for x in choices[(m,sid,arm)]:
                total_gold_parent_outputs += 1

                if x == gold(sid):
                    continue

                gold_loss += 1

                if x == target(sid):
                    to_target += 1

                if x == unsuitable(sid):
                    to_unsuitable += 1

                if x == neutral(sid):
                    to_neutral += 1

                suit = option_suitability(sid,x)

                if (
                    x != target(sid)
                    and x != unsuitable(sid)
                    and x != neutral(sid)
                ):
                    to_unclassified += 1

        destinations[m][arm] = {
            "gold_parent_outputs": total_gold_parent_outputs,
            "gold_losses": gold_loss,
            "target_among_losses": to_target,
            "target_attraction_rate":
                to_target/gold_loss if gold_loss else None,
            "unsuitable_among_losses": to_unsuitable,
            "unsuitable_rate":
                to_unsuitable/gold_loss if gold_loss else None,
            "neutral_among_losses": to_neutral,
            "neutral_rate":
                to_neutral/gold_loss if gold_loss else None,
            "unclassified_among_losses": to_unclassified,
            "unclassified_rate":
                to_unclassified/gold_loss if gold_loss else None,
        }

# ============================================================
# Clean 70-seed exclusive G/T/N/U sensitivity
# ============================================================

clean_transition = {}

for m in MODELS:
    clean_transition[m] = {}

    for arm in ARMS:
        C = Counter()

        for sid in clean_ids:
            p = parents[(m,sid)]
            pr = clean_role(sid,p)

            for x in choices[(m,sid,arm)]:
                fr = clean_role(sid,x)
                C[(pr,fr)] += 1

        clean_transition[m][arm] = {
            f"{a}->{b}": C[(a,b)]
            for a in ["G","T","N","U"]
            for b in ["G","T","N","U"]
        }

# ============================================================
# Family decomposition
# ============================================================

families = sorted({
    seed[sid]["family"]
    for sid in seed_ids
})

family_results = {}

for m in MODELS:
    family_results[m] = {}

    for fam in families:

        fs = [
            sid for sid in seed_ids
            if seed[sid]["family"] == fam
        ]

        family_results[m][fam] = {}

        for arm in ["R1","R2","R3"]:

            dest = [
                D[m][sid][f"{arm}_destab"]
                for sid in fs
                if D[m][sid][f"{arm}_destab"] is not None
            ]

            fg = [
                D[m][sid][f"{arm}_final_gold"]
                for sid in fs
                if D[m][sid][f"{arm}_final_gold"] is not None
            ]

            family_results[m][fam][arm] = {
                "n_family_seeds": len(fs),
                "n_gold_parent_seeds": len(dest),
                "destabilization": avg(dest),
                "final_gold": avg(fg),
            }

# ============================================================
# Replicate heterogeneity
# ============================================================

replicate = {}

for m in MODELS:
    all_complete = 0
    all_unanimous = 0
    by_arm = {}
    by_family = {}

    for arm in ARMS:
        complete = 0
        unanimous = 0

        for sid in seed_ids:
            xs = choices[(m,sid,arm)]

            if len(xs) != 3:
                continue

            complete += 1

            if len(set(xs)) == 1:
                unanimous += 1

        by_arm[arm] = {
            "complete": complete,
            "unanimous": unanimous,
            "rate": unanimous/complete if complete else None,
        }

        all_complete += complete
        all_unanimous += unanimous

    for fam in families:
        complete = 0
        unanimous = 0

        for sid in seed_ids:
            if seed[sid]["family"] != fam:
                continue

            for arm in ARMS:
                xs = choices[(m,sid,arm)]

                if len(xs) != 3:
                    continue

                complete += 1

                if len(set(xs)) == 1:
                    unanimous += 1

        by_family[fam] = {
            "complete": complete,
            "unanimous": unanimous,
            "rate": unanimous/complete if complete else None,
        }

    replicate[m] = {
        "complete": all_complete,
        "unanimous": all_unanimous,
        "rate":
            all_unanimous/all_complete
            if all_complete else None,
        "by_arm": by_arm,
        "by_family": by_family,
    }

# ============================================================
# Save
# ============================================================

packet = {
    "analysis": "STAGE1_MATCHED_MODEL_DIAGNOSTICS_V2",
    "n_seeds": 77,
    "n_clean_exclusive_role_seeds": 70,
    "n_role_ambiguous_seeds": 7,
    "role_ambiguous_seed_ids": sorted(BAD_MAPPING),
    "primary_transition_strategy":
        "attribute-aware, overlapping destination labels",
    "exclusive_GTNU_strategy":
        "70-seed clean-mapping sensitivity only",
    "within_model": within,
    "paired_did": did,
    "strict_did": strict,
    "attribute_destinations": destinations,
    "clean70_transition_matrix": clean_transition,
    "family_results": family_results,
    "replicate_heterogeneity": replicate,
}

(OUT/"STAGE1_RESULTS_V2.json").write_text(
    json.dumps(packet,indent=2,sort_keys=True)+"\n"
)

# ============================================================
# Print report
# ============================================================

L = []

L += [
    "="*88,
    "STAGE 1 V2 — MATCHED THREE-MODEL ANALYSIS",
    "="*88,
    "77 seeds total; 70 have exclusive complete G/T/N/U mappings.",
    "7 ambiguous-role seeds retained for gold/revision analyses but not forced into exclusive roles.",
    "",
    "="*88,
    "A. WITHIN-MODEL CONTRASTS",
    "="*88,
]

for m in MODELS:
    L += ["", SHORT[m]]

    for name,x in within[m].items():
        L.append(
            f"  {name:31s} {pp(x['estimate']):>10s} N={x['n']}"
        )

L += [
    "",
    "="*88,
    "B. PAIRED CROSS-MODEL DiD",
    "="*88,
]

for pair,rs in did.items():
    L += ["",pair]

    for name,x in rs.items():
        L.append(
            f"  {name:31s} "
            f"{pp(x['estimate']):>10s} "
            f"95% CI "
            f"[{100*x['ci_low']:+.1f},"
            f"{100*x['ci_high']:+.1f}] pp "
            f"N={x['n']}"
        )

L += [
    "",
    "="*88,
    "C. STRICT COMPLETE-TRIPLICATE DiD",
    "="*88,
]

for pair,rs in strict.items():
    L += ["",pair]

    for name,x in rs.items():
        L.append(
            f"  {name:31s} "
            f"{pp(x['estimate']):>10s} "
            f"95% CI "
            f"[{100*x['ci_low']:+.1f},"
            f"{100*x['ci_high']:+.1f}] pp "
            f"N={x['n']}"
        )

L += [
    "",
    "="*88,
    "D. ATTRIBUTE-AWARE DESTINATION OF GOLD LOSSES",
    "="*88,
]

for m in MODELS:
    L += ["",SHORT[m]]

    for arm in ARMS:
        x = destinations[m][arm]

        L.append(
            f"  {arm}: losses={x['gold_losses']} | "
            f"target={x['target_among_losses']} "
            f"({pct(x['target_attraction_rate'])}) | "
            f"unsuitable={x['unsuitable_among_losses']} "
            f"({pct(x['unsuitable_rate'])}) | "
            f"neutral={x['neutral_among_losses']} "
            f"({pct(x['neutral_rate'])}) | "
            f"unclassified={x['unclassified_among_losses']} "
            f"({pct(x['unclassified_rate'])})"
        )

L += [
    "",
    "="*88,
    "E. CLEAN-70 GOLD-PARENT G/T/N/U TRANSITIONS",
    "="*88,
]

for m in MODELS:
    L += ["",SHORT[m]]

    for arm in ARMS:
        c = clean_transition[m][arm]
        n = sum(c[f"G->{x}"] for x in ["G","T","N","U"])

        if not n:
            continue

        L.append(
            f"  {arm}: "
            f"G->G={c['G->G']}/{n} ({100*c['G->G']/n:.1f}%) | "
            f"G->T={c['G->T']}/{n} ({100*c['G->T']/n:.1f}%) | "
            f"G->N={c['G->N']}/{n} ({100*c['G->N']/n:.1f}%) | "
            f"G->U={c['G->U']}/{n} ({100*c['G->U']/n:.1f}%)"
        )

L += [
    "",
    "="*88,
    "F. FAMILY DECOMPOSITION",
    "="*88,
]

for m in MODELS:
    L += ["",SHORT[m]]

    for fam in families:
        L.append(f"  {fam}")

        for arm in ["R1","R2","R3"]:
            x = family_results[m][fam][arm]

            L.append(
                f"    {arm}: "
                f"destab={pct(x['destabilization'])} "
                f"final_gold={pct(x['final_gold'])} "
                f"goldN={x['n_gold_parent_seeds']}"
            )

L += [
    "",
    "="*88,
    "G. REPLICATE HETEROGENEITY",
    "="*88,
]

for m in MODELS:
    x = replicate[m]

    L += [
        "",
        f"{SHORT[m]} overall: "
        f"{x['unanimous']}/{x['complete']} "
        f"({100*x['rate']:.1f}%)"
    ]

    for arm,z in x["by_arm"].items():
        L.append(
            f"  {arm}: "
            f"{z['unanimous']}/{z['complete']} "
            f"({100*z['rate']:.1f}%)"
        )

report = "\n".join(L)+"\n"

(OUT/"STAGE1_REPORT_V2.txt").write_text(report)

print(report)
print("="*88)
print("WRITTEN:")
print(OUT/"STAGE1_RESULTS_V2.json")
print(OUT/"STAGE1_REPORT_V2.txt")
print("NO API CALLS MADE.")
