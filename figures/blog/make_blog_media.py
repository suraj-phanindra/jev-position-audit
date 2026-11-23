"""Blog media for the Jev position-bias audit.

Colour rules (same thing, same colour, in every visual):
  question types: Choice blue, Noul orange, Score green
  slots:          first slot gold, second slot slate
  noise floor:    light grey
Numbers: worked examples from posthoc-20261118/worked-example-candidates.json (MT-Bench, Choice,
legacy format, mean of 16 Jev calls per order); charts from results/paper-data-amendment010.json
and posthoc/posthoc-direction-20261118.json.
Usage: python figures/blog/make_blog_media.py [out_dir] [paper_data_json] [posthoc_json]
"""
import json, os, sys, textwrap
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Polygon, Circle
from matplotlib.animation import FuncAnimation, PillowWriter
from PIL import Image

OUT = sys.argv[1] if len(sys.argv) > 1 else 'figures/blog/'
PAPER_DATA = sys.argv[2] if len(sys.argv) > 2 else 'results/paper-data-amendment010.json'
POSTHOC = sys.argv[3] if len(sys.argv) > 3 else 'posthoc/posthoc-direction-20261118.json'
os.makedirs(OUT, exist_ok=True)

CHOICE, NOUL, SCORE = '#2a78d6', '#eb6834', '#1baf7a'
TYPE_COL = {'choice': CHOICE, 'noul': NOUL, 'score': SCORE}
FIRST, SECOND, FLOOR = '#d99a00', '#64748b', '#c3c9d1'
STAGE = ['#dce9fa', '#fbe3d8', '#d9f2e8', '#fcefcf', '#f8dde8']
STAGE_EDGE = [CHOICE, NOUL, SCORE, '#eda100', '#e87ba4']
INK, MUTED, CARD, BG = '#1f2933', '#6b7785', '#ffffff', '#f6f4ef'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'text.parse_math': False,
                     'axes.spines.top': False, 'axes.spines.right': False})

ENGINE_TASK = 'Which word does not belong with the others?\ntyre, steering wheel, car, engine'
ENGINE_SHORT = 'The word that does not belong with the others is "engine".'
ENGINE_LONG = ('The word that does not belong with the others is "engine." A tyre is a type of tire '
               'used on vehicles, a steering wheel is a device used to steer a vehicle, and a car is '
               'a type of automobile. An engine is a machine that converts energy into mechanical motion.')
IDENT = dict(order1=0.5575, order2=0.575)
NEAR = dict(short_first=0.475, short_second=0.5413)
STARTUP_TASK = ("A tech startup invests $8000 in software development in the first year, and then invests half of "
                "that amount in software development in the second year. What's the total amount the startup "
                "invested in software development over the two years?")
STARTUP_RIGHT = ('The startup invested $8000 in the first year and half of that amount, which is $4000, in the second '
                 'year. So the total amount invested in software development over the two years is: $8000 + $4000 = $12,000')
STARTUP_WRONG = 'The total amount the startup invested in software development over the two years is $16,000.'
STEPS = [
    ('1  Real data', '3 human-rated datasets\nMT-Bench, HANNA, SummEval\n212 tasks'),
    ('2  Build pairs', 'identical copy (a true tie)\n+ pairs with small to large\nhuman-rated quality gaps'),
    ('3  Swap and repeat', 'show A then B, and B then A\nask every request twice\nalso swap question order, format'),
    ('4  Ask the judges', 'Jev 1.13: probabilities\nHaiku 4.5, DeepSeek V4 Flash:\n20 votes on 40 tasks'),
    ('5  Measure', 'shift toward the first slot\ndecisions that flip\nchange with the quality gap'),
]


def save(fig, name, **kw):
    fig.savefig(OUT + name, **kw)
    plt.close(fig)


def hero():
    fig = plt.figure(figsize=(12, 6.3), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 12); ax.set_ylim(0, 6.3); ax.axis('off')
    fig.patch.set_facecolor('#10233f')
    ang = np.deg2rad(7)
    cx, cy, L = 6, 4.15, 4.2
    lx, ly = cx - L * np.cos(ang), cy - L * np.sin(ang)
    rx, ry = cx + L * np.cos(ang), cy + L * np.sin(ang)
    ax.add_patch(Polygon([[cx - 0.6, 0.7], [cx + 0.6, 0.7], [cx + 0.12, cy], [cx - 0.12, cy]], fc='#c9d3e0', ec='none'))
    ax.add_patch(Rectangle((cx - 1.6, 0.45), 3.2, 0.3, fc='#c9d3e0', ec='none'))
    ax.plot([lx, rx], [ly, ry], color='#e8edf3', lw=7, solid_capstyle='round')
    ax.add_patch(Circle((cx, cy), 0.22, fc='#eda100', ec='none'))
    for (px, py), col, tag in (((lx, ly), FIRST, '1st'), ((rx, ry), SECOND, '2nd')):
        ax.plot([px, px - 0.9], [py, py - 1.1], color='#e8edf3', lw=1.5)
        ax.plot([px, px + 0.9], [py, py - 1.1], color='#e8edf3', lw=1.5)
        ax.add_patch(FancyBboxPatch((px - 1.25, py - 2.55), 2.5, 1.45, boxstyle='round,pad=0.05,rounding_size=0.15',
                                    fc='#ffffff', ec=col, lw=5))
        for k in range(4):
            ax.plot([px - 0.95, px + (0.95 if k < 3 else 0.2)], [py - 1.45 - 0.27 * k] * 2, color='#9aa6b4', lw=3.5,
                    solid_capstyle='round')
        ax.text(px, py - 2.85, tag, color='#ffffff', fontsize=20, weight='bold', ha='center', va='top',
                bbox=dict(boxstyle='round,pad=0.25', fc=col, ec='none'))
    ax.text(cx, 5.75, '=', color='#e8edf3', fontsize=40, ha='center', va='center', weight='bold')
    save(fig, 'hero_tilted_judge.png', facecolor=fig.get_facecolor())


def method():
    fig = plt.figure(figsize=(5.2, 9.2), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    fig.patch.set_facecolor(BG)
    h, gap, top = 0.155, 0.035, 0.965
    for i, (t, body) in enumerate(STEPS):
        y = top - (i + 1) * h - i * gap
        ax.add_patch(FancyBboxPatch((0.07, y), 0.86, h, boxstyle='round,pad=0.008,rounding_size=0.025',
                                    fc=STAGE[i], ec=STAGE_EDGE[i], lw=2.2))
        ax.text(0.11, y + h - 0.025, t, fontsize=14, weight='bold', color=INK, va='top')
        ax.text(0.11, y + h - 0.068, body, fontsize=11.2, color=INK, va='top', linespacing=1.35)
        if i < len(STEPS) - 1:
            ax.annotate('', xy=(0.5, y - gap + 0.004), xytext=(0.5, y - 0.004),
                        arrowprops=dict(arrowstyle='-|>', color=MUTED, lw=2))
    save(fig, 'method_phone.png', facecolor=BG)


def worked():
    fig = plt.figure(figsize=(10, 13.8), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 10); ax.set_ylim(0, 13.8); ax.axis('off')
    fig.patch.set_facecolor(BG)

    def box(x, y, w, h, title, text):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.04,rounding_size=0.12', fc=CARD, ec=MUTED, lw=1.6))
        ax.text(x + 0.15, y + h - 0.12, title, fontsize=9.5, color=INK, weight='bold', va='top')
        ax.text(x + 0.15, y + h - 0.42, textwrap.fill(text, 52), fontsize=9.3, color=INK, va='top', linespacing=1.3)

    def bar(y, p, lab1, lab2, row):
        x0, w, h = 1.3, 8.3, 0.28
        ax.text(0.35, y + h / 2, row, fontsize=10, color=INK, weight='bold', va='center')
        ax.add_patch(Rectangle((x0, y), w * p, h, fc=FIRST, ec='none'))
        ax.add_patch(Rectangle((x0 + w * p, y), w * (1 - p), h, fc=SECOND, ec='none'))
        ax.plot([x0 + w / 2] * 2, [y - 0.06, y + h + 0.06], color=INK, lw=1.2, ls='--')
        ax.text(x0, y - 0.07, f'1st slot, {lab1}: {100 * p:.1f}%', color=FIRST, fontsize=9.6, weight='bold', va='top')
        ax.text(x0 + w, y - 0.07, f'2nd slot, {lab2}: {100 * (1 - p):.1f}%', color=SECOND, fontsize=9.6, weight='bold',
                va='top', ha='right')

    def panel(y0, head, task, a, b, rows, verdict, bh):
        ax.text(0.35, y0, head, fontsize=15, weight='bold', color=INK, va='top')
        tl = textwrap.fill('Task: ' + task.replace('\n', ' '), 100)
        ax.text(0.35, y0 - 0.42, tl, fontsize=10, color=MUTED, va='top')
        top = y0 - 0.62 - 0.2 * tl.count('\n') - 0.2
        box(0.35, top - bh, 4.45, bh, a[0], a[1]); box(5.2, top - bh, 4.45, bh, b[0], b[1])
        y = top - bh - 0.55
        for p, l1, l2, r in rows:
            bar(y, p, l1, l2, r); y -= 0.75
        ax.text(0.35, y + 0.2, verdict, fontsize=10.5, color=INK, va='top', style='italic')

    panel(13.55, 'A. Clear winner: the decision holds in both orders', STARTUP_TASK,
          ('Answer R (right)', STARTUP_RIGHT), ('Answer W (wrong)', STARTUP_WRONG),
          [(1.0, 'R', 'W', 'Order 1'), (0.0, 'W', 'R', 'Order 2')],
          'Jev gives R 100% in both orders. Order cannot move a confident decision.', 1.3)
    panel(8.82, 'B. Same answer twice: the first copy wins', ENGINE_TASK,
          ('Copy 1', ENGINE_SHORT), ('Copy 2 (identical)', ENGINE_SHORT),
          [(IDENT['order1'], 'copy 1', 'copy 2', 'Order 1'), (IDENT['order2'], 'copy 2', 'copy 1', 'Order 2')],
          'Jev was told to split 50/50 when answers are equally good. The first slot wins both times.', 0.95)
    panel(4.62, 'C. Close call: the decision flips with the order', ENGINE_TASK,
          ('Answer S (short)', ENGINE_SHORT), ('Answer E (explains why)', ENGINE_LONG),
          [(NEAR['short_first'], 'S', 'E', 'Order 1'), (1 - NEAR['short_second'], 'E', 'S', 'Order 2')],
          'Human raters tied these two answers. Whichever comes second wins, so the decision flips.', 1.6)
    save(fig, 'worked_example.png', facecolor=BG)
    im = Image.open(OUT + 'worked_example.png'); W = im.size[0]
    for name, (a, b) in {'worked_A_clear_winner.png': (0.18, 4.88), 'worked_B_identical.png': (4.9, 9.12),
                         'worked_C_close_call.png': (9.14, 13.78)}.items():
        im.crop((0, int(a * 200), W, int(b * 200))).save(OUT + name)


def charts():
    D = json.load(open(PAPER_DATA))
    prim = {r['hypothesis']: r for r in D['primary']}
    e1 = {(r['hypothesis'], r['source']): r for r in D['E1']}
    kinds = ['choice', 'noul', 'score']
    fig, ax = plt.subplots(figsize=(6.4, 3.8), dpi=200)
    for k, kind in enumerate(kinds):
        r = prim['A1_' + kind]; c = TYPE_COL[kind]
        ax.bar(k, 100 * r['estimate'], color=c, width=0.55)
        ax.errorbar(k, 100 * r['estimate'], yerr=[[100 * (r['estimate'] - r['ci95'][0])], [100 * (r['ci95'][1] - r['estimate'])]],
                    color=INK, capsize=4, lw=1.2)
        for src, mk in (('MTBench', 'o'), ('HANNA', 's'), ('SummEval', '^')):
            v = e1[('A1_' + kind, src)]['estimate']
            ax.plot(k + 0.36, 100 * v, mk, ms=5, mfc='white', mec=c, mew=1.4, label=src if k == 0 else None)
        ax.text(k, 100 * r['ci95'][1] + 0.5, f"{100 * r['estimate']:.1f}", ha='center', fontsize=10, weight='bold', color=c)
    ax.axhline(0, color=INK, lw=0.8)
    ax.set_xticks(range(3)); ax.set_xticklabels(['Choice', 'Noul', 'Score'])
    ax.set_ylabel('Shift toward 1st slot\n(probability points, 0 = fair)')
    ax.legend(title='single dataset', frameon=False, fontsize=8, title_fontsize=8, loc='upper right')
    fig.tight_layout(); save(fig, 'blog_f1_primacy.png')
    fig, ax = plt.subplots(figsize=(6.4, 3.8), dpi=200)
    for k, kind in enumerate(kinds):
        rows = sorted([g for g in D['gap_by_bin'] if g['kind'] == kind], key=lambda g: g['gap_bin'])
        xs = [g['gap_bin'] + (k - 1) * 0.1 for g in rows]; ys = [g['estimate'] for g in rows]
        err = [[g['estimate'] - g['ci95'][0] for g in rows], [g['ci95'][1] - g['estimate'] for g in rows]]
        ax.errorbar(xs, ys, yerr=err, fmt='-o', ms=4, lw=1.6, color=TYPE_COL[kind], capsize=2, label=kind.capitalize())
    ax.set_xticks(range(5)); ax.set_xticklabels(['0\nidentical', '1\nclosest', '2', '3', '4\nclearest'])
    ax.set_xlabel('Human-rated quality gap between the two answers')
    ax.set_ylabel('Size of the order effect\n(squared log-odds)')
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout(); save(fig, 'blog_f2_gap.png')
    rows = D['E3']['rows']; bins = ['below 0.6', '0.6 to 0.9', '0.9 or above']
    fig, ax = plt.subplots(figsize=(6.4, 3.8), dpi=200)
    for j, (metric, lab, col) in enumerate((('cross', 'order reversed', CHOICE), ('same', 'same order, asked again', FLOOR))):
        rr = [next(r for r in rows if r['bin'] == b and r['metric'] == metric) for b in bins]
        x = np.arange(3) + (j - .5) * 0.34
        ax.bar(x, [100 * r['rate'] for r in rr], width=0.34, color=col, label=lab,
               yerr=[[100 * (r['rate'] - r['ci95'][0]) for r in rr], [100 * (r['ci95'][1] - r['rate']) for r in rr]],
               capsize=3, error_kw=dict(ecolor=INK, lw=1))
        for xi, r in zip(x, rr):
            v = 100 * r['rate']
            ax.text(xi, 100 * r['ci95'][1] + 1.2, f'{v:.1f}%' if v >= 0.1 else f'{v:.2f}%', ha='center', fontsize=9,
                    color=INK, weight='bold' if metric == 'cross' else 'normal')
    ax.set_xticks(range(3)); ax.set_xticklabels(bins)
    ax.set_xlabel("Jev's confidence in its top choice (probability)")
    ax.set_ylabel('Choice decisions that changed (%)')
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout(); save(fig, 'blog_f3_confidence.png')
    P = json.load(open(POSTHOC))
    fig, ax = plt.subplots(figsize=(6.4, 3.8), dpi=200)
    for k, kind in enumerate(kinds):
        rr = sorted([r for r in P['rows'] if r['kind'] == kind], key=lambda r: r['gap_bin'])
        xs = [r['gap_bin'] + (k - 1) * 0.1 for r in rr]; ys = [100 * r['estimate'] for r in rr]
        err = [[100 * (r['estimate'] - r['ci95'][0]) for r in rr], [100 * (r['ci95'][1] - r['estimate']) for r in rr]]
        ax.errorbar(xs, ys, yerr=err, fmt='-o', ms=4, lw=1.6, color=TYPE_COL[kind], capsize=2, label=kind.capitalize())
    ax.axhline(0, color=INK, lw=0.8)
    ax.set_xticks(range(5)); ax.set_xticklabels(['0\nidentical', '1\nclosest', '2', '3', '4\nclearest'])
    ax.set_xlabel('Human-rated quality gap between the two answers')
    ax.set_ylabel('Shift toward 1st slot\n(probability points)')
    ax.text(0.98, 0.04, 'post hoc analysis', transform=ax.transAxes, ha='right', fontsize=9, color=MUTED, style='italic')
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout(); save(fig, 'blog_posthoc_direction.png')


def animation():
    fig = plt.figure(figsize=(8, 4.5), dpi=110)
    ax = fig.add_axes([0, 0, 1, 1]); fig.patch.set_facecolor(BG)
    seq = ([('data', i) for i in range(22)] + [('pairs', i) for i in range(26)] + [('swap1', i) for i in range(16)] +
           [('swap', i) for i in range(20)] + [('swap2', i) for i in range(16)] + [('agg', i) for i in range(34)] +
           [('gap', i) for i in range(30)] + [('conf', i) for i in range(44)])

    def tag(n):
        ax.add_patch(FancyBboxPatch((0.02, 0.9), 0.23, 0.075, boxstyle='round,pad=0.005,rounding_size=0.015',
                                    fc=STAGE[n - 1], ec=STAGE_EDGE[n - 1], lw=1.8))
        ax.text(0.135, 0.937, 'Stage ' + STEPS[n - 1][0].replace('  ', ': '), ha='center', va='center', fontsize=9.5,
                weight='bold', color=INK)

    def answer_card(x, y, title, col, text, w=0.34, h=0.22):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.01,rounding_size=0.02', fc=CARD, ec=col, lw=2.5))
        ax.text(x + w / 2, y + h - 0.045, title, ha='center', fontsize=10.5, weight='bold', color=col)
        ax.text(x + w / 2, y + h / 2 - 0.035, text, ha='center', va='center', fontsize=9.5, color=INK)

    def draw(k):
        ax.clear(); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
        phase, i = seq[k]
        if phase == 'data':
            tag(1)
            ax.text(0.5, 0.8, 'Start from answers that humans already rated', ha='center', fontsize=13.5, weight='bold', color=INK)
            for j, (name, n, what) in enumerate((('MT-Bench', 64, 'chat answers, human votes'), ('HANNA', 75, 'stories, coherence ratings'),
                                                 ('SummEval', 73, 'summaries, expert ratings'))):
                if i >= j * 5:
                    x = 0.06 + j * 0.31
                    ax.add_patch(FancyBboxPatch((x, 0.33), 0.27, 0.3, boxstyle='round,pad=0.01,rounding_size=0.02', fc=STAGE[0], ec=STAGE_EDGE[0], lw=2))
                    ax.text(x + 0.135, 0.56, name, ha='center', fontsize=13, weight='bold', color=INK)
                    ax.text(x + 0.135, 0.47, f'{n} tasks', ha='center', fontsize=11.5, color=INK)
                    ax.text(x + 0.135, 0.39, what, ha='center', fontsize=9, color=MUTED)
            if i > 14:
                ax.text(0.5, 0.18, '212 tasks in total', ha='center', fontsize=12, color=INK, weight='bold')
        elif phase == 'pairs':
            tag(2)
            ax.text(0.5, 0.8, 'For each task, build pairs of answers', ha='center', fontsize=13.5, weight='bold', color=INK)
            ax.text(0.5, 0.72, 'Example task: Which word does not belong with the others? tyre, steering wheel, car, engine',
                    ha='center', fontsize=9.5, color=MUTED)
            labels = [('gap 0', 'the same answer\ntwice (fair = 50/50)'), ('gap 1', 'humans saw almost\nno difference'),
                      ('gap 2', ''), ('gap 3', ''), ('gap 4', 'humans saw a\nclear winner')]
            for j, (g, d) in enumerate(labels):
                if i >= j * 4:
                    x = 0.05 + j * 0.185
                    ax.add_patch(FancyBboxPatch((x, 0.36), 0.16, 0.24, boxstyle='round,pad=0.008,rounding_size=0.02',
                                                fc=STAGE[1], ec=STAGE_EDGE[1], lw=3 if j == 0 else 2))
                    ax.text(x + 0.08, 0.54, g, ha='center', fontsize=12, weight='bold', color=INK)
                    ax.text(x + 0.08, 0.43, d, ha='center', va='center', fontsize=8.2, color=INK)
            ax.text(0.5, 0.2, 'Gap 0 is the cleanest test: any preference must come from order alone.', ha='center', fontsize=10.5, color=INK)
        elif phase in ('swap1', 'swap', 'swap2'):
            ax.text(0.5, 0.82, 'Same answer, shown twice, in both orders', ha='center', fontsize=13.5, weight='bold', color=INK)
            tag(3 if phase == 'swap' else 4)
            t = 0 if phase == 'swap1' else (1 if phase == 'swap2' else (1 - np.cos(np.pi * i / 19)) / 2)
            xa = 0.08 + t * 0.5; xb = 0.58 - t * 0.5
            ya = 0.45 + 0.1 * np.sin(np.pi * t); yb = 0.45 - 0.1 * np.sin(np.pi * t)
            text = 'The word that does not belong\nwith the others is "engine".'
            for x, y, name in ((xa, ya, 'copy A'), (xb, yb, 'copy B')):
                answer_card(x, y, name, FIRST if x < 0.33 else SECOND, text)
            ax.text(0.25, 0.39, '1st slot', ha='center', fontsize=10, color=FIRST, weight='bold')
            ax.text(0.75, 0.39, '2nd slot', ha='center', fontsize=10, color=SECOND, weight='bold')
            if phase != 'swap':
                p = IDENT['order1'] if phase == 'swap1' else IDENT['order2']
                msg = ('Order 1: A first. Jev returns a probability for each copy.' if phase == 'swap1'
                       else 'Order 2: B first. The first slot still gets more.')
                ax.text(0.5, 0.25, msg, ha='center', fontsize=10, color=INK)
                ax.add_patch(Rectangle((0.08, 0.13), 0.84 * p, 0.07, fc=FIRST))
                ax.add_patch(Rectangle((0.08 + 0.84 * p, 0.13), 0.84 * (1 - p), 0.07, fc=SECOND))
                ax.plot([0.5, 0.5], [0.11, 0.22], color=INK, ls='--', lw=1)
                ax.text(0.08, 0.06, f'1st slot: {100 * p:.1f}%', color=FIRST, fontsize=11, weight='bold')
                ax.text(0.92, 0.06, f'2nd slot: {100 * (1 - p):.1f}%', color=SECOND, fontsize=11, weight='bold', ha='right')
                ax.text(0.5, 0.015, 'dashed line = fair 50/50 split', ha='center', fontsize=8.5, color=MUTED)
        elif phase == 'agg':
            tag(5)
            ax.text(0.5, 0.8, 'Repeat for all 212 tasks: the first copy wins', ha='center', fontsize=13.5, weight='bold', color=INK)
            frac = min(1, (i + 1) / 20)
            for j, (name, v, col) in enumerate((('Choice', 98.6, CHOICE), ('Noul', 88.7, NOUL), ('Score', 57.5, SCORE))):
                y = 0.58 - j * 0.16
                ax.text(0.06, y + 0.03, name, fontsize=12, weight='bold', color=col, va='center')
                ax.add_patch(Rectangle((0.2, y), 0.7, 0.06, fc='#e3e6ea'))
                ax.add_patch(Rectangle((0.2, y), 0.7 * v / 100 * frac, 0.06, fc=col))
                ax.text(0.2 + 0.7 * v / 100 * frac + 0.01, y + 0.03, f'{v * frac:.1f}%', fontsize=11, va='center', color=INK)
            ax.text(0.5, 0.1, 'share of identical pairs where the first copy got more than half', ha='center', fontsize=10, color=MUTED)
        elif phase == 'gap':
            tag(5)
            ax.text(0.5, 0.8, 'The order effect is biggest on close calls', ha='center', fontsize=13.5, weight='bold', color=INK)
            D = json.load(open(PAPER_DATA))
            vals = [g['estimate'] for g in sorted([g for g in D['gap_by_bin'] if g['kind'] == 'choice'], key=lambda g: g['gap_bin'])]
            frac = min(1, (i + 1) / 18)
            for j, v in enumerate(vals):
                x = 0.13 + j * 0.16; hgt = 0.45 * v / max(vals) * frac
                ax.add_patch(Rectangle((x, 0.2), 0.1, hgt, fc=CHOICE))
                ax.text(x + 0.05, 0.13, ['identical', 'closest', '2', '3', 'clearest'][j], ha='center', fontsize=9.5, color=INK)
            ax.text(0.5, 0.05, 'Choice: size of the order effect by human-rated quality gap', ha='center', fontsize=9.5, color=MUTED)
        else:
            tag(5)
            ax.text(0.5, 0.8, 'Order flips decisions mostly when Jev is unsure', ha='center', fontsize=13.5, weight='bold', color=INK)
            frac = min(1, (i + 1) / 20)
            for j, (name, cross, same) in enumerate((('confidence < 0.6', 47.5, 10.0), ('0.6 to 0.9', 10.8, 0.8), ('0.9 or above', 0.1, 0.02))):
                x = 0.12 + j * 0.29
                hc, hs = 0.5 * cross / 50 * frac, 0.5 * same / 50 * frac
                ax.add_patch(Rectangle((x, 0.2), 0.1, hc, fc=CHOICE))
                ax.add_patch(Rectangle((x + 0.11, 0.2), 0.1, hs, fc=FLOOR))
                ax.text(x + 0.05, 0.21 + hc, f'{cross * frac:.1f}%', ha='center', fontsize=10, color=CHOICE, weight='bold')
                ax.text(x + 0.16, 0.21 + hs, f'{same * frac:.2f}%' if same < 0.1 else f'{same * frac:.1f}%', ha='center', fontsize=10, color=MUTED)
                ax.text(x + 0.105, 0.13, name, ha='center', fontsize=10, color=INK)
            ax.text(0.5, 0.05, 'blue: order reversed    grey: same order asked again (noise)', ha='center', fontsize=9.5, color=MUTED)

    anim = FuncAnimation(fig, draw, frames=len(seq), interval=100)
    anim.save(OUT + 'audit_walkthrough.gif', writer=PillowWriter(fps=10))
    keys = [21, 47, 63, 95, 129, 159, len(seq) - 1]
    frames = []
    for kk in keys:
        draw(kk); fig.canvas.draw()
        frames.append(Image.frombuffer('RGBA', fig.canvas.get_width_height(), fig.canvas.buffer_rgba()).convert('RGB'))
    w, h = frames[0].size
    strip = Image.new('RGB', (w * 2, h * 4), BG)
    for n, f in enumerate(frames):
        strip.paste(f, ((n % 2) * w, (n // 2) * h))
    strip.save(OUT + 'audit_walkthrough_strip.png')
    plt.close(fig)


if __name__ == '__main__':
    hero(); method(); worked(); charts(); animation()
    print('done')
