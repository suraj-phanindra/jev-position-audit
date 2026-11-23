"""Synthetic null calibration of the proposed max-p rule. Original 2026-09-23 generators plus a
symmetric rare generator. Synthetic data only; no API outcomes read."""
import json, sys, time
import numpy as np
from signflip import signflip_p, registered_boot_p, holm_reject

COUNTS = [64, 75, 73]


def gen(kind, rng):
    out = []
    for n in COUNTS:
        if kind == 'symmetric_uniform': v = rng.uniform(-.5, .5, n)
        elif kind == 'centered_beta': v = rng.beta(.4, 4, n) - .4/4.4
        elif kind == 'rare_centered_bernoulli': v = rng.binomial(1, .02, n) - .02          # original, asymmetric
        elif kind == 'rare_symmetric': v = rng.binomial(1, .02, n) * rng.choice((-1., 1.), n)  # order-exchangeable
        out.append(v.astype(float))
    return out


def size(kind, sims, draws, seed):
    rng = np.random.default_rng(seed); hits = {k: [0, 0] for k in ('boot', 'flip', 'max')}; cov = 0
    for _ in range(sims):
        v = gen(kind, rng)
        pb, ci = registered_boot_p(v, draws, rng); pf = signflip_p(v, draws, rng); pm = max(pb, pf)
        for k, p in (('boot', pb), ('flip', pf), ('max', pm)):
            hits[k][0] += p <= .05; hits[k][1] += p <= .005
        cov += ci[0] <= 0 <= ci[1]
    return dict(kind=kind, sims=sims, draws=draws,
                rate_05={k: h[0]/sims for k, h in hits.items()},
                rate_005={k: h[1]/sims for k, h in hits.items()}, coverage95=cov/sims)


def fwer(kind, sims, draws, seed, m=10, rho=.5):
    rng = np.random.default_rng(seed); rb = rm = 0
    for _ in range(sims):
        common = gen(kind, rng); pbs = []; pms = []
        for _ in range(m):
            own = gen(kind, rng)
            v = [np.sqrt(rho)*c + np.sqrt(1-rho)*o for c, o in zip(common, own)]
            pb, _ = registered_boot_p(v, draws, rng); pf = signflip_p(v, draws, rng)
            pbs.append(pb); pms.append(max(pb, pf))
        rb += holm_reject(np.array(pbs)).any(); rm += holm_reject(np.array(pms)).any()
    return dict(kind=kind, sims=sims, draws=draws, m=m, rho=rho, fwer_boot=rb/sims, fwer_max=rm/sims)


if __name__ == '__main__':
    job, kind, sims, draws, seed = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
    t = time.time()
    r = size(kind, sims, draws, seed) if job == 'size' else fwer(kind, sims, draws, seed)
    r['seconds'] = round(time.time() - t)
    print(json.dumps(r), flush=True)
