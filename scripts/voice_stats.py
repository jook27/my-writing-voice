#!/usr/bin/env python3
"""Measure the stylistic fingerprint of Korean (or any) prose.

Turns a voice profile from an opinion into something checkable: a draft can be
compared against the corpus it is supposed to sound like.

    python voice_stats.py corpus/*.md --json > metrics.json
    python voice_stats.py draft.md --compare metrics.json

Standard library only. Metrics are shallow by design -- they catch drift toward
generic model prose, not literary quality.
"""

import argparse
import glob
import json
import os
import re
import statistics
import sys
import unicodedata

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HANGUL = r"가-힣"

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


# --------------------------------------------------------------------------- io

def read_text(path):
    """Return (body, front_matter_dict) with markdown scaffolding removed."""
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

    raw = re.sub(r"```.*?```", "", raw, flags=re.S)      # code fences
    raw = re.sub(r"^\s{0,3}#{1,6}\s+", "", raw, flags=re.M)  # headings
    raw = re.sub(r"^\s{0,3}[-*+]\s+", "", raw, flags=re.M)   # bullets
    raw = re.sub(r"^\s{0,3}>\s?", "", raw, flags=re.M)       # quotes
    return raw.strip(), meta


def expand(patterns):
    out = []
    for p in patterns:
        p = os.path.expanduser(p)
        hits = glob.glob(p)
        out.extend(sorted(hits) if hits else [p])
    return out


# ---------------------------------------------------------------------- parsing

def paragraphs(text):
    return [re.sub(r"\s+", " ", p).strip()
            for p in re.split(r"\n\s*\n", text) if p.strip()]


def sentences(text):
    """Split into sentences; a paragraph with no terminal punctuation counts as one."""
    out = []
    for para in paragraphs(text):
        parts = re.split(r"(?<=[.!?…])\s+", para)
        out.extend(s.strip() for s in parts if s.strip())
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


# ---------------------------------------------------------------------- metrics

def analyze(texts, metas=None):
    text = "\n\n".join(texts)
    sents = sentences(text)
    paras = paragraphs(text)
    n = len(sents) or 1

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

    def per100(words):
        return round(sum(text.count(w) for w in words) * 100.0 / n, 1)

    quoted = sum(len(m) for m in re.findall(r"[\"“][^\"”]{1,300}[\"”]", text))

    m = {
        "files": len(texts),
        "chars": chars,
        "chars_no_space": len(re.sub(r"\s", "", text)),
        "sentences": len(sents),
        "paragraphs": len(paras),
        "sent_len_mean": round(statistics.fmean(lengths), 1),
        "sent_len_sd": round(statistics.pstdev(lengths), 1) if len(lengths) > 1 else 0.0,
        "sent_len_p10": sorted(lengths)[int(len(lengths) * 0.10)],
        "sent_len_p50": sorted(lengths)[int(len(lengths) * 0.50)],
        "sent_len_p90": sorted(lengths)[int(len(lengths) * 0.90)],
        "short_ratio": round(sum(1 for x in lengths if x <= 25) / n, 3),
        "long_ratio": round(sum(1 for x in lengths if x >= 80) / n, 3),
        "sents_per_para": round(len(sents) / (len(paras) or 1), 2),
        "comma_per_sent": round(text.count(",") / n, 2),
        "connectives_per_100_sent": per100(CONNECTIVES),
        "hedges_per_100_sent": per100(HEDGES),
        "drift_markers_per_100_sent": per100(DRIFT_MARKERS),
        "question_ratio": round(text.count("?") / n, 3),
        "exclaim_ratio": round(text.count("!") / n, 3),
        "quote_ratio": round(quoted / (chars or 1), 3),
        "ttr": round(len(set(tokens)) / (len(tokens) or 1), 3),
        "avg_token_len": round(statistics.fmean([len(t) for t in tokens]) if tokens else 0, 2),
        "endings": {k: round(v / n, 3) for k, v in
                    sorted(classes.items(), key=lambda kv: -kv[1])},
        "top_endings": dict(sorted(top_tails.items(), key=lambda kv: -kv[1])[:10]),
        "top_connectives": {w: text.count(w) for w in CONNECTIVES if text.count(w)},
    }

    if metas:
        by_mode = {}
        for meta, t in zip(metas, texts):
            mode = meta.get("mode", "미지정")
            e = by_mode.setdefault(mode, {"files": 0, "chars": 0})
            e["files"] += 1
            e["chars"] += len(t)
        m["by_mode"] = by_mode
    return m


# ---------------------------------------------------------------------- compare

# metric -> (tolerance, kind); "rel" = fraction of baseline, "abs" = absolute
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
    "ttr": (0.15, "rel"),
}


def pad(s, width, right=False):
    """Pad to a display width, counting East Asian wide characters as two columns."""
    s = str(s)
    w = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)
    fill = " " * max(width - w, 0)
    return fill + s if right else s + fill


def compare(draft, base):
    rows = []
    for key, (tol, kind) in TOLERANCE.items():
        if key not in draft or key not in base:
            continue
        d, b = draft[key], base[key]
        delta = d - b
        if kind == "rel":
            off = abs(delta) > max(abs(b) * tol, 0.01)
            pct = f" ({delta / b * 100:+.0f}%)" if b else "  (기준 0)"
            shown = f"{delta:+.2f}{pct}"
        else:
            off = abs(delta) > tol
            shown = f"{delta:+.3f}"
        rows.append((key, b, d, shown, off))

    print("지표 비교 — 기준(코퍼스) vs 초안\n")
    print(pad("지표", 30) + pad("기준", 10, True) + pad("초안", 10, True)
          + "   " + pad("차이", 20) + "판정")
    print("-" * 84)
    for key, b, d, shown, off in rows:
        print(pad(key, 30) + pad(b, 10, True) + pad(d, 10, True)
              + "   " + pad(shown, 20) + ("점검 필요" if off else "ok"))

    de, be = draft.get("endings", {}), base.get("endings", {})
    keys = sorted(set(de) | set(be), key=lambda k: -(be.get(k, 0) + de.get(k, 0)))
    if keys:
        print("\n종결어미 분포")
        print("-" * 84)
        for k in keys:
            b, d = be.get(k, 0.0), de.get(k, 0.0)
            flag = "점검 필요" if abs(d - b) > 0.15 else "ok"
            print(pad(k, 30) + pad(f"{b:.3f}", 10, True) + pad(f"{d:.3f}", 10, True)
                  + "   " + pad(f"{d - b:+.3f}", 20) + flag)

    flagged = [r[0] for r in rows if r[4]]
    print("\n" + "-" * 82)
    if flagged:
        print("점검 필요: " + ", ".join(flagged))
        print("각 항목이 장르 때문에 달라진 것인지, 모델 표류인지 판단한 뒤 표류만 수정하십시오.")
    else:
        print("허용 범위 안입니다.")
    return 0


# ------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Measure a writer's stylistic fingerprint.")
    ap.add_argument("files", nargs="+", help="text or markdown files (globs ok)")
    ap.add_argument("--json", action="store_true", help="print metrics as JSON")
    ap.add_argument("--compare", metavar="METRICS", help="compare against a metrics.json baseline")
    args = ap.parse_args()

    paths = expand(args.files)
    texts, metas = [], []
    for p in paths:
        try:
            body, meta = read_text(p)
        except OSError as exc:
            print(f"건너뜀: {p} ({exc})", file=sys.stderr)
            continue
        if body:
            texts.append(body)
            metas.append(meta)

    if not texts:
        print("읽을 수 있는 텍스트가 없습니다.", file=sys.stderr)
        return 1

    metrics = analyze(texts, metas)

    if args.compare:
        with open(os.path.expanduser(args.compare), encoding="utf-8") as fh:
            return compare(metrics, json.load(fh))

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
