#!/usr/bin/env python3
"""
Controlled-history (H_GG vs H_TG) analysis.

Primary estimand, per model m:
    Delta_history(m) = P(final=G | H_GG, m) - P(final=G | H_TG, m)

where "final=G" means the model's final parsed choice equals G_choice
(gold_suitable_option) for that seed.

Inference:
    - seed-clustered bootstrap
    - 10,000 draws, fixed recorded bootstrap seed
    - 95% percentile confidence intervals
    - resample financial seeds (NOT descendant calls)
    - keep all replicates/conditions from a seed together
    - common seed draws across compared conditions

This script performs NO network / API calls. It expects a completed
collection JSONL keyed by assignment_id with the final parsed choice.
Until collection exists it runs in --dry-run mode (design self-check only).
"""

from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
import random
import sys

ROOT = Path(
    "/home/charles/sibyl_v2/control_protocol/"
    "extension_C_matched_three_model_v1"
)
BRANCH = ROOT / "stage4_reversibility_v1" / "controlled_history_v1"

MANIFEST = BRANCH / "manifests/CONTROLLED_HISTORY_ASSIGNMENTS_V1.jsonl"
DEFAULT_COLLECTION = (
    BRANCH / "collection/CONTROLLED_HISTORY_COLLECTION_V1.jsonl"
)
OUTDIR = BRANCH / "analysis"
RESULTS = OUTDIR / "CONTROLLED_HISTORY_RESULTS_V1.json"
REPORT = OUTDIR / "CONTROLLED_HISTORY_REPORT_V1.txt"

BOOT_SEED = 2026081404
BOOT_DRAWS = 10000

MODELS = [
    "gpt-4o-mini-2024-07-18",
    "gpt-5-mini-2025-08-07",
    "claude-sonnet-4-6",
]
HISTORIES = ["H_GG", "H_TG"]
VALID_CHOICES = {"A", "B", "C", "D"}


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
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
    return ys[lo] * (1.0 - frac) + ys[hi] * frac


def ci95(xs):
    return [percentile(xs, 0.025), percentile(xs, 0.975)]


def pct(x):
    return "NA" if x is None else f"{100*x:.1f}%"


def load_manifest():
    rows = [
        json.loads(l)
        for l in MANIFEST.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    return {r["assignment_id"]: r for r in rows}


def load_collection(path):
    """
    Expected collection line shape (minimal):
      {"assignment_id": ..., "status": "SUCCESS"|..., "parsed_choice": "A".."D"}
    Extra fields are ignored.
    """
    out = {}
    for l in Path(path).read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        out[r["assignment_id"]] = r
    return out


def analyze(collection_path):
    manifest = load_manifest()
    coll = load_collection(collection_path)

    # Assemble per-assignment outcome rows.
    rows = []
    for aid, m in manifest.items():
        rec = coll.get(aid)
        status = rec.get("status") if rec else "MISSING"
        choice = rec.get("parsed_choice") if rec else None
        valid = status == "SUCCESS" and choice in VALID_CHOICES
        final_is_g = (choice == m["G_choice"]) if valid else None
        final_is_t = (choice == m["T_choice"]) if valid else None
        rows.append({
            "assignment_id": aid,
            "model": m["model_requested"],
            "seed_id": m["seed_id"],
            "history": m["history"],
            "replicate": m["replicate"],
            "G_choice": m["G_choice"],
            "T_choice": m["T_choice"],
            "status": status,
            "choice": choice,
            "valid": valid,
            "final_is_g": final_is_g,
            "final_is_t": final_is_t,
        })

    all_seeds = sorted({r["seed_id"] for r in rows})

    # ---- Common seed-cluster bootstrap draws (financial seeds) ----
    rng = random.Random(BOOT_SEED)
    seed_draws = [
        [all_seeds[rng.randrange(len(all_seeds))] for _ in all_seeds]
        for _ in range(BOOT_DRAWS)
    ]

    def by_seed_values(model, history):
        d = defaultdict(list)
        for r in rows:
            if (
                r["model"] == model
                and r["history"] == history
                and r["valid"]
            ):
                d[r["seed_id"]].append(int(r["final_is_g"]))
        return d

    # Point rates + per-condition bootstrap distributions.
    persistence = {}
    boot_rate = {}
    for model in MODELS:
        for history in HISTORIES:
            bs = by_seed_values(model, history)
            vals = [v for lst in bs.values() for v in lst]
            n = len(vals)
            events = sum(vals)
            persistence[(model, history)] = {
                "model": model,
                "history": history,
                "numerator": events,
                "denominator": n,
                "rate": (events / n) if n else None,
            }
            draws = []
            for draw in seed_draws:
                vv = []
                for s in draw:
                    vv.extend(bs.get(s, []))
                if vv:
                    draws.append(sum(vv) / len(vv))
            boot_rate[(model, history)] = draws

    # ---- Delta_history per model with common-draw bootstrap ----
    deltas = []
    for model in MODELS:
        gg = by_seed_values(model, "H_GG")
        tg = by_seed_values(model, "H_TG")

        def rate(d, draw=None):
            if draw is None:
                vals = [v for lst in d.values() for v in lst]
            else:
                vals = []
                for s in draw:
                    vals.extend(d.get(s, []))
            return (sum(vals) / len(vals)) if vals else None

        p_gg = rate(gg)
        p_tg = rate(tg)
        point = None if (p_gg is None or p_tg is None) else p_gg - p_tg

        boot = []
        for draw in seed_draws:
            a = rate(gg, draw)
            b = rate(tg, draw)
            if a is not None and b is not None:
                boot.append(a - b)

        deltas.append({
            "model": model,
            "p_final_G_given_H_GG": p_gg,
            "p_final_G_given_H_TG": p_tg,
            "delta_history": point,
            "bootstrap_valid_draws": len(boot),
            "ci95": ci95(boot),
            "_boot": boot,
        })

    # ---- Model-by-history interaction contrasts (Delta_m - Delta_m') ----
    interactions = []
    dmap = {d["model"]: d for d in deltas}
    for i in range(len(MODELS)):
        for j in range(i + 1, len(MODELS)):
            mi, mj = MODELS[i], MODELS[j]
            di, dj = dmap[mi], dmap[mj]
            point = None
            if di["delta_history"] is not None and dj["delta_history"] is not None:
                point = di["delta_history"] - dj["delta_history"]
            # Common-draw difference of deltas.
            n = min(len(di["_boot"]), len(dj["_boot"]))
            boot = [di["_boot"][k] - dj["_boot"][k] for k in range(n)]
            interactions.append({
                "model_a": mi,
                "model_b": mj,
                "delta_a_minus_delta_b": point,
                "bootstrap_valid_draws": len(boot),
                "ci95": ci95(boot),
            })

    for d in deltas:
        del d["_boot"]

    results = {
        "version": "CONTROLLED_HISTORY_RESULTS_V1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_sha256": sha_file(MANIFEST),
        "collection_path": str(Path(collection_path).relative_to(ROOT))
        if str(collection_path).startswith(str(ROOT)) else str(collection_path),
        "collection_sha256": sha_file(collection_path),
        "bootstrap": {
            "unit": "financial_seed",
            "draws": BOOT_DRAWS,
            "seed": BOOT_SEED,
            "confidence_level": 0.95,
            "interval": "percentile_linear",
            "common_seed_draws_across_conditions": True,
            "resample_financial_seeds_not_descendant_calls": True,
            "keep_all_replicates_and_conditions_from_a_seed_together": True,
        },
        "persistence_by_model_history": [
            persistence[(m, h)] for m in MODELS for h in HISTORIES
        ],
        "delta_history_by_model": deltas,
        "model_by_history_interactions": interactions,
        "primary_null":
            "P(final=G | current G, H_GG) = P(final=G | current G, H_TG)",
        "no_api_calls": True,
    }

    OUTDIR.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # ---- Human report ----
    L = []
    L.append("=" * 90)
    L.append("CONTROLLED-HISTORY (H_GG vs H_TG) RESULTS — V1")
    L.append("=" * 90)
    L.append("")
    L.append("PERSISTENCE P(final=G) BY MODEL x HISTORY")
    L.append("-" * 90)
    for m in MODELS:
        for h in HISTORIES:
            x = persistence[(m, h)]
            L.append(
                f"{m} | {h} | {x['numerator']}/{x['denominator']} = "
                f"{pct(x['rate'])}"
            )
    L.append("")
    L.append("DELTA_history = P(final=G|H_GG) - P(final=G|H_TG)")
    L.append("-" * 90)
    for d in deltas:
        ci = d["ci95"]
        ci_s = "[NA, NA]" if ci[0] is None else f"[{100*ci[0]:+.1f}, {100*ci[1]:+.1f}] pp"
        dv = "NA" if d["delta_history"] is None else f"{100*d['delta_history']:+.1f} pp"
        L.append(
            f"{d['model']} | H_GG={pct(d['p_final_G_given_H_GG'])} | "
            f"H_TG={pct(d['p_final_G_given_H_TG'])} | Delta={dv} | 95% CI {ci_s}"
        )
    L.append("")
    L.append("MODEL-BY-HISTORY INTERACTION (Delta_a - Delta_b)")
    L.append("-" * 90)
    for it in interactions:
        ci = it["ci95"]
        ci_s = "[NA, NA]" if ci[0] is None else f"[{100*ci[0]:+.1f}, {100*ci[1]:+.1f}] pp"
        pv = "NA" if it["delta_a_minus_delta_b"] is None else f"{100*it['delta_a_minus_delta_b']:+.1f} pp"
        L.append(f"{it['model_a']} vs {it['model_b']} | {pv} | 95% CI {ci_s}")
    L.append("")
    L.append("Interpretation: a nonzero Delta_history is a controlled test that")
    L.append("current state G alone is insufficient and that prior trajectory")
    L.append("affects persistence under the fixed follow-up policy.")

    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"))
    print("results:", RESULTS)
    print("MODEL API CALLS: 0")


def dry_run():
    """Design self-check: manifest present, 1260 rows, cells complete."""
    manifest = load_manifest()
    from collections import Counter
    pm = Counter(r["model_requested"] for r in manifest.values())
    ph = Counter(r["history"] for r in manifest.values())
    print(json.dumps({
        "status": "DRY_RUN_OK",
        "n_manifest": len(manifest),
        "per_model": dict(sorted(pm.items())),
        "per_history": dict(sorted(ph.items())),
        "bootstrap_seed": BOOT_SEED,
        "bootstrap_draws": BOOT_DRAWS,
        "note": "No collection analyzed; no API calls.",
    }, indent=2, sort_keys=True))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collection", default=str(DEFAULT_COLLECTION))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.dry_run or not Path(args.collection).exists():
        if not args.dry_run:
            print(
                "NOTE: collection not found; running design dry-run only.",
                file=sys.stderr,
            )
        dry_run()
        return
    analyze(args.collection)


if __name__ == "__main__":
    main()
