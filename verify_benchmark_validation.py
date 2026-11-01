#!/usr/bin/env python3
"""Verify saved, anonymized financial scenario annotations using only Python stdlib."""
import csv, json, collections
from pathlib import Path
here=Path(__file__).resolve().parent
root=here.parent/'control_protocol/extension_C_matched_three_model_v1'
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
ballots=read(here/'benchmark_votes_anonymized.csv')
aggregate=read(here/'benchmark_consensus.csv')
scenarios=read(root/'frozen/seed_inventory.csv')
clean=read(root/'stage3_parent_state_intervention/frozen/STAGE3_PRIMARY_SEEDS_70_V1.csv')
assert len(ballots)==len(aggregate)==len(scenarios)==77
assert len(clean)==70
seed={r['seed_id']:r for r in scenarios};clean_id={r['seed_id'] for r in clean}
assert len(seed)==77 and len(clean_id)==70
assert {r['seed_id'] for r in ballots}=={r['seed_id'] for r in aggregate}==set(seed)
assert clean_id <= set(seed)
assert all(all(r[k]==seed[r['seed_id']][k] for k in r) for r in clean)
votes={r['seed_id']:[r[f'annotator_{i}_option'] for i in (1,2,3)] for r in ballots}
total=collections.Counter()
pbar_sum=0
unanimous=majority=majority_match=0
no_majority=[]
for r in aggregate:
    sid=r['seed_id'];a=votes[sid]
    assert len(a)==3 and all(len(v)==1 and v in 'ABCD' for v in a)
    c=collections.Counter(a); total.update(a)
    assert all(int(r[f'votes_{x}'])==c[x] for x in 'ABCD')
    pbar_sum+=sum(v*(v-1) for v in c.values())/6
    winner=next((x for x in 'ABCD' if c[x]>=2),'NO_MAJORITY')
    assert r['majority_option']==winner
    assert r['gold_option']==seed[sid]['gold_suitable_option']
    assert r['family']==seed[sid]['family']
    assert int(r['included_in_study2_clean70'])==int(sid in clean_id)
    un=int(len(c)==1); ma=int(winner!='NO_MAJORITY');match=int(ma and winner==r['gold_option'])
    assert int(r['unanimous'])==un and int(r['majority_matches_gold'])==match
    unanimous+=un;majority+=ma;majority_match+=match
    if not ma: no_majority.append(sid)
n=77;m=3
pbar=pbar_sum/n
pe=sum((total[x]/(n*m))**2 for x in 'ABCD')
kap=(pbar-pe)/(1-pe)
expected=json.loads((here/'benchmark_validation_summary.json').read_text())
assert (unanimous,majority,majority_match)==(65,76,76)
assert abs(kap-expected['fleiss_kappa'])<1e-12
assert set(no_majority)==set(expected['no_majority_seed_ids'])
print(f'PASS: {n} scenarios, 3 votes/scenario, {len(clean_id)} clean Study 2 seeds')
print(f'PASS: unanimous {unanimous}, majority {majority}, majority matches gold {majority_match}, no majority {len(no_majority)}')
print(f'PASS: Fleiss kappa = {kap:.10f}')
print('NOTE: review provenance and independent-blinding evidence require author approval')
