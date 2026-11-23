"""Bounded recovery of this preflight schedule; every attempt stays in its own log."""
import time
from harness.audit import load_env,read_jsonl
from preflight.repeats import schedule,resume,run

if __name__=='__main__':
    load_env('.env')
    rows=schedule(read_jsonl('stimuli/prepared/preflight50.jsonl'),'typesafe',200)
    paths=['runs/jev-g2-20260921.jsonl','runs/jev-g2-20260921-resume1.jsonl','runs/jev-g2-20260921-resume2.jsonl']
    for number in range(3,8):
        prior=[r for p in paths for r in read_jsonl(p)]
        remaining=resume(rows,prior,retry_failed=True)
        if not remaining:break
        path=f'runs/jev-g2-20260921-resume{number}.jsonl'
        try:run(remaining,path,11000-len(prior),8,8)
        except RuntimeError:
            new=read_jsonl(path)
            failures=[r for r in new if r['status']!=200]
            if not failures or any(r['status'] not in (None,429,500,502,503,504) for r in failures):raise
            time.sleep(2)
        paths.append(path)
    else:
        prior=[r for p in paths for r in read_jsonl(p)]
        if resume(rows,prior,retry_failed=True):raise RuntimeError('Recovery limit reached; stop for diagnosis')
    print('G2 schedule complete; analysis must retain all listed attempts:',paths,flush=True)
