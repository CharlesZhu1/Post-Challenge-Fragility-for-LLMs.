#!/usr/bin/env python3
"""Reproduce all study summary statistics, no API/network calls, Python stdlib only."""
from pathlib import Path
import hashlib, json, subprocess, sys
ROOT=Path(__file__).resolve().parent
C=ROOT/'control_protocol/extension_C_matched_three_model_v1'

def verify(actual_path,expected_path,ignore=()):
    actual=json.loads(actual_path.read_text(encoding='utf-8'))
    expected=json.loads(expected_path.read_text(encoding='utf-8'))
    for k in ignore:
        actual.pop(k,None);expected.pop(k,None)
    if actual!=expected:
        raise SystemExit(f'FAIL: results do not match {expected_path.name}')
    print('PASS:',expected_path.name, '(ignored metadata: '+', '.join(ignore)+')' if ignore else '(exact JSON equality)',flush=True)

jobs=[
 ('Study 1', ROOT/'reproduce_study1.py', [], C/'stage1_analysis/STAGE1_RESULTS_V2.json',ROOT/'expected/STAGE1_RESULTS_V2.json',()),
 ('Study 2', C/'stage3_parent_state_intervention/stage3_analysis/run_stage3_analysis_v1.py', [], C/'stage3_parent_state_intervention/stage3_analysis/STAGE3_RESULTS_V1.json',ROOT/'expected/STAGE3_RESULTS_V1.json',()),
 ('Study 3 sequential', C/'stage4_reversibility_v1/stage4_analysis_r1_v1/run_stage4_analysis_r1_v1.py', [], C/'stage4_reversibility_v1/stage4_analysis_r1_v1/STAGE4_RESULTS_R1_V1.json',ROOT/'expected/STAGE4_RESULTS_R1_V1.json',('created_utc',)),
 ('Study 3 controlled history', C/'stage4_reversibility_v1/controlled_history_v1/analysis/run_controlled_history_analysis_v1.py', ['--collection',str(C/'stage4_reversibility_v1/controlled_history_v1/runs/CTLHIST-STUDY3-PROD-V1/attempts.jsonl')], C/'stage4_reversibility_v1/controlled_history_v1/analysis/CONTROLLED_HISTORY_RESULTS_V1.json',ROOT/'expected/CONTROLLED_HISTORY_RESULTS_V1.json',('created_utc',)),
]
for label,script,args,actual,expected,ignore in jobs:
    print('RUN:',label,flush=True)
    p=subprocess.run([sys.executable,str(script),*args],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    if p.returncode:
        print(p.stdout[-4000:]);raise SystemExit(f'{label} failed, exit {p.returncode}')
    verify(actual,expected,ignore)
print('ALL FOUR ANALYSIS RUNS PASSED; ZERO MODEL API CALLS',flush=True)
