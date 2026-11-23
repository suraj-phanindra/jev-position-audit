import base64
import copy
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import Mock, patch

from harness.audit import (digest, encode, generate, load_env, preflight_report, read_jsonl,
                           run, target_value, validate_manifest, validate_response, write_jsonl)


ROOT = Path(__file__).resolve().parents[1]


class AuditChecks(unittest.TestCase):
    def setUp(self):
        self.stimuli = read_jsonl(ROOT / "stimuli/example.jsonl")
        self.rows = generate(self.stimuli, "jev-1.13.0")

    def test_manifest_and_corruption(self):
        self.assertEqual(len(self.rows), 152)
        self.assertEqual(self.rows, generate(self.stimuli, "jev-1.13.0"))
        self.assertEqual(sum(len(json.loads(r["request_body"])["questions"]) for r in self.rows), 200)
        validate_manifest(self.rows)
        corrupt = copy.deepcopy(self.rows)
        request = json.loads(corrupt[0]["request_body"])
        request["state"]["task"] += " "
        corrupt[0]["request_body"] = encode(request)
        corrupt[0]["request_sha256"] = digest(corrupt[0]["request_body"])
        with self.assertRaisesRegex(ValueError, "incidental"):
            validate_manifest(corrupt)
        with self.assertRaises(ValueError):
            validate_manifest(self.rows[:-1])
        with self.assertRaises(ValueError):
            validate_manifest(self.rows + [self.rows[0]])

    def test_format_is_lossless_and_content_assignment_balanced(self):
        counts = {}
        for row in self.rows:
            m = row["meta"]
            if m["probe"] != "C-iii":
                continue
            counts[m["formatted_content"]] = counts.get(m["formatted_content"], 0) + 1
            candidates = json.loads(row["request_body"])["state"]["candidates"]
            original = next(s for s in self.stimuli if s["id"] == m["stimulus_id"])
            for candidate in candidates:
                content = "x" if candidate["id"] == m["target"] else "y"
                value = candidate["text"]
                if m["structured"] and content == m["formatted_content"]:
                    value = json.loads(value)["answer"]
                self.assertEqual(value, original[content])
        self.assertEqual(counts, {"x": 48, "y": 48})

    def test_semantic_score_reversal_and_pins(self):
        rows = [r for r in self.rows if r["meta"]["probe"] == "A" and r["meta"]["kind"] == "score"]
        for row in rows:
            request, target = json.loads(row["request_body"]), row["meta"]["target"]
            q = request["questions"]["preference"]
            weights = [Decimal(".1"), Decimal(".2"), Decimal(".7")]
            if row["meta"]["rubric_order"]:
                weights.reverse()
            answer = {"type": "score", "score": sum(i * p for i, p in enumerate(weights)), "confidence": Decimal(".42"),
                      "legend": {str(i): v for i, v in enumerate(q["criteria"])},
                      "probabilities": {str(i): v for i, v in enumerate(weights)}}
            self.assertEqual(target_value(answer, q, target), Decimal(".8"))
            response = {"model": "jev-1.13.0", "answers": {"preference": answer}}
            validate_response(response, request)
            response["model"] = "jev-1.14.0"
            with self.assertRaisesRegex(ValueError, "G3"):
                validate_response(response, request)
            answer["score"] = 0
            with self.assertRaisesRegex(ValueError, "contradicts"):
                target_value(answer, q, target)

    def test_full_distribution_stability_and_lexical_precision(self):
        row = next(r for r in self.rows if r["meta"]["kind"] == "noul")
        def response(value):
            raw = ('{"model":"jev-1.13.0","answers":{"preference":'
                   '{"type":"noul","noul":' + value + '}}}').encode()
            return {**row, "status": 200, "response_body_b64": base64.b64encode(raw).decode()}
        report = preflight_report([response("0.5010"), response("0.5020"), response("0.5010")])
        self.assertEqual(report["G2"]["changed_answer_vectors"], 1)
        self.assertEqual(report["G1"]["decimal_places_histograms"]["noul.noul"], {"4": 3})
        self.assertEqual(report["G4"]["status"], "requires_run_schedule")
        self.assertAlmostEqual(report["within_request_sd"]["noul"]["median"], .001/(3**.5))

    def test_input_and_budget_guards(self):
        bad = copy.deepcopy(self.stimuli)
        bad[0]["y"] += "different"
        with self.assertRaises(ValueError):
            generate(bad, "jev-1.13.0")
        with self.assertRaises(ValueError):
            generate(self.stimuli, "jev-latest")
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "budget"):
                run(self.rows, "/unused", 1)
            with self.assertRaisesRegex(ValueError, "TYPESAFE_API_KEY"):
                run(self.rows, "/unused", 152)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.jsonl"
            write_jsonl(path, self.rows)
            self.assertEqual(read_jsonl(path), self.rows)
            with self.assertRaises(FileExistsError):
                write_jsonl(path, self.rows)

    def test_literal_env_and_reference_envelopes(self):
        import os
        from preflight.live_check import payload, check_response
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {}, clear=True):
            path = Path(directory) / ".env"
            path.write_text('export TEST_A="literal $(echo secret)" # comment\nTEST_B=second\n')
            load_env(path)
            self.assertEqual(os.environ["TEST_A"], "literal $(echo secret)")
        a, b = payload("anthropic"), payload("together")
        self.assertEqual(a["messages"][-1], b["messages"][-1])
        self.assertEqual(a["system"], b["messages"][0]["content"])
        self.assertIs(b["logprobs"], True)
        self.assertEqual(b["top_logprobs"], 20)
        self.assertEqual(a["output_config"]["format"]["schema"], b["response_format"]["json_schema"]["schema"])
        data = {"model": a["model"], "stop_reason": "max_tokens", "content": [
            {"type": "text", "text": '{"noul":"true","choice":"X","score":"2"}'}]}
        self.assertFalse(check_response("anthropic", data, a)["valid_answers"])

    def test_http_failure_retains_raw_bytes_and_stops(self):
        import io
        raw = b'{"error":"rate limited", "detail":0.0100}\n'
        opener = Mock()
        opener.open.side_effect = urllib.error.HTTPError(
            "https://api.typesafe.ai/v1/systemone", 429, "rate limit", {}, io.BytesIO(raw))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run.jsonl"
            with patch.dict("os.environ", {"TYPESAFE_API_KEY": "local-test-secret"}):
                with patch("urllib.request.build_opener", return_value=opener):
                    with self.assertRaisesRegex(RuntimeError, "HTTP 429"):
                        run(self.rows, output, 152)
            logged = read_jsonl(output)
            self.assertEqual(len(logged), 1)
            self.assertEqual(base64.b64decode(logged[0]["response_body_b64"]), raw)
            self.assertEqual(opener.open.call_count, 1)
            self.assertNotIn("local-test-secret", output.read_text())


if __name__ == "__main__":
    unittest.main()
