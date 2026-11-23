"""Blog media for the Jev audit: hero, phone method diagram, worked example, animation.
All numbers come from posthoc-20261118/worked-example-candidates.json (MT-Bench, Choice,
legacy format, mean of 16 Jev calls per order) and the registered/exploratory results."""
import textwrap
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Polygon, Circle
from matplotlib.animation import FuncAnimation, PillowWriter

OUT = 'figures/blog/'
BLUE, ORANGE, GREEN, GOLD, PINK = '#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4'
INK, MUTED, CARD, BG = '#1f2933', '#6b7785', '#ffffff', '#f6f4ef'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'text.parse_math': False})

# Real values (fractions of probability mass, mean over 16 calls per order)
ENGINE_TASK = 'Which word does not belong with the others?\ntyre, steering wheel, car, engine'
ENGINE_SHORT = 'The word that does not belong with the others is "engine".'
ENGINE_LONG = ('The word that does not belong with the others is "engine." A tyre is a type of tire '
               'used on vehicles, a steering wheel is a device used to steer a vehicle, and a car is '
               'a type of automobile. An engine is a machine that converts energy into mechanical motion.')
IDENT = dict(order1=(0.5575, 0.4425), order2=(0.575, 0.425))   # (first slot, second slot)
NEAR = dict(short_first=0.475, short_second=0.5413)            # P(short answer)
STARTUP_TASK = ('A tech startup invests $8000 in software development in the first year, and then invests half of that amount in software development in the second year. What\'s the total amount the startup invested in software development over the two years?')
STARTUP_RIGHT = ('The startup invested $8000 in the first year and half of that amount, which is $4000, in the second year. So the total amount invested in software development over the two years is: $8000 + $4000 = $12,000')
STARTUP_WRONG = 'The total amount the startup invested in software development over the two years is $16,000.'


def card(ax, x, y, w, h, text, color, width=34, fs=10, title=None):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.012,rounding_size=0.02',
                                fc=CARD, ec=color, lw=2.2))
    if title:
        ax.text(x + 0.015, y + h - 0.03, title, fontsize=fs - 1, color=color, weight='bold', va='top')
    ax.text(x + 0.015, y + h - (0.075 if title else 0.03), textwrap.fill(text, width), fontsize=fs,
            color=INK, va='top')


def pbar(ax, x, y, w, p_first, label_first='first', label_second='second', fs=10):
    ax.add_patch(Rectangle((x, y), w * p_first, 0.05, fc=BLUE, ec='none'))
    ax.add_patch(Rectangle((x + w * p_first, y), w * (1 - p_first), 0.05, fc=ORANGE, ec='none'))
    ax.plot([x + w / 2] * 2, [y - 0.012, y + 0.062], color=INK, lw=1, ls='--')
    ax.text(x, y - 0.03, f'{label_first} {100 * p_first:.1f}%', color=BLUE, fontsize=fs, weight='bold', va='top')
    ax.text(x + w, y - 0.03, f'{label_second} {100 * (1 - p_first):.1f}%', color=ORANGE, fontsize=fs,
            weight='bold', va='top', ha='right')


# 1. Hero image: two identical cards on a tilted scale
def hero():
    fig = plt.figure(figsize=(12, 6.3), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 12); ax.set_ylim(0, 6.3); ax.axis('off')
    fig.patch.set_facecolor('#10233f')
    ang = np.deg2rad(7)   # first slot (left) sits lower: it carries more weight
    cx, cy, L = 6, 4.15, 4.2
    lx, ly = cx - L * np.cos(ang), cy - L * np.sin(ang)
    rx, ry = cx + L * np.cos(ang), cy + L * np.sin(ang)
    ax.add_patch(Polygon([[cx - 0.6, 0.7], [cx + 0.6, 0.7], [cx + 0.12, cy], [cx - 0.12, cy]], fc='#c9d3e0', ec='none'))
    ax.add_patch(Rectangle((cx - 1.6, 0.45), 3.2, 0.3, fc='#c9d3e0', ec='none'))
    ax.plot([lx, rx], [ly, ry], color='#e8edf3', lw=7, solid_capstyle='round')
    ax.add_patch(Circle((cx, cy), 0.22, fc=GOLD, ec='none'))
    for (px, py), col, tag in (((lx, ly), BLUE, '1st'), ((rx, ry), ORANGE, '2nd')):
        ax.plot([px, px - 0.9], [py, py - 1.1], color='#e8edf3', lw=1.5)
        ax.plot([px, px + 0.9], [py, py - 1.1], color='#e8edf3', lw=1.5)
        ax.add_patch(FancyBboxPatch((px - 1.25, py - 2.55), 2.5, 1.45, boxstyle='round,pad=0.05,rounding_size=0.15',
                                    fc='#ffffff', ec=col, lw=4))
        for k in range(4):
            ax.plot([px - 0.95, px + (0.95 if k < 3 else 0.2)], [py - 1.45 - 0.27 * k] * 2, color='#9aa6b4', lw=3.5,
                    solid_capstyle='round')
        ax.text(px, py - 2.85, tag, color=col, fontsize=22, weight='bold', ha='center', va='top')
    ax.text(cx, 5.75, '=', color='#e8edf3', fontsize=40, ha='center', va='center', weight='bold')
    fig.savefig(OUT + 'hero_tilted_judge.png', facecolor=fig.get_facecolor())
    plt.close(fig)


# 2. Method diagram, vertical, phone readable
def method():
    fig = plt.figure(figsize=(5.2, 9.2), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    fig.patch.set_facecolor(BG)
    steps = [
        ('1  Real data', '3 human-rated datasets\nMT-Bench, HANNA, SummEval\n212 tasks', '#dce9fa', BLUE),
        ('2  Build pairs', 'identical copy (a true tie)\n+ pairs with small to large\nhuman-rated quality gaps', '#fbe3d8', ORANGE),
        ('3  Swap and repeat', 'show A then B, and B then A\nask every request twice\nalso swap question order, format', '#d9f2e8', GREEN),
        ('4  Ask the judges', 'Jev 1.13: probabilities\nHaiku 4.5, DeepSeek V4 Flash:\n20 votes on 40 tasks', '#fcefcf', GOLD),
        ('5  Measure', 'shift toward the first slot\ndecisions that flip\nchange with the quality gap', '#f8dde8', PINK),
    ]
    h, gap, top = 0.155, 0.035, 0.965
    for i, (t, body, fc, ec) in enumerate(steps):
        y = top - (i + 1) * h - i * gap
        ax.add_patch(FancyBboxPatch((0.07, y), 0.86, h, boxstyle='round,pad=0.008,rounding_size=0.025',
                                    fc=fc, ec=ec, lw=2.2))
        ax.text(0.11, y + h - 0.025, t, fontsize=14, weight='bold', color=INK, va='top')
        ax.text(0.11, y + h - 0.068, body, fontsize=11.2, color=INK, va='top', linespacing=1.35)
        if i < len(steps) - 1:
            ax.annotate('', xy=(0.5, y - gap + 0.004), xytext=(0.5, y - 0.004),
                        arrowprops=dict(arrowstyle='-|>', color=MUTED, lw=2))
    fig.savefig(OUT + 'method_phone.png', facecolor=BG)
    plt.close(fig)


# 3. Worked example: three real MT-Bench cases (data units = inches)
def worked():
    fig = plt.figure(figsize=(10, 13.8), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 10); ax.set_ylim(0, 13.8); ax.axis('off')
    fig.patch.set_facecolor(BG)

    def box(x, y, w, h, title, text, color):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.04,rounding_size=0.12', fc=CARD, ec=color, lw=2.2))
        ax.text(x + 0.15, y + h - 0.12, title, fontsize=9.5, color=color, weight='bold', va='top')
        ax.text(x + 0.15, y + h - 0.42, textwrap.fill(text, 52), fontsize=9.3, color=INK, va='top', linespacing=1.3)

    def bar(y, p, lab1, lab2, row):
        x0, w, h = 1.3, 8.3, 0.28
        ax.text(0.35, y + h / 2, row, fontsize=10, color=INK, weight='bold', va='center')
        ax.add_patch(Rectangle((x0, y), w * p, h, fc=BLUE, ec='none'))
        ax.add_patch(Rectangle((x0 + w * p, y), w * (1 - p), h, fc=ORANGE, ec='none'))
        ax.plot([x0 + w / 2] * 2, [y - 0.06, y + h + 0.06], color=INK, lw=1.2, ls='--')
        ax.text(x0, y - 0.07, f'{lab1}: {100 * p:.1f}%', color=BLUE, fontsize=9.6, weight='bold', va='top')
        ax.text(x0 + w, y - 0.07, f'{lab2}: {100 * (1 - p):.1f}%', color=ORANGE, fontsize=9.6, weight='bold', va='top', ha='right')

    def panel(y0, head, color, task, a, b, rows, verdict, bh=1.25):
        ax.text(0.35, y0, head, fontsize=15, weight='bold', color=color, va='top')
        tl = textwrap.fill('Task: ' + task.replace('\n', ' '), 100)
        ax.text(0.35, y0 - 0.42, tl, fontsize=10, color=MUTED, va='top')
        top = y0 - 0.62 - 0.2 * tl.count('\n') - 0.2
        box(0.35, top - bh, 4.45, bh, a[0], a[1], BLUE)
        box(5.2, top - bh, 4.45, bh, b[0], b[1], ORANGE)
        y = top - bh - 0.55
        for p, l1, l2, r in rows:
            bar(y, p, l1, l2, r); y -= 0.75
        ax.text(0.35, y + 0.2, verdict, fontsize=10.5, color=INK, va='top', style='italic')

    panel(13.55, 'A. Clear winner: the decision holds in both orders', GREEN, STARTUP_TASK,
          ('Answer R (right)', STARTUP_RIGHT), ('Answer W (wrong)', STARTUP_WRONG),
          [(1.0, 'R, shown first', 'W', 'Order 1'), (0.0, 'W, shown first', 'R', 'Order 2')],
          'Jev gives R 100% in both orders. Order cannot move a confident decision.', bh=1.3)
    panel(8.82, 'B. Same answer twice: the first copy wins', BLUE, ENGINE_TASK,
          ('Copy 1', ENGINE_SHORT), ('Copy 2 (identical)', ENGINE_SHORT),
          [(IDENT['order1'][0], 'Copy 1, shown first', 'Copy 2', 'Order 1'),
           (IDENT['order2'][0], 'Copy 2, shown first', 'Copy 1', 'Order 2')],
          'Jev was told to split 50/50 when answers are equally good. The first slot wins both times.', bh=0.95)
    panel(4.62, 'C. Close call: the decision flips with the order', ORANGE, ENGINE_TASK,
          ('Answer S (short)', ENGINE_SHORT), ('Answer E (explains why)', ENGINE_LONG),
          [(NEAR['short_first'], 'S, shown first', 'E', 'Order 1'),
           (1 - NEAR['short_second'], 'E, shown first', 'S', 'Order 2')],
          'Human raters tied these two answers. Whichever comes second wins, so the decision flips.', bh=1.6)
    fig.savefig(OUT + 'worked_example.png', facecolor=BG)
    plt.close(fig)


# 4. Animation: identical copies swap places, the bar follows the first slot; then the big numbers
def animation():
    fig = plt.figure(figsize=(8, 4.5), dpi=110)
    ax = fig.add_axes([0, 0, 1, 1])
    fig.patch.set_facecolor(BG)
    frames_swap, frames_hold = 24, 18
    seq = ([('hold1', i) for i in range(frames_hold)] + [('swap', i) for i in range(frames_swap)] +
           [('hold2', i) for i in range(frames_hold)] + [('ladder', i) for i in range(45)] +
           [('conf', i) for i in range(50)])

    def draw(k):
        ax.clear(); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
        phase, i = seq[k]
        if phase in ('hold1', 'swap', 'hold2'):
            ax.text(0.5, 0.94, 'Same answer, shown twice. Jev picks a winner anyway.', ha='center', fontsize=14,
                    weight='bold', color=INK)
            ax.text(0.5, 0.86, 'Task: Which word does not belong with the others? tyre, steering wheel, car, engine', ha='center',
                    fontsize=10.5, color=MUTED)
            t = 0 if phase == 'hold1' else (1 if phase == 'hold2' else (1 - np.cos(np.pi * i / (frames_swap - 1))) / 2)
            xa = 0.08 + t * 0.5; xb = 0.58 - t * 0.5
            ya = 0.45 + 0.12 * np.sin(np.pi * t); yb = 0.45 - 0.12 * np.sin(np.pi * t)
            for x, y, name in ((xa, ya, 'copy A'), (xb, yb, 'copy B')):
                left = x < 0.33
                col = BLUE if left else ORANGE
                ax.add_patch(FancyBboxPatch((x, y), 0.34, 0.25, boxstyle='round,pad=0.01,rounding_size=0.02',
                                            fc=CARD, ec=col, lw=2.5))
                ax.text(x + 0.17, y + 0.2, name, ha='center', fontsize=11, weight='bold', color=col)
                ax.text(x + 0.17, y + 0.09, 'The word that does not belong\nwith the others is "engine".', ha='center',
                        fontsize=10, color=INK)
            ax.text(0.25, 0.39, 'shown 1st', ha='center', fontsize=10, color=BLUE)
            ax.text(0.75, 0.39, 'shown 2nd', ha='center', fontsize=10, color=ORANGE)
            if phase != 'swap':
                p = IDENT['order1'][0] if phase == 'hold1' else IDENT['order2'][0]
                ax.add_patch(Rectangle((0.08, 0.17), 0.84 * p, 0.08, fc=BLUE))
                ax.add_patch(Rectangle((0.08 + 0.84 * p, 0.17), 0.84 * (1 - p), 0.08, fc=ORANGE))
                ax.plot([0.5, 0.5], [0.15, 0.27], color=INK, ls='--', lw=1)
                first = 'A' if phase == 'hold1' else 'B'
                ax.text(0.08, 0.1, f'1st slot (copy {first}): {100 * p:.1f}%', color=BLUE, fontsize=11, weight='bold')
                ax.text(0.92, 0.1, f'2nd slot: {100 * (1 - p):.1f}%', color=ORANGE, fontsize=11, weight='bold',
                        ha='right')
                ax.text(0.5, 0.03, 'dashed line = a fair 50/50 split', ha='center', fontsize=9, color=MUTED)
        elif phase == 'ladder':
            ax.text(0.5, 0.93, 'Across 212 tasks, the first copy got more probability', ha='center', fontsize=14,
                    weight='bold', color=INK)
            frac = min(1, (i + 1) / 20)
            vals = [('Choice', 98.6, BLUE), ('Noul', 88.7, ORANGE), ('Score', 57.5, GREEN)]
            for j, (name, v, col) in enumerate(vals):
                y = 0.66 - j * 0.2
                ax.text(0.06, y + 0.035, name, fontsize=12, weight='bold', color=col, va='center')
                ax.add_patch(Rectangle((0.2, y), 0.7, 0.07, fc='#e3e6ea'))
                ax.add_patch(Rectangle((0.2, y), 0.7 * v / 100 * frac, 0.07, fc=col))
                ax.text(0.2 + 0.7 * v / 100 * frac + 0.01, y + 0.035, f'{v * frac:.1f}%', fontsize=11, va='center',
                        color=INK)
            ax.text(0.5, 0.08, 'share of identical pairs where the first copy got more than half', ha='center',
                    fontsize=10, color=MUTED)
        else:
            ax.text(0.5, 0.93, 'Order flips decisions mostly when Jev is unsure', ha='center', fontsize=14,
                    weight='bold', color=INK)
            frac = min(1, (i + 1) / 20)
            bins = [('top prob. < 0.6', 47.5, 10.0), ('0.6 to 0.9', 10.8, 0.8), ('>= 0.9', 0.1, 0.02)]
            for j, (name, cross, same) in enumerate(bins):
                x = 0.12 + j * 0.29
                hc, hs = 0.6 * cross / 50 * frac, 0.6 * same / 50 * frac
                ax.add_patch(Rectangle((x, 0.18), 0.1, hc, fc=BLUE))
                ax.add_patch(Rectangle((x + 0.11, 0.18), 0.1, hs, fc=ORANGE))
                ax.text(x + 0.05, 0.19 + hc, f'{cross * frac:.1f}%', ha='center', fontsize=10, color=BLUE, weight='bold')
                ax.text(x + 0.16, 0.19 + hs, (f'{same * frac:.2f}%' if same < 0.1 else f'{same * frac:.1f}%'), ha='center', fontsize=10, color=ORANGE)
                ax.text(x + 0.105, 0.11, name, ha='center', fontsize=10.5, color=INK)
            ax.text(0.5, 0.03, 'blue: order reversed    orange: same order asked again (noise floor)', ha='center',
                    fontsize=10, color=MUTED)

    anim = FuncAnimation(fig, draw, frames=len(seq), interval=100)
    anim.save(OUT + 'audit_walkthrough.gif', writer=PillowWriter(fps=10))
    plt.close(fig)


if __name__ == '__main__':
    hero(); method(); worked(); animation()
    print('done')
