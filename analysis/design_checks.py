"""Illustrative protocol arithmetic, not a pilot estimator or power calculation."""

from decimal import Decimal
import json
import math


def main():
    # A common one-direction shift and a bound allowing either direction differ.
    density = 1.2
    common_shift = .01 / density
    bounded_shift = .01 / (2 * density)
    assert math.isclose(common_shift, 2 * bounded_shift)

    samples, stimuli, conditions = 20, 4000, 2
    calls = stimuli * conditions * samples
    assert calls == 160000
    probability_se = math.sqrt(.5 * .5 / samples)
    contrast_se = math.sqrt(2 * .5 * .5 / samples)
    assert math.isclose(contrast_se, math.sqrt(2) * probability_se)

    # Deterministic rounding can hide a nonzero mean for arbitrarily many items.
    before, after, step = Decimal('.491'), Decimal('.494'), Decimal('.01')
    assert after - before == Decimal('.003')
    assert after.quantize(step) - before.quantize(step) == 0

    input_tokens, output_tokens = 1000, 20
    deepseek = calls * (input_tokens * .14 + output_tokens * .28) / 1_000_000
    haiku = calls * (input_tokens * 1 + output_tokens * 5) / 1_000_000
    assert math.isclose(deepseek, 23.296)
    assert math.isclose(haiku, 176)
    print(json.dumps({
        'status': 'illustrative arithmetic only; not an adopted margin',
        'common_shift_margin': common_shift,
        'bounded_bidirectional_margin': bounded_shift,
        'single_condition_se_at_half': probability_se,
        'independent_paired_contrast_se_at_half': contrast_se,
        'calls_per_judge_two_conditions': calls,
        'deepseek_usd_example': deepseek,
        'haiku_usd_example': haiku,
        'jev_usd_200k_calls_1k_input_tokens': 200000 * 1000 * .042 / 1_000_000,
        'latent_rounding_example_shift': str(after - before),
        'returned_rounding_example_shift': str(after.quantize(step) - before.quantize(step)),
    }, indent=2))


if __name__ == '__main__':
    main()
