"""Stdlib-only Probe A and C-iii preflight. No main-study execution command."""

import argparse
import base64
import copy
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import gzip
import hashlib
import itertools
import json
import os
from pathlib import Path
import random
import re
import shlex
import statistics
import time
import urllib.error
import urllib.request


ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DIMENSIONS = ("helpfulness", "accuracy", "safety", "style")


def load_env(path):
    """Read literal KEY=value assignments; never execute shell or expand values."""
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        try:
            parts = shlex.split(line, comments=True)
        except ValueError:
            raise ValueError(f"Invalid env syntax on line {number}") from None
        if parts and parts[0] == "export":
            parts = parts[1:]
        if not parts:
            continue
        if len(parts) != 1 or "=" not in parts[0]:
            raise ValueError(f"Expected one KEY=value assignment on env line {number}")
        name, value = parts[0].split("=", 1)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError(f"Invalid variable name on env line {number}")
        os.environ.setdefault(name, value)


def encode(value):
    # Never sort request keys: insertion order is an experimental treatment.
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_jsonl(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write_jsonl(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(encode(row) + "\n")


def validate_stimuli(stimuli):
    ids = set()
    if not stimuli:
        raise ValueError("Empty stimulus corpus")
    for item in stimuli:
        for key in ("id", "seed_id", "source", "gap_basis", "prompt", "x", "y"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError(f"Nonempty string required: {key}")
        if item["id"] in ids:
            raise ValueError("Duplicate stimulus id")
        ids.add(item["id"])
        if type(item.get("gap_bin")) is not int or item["gap_bin"] not in range(5):
            raise ValueError("gap_bin must be an integer from 0 to 4")
        if (item["gap_bin"] == 0) != (item["x"] == item["y"]):
            raise ValueError("Exact copies must be in gap_bin 0, and only exact copies")


def question(kind, target, other, dimension="overall response quality"):
    context = f"Evaluate `candidates` as answers to `task` on {dimension}. "
    if kind == "noul":
        return {"type": kind,
                "instructions": context + f"Is candidate {target} strictly better than candidate {other}?",
                "criteria": {"true": f"{target} is strictly better.",
                             "false": f"{target} is worse or the candidates are equally good."}}
    if kind == "choice":
        return {"type": kind,
                "instructions": context + "Select a preferred candidate. If equally good, "
                "assign equal preference probability to both candidates.",
                "criteria": {key: f"Prefer candidate {key}." for key in ("X", "Y")}}
    return {"type": "score", "instructions": context + f"Rate {target} relative to {other}.",
            "criteria": [f"{other} is better than {target}.", "The candidates are equally good.",
                         f"{target} is better than {other}."]}


def format_candidate(text, family):
    if family == "simple":
        return encode({"answer": text})
    if family == "neutral":
        return encode({"records": {"response": {"kind": "choice", "selected": text}}})
    if family == "native":
        return encode({"answers": {"response": {"type": "choice", "choice": text}}})
    raise ValueError("Unknown format family")


def unformat_candidate(text, family):
    wrapped = json.loads(text)
    try:
        value = (wrapped["answer"] if family == "simple" else
                 wrapped["records"]["response"]["selected"] if family == "neutral" else
                 wrapped["answers"]["response"]["choice"])
    except (KeyError, TypeError):
        raise ValueError("C-iii wrapper changed content schema") from None
    if not isinstance(value, str) or format_candidate(value, family) != text:
        raise ValueError("C-iii wrapper changed content schema")
    return value


def generate(stimuli, model, seed=20260921, repeats=1, format_controls=False):
    validate_stimuli(stimuli)
    if not re.fullmatch(r"jev-\d+\.\d+\.\d+", model):
        raise ValueError("Use an explicit versioned Jev model, not an alias")
    if repeats < 1:
        raise ValueError("repeats must be positive")
    rows = []
    for item, labels_swapped, kind in itertools.product(stimuli, (0, 1), ("noul", "choice", "score", "questions")):
        target, other = ("Y", "X") if labels_swapped else ("X", "Y")
        state = {"task": item["prompt"], "candidates": [
            {"id": target, "text": item["x"]}, {"id": other, "text": item["y"]}]}
        questions = ({d: question("choice", target, other, d) for d in DIMENSIONS}
                     if kind == "questions" else {"preference": question(kind, target, other, item.get("dimension", "overall response quality"))})
        surface = {"noul": None, "choice": "choice_order", "score": "rubric_order",
                   "questions": "question_order"}[kind]
        for state_order, second_order in itertools.product((0, 1), (0, 1) if surface else (0,)):
            request = {"state": copy.deepcopy(state), "model": model, "questions": copy.deepcopy(questions)}
            if state_order:
                request["state"]["candidates"].reverse()
            if second_order and kind == "questions":
                request["questions"] = dict(reversed(list(request["questions"].items())))
            elif second_order:
                criteria = request["questions"]["preference"]["criteria"]
                request["questions"]["preference"]["criteria"] = (
                    dict(reversed(list(criteria.items()))) if kind == "choice" else list(reversed(criteria)))
            body = encode(request)
            metadata = {"probe": "A", "stimulus_id": item["id"], "seed_id": item["seed_id"], "source": item["source"],
                        "stimulus_sha256": digest(encode(item)), "gap_bin": item["gap_bin"],
                        "gap_basis": item["gap_basis"], "kind": kind, "target": target,
                        "labels_swapped": labels_swapped, "state_order": state_order,
                        "choice_order": second_order if kind == "choice" else 0,
                        "rubric_order": second_order if kind == "score" else 0,
                        "question_order": second_order if kind == "questions" else 0}
            for replicate in range(repeats):
                rows.append({"meta": metadata, "replicate": replicate,
                             "request_body": body, "request_sha256": digest(body)})
    # Cross format with state position, content identity, and candidate labels.
    for item, labels_swapped, kind, formatted_content, state_order, structured, family in itertools.product(
            stimuli, (0, 1), ("noul", "choice", "score"), ("x", "y"), (0, 1), (0, 1),
            ("simple", "neutral", "native") if format_controls else ("simple",)):
        target, other = ("Y", "X") if labels_swapped else ("X", "Y")
        candidates = [{"id": label, "text": format_candidate(item[content], family)
                       if structured and content == formatted_content else item[content]}
                      for label, content in ((target, "x"), (other, "y"))]
        if state_order:
            candidates.reverse()
        request = {"state": {"task": item["prompt"], "candidates": candidates}, "model": model,
                   "questions": {"preference": question(kind, target, other, item.get("dimension", "overall response quality"))}}
        body = encode(request)
        metadata = {"probe": "C-iii", "stimulus_id": item["id"], "seed_id": item["seed_id"],
                    "source": item["source"], "stimulus_sha256": digest(encode(item)),
                    "gap_bin": item["gap_bin"], "gap_basis": item["gap_basis"], "kind": kind,
                    "target": target, "labels_swapped": labels_swapped, "state_order": state_order,
                    "choice_order": 0, "rubric_order": 0, "question_order": 0,
                    "formatted_content": formatted_content, "structured": structured}
        if format_controls:
            metadata["format_family"] = family
        for replicate in range(repeats):
            rows.append({"meta": metadata, "replicate": replicate,
                         "request_body": body, "request_sha256": digest(body)})
    random.Random(seed).shuffle(rows)
    validate_manifest(rows)
    return rows


def validate_manifest(rows):
    """G5: undo only declared permutations; all remaining bytes must match."""
    if not rows:
        raise ValueError("Empty manifest")
    extensions = [r for r in rows if r['meta'].get('extension')]
    if extensions:
        from harness.extensions import validate_extensions
        validate_extensions(extensions)
        rows = [r for r in rows if not r['meta'].get('extension')]
    groups, cells = {}, defaultdict(Counter)
    for row in rows:
        body, meta = row["request_body"], row["meta"]
        if digest(body) != row["request_sha256"]:
            raise ValueError("Request hash mismatch")
        request = json.loads(body)
        if encode(request) != body:
            raise ValueError("Noncanonical request bytes")
        if not re.fullmatch(r"jev-\d+\.\d+\.\d+", request["model"]):
            raise ValueError("Unpinned model")
        if meta["probe"] == "C-iii" and meta["structured"]:
            label = meta["target"] if meta["formatted_content"] == "x" else ("Y" if meta["target"] == "X" else "X")
            candidate = next(c for c in request["state"]["candidates"] if c["id"] == label)
            candidate["text"] = unformat_candidate(candidate["text"], meta.get("format_family", "simple"))
        if meta["state_order"]:
            request["state"]["candidates"].reverse()
        if meta["choice_order"]:
            q = request["questions"]["preference"]
            q["criteria"] = dict(reversed(list(q["criteria"].items())))
        if meta["rubric_order"]:
            request["questions"]["preference"]["criteria"].reverse()
        if meta["question_order"]:
            request["questions"] = dict(reversed(list(request["questions"].items())))
        key = (meta["stimulus_id"], meta["labels_swapped"], meta["kind"], row["replicate"],
               meta["probe"], meta.get("formatted_content"), meta.get("format_family"))
        canonical = encode(request)
        if key in groups and groups[key] != canonical:
            raise ValueError("G5 failed: incidental differences between mirrored requests")
        groups[key] = canonical
        cell = ((meta["state_order"], meta["structured"]) if meta["probe"] == "C-iii" else
                tuple(meta[k] for k in ("state_order", "choice_order", "rubric_order", "question_order")))
        cells[key][cell] += 1
    for key, observed in cells.items():
        if key[4] == "C-iii":
            if set(observed) != set(itertools.product((0, 1), repeat=2)) or any(n != 1 for n in observed.values()):
                raise ValueError("Missing or duplicated C-iii cells")
            continue
        kind = key[2]
        axis = {"noul": None, "choice": 1, "score": 2, "questions": 3}[kind]
        expected = set()
        for state_order, second in itertools.product((0, 1), (0, 1) if axis else (0,)):
            cell = [state_order, 0, 0, 0]
            if axis:
                cell[axis] = second
            expected.add(tuple(cell))
        if set(observed) != expected or any(n != 1 for n in observed.values()):
            raise ValueError("Missing or duplicated factorial cells")


def probability(value):
    value = Decimal(str(value))
    if not value.is_finite() or not 0 <= value <= 1:
        raise ValueError("Invalid probability")
    return value


def score_value(probs, levels, canonical):
    if len(canonical)<2 or len(set(canonical))!=len(canonical) or set(levels)!=set(canonical):
        raise ValueError("Score semantic mapping unspecified or duplicated")
    return sum(Decimal(canonical.index(level))*Decimal(str(probs[str(i)]))
               for i,level in enumerate(levels))/Decimal(len(canonical)-1)


def target_value(answer, request_question, target, canonical_levels=None):
    """Normalize direction; score output is a rubric coordinate, not P(preference)."""
    kind = request_question["type"]
    if answer.get("type") != kind:
        raise ValueError("Answer type mismatch")
    if kind == "noul":
        return probability(answer["noul"])
    raw = answer["probabilities"]
    expected = (set(request_question["criteria"]) if kind == "choice"
                else {str(i) for i in range(len(request_question["criteria"]))})
    if set(raw) != expected:
        raise ValueError("Answer probability keys differ from requested outcomes")
    probs = {k: probability(v) for k, v in raw.items()}
    # Permit explicitly bounded decimal rounding; never silently renormalize.
    mass_tolerance = max(Decimal("0.02"), Decimal("0.005")*len(probs))
    if abs(sum(probs.values()) - 1) > mass_tolerance:
        raise ValueError("Probability mass does not sum to one within rounding tolerance")
    probability(answer["confidence"])
    if kind == "choice":
        if answer["choice"] not in expected:
            raise ValueError("Unknown choice")
        if probs[answer["choice"]] < max(probs.values()) - Decimal("0.01"):
            raise ValueError("Returned choice contradicts its probability distribution")
        return probs[target]
    levels = request_question["criteria"]
    if answer["legend"] != {str(i): level for i, level in enumerate(levels)}:
        raise ValueError("Score legend does not match request")
    score = Decimal(str(answer["score"]))
    raw_expected = sum(Decimal(i) * probs[str(i)] for i in range(len(levels)))
    score_tolerance = max(Decimal("0.04"),Decimal("0.005")*(sum(range(len(levels)))+1))
    if not score.is_finite() or not 0 <= score <= len(levels) - 1 or abs(score - raw_expected) > score_tolerance:
        raise ValueError("Returned score contradicts its probability distribution")
    opposite = "Y" if target == "X" else "X"
    canonical = canonical_levels if canonical_levels is not None else [
        f"{opposite} is better than {target}.", "The candidates are equally good.",
        f"{target} is better than {opposite}."]
    return score_value(probs,levels,canonical)


def validate_response(response, request):
    if response["model"] != request["model"]:
        raise ValueError("G3 failed: response model differs from pinned model")
    if set(response["answers"]) != set(request["questions"]):
        raise ValueError("Response question ids do not match")
    for name, q in request["questions"].items():
        target = next(iter(q['criteria'])) if q['type']=='choice' else 'X'
        target_value(response["answers"][name], q, target,
                     canonical_levels=q['criteria'] if q['type']=='score' else None)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "Redirect refused", headers, fp)


def run(rows, output, max_calls):
    validate_manifest(rows)
    if not 1 <= len(rows) <= max_calls:
        raise ValueError(f"Manifest has {len(rows)} calls; explicit budget is {max_calls}")
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        raise ValueError("Set TYPESAFE_API_KEY before a live preflight")
    opener = urllib.request.build_opener(NoRedirect())
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    # ponytail: serial, fail-fast preflight; add paced concurrency for the main sweep.
    with open(output, "x", encoding="utf-8") as stream:
        for row in rows:
            request = urllib.request.Request(ENDPOINT, data=row["request_body"].encode("utf-8"),
                                             headers={"Authorization": f"Bearer {key}",
                                                      "Content-Type": "application/json"}, method="POST")
            record = {**row, "started_at": datetime.now(timezone.utc).isoformat(),
                      "endpoint": ENDPOINT, "phase": "preflight"}
            start = time.monotonic()
            try:
                with opener.open(request, timeout=60) as response:
                    raw, status = response.read(), response.status
            except urllib.error.HTTPError as error:
                raw, status = error.read(), error.code
            except (OSError, urllib.error.URLError) as error:
                record.update(status=None, transport_error=type(error).__name__, elapsed_s=time.monotonic() - start)
                stream.write(encode(record) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
                raise RuntimeError("Transport failure logged; stopped without retry") from None
            record.update(status=status, elapsed_s=time.monotonic() - start,
                          response_body_b64=base64.b64encode(raw).decode("ascii"))
            stream.write(encode(record) + "\n")
            stream.flush()
            os.fsync(stream.fileno())  # Persist original bytes before parsing or validating.
            if status != 200:
                raise RuntimeError(f"HTTP {status} logged; stopped without retry")
            validate_response(json.loads(raw, parse_float=Decimal), json.loads(row["request_body"]))


def preflight_report(records):
    precision, repeats, models = defaultdict(Counter), defaultdict(list), Counter()
    grid_distance = defaultdict(Decimal)
    request_questions = {}
    usage = Counter()
    latencies = []
    failures, successes = 0, 0
    for row in records:
        if digest(row["request_body"]) != row["request_sha256"]:
            raise ValueError("Recorded request hash mismatch")
        if row.get("status") != 200:
            failures += 1
            continue
        raw = base64.b64decode(row["response_body_b64"], validate=True)
        data = json.loads(raw, parse_float=Decimal, parse_int=Decimal)
        validate_response(data, json.loads(row["request_body"]))
        successes += 1
        latencies.append(row.get("elapsed_s",0))
        usage.update({k:int(v) for k,v in data.get("usage",{}).items() if isinstance(v,(int,Decimal))})
        models[data["model"]] += 1
        repeats[row["request_sha256"]].append(data["answers"])
        request_questions[row["request_sha256"]] = json.loads(row["request_body"])["questions"]
        for answer in data["answers"].values():
            for field in ("noul", "confidence", "score", "probabilities"):
                if field not in answer:
                    continue
                values = answer[field].values() if field == "probabilities" else [answer[field]]
                for value in values:
                    value = Decimal(value)
                    places = max(0, -value.as_tuple().exponent)
                    name = answer["type"] + "." + field
                    precision[name][str(places)] += 1
                    grid_distance[name] = max(grid_distance[name], abs(value-value.quantize(Decimal(".01"))))
    within_sd = defaultdict(list)
    for request_hash, answers in repeats.items():
        if len(answers) < 2:
            continue
        for name, q in request_questions[request_hash].items():
            target = sorted(q['criteria'])[0] if q['type']=='choice' else 'X'
            values = [float(target_value(a[name], q, target,
                       canonical_levels=q['criteria'] if q['type']=='score' else None)) for a in answers]
            within_sd[q["type"]].append(statistics.stdev(values))
    repeated = [answers for answers in repeats.values() if len(answers) > 1]
    comparisons = sum(len(a) - 1 for a in repeated)
    changes = sum(answer != answers[0] for answers in repeated for answer in answers[1:])
    return {"successful_calls": successes, "failed_calls": failures,
            "G1": {"status": "descriptive_only", "decimal_places_histograms": dict(precision),
                   "max_distance_from_001_grid": {k:str(v) for k,v in grid_distance.items()},
                   "note": "Lexical precision does not prove a rounding quantum or a population MDE."},
            "G2": {"status": "observed_only" if comparisons else "not_measured",
                   "repeated_requests": len(repeated), "comparisons_to_first": comparisons,
                   "changed_answer_vectors": changes,
                   "note": "Finite repeats cannot prove determinism; verdict stability alone is insufficient."},
            "G3": {"status": "observed_pin_match" if successes else "not_measured", "models": dict(models)},
            "G4": {"status": "requires_run_schedule", "note": "Interpret timings with the requested pacing and concurrency."},
            "within_request_sd": {kind: {"request_shapes": len(values), "median": statistics.median(values),
                "max": max(values)} for kind, values in within_sd.items()},
            "usage": dict(usage), "latency_s": {"mean": sum(latencies)/len(latencies) if latencies else None,
            "max": max(latencies) if latencies else None},
            "G5": {"status": "check_manifest", "note": "Use the check command on the complete manifest."}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("manifest")
    build.add_argument("stimuli")
    build.add_argument("output")
    build.add_argument("--model", default="jev-1.13.0")
    build.add_argument("--seed", type=int, default=20260921)
    build.add_argument("--repeats", type=int, default=1)
    build.add_argument("--format-controls", action="store_true", help="Add neutral and Jev-like nested envelopes")
    check = commands.add_parser("check")
    check.add_argument("manifest")
    live = commands.add_parser("run-preflight")
    live.add_argument("manifest")
    live.add_argument("output")
    live.add_argument("--max-calls", type=int, required=True)
    live.add_argument("--env-file", help="Read literal assignments without executing shell")
    report = commands.add_parser("report")
    report.add_argument("run")
    args = parser.parse_args()
    if args.command == "manifest":
        rows = generate(read_jsonl(args.stimuli), args.model, args.seed, args.repeats, args.format_controls)
        write_jsonl(args.output, rows)
        print(f"Wrote {len(rows)} calls; {sum(len(json.loads(r['request_body'])['questions']) for r in rows)} judgments")
    elif args.command == "check":
        rows = read_jsonl(args.manifest)
        validate_manifest(rows)
        print(f"G5 passed for {len(rows)} calls; manifest SHA256={digest(Path(args.manifest).read_text())}")
    elif args.command == "run-preflight":
        if args.env_file:
            load_env(args.env_file)
        run(read_jsonl(args.manifest), args.output, args.max_calls)
    else:
        print(json.dumps(preflight_report(read_jsonl(args.run)), indent=2))


if __name__ == "__main__":
    main()
