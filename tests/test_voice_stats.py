#!/usr/bin/env python3
"""Regression tests for voice_stats.py.

Every test here corresponds to a measurement that was once wrong. The point of
the suite is not coverage; it is that the numbers the skill acts on stay true.

    python3 -m unittest discover -s tests -v
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "voice_stats.py")

spec = importlib.util.spec_from_file_location("voice_stats", SCRIPT)
vs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vs)


def measure(text):
    lines, paras = vs.split_units(text)
    return vs.analyze([(lines, paras)])


def run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args],
                          capture_output=True, text=True)


class Segmentation(unittest.TestCase):
    """개조식 lists were collapsed into a single 99-character 'sentence'."""

    BULLETS = (
        "# 사업 개요\n\n"
        "- 시장 규모는 1,200억 원이다\n"
        "- 경쟁사는 3곳이다\n"
        "- 우리는 즉시 대응한다\n"
        "- 마진율은 42퍼센트다\n"
        "- 손익분기는 18개월이다\n"
    )

    def test_each_list_item_is_a_sentence(self):
        m = measure(self.BULLETS)
        self.assertEqual(m["sentences"], 5)
        self.assertLess(m["sent_len_mean"], 20)
        self.assertEqual(m["long_ratio"], 0.0)

    def test_headings_are_not_counted_as_prose(self):
        m = measure("# 제목\n\n## 부제\n\n본문 한 문장이다.\n")
        self.assertEqual(m["sentences"], 1)
        self.assertEqual(m["endings"], {"한다체": 1.0})

    def test_tables_rules_and_fences_are_dropped(self):
        m = measure(
            "본문이다.\n\n"
            "| a | b |\n| --- | --- |\n| 1 | 2 |\n\n"
            "---\n\n"
            "```\ncode = 1\n```\n"
        )
        self.assertEqual(m["sentences"], 1)

    def test_terminal_punctuation_still_splits_within_a_line(self):
        m = measure("첫 문장이다. 둘째 문장이다. 셋째 문장이다.\n")
        self.assertEqual(m["sentences"], 3)

    def test_numbered_lists_and_checkboxes(self):
        m = measure("1. 첫째다\n2. 둘째다\n\n- [ ] 셋째다\n")
        self.assertEqual(m["sentences"], 3)
        self.assertNotIn("[", "".join(str(m["top_endings"])))


class Counting(unittest.TestCase):

    def test_thousands_separator_is_not_a_comma(self):
        m = measure("시장 규모는 1,200억 원이다.\n")
        self.assertEqual(m["comma_per_sent"], 0.0)

    def test_real_commas_are_still_counted(self):
        m = measure("장면, 맥락, 해석 순으로 쓴다.\n")
        self.assertEqual(m["comma_per_sent"], 2.0)

    def test_connective_requires_word_boundary(self):
        """즉시 / 즉각 must not be counted as the connective 즉."""
        self.assertEqual(measure("우리는 즉시 대응한다.\n")["top_connectives"], {})
        self.assertEqual(measure("즉각 움직였다.\n")["top_connectives"], {})
        self.assertEqual(measure("즉, 실패했다.\n")["top_connectives"], {"즉": 1})

    def test_stems_still_match_inflections(self):
        """Hedges and drift markers are stems on purpose."""
        m = measure("데이터를 활용하는 방안을 진행하였다.\n")
        self.assertGreater(m["drift_markers_per_100_sent"], 0)
        h = measure("그럴 수 있다고 보인다.\n")
        self.assertGreater(h["hedges_per_100_sent"], 0)


class LengthIndependence(unittest.TestCase):
    """Plain TTR falls as text grows, so drafts could never match a corpus."""

    UNIT = ("장면이 먼저 온다.\n해석은 나중이다.\n문장 길이를 흔든다.\n"
            "감정은 명명하지 않는다.\n증거를 제출한다.\n")

    def test_mattr_is_stable_across_length(self):
        short = measure(self.UNIT * 8)["mattr"]
        long = measure(self.UNIT * 30)["mattr"]
        self.assertIsNotNone(short)
        self.assertAlmostEqual(short, long, delta=0.03)

    def test_raw_ttr_is_not_stable(self):
        short = measure(self.UNIT * 8)["ttr_raw"]
        long = measure(self.UNIT * 30)["ttr_raw"]
        self.assertGreater(short - long, 0.05)

    def test_mattr_is_none_below_a_full_window(self):
        self.assertIsNone(measure("짧은 글이다.\n")["mattr"])


class Verdicts(unittest.TestCase):

    def test_zero_baseline_is_no_evidence_not_a_deviation(self):
        base = {"connectives_per_100_sent": 0.0}
        draft = {"connectives_per_100_sent": 90.0}
        v, _ = vs.verdict_for("connectives_per_100_sent", draft, base, 0.60, "rel")
        self.assertEqual(v, vs.NOBASE)

    def test_real_deviation_is_flagged(self):
        base = {"connectives_per_100_sent": 10.0}
        draft = {"connectives_per_100_sent": 90.0}
        v, _ = vs.verdict_for("connectives_per_100_sent", draft, base, 0.60, "rel")
        self.assertEqual(v, vs.FLAG)

    def test_missing_metric_yields_no_evidence(self):
        v, _ = vs.verdict_for("mattr", {"mattr": None}, {"mattr": 0.7}, 0.15, "rel")
        self.assertEqual(v, vs.NOBASE)

    def test_noisy_short_draft_mean_is_not_called_drift(self):
        """A wide bootstrap interval covering the baseline means 'cannot tell'."""
        draft = {"sent_len_mean": 30.0, "sent_len_ci90": [18.0, 44.0]}
        v, _ = vs.verdict_for("sent_len_mean", draft, {"sent_len_mean": 40.0},
                              0.20, "rel")
        self.assertEqual(v, vs.INDIST)

    def test_confident_mean_shift_is_flagged(self):
        draft = {"sent_len_mean": 30.0, "sent_len_ci90": [28.0, 32.0]}
        v, _ = vs.verdict_for("sent_len_mean", draft, {"sent_len_mean": 40.0},
                              0.20, "rel")
        self.assertEqual(v, vs.FLAG)

    def test_bootstrap_ci_is_deterministic(self):
        vals = [10, 20, 30, 40, 50, 60, 70]
        self.assertEqual(vs.bootstrap_mean_ci(vals), vs.bootstrap_mean_ci(vals))


class SampleGate(unittest.TestCase):

    def test_thin_corpus_is_marked_unreliable(self):
        self.assertFalse(measure("짧다.\n")["reliable"])

    def test_large_corpus_is_reliable(self):
        self.assertTrue(measure("문장을 충분히 길게 반복한다.\n" * 200)["reliable"])


class CliContract(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def path(self, name, text=""):
        p = os.path.join(self.dir, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return p

    def test_out_does_not_truncate_on_failure(self):
        """The original `> metrics.json` destroyed the baseline whenever the
        script exited nonzero."""
        out = self.path("metrics.json", '{"sentences": 9}')
        empty = self.path("empty.md", "")
        r = run(empty, "--out", out)
        self.assertEqual(r.returncode, 1)
        with open(out, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["sentences"], 9)

    def test_out_writes_valid_json_on_success(self):
        src = self.path("a.md", "문장이 하나 있다.\n")
        out = os.path.join(self.dir, "m.json")
        self.assertEqual(run(src, "--out", out).returncode, 0)
        with open(out, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["sentences"], 1)

    def test_corrupt_baseline_gives_a_message_not_a_traceback(self):
        base = self.path("bad.json", "")
        src = self.path("d.md", "초안이다.\n")
        r = run(src, "--compare", base)
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("손상", r.stderr)

    def test_missing_baseline_gives_a_message_not_a_traceback(self):
        src = self.path("d.md", "초안이다.\n")
        r = run(src, "--compare", os.path.join(self.dir, "nope.json"))
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Traceback", r.stderr)

    def test_compare_exit_code_signals_flags(self):
        # Paragraphs of four, as real prose is; a single 220-sentence block
        # would make sents_per_para a function of document length.
        para = "장면을 먼저 적는다.\n" * 4 + "\n"
        # 1,500+ chars so the baseline clears the reliability gate; a thinner
        # corpus is suppressed to 참고 on purpose (see the test below).
        corpus = self.path("c.md", para * 55)
        out = os.path.join(self.dir, "m.json")
        run(corpus, "--out", out)

        clean = self.path("clean.md", para * 10)
        self.assertEqual(run(clean, "--compare", out).returncode, 0)

        drifted = ("따라서 데이터를 활용하여 사업을 진행하고 시장 상황을 면밀히 "
                   "검토한 결과를 종합적으로 반영하였습니다.\n") * 4 + "\n"
        drift = self.path("drift.md", drifted * 10)
        self.assertEqual(run(drift, "--compare", out).returncode, 2)

    def test_thin_baseline_suppresses_drift_verdicts(self):
        corpus = self.path("c.md", "짧다.\n")
        out = os.path.join(self.dir, "m.json")
        run(corpus, "--out", out)
        drift = self.path("d.md", "따라서 매우 길고 장황한 문장을 계속 이어서 씁니다.\n" * 20)
        r = run(drift, "--compare", out)
        self.assertEqual(r.returncode, 0)
        self.assertIn("참고", r.stdout)


class Holdout(unittest.TestCase):
    """Leave-one-out: every fold's draft is the writer's own writing, so every
    flag it produces is a false positive by construction."""

    SENTS = ["쌀통을 기울여야 한 컵이 나왔다.", "어머니는 그걸 매일 아침에 했다.",
             "나는 그 소리로 잠에서 깼다.", "그 소리가 짧으면 밥이 적었다.",
             "학교에서는 아무 말도 하지 않았다.", "도시락을 열면 김치와 밥이었다."]

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def corpus(self, count, repeats=12):
        os.makedirs(os.path.join(self.dir, "c"), exist_ok=True)
        paths = []
        for i in range(count):
            rotated = self.SENTS[i:] + self.SENTS[:i]
            body = ""
            for _ in range(repeats):
                for j in range(0, len(rotated), 3):
                    body += "\n".join(rotated[j:j + 3]) + "\n\n"
            p = os.path.join(self.dir, "c", f"s{i}.md")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("---\nmode: 회고·서사\nsource: user\n---\n\n" + body)
            paths.append(p)
        return paths

    def test_refuses_below_three_samples(self):
        r = run(*self.corpus(2), "--holdout")
        self.assertEqual(r.returncode, 1)
        self.assertIn("3편 이상", r.stderr)

    def test_reports_a_false_positive_rate(self):
        r = run(*self.corpus(4), "--holdout")
        self.assertEqual(r.returncode, 0)
        self.assertIn("전체 오탐률", r.stdout)
        self.assertIn("권장", r.stdout)

    def test_identical_samples_produce_no_false_positives(self):
        """A corpus with no internal variation must flag nothing."""
        os.makedirs(os.path.join(self.dir, "same"), exist_ok=True)
        body = "장면을 먼저 적는다.\n해석은 나중이다.\n\n" * 40
        paths = []
        for i in range(4):
            p = os.path.join(self.dir, "same", f"s{i}.md")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(body)
            paths.append(p)
        r = run(*paths, "--holdout")
        self.assertEqual(r.returncode, 0)
        self.assertIn("전체 오탐률 0%", r.stdout)

    def test_thin_folds_are_excluded_not_counted(self):
        r = run(*self.corpus(3, repeats=1), "--holdout")
        self.assertIn("제외했습니다", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
