import json, numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
D = json.load(open('results/paper-data-amendment010.json'))
C = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4']
SRC = ['MTBench', 'HANNA', 'SummEval']; KIND = ['choice', 'noul', 'score']
plt.rcParams.update({'font.size': 8, 'font.family': 'serif', 'axes.spines.top': False, 'axes.spines.right': False,
                     'pdf.fonttype': 42, 'axes.titlesize': 8.5})
out = 'figures/paper/'
def save(fig, name):
    fig.savefig(out + name + '.pdf', bbox_inches='tight'); fig.savefig(out + name + '.png', dpi=300, bbox_inches='tight'); plt.close(fig)

# Fig 2: (a) A1 by source and question type, (b) order magnitude by gap bin
fig, ax = plt.subplots(1, 2, figsize=(6.6, 2.3), gridspec_kw={'width_ratios': [1, 1.25]})
e1 = {(r['hypothesis'], r['source']): r for r in D['E1']}
for k, kind in enumerate(KIND):
    for s, src in enumerate(SRC):
        r = e1[('A1_' + kind, src)]; x = k + (s - 1) * 0.22
        ax[0].errorbar(x, r['estimate'], yerr=[[r['estimate'] - r['ci95'][0]], [r['ci95'][1] - r['estimate']]],
                       fmt='o', ms=3.5, color=C[s], capsize=2, label=src if k == 0 else None)
ax[0].axhline(0, color='grey', lw=.6); ax[0].set_xticks(range(3)); ax[0].set_xticklabels(['Choice', 'Noul', 'Score'])
ax[0].set_ylabel('Order shift on identical copies'); ax[0].set_title('(a) A1, positive = first slot favoured')
ax[0].legend(frameon=False, fontsize=7)
for k, kind in enumerate(KIND):
    rows = sorted([g for g in D['gap_by_bin'] if g['kind'] == kind], key=lambda g: g['gap_bin'])
    xs = [g['gap_bin'] + (k - 1) * 0.12 for g in rows]; ys = [g['estimate'] for g in rows]
    err = [[g['estimate'] - g['ci95'][0] for g in rows], [g['ci95'][1] - g['estimate'] for g in rows]]
    ax[1].errorbar(xs, ys, yerr=err, fmt='-o', ms=3, lw=1, color=C[k], capsize=2, label=kind.capitalize())
ax[1].set_xticks(range(5)); ax[1].set_xticklabels(['0\n(identical)', '1', '2', '3', '4\n(largest)'])
ax[1].set_xlabel('Human-annotated quality-gap bin'); ax[1].set_ylabel('Order-effect magnitude (logit² units)')
ax[1].set_title('(b) Order-effect magnitude by quality gap'); ax[1].legend(frameon=False, fontsize=7)
fig.tight_layout(); save(fig, 'fig_order_effects')

# Fig 3: (a) decision change by confidence, (b) listwise position mass
fig, ax = plt.subplots(1, 2, figsize=(6.6, 2.3))
rows = D['E3']['rows']; bins = ['below 0.6', '0.6 to 0.9', '0.9 or above']
for j, (metric, lab) in enumerate((('cross', 'Order reversed'), ('same', 'Same order repeated'))):
    rr = [next(r for r in rows if r['bin'] == b and r['metric'] == metric) for b in bins]
    x = np.arange(3) + (j - .5) * 0.3
    ax[0].bar(x, [100 * r['rate'] for r in rr], width=.3, color=C[j], label=lab, error_kw=dict(ecolor='#444444', lw=.8),
              yerr=[[100 * (r['rate'] - r['ci95'][0]) for r in rr], [100 * (r['ci95'][1] - r['rate']) for r in rr]], capsize=2)
ax[0].set_xticks(range(3)); ax[0].set_xticklabels(['< 0.6', '0.6 to 0.9', '≥ 0.9'])
ax[0].set_xlabel("Jev's top-option probability"); ax[0].set_ylabel('Decisions changed (%)')
ax[0].set_title('(a) Choice decisions changed, nonidentical pairs'); ax[0].legend(frameon=False, fontsize=7)
e4 = D['E4']; ks = [r['cardinality'] for r in e4]
for j, (key, lab) in enumerate((('first', 'First position'), ('last', 'Last position'))):
    ratio = [r[key + '_position_mass'] / r['uniform'] for r in e4]
    ax[1].plot(range(len(ks)), ratio, '-o', ms=3, color=C[j + 2], label=lab)
    if key == 'first':
        lo = [r['first_ci95'][0] / r['uniform'] for r in e4]; hi = [r['first_ci95'][1] / r['uniform'] for r in e4]
        ax[1].fill_between(range(len(ks)), lo, hi, color=C[2], alpha=.2, lw=0)
ax[1].axhline(1, color='grey', lw=.6, ls='--'); ax[1].set_xticks(range(len(ks))); ax[1].set_xticklabels(ks)
ax[1].set_xlabel('Number of identical candidates'); ax[1].set_ylabel('Probability mass / uniform share')
ax[1].set_title('(b) Listwise identical copies'); ax[1].legend(frameon=False, fontsize=7)
fig.tight_layout(); save(fig, 'fig_confidence_listwise')

# Fig 4 (appendix): reference judges and C-iii by source
fig, ax = plt.subplots(1, 2, figsize=(6.6, 2.3))
def cell(cells, kind, src, axis='state_order', gap0=True):
    return next(c for c in cells if c['probe'] == 'A' and c['axis'] == axis and c['kind'] == kind and c['source'] == src and (c['gap_bin'] == 0) == gap0)
series = [('Jev 1.13', D['reference']['anthropic']['jev']), ('Claude Haiku 4.5', D['reference']['anthropic']['ref']),
          ('DeepSeek V4 Flash', D['reference']['together']['ref'])]
for j, (lab, cells) in enumerate(series):
    for s, src in enumerate(SRC):
        c = cell(cells, 'choice', src); x = s + (j - 1) * 0.25
        ci = c.get('ci95') or [c['mean'], c['mean']]
        ax[0].errorbar(x, c['mean'], yerr=[[c['mean'] - ci[0]], [ci[1] - c['mean']]], fmt='os^'[j], ms=3.5, color=C[j], capsize=2,
                       label=lab if s == 0 else None)
ax[0].axhline(0, color='grey', lw=.6); ax[0].set_xticks(range(3)); ax[0].set_xticklabels(SRC)
ax[0].set_ylabel('Choice order shift, identical copies'); ax[0].set_title('(a) Matched subset, 40 tasks'); ax[0].legend(frameon=False, fontsize=7, loc='upper center', bbox_to_anchor=(0.5, -0.18), ncol=3); ax[0].set_ylim(-0.2, 0.6)
for k, kind in enumerate(KIND):
    for s, src in enumerate(SRC):
        r = e1[('Ciii_' + kind, src)]; x = k + (s - 1) * 0.22
        ax[1].errorbar(x, r['estimate'], yerr=[[r['estimate'] - r['ci95'][0]], [r['ci95'][1] - r['estimate']]], fmt='o', ms=3.5,
                       color=C[s], capsize=2, label=src if k == 0 else None)
ax[1].axhline(0, color='grey', lw=.6); ax[1].set_xticks(range(3)); ax[1].set_xticklabels(['Choice', 'Noul', 'Score'])
ax[1].set_ylabel('Jev-style minus neutral format'); ax[1].set_title('(b) C-iii by source (exploratory)'); ax[1].legend(frameon=False, fontsize=7, loc='upper center', bbox_to_anchor=(0.5, -0.18), ncol=3)
fig.tight_layout(); save(fig, 'fig_reference_format')
print('ok')
