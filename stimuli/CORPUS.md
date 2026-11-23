# Corpus audit — 21 September 2026

Imported source revisions and exact file hashes are in `sources.json`. Raw and
prepared data are local, gitignored artifacts. Rebuild with:

```sh
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m stimuli.prepare --output stimuli/prepared-new
```

The importer checks every source checksum and refuses an existing output directory.
The parser dependency is `pyarrow==25.0.1`; execution and analysis use the standard
library; plotting uses pinned Matplotlib. A download helper is not yet packaged; exact pinned URLs are in the manifest.

| Source | Usable nonidentity pairs | Independent task IDs | Pilot/main task split | Annotation outcome |
| --- | ---: | ---: | ---: | --- |
| MTBench | 877 | 80 | 16 / 64 | First-turn human preference margin |
| HANNA | 5,280 | 96 | 21 / 75 | Mean coherence rating difference, divided by 4 |
| SummEval | 11,938 | 100 | 27 / 73 | Mean expert consistency rating difference, divided by 4 |

Pair counts are not independent sample sizes. All pairs, exact copies, and format
variants of a task remain in its split. Splits use SHA256 of `split-v1:<task ID>`,
modulo five; zero is pilot. This rule does not use any audited judge output.

## MTBench

Human annotations only, first turn only. The two candidates must have identical
first user messages. Exact response texts determine pair identity; reversed votes
are realigned. Identical human votes from the same judge are deduplicated (3);
conflicting duplicates fail validation. Nonidentical responses with empty text
are excluded (4 pairs). Identical source responses are reserved for constructed
identity controls rather than being assigned a human quality gap.

Raters per usable pair: 404 have one, 265 two, 135 three, 51 four, 16 five,
5 six, and 1 seven. Descriptive gap-bin counts are 183 / 16 / 101 / 577 for
bins 1–4. These votes cannot establish fine true preference margins. Do not
advertise the five-bin ladder as externally known ground truth.

Source: [LMSYS human judgments](https://huggingface.co/datasets/lmsys/mt_bench_human_judgments),
revision `f7d2896d2cc5d80f8b55c2bbc722613555233c25`; card declares CC BY 4.0.

## HANNA

3,168 human rating rows for 1,056 stories and 96 prompts; three raters per story.
Pair different stories sharing a prompt. The initial import selects **coherence**,
retains all three ratings per story, and asks judges about story coherence.
Normalized rating gaps are not human preference margins. Descriptive bin counts
are 1,989 / 1,833 / 1,355 / 103.

Source: [HANNA authors' repository](https://github.com/dig-team/hanna-benchmark-asg),
revision `282f27536a5d05ad4ce14298abcd70c45668fed2`. The repository has an MIT license;
underlying WritingPrompts text provenance must also be retained at release.

## SummEval

1,600 summaries, 100 articles, three expert annotations per summary. Initial import
selects **factual consistency**. All 100 article IDs join to the pinned CNN/DailyMail
3.0.0 test split; missing articles cause a hard error. Candidate summaries remain
in their original annotated tokenization. Article text comes from the documented
CNN/DailyMail preprocessing, which should be acknowledged when comparing stimuli
with the original evaluation UI. Of 12,000 possible within-article pairs, 62 are
identical texts and omitted. Descriptive bin counts: 9,041 / 672 / 673 / 1,552.

Sources: [SummEval authors](https://github.com/Yale-LILY/SummEval), revision
`81b59ad53d63cb6009764240853c91235a44e238`; annotations downloaded from the authors'
Google Storage URL and content-hashed. [CNN/DailyMail](https://huggingface.co/datasets/abisee/cnn_dailymail),
revision `96df5e686bee6baa90b8bee7c28b81fa3fa6223d`. Repository/software licensing
does not establish unrestricted redistribution rights for original news articles.

## Preflight and pilot selection

G2 uses 50 request shapes from 37 MTBench/HANNA pilot tasks, with exact copies
filling the remaining shapes. It is a repeatability check, not 50 independent
human-labeled tasks. SummEval was joined after this manifest was fixed and is
included in the subsequent pilot.

The initial pilot selects 12 MTBench, 14 HANNA, and 14 SummEval tasks by seeded
hash order. Within each source, the desired nonidentity bin cycles 1–4 and the
closest available bin is selected, with hash tie-breaking. Four exact-copy
controls per source bring it to 52 stimuli / 40 tasks. Bin counts 0–4 are
12 / 14 / 7 / 14 / 5. The 3,952-call manifest is stored with hashes before execution.

Only one annotated criterion per rating corpus is imported initially. Other
criteria, listwise distractor construction, and expanded rubric granularities
need their own specified estimands before confirmatory use.
