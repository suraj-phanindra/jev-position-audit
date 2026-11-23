"""POST HOC: figure and table from posthoc-direction-20261118.json. Descriptive only, no tests."""
import json, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
d = json.load(open('posthoc/posthoc-direction-20261118.json'))
rows = d['rows']
for r in rows:
    print(r['kind'], r['gap_bin'], round(r['estimate'],4), [round(x,4) for x in r['ci95']],
          round(100*r['share_first_favoured'],1), round(100*r['share_second_favoured'],1), r['stimuli'], r['tasks'],
          {s: (round(v['estimate'],4), [round(x,4) for x in v['ci95']], round(100*v['share_first_favoured'],1)) for s, v in r['per_source'].items()})
neg = [(r['kind'], r['gap_bin'], s, round(v['estimate'],4)) for r in rows if r['gap_bin'] >= 1 for s, v in r['per_source'].items() if v['estimate'] < 0]
print('NEGATIVE per-source cells bins1-4:', neg)
plt.rcParams.update({'font.family': 'serif', 'font.size': 8})
fig, ax = plt.subplots(figsize=(3.2, 2.2))
pal = {'choice': '#2a78d6', 'noul': '#eb6834', 'score': '#1baf7a'}
lab = {'choice': 'Choice', 'noul': 'Noul', 'score': 'Score'}
off = {'choice': -0.12, 'noul': 0.0, 'score': 0.12}
ax.axhline(0, color='0.5', lw=0.7)
for k in ('choice', 'noul', 'score'):
    rr = sorted([r for r in rows if r['kind'] == k], key=lambda r: r['gap_bin'])
    x = [r['gap_bin'] + off[k] for r in rr]; y = [r['estimate'] for r in rr]
    lo = [r['estimate'] - r['ci95'][0] for r in rr]; hi = [r['ci95'][1] - r['estimate'] for r in rr]
    ax.errorbar(x, y, yerr=[lo, hi], color=pal[k], marker='o', ms=3, lw=1, capsize=2, elinewidth=0.8, label=lab[k])
ax.set_xticks(range(5)); ax.set_xticklabels(['0 (identical)', '1', '2', '3', '4 (largest)'])
ax.set_xlabel('Gap bin'); ax.set_ylabel('Signed order shift')
ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
ax.legend(frameon=False, fontsize=7)
fig.tight_layout()
fig.savefig('figures/paper/fig_posthoc_direction.pdf'); fig.savefig('figures/paper/fig_posthoc_direction.png', dpi=300)
def f(v): s = f'{v:.3f}'; return s.replace('-', '$-$')
L = [r'% POST HOC, descriptive, added 2026-11-18. Generated from posthoc-direction-20261118.json. No tests.',
     r'\begin{tabular}{llrcr}', r'\toprule', r'Type & Bin & Estimate & 95\% CI & First slot favoured (\%) \\', r'\midrule']
for k in ('choice', 'noul', 'score'):
    rr = sorted([r for r in rows if r['kind'] == k], key=lambda r: r['gap_bin'])
    for i, r in enumerate(rr):
        L.append(f"{lab[k] if i == 0 else ''} & {r['gap_bin']} & {f(r['estimate'])} & [{f(r['ci95'][0])}, {f(r['ci95'][1])}] & {100*r['share_first_favoured']:.1f} \\\\")
    if k != 'score': L.append(r'\midrule')
L += [r'\bottomrule', r'\end{tabular}']
open('tables/tab_posthoc_direction.tex', 'x').write('\n'.join(L) + '\n')
