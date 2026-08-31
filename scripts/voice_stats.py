#!/usr/bin/env python3
"""Measure the stylistic fingerprint of Korean (or any) prose.

Turns a voice profile from an opinion into something checkable: a draft can be
compared against the corpus it is supposed to sound like.

    python3 voice_stats.py corpus/*.md --json --out metrics.json
    python3 voice_stats.py draft.md --compare metrics.json

Standard library only. Metrics are shallow by design -- they catch drift toward
generic model prose, not literary quality.

Two things this tool deliberately refuses to do:

* It does not flag a metric whose baseline is 0 or whose corpus is too small.
  "No evidence" is reported as no evidence, never as a deviation.
* It does not ask you to move a draft toward the corpus mean. Variance is what
  makes prose sound human; a flag is a question, not an instruction.

Segmentation note: every markdown line is a sentence boundary, so 개조식 lists
are counted as the several sentences they are. Headings, tables, code fences and
horizontal rules are dropped rather than counted as prose. A hard-wrapped
paragraph would be over-split; write one paragraph per line.
"""

import argparse
import glob
import json
import os
import random
import re
import statistics
import sys
import tempfile
import unicodedata

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HANGUL = r"가-힣"

# Below this, a baseline is too thin to compare against. Matches the "잠정"
# threshold in references/learning-protocol.md -- the doc and the code must agree.
MIN_BASELINE_CHARS = 1500
MIN_DRAFT_SENTENCES = 8
MATTR_WINDOW = 100

CONNECTIVES = [
    "그리고", "그러나", "하지만", "그래서", "따라서", "그러므로", "즉", "또한",
    "물론", "다만", "오히려", "한편", "그런데", "게다가", "결국", "특히",
    "예를 들어", "무엇보다", "이처럼", "그럼에도",
]

HEDGES = [
    "아마", "듯하다", "듯했다", "것 같다", "것 같았다", "수 있다", "수도 있다",
    "보인다", "여겨진다", "추정", "가능성", "어쩌면", "대체로", "아마도",
]

# Vocabulary uplift: bureaucratic verbs a model reaches for when drifting.
DRIFT_MARKERS = [
    "활용하", "진행하", "수행하", "실시하", "도모하", "제고하", "기여하",
    "확보하", "모색하", "구축하", "제반", "일환",
]

ENDING_CLASSES = [
    ("합니다체", ["습니다", "ㅂ니다", "입니다", "습니까", "ㅂ니까", "십시오"]),
    ("해요체", ["이에요", "예요", "에요", "어요", "아요", "네요", "세요", "죠", "지요"]),
    ("명사형", ["음", "함", "임", "됨", "짐", "옴"]),
    ("한다체", ["는다", "ㄴ다", "았다", "었다", "이다", "한다", "다"]),
    ("반말", ["야", "해", "지", "어", "아"]),
]


def _compile(terms, right_boundary):
    """Word-boundary matchers. Korean has no \\b, so we forbid adjacent 한글.

    Connectives get a boundary on both sides: 즉 must not match 즉시.
    Hedges and drift markers are stems meant to match inflections (활용하는,
    활용하여), so they get a left boundary only.
    """
    tail = rf"(?![{HANGUL}])" if right_boundary else ""
    return [(t, re.compile(rf"(?<![{HANGUL}]){re.escape(t)}{tail}")) for t in terms]


CONNECTIVE_RE = _compile(CONNECTIVES, right_boundary=True)
HEDGE_RE = _compile(HEDGES, right_boundary=False)
DRIFT_RE = _compile(DRIFT_MARKERS, right_boundary=False)


# --------------------------------------------------------------------------- io

DROP_LINE = re.compile(
    r"""^\s{0,3}(
          \#{1,6}\s          # heading
        | (-{3,}|\*{3,}|_{3,})\s*$   # horizontal rule
        | \|                 # table row
        )""",
    re.X,
)
LIST_MARKER = re.compile(r"^\s{0,3}(?:[-*+]|\d+[.)])\s+")
QUOTE_MARKER = re.compile(r"^\s{0,3}>\s?")
CHECKBOX = re.compile(r"^\[[ xX]\]\s*")
LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
EMPHASIS = re.compile(r"(\*\*|__|\*|_|`)")


def clean_line(line):
    """Strip markdown scaffolding from one line. Returns '' if it is not prose."""
    if DROP_LINE.match(line):
        return ""
    line = QUOTE_MARKER.sub("", line)
    line = LIST_MARKER.sub("", line)
    line = CHECKBOX.sub("", line)
    line = LINK.sub(r"\1", line)
    line = EMPHASIS.sub("", line)
    return line.strip()


def split_units(raw):
    """Return (lines, paragraph_count).

    One entry per prose line, markers removed. Paragraphs are runs of prose
    lines separated by blank lines.
    """
    raw = re.sub(r"```.*?```", "", raw, flags=re.S)
    raw = re.sub(r"~~~.*?~~~", "", raw, flags=re.S)

    lines, paras, in_para = [], 0, False
    for line in raw.splitlines():
        if not line.strip():
            in_para = False
            continue
        cleaned = clean_line(line)
        if not cleaned:
            continue
        lines.append(cleaned)
        if not in_para:
            paras += 1
            in_para = True
    return lines, paras


def read_text(path):
    """Return (lines, paragraph_count, front_matter_dict)."""
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()

    meta = {}
    fm = re.match(r"^---\n(.*?)\n---\n", raw, re.S)
    if fm:
        for line in fm.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        raw = raw[fm.end():]

    lines, paras = split_units(raw)
    return lines, paras, meta


def expand(patterns):
    out = []
    for p in patterns:
        p = os.path.expanduser(p)
        hits = glob.glob(p)
        out.extend(sorted(hits) if hits else [p])
    return out


def write_json_atomic(path, payload):
    """Write via a temp file so a crash never truncates an existing baseline."""
    path = os.path.expanduser(path)
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".voice_stats-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


# ---------------------------------------------------------------------- parsing

def sentences(lines):
    """One line is at least one sentence; terminal punctuation splits it further."""
    out = []
    for line in lines:
        for part in re.split(r"(?<=[.!?…])\s+", line):
            part = part.strip()
            if part:
                out.append(part)
    return out


def ending_of(sentence):
    tail = re.sub(r"[\s.!?…\"'”’)\]]+$", "", sentence)
    return tail[-4:] if tail else ""


def classify_ending(tail):
    for name, suffixes in ENDING_CLASSES:
        for suf in suffixes:
            if tail.endswith(suf):
                return name
    return "기타"


def strip_digit_commas(text):
    """1,200억 is one number, not a comma the writer chose to place."""
    return re.sub(r"(?<=\d),(?=\d)", "", text)


def mattr(tokens, window=MATTR_WINDOW):
    """Moving-average type-token ratio: TTR without the length dependence.

    Plain TTR falls as text grows, so a 300-char draft can never match a
    3,000-char corpus. MATTR averages over fixed windows instead.
    Returns None when there is not a full window of tokens.
    """
    if len(tokens) < window:
        return None
    ratios = []
    for i in range(len(tokens) - window + 1):
        ratios.append(len(set(tokens[i:i + window])) / window)
    return round(statistics.fmean(ratios), 3)


def bootstrap_mean_ci(values, alpha=0.10, iters=2000, seed=0):
    """Percentile bootstrap CI for the mean. Deterministic seed: same input,
    same interval, so a report can be reproduced."""
    n = len(values)
    if n < 5:
        return None
    rnd = random.Random(seed)
    means = []
    for _ in range(iters):
        means.append(sum(values[rnd.randrange(n)] for _ in range(n)) / n)
    means.sort()
    lo = means[int(iters * alpha / 2)]
    hi = means[min(int(iters * (1 - alpha / 2)), iters - 1)]
    return [round(lo, 1), round(hi, 1)]


# ---------------------------------------------------------------------- metrics

def analyze(docs, metas=None):
    """docs: list of (lines, paragraph_count)."""
    lines = [ln for doc_lines, _ in docs for ln in doc_lines]
    paras = sum(p for _, p in docs)
    sents = sentences(lines)
    n = len(sents) or 1

    text = "\n".join(lines)
    lengths = [len(s) for s in sents] or [0]
    chars = len(text)
    tokens = [t for t in re.split(r"\s+", text) if t]

    tails = [ending_of(s) for s in sents]
    classes = {}
    for t in tails:
        c = classify_ending(t)
        classes[c] = classes.get(c, 0) + 1

    top_tails = {}
    for t in tails:
        key = t[-3:].strip()
        if len(key) >= 2:
            top_tails[key] = top_tails.get(key, 0) + 1

    def per100(compiled):
        total = sum(len(rx.findall(text)) for _, rx in compiled)
        return round(total * 100.0 / n, 1)

    quoted = sum(len(m) for m in re.findall(r"[\"“][^\"”]{1,300}[\"”]", text))
    commas = strip_digit_commas(text).count(",")
    chars_no_space = len(re.sub(r"\s", "", text))

    m = {
        "files": len(docs),
        "chars": chars,
        "chars_no_space": chars_no_space,
        "sentences": len(sents),
        "paragraphs": paras,
        "tokens": len(tokens),
        "sent_len_mean": round(statistics.fmean(lengths), 1),
        "sent_len_sd": round(statistics.pstdev(lengths), 1) if len(lengths) > 1 else 0.0,
        "sent_len_p10": sorted(lengths)[int(len(lengths) * 0.10)],
        "sent_len_p50": sorted(lengths)[int(len(lengths) * 0.50)],
        "sent_len_p90": sorted(lengths)[int(len(lengths) * 0.90)],
        "sent_len_ci90": bootstrap_mean_ci(lengths),
        "short_ratio": round(sum(1 for x in lengths if x <= 25) / n, 3),
        "long_ratio": round(sum(1 for x in lengths if x >= 80) / n, 3),
        "sents_per_para": round(len(sents) / (paras or 1), 2),
        "comma_per_sent": round(commas / n, 2),
        "connectives_per_100_sent": per100(CONNECTIVE_RE),
        "hedges_per_100_sent": per100(HEDGE_RE),
        "drift_markers_per_100_sent": per100(DRIFT_RE),
        "question_ratio": round(text.count("?") / n, 3),
        "exclaim_ratio": round(text.count("!") / n, 3),
        "quote_ratio": round(quoted / (chars or 1), 3),
        "mattr": mattr(tokens),
        "ttr_raw": round(len(set(tokens)) / (len(tokens) or 1), 3),
        "avg_token_len": round(statistics.fmean([len(t) for t in tokens]) if tokens else 0, 2),
        "reliable": chars_no_space >= MIN_BASELINE_CHARS,
        "endings": {k: round(v / n, 3) for k, v in
                    sorted(classes.items(), key=lambda kv: -kv[1])},
        "top_endings": dict(sorted(top_tails.items(), key=lambda kv: -kv[1])[:10]),
        "top_connectives": {t: len(rx.findall(text)) for t, rx in CONNECTIVE_RE
                            if rx.search(text)},
    }

    if metas:
        by_mode = {}
        for meta, (doc_lines, _) in zip(metas, docs):
            mode = meta.get("mode", "미지정")
            e = by_mode.setdefault(mode, {"files": 0, "chars": 0})
            e["files"] += 1
            e["chars"] += sum(len(ln) for ln in doc_lines)
        m["by_mode"] = by_mode
    return m


# ---------------------------------------------------------------------- compare

# metric -> (tolerance, kind); "rel" = fraction of baseline, "abs" = absolute
# ttr is absent on purpose: it is length-dependent and not comparable. mattr
# replaces it and is only compared when both sides have a full window.
TOLERANCE = {
    "sent_len_mean": (0.20, "rel"),
    "sent_len_sd": (0.35, "rel"),
    "short_ratio": (0.12, "abs"),
    "long_ratio": (0.10, "abs"),
    "sents_per_para": (0.40, "rel"),
    "comma_per_sent": (0.50, "rel"),
    "connectives_per_100_sent": (0.60, "rel"),
    "hedges_per_100_sent": (0.60, "rel"),
    "drift_markers_per_100_sent": (0.50, "rel"),
    "quote_ratio": (0.10, "abs"),
    "mattr": (0.15, "rel"),
}

OK, FLAG, NOBASE = "ok", "확인 필요", "근거 없음"
INDIST = "구별 안 됨"


def verdict_for(key, draft, base, tol, kind):
    """Return (verdict, delta_text). Never flags without a usable baseline."""
    d, b = draft.get(key), base.get(key)
    if d is None or b is None:
        return NOBASE, "한쪽 값 없음"

    delta = d - b
    if kind == "rel":
        if not b:
            # Baseline 0 is an absence of evidence, not a measurement of zero.
            return NOBASE, f"{delta:+.2f} (기준 0)"
        shown = f"{delta:+.2f} ({delta / b * 100:+.0f}%)"
        off = abs(delta) > abs(b) * tol
    else:
        shown = f"{delta:+.3f}"
        off = abs(delta) > tol

    if off and key == "sent_len_mean":
        # Before calling a mean shift real, check the draft is long enough to
        # distinguish it. A ten-sentence draft has a very wide interval.
        ci = draft.get("sent_len_ci90")
        if ci and ci[0] <= b <= ci[1]:
            return INDIST, f"{shown}  CI90 {ci[0]}~{ci[1]}"
    return (FLAG if off else OK), shown


def pad(s, width, right=False):
    """Pad to a display width, counting East Asian wide characters as two columns."""
    s = str(s)
    w = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)
    fill = " " * max(width - w, 0)
    return fill + s if right else s + fill


def compare(draft, base):
    thin_base = not base.get("reliable", True)
    thin_draft = draft.get("sentences", 0) < MIN_DRAFT_SENTENCES

    print("지표 비교 — 기준(코퍼스) vs 초안\n")
    if thin_base:
        print(f"! 기준 코퍼스가 {base.get('chars_no_space', 0)}자입니다 "
              f"({MIN_BASELINE_CHARS}자 미만). 아래는 전부 참고용이며, "
              "표류 판정의 근거로 쓰지 마십시오.\n")
    if thin_draft:
        print(f"! 초안이 {draft.get('sentences', 0)}문장입니다 "
              f"({MIN_DRAFT_SENTENCES}문장 미만). 문장당 비율 지표는 불안정합니다.\n")

    rows = []
    for key, (tol, kind) in TOLERANCE.items():
        if key not in draft and key not in base:
            continue
        v, shown = verdict_for(key, draft, base, tol, kind)
        rows.append((key, base.get(key), draft.get(key), shown, v))

    print(pad("지표", 30) + pad("기준", 10, True) + pad("초안", 10, True)
          + "   " + pad("차이", 26) + "판정")
    print("-" * 90)
    for key, b, d, shown, v in rows:
        b = "—" if b is None else b
        d = "—" if d is None else d
        print(pad(key, 30) + pad(b, 10, True) + pad(d, 10, True)
              + "   " + pad(shown, 26) + (v if not thin_base or v == NOBASE else "참고"))

    de, be = draft.get("endings", {}), base.get("endings", {})
    keys = sorted(set(de) | set(be), key=lambda k: -(be.get(k, 0) + de.get(k, 0)))
    if keys:
        print("\n종결어미 분포")
        print("-" * 90)
        for k in keys:
            b, d = be.get(k, 0.0), de.get(k, 0.0)
            v = FLAG if abs(d - b) > 0.15 else OK
            print(pad(k, 30) + pad(f"{b:.3f}", 10, True) + pad(f"{d:.3f}", 10, True)
                  + "   " + pad(f"{d - b:+.3f}", 26)
                  + (v if not thin_base else "참고"))

    flagged = [r[0] for r in rows if r[4] == FLAG]
    nobase = [r[0] for r in rows if r[4] == NOBASE]
    print("\n" + "-" * 90)
    if nobase:
        print("근거 없음: " + ", ".join(nobase)
              + "\n  → 기준값이 0이거나 표본이 부족합니다. 판정을 유보합니다.")
    if flagged and not thin_base:
        print("확인 필요: " + ", ".join(flagged))
        print("각 항목이 장르 때문인지 모델 표류인지 물어보십시오. 판정이 아니라 질문입니다.")
        print("특히 sent_len_sd 가 낮아졌다면 초안을 코퍼스 평균으로 다린 것입니다 — "
              "그쪽이 더 나쁜 표류입니다.")
    elif not flagged:
        print("허용 범위 안입니다.")
    return 2 if (flagged and not thin_base) else 0


# ------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Measure a writer's stylistic fingerprint.")
    ap.add_argument("files", nargs="+", help="text or markdown files (globs ok)")
    ap.add_argument("--json", action="store_true", help="print metrics as JSON")
    ap.add_argument("--out", metavar="PATH",
                    help="write metrics JSON to PATH atomically (never truncates on failure)")
    ap.add_argument("--compare", metavar="METRICS",
                    help="compare against a metrics.json baseline")
    args = ap.parse_args()

    paths = expand(args.files)
    docs, metas = [], []
    for p in paths:
        try:
            lines, paras, meta = read_text(p)
        except OSError as exc:
            print(f"건너뜀: {p} ({exc})", file=sys.stderr)
            continue
        if lines:
            docs.append((lines, paras))
            metas.append(meta)

    if not docs:
        print("읽을 수 있는 텍스트가 없습니다.", file=sys.stderr)
        return 1

    metrics = analyze(docs, metas)

    if args.compare:
        target = os.path.expanduser(args.compare)
        try:
            with open(target, encoding="utf-8") as fh:
                base = json.load(fh)
        except FileNotFoundError:
            print(f"기준 파일이 없습니다: {target}\n"
                  "  먼저 --out 으로 코퍼스 지표를 만드십시오.", file=sys.stderr)
            return 1
        except json.JSONDecodeError as exc:
            print(f"기준 파일이 손상됐습니다: {target} ({exc})\n"
                  "  --out 으로 다시 생성하십시오. (셸 리다이렉트 > 는 쓰지 마십시오.)",
                  file=sys.stderr)
            return 1
        return compare(metrics, base)

    if args.out:
        write_json_atomic(args.out, metrics)
        print(f"기록: {args.out}  ({metrics['files']}편, "
              f"{metrics['chars_no_space']}자, {metrics['sentences']}문장, "
              f"신뢰도 {'보통 이상' if metrics['reliable'] else '잠정'})")
        if not args.json:
            return 0

    if args.json:
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
        return 0

    for k, v in metrics.items():
        if isinstance(v, dict):
            print(f"{k}:")
            for kk, vv in v.items():
                print(f"    {kk}: {vv}")
        else:
            print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
