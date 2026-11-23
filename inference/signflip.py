"""Proposed addition (2026-11-15, not adopted): task-level sign-flip test for the ten mean-type
primary estimands (A1, A5, C-iii), using the registered weights (sources 1/3, tasks equal within
source). Decision p = max(registered centered-bootstrap p, sign-flip p). Opens no outcomes."""
import numpy as np


def weighted_stat(task_means_by_source):
    return float(np.mean([v.mean() for v in task_means_by_source]))


def signflip_p(task_means_by_source, draws=9999, rng=None):
    rng = rng or np.random.default_rng(20261115)
    obs = abs(weighted_stat(task_means_by_source))
    null = np.zeros(draws)
    for v in task_means_by_source:
        signs = rng.choice((-1.0, 1.0), size=(draws, len(v)))
        null += (signs * v).mean(axis=1)
    null = np.abs(null / len(task_means_by_source))
    return (1 + int(np.sum(null >= obs - 1e-12))) / (draws + 1)


def registered_boot_p(task_means_by_source, draws=9999, rng=None):
    """Copy of the registered centered-bootstrap p in analysis/main.py:mean_tests (same formula)."""
    rng = rng or np.random.default_rng(20260930)
    est = weighted_stat(task_means_by_source)
    boot = np.mean([v[rng.integers(0, len(v), (draws, len(v)))].mean(axis=1)
                    for v in task_means_by_source], axis=0)
    p = (1 + int(np.sum(abs(boot - est) >= abs(est)))) / (draws + 1)
    return p, np.quantile(boot, [.025, .975]).tolist()


def holm_reject(pvals, alpha=.05):
    order = np.argsort(pvals); m = len(pvals); prev = 0; rej = np.zeros(m, bool)
    for i, j in enumerate(order):
        prev = max(prev, min(1, (m - i) * pvals[j])); rej[j] = prev <= alpha
    return rej
