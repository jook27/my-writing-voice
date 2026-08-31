# Learning Protocol

How the voice store is updated, and what is not allowed to update it.

The store is at `~/.claude/my-writing-voice/`. Load this file when registering a sample, capturing feedback, or resolving a conflict between the profile and an explicit user rule.

---

## Bootstrapping an Empty Store

1. Create `~/.claude/my-writing-voice/corpus/`.
2. Copy `references/profile-template.md` to `~/.claude/my-writing-voice/profile.md`.
3. Create `feedback.md` with a single heading and no rules.
4. Register the user's first sample.

Never pre-fill the profile with example traits. An empty profile that says so is more useful than a plausible one that is wrong.

---

## Registering a Sample

**Precondition:** the user has identified the text as their own writing.

```text
corpus/2026-08-26-회고서사-01.md
---
mode: 회고·서사
date: 2026-08-26
source: user
chars: 512
note: 유년기 장소 회고
---

<the sample text, verbatim, uncorrected>
```

Store the sample **verbatim**, including its errors. The corpus is evidence, not a publication. Corrections happen at drafting time, not at registration time — otherwise the record of what the writer actually does is lost.

Then:

```bash
python3 ~/.claude/skills/my-writing-voice/scripts/voice_stats.py ~/.claude/my-writing-voice/corpus/*.md --out ~/.claude/my-writing-voice/metrics.json
```

`--out` writes through a temp file and renames. A `>` redirect empties `metrics.json` before the script starts, so a failed run leaves you with no baseline and the next `--compare` fails on an empty file.

The script reports the store's confidence with the same 1,500-character threshold this document uses, and `--compare` refuses to call anything drift while the baseline is below it. Code and protocol have to agree, or the protocol is decoration.

Then update `profile.md`:

- promote a provisional trait to durable when a second sample supports it;
- demote or delete a trait the new sample contradicts;
- update the coverage table for the sample's mode;
- append one dated line to 학습 기록 naming what changed and why.

---

## Capturing Feedback

Feedback is the highest-value signal in the system and the easiest to lose. Capture it the moment it appears, including when it arrives casually mid-conversation.

Triggers to watch for:

- rejection — "이건 내 톤이 아니야", "너무 딱딱해", "이런 말 안 써"
- approval — "이 표현 좋다", "이게 딱 내 느낌이야"
- silent correction — the user pastes back an edited version of your draft
- constraint — "앞으로 ~는 쓰지 마"

The third one matters most and is the easiest to miss. When a user returns your draft with edits, **diff it**. Each change is a rule. Ask once whether to record the pattern you extracted, then write it.

Format in `feedback.md`:

```markdown
## 2026-08-26 — 공식·사업
- 규칙: "~하고자 합니다" 대신 "~하겠습니다"를 쓴다.
- 이유: 사용자가 과도한 격식체를 자기 목소리가 아니라고 지적함.
- 적용: 공식·사업, 설득·제안.
- 출처: 사용자 직접 수정
```

Rules are append-only. When a new rule contradicts an old one, add the new rule and mark the old one `- 폐기: 2026-09-10, <이유>` rather than deleting it. The history of a changed preference is itself information.

---

## Precedence

When sources disagree, resolve in this order:

1. What the user said **in this conversation**.
2. A rule in `feedback.md`.
3. A durable trait in `profile.md`.
4. A statistic in `metrics.json`.
5. A provisional trait in `profile.md`.
6. Genre convention from `references/mode-playbooks.md`.
7. This skill's defaults.

Say which level you are acting on when it would surprise the user: "프로필상 긴 문장을 선호하시지만, 지난번 피드백에 따라 사업 문서에서는 짧게 끊었습니다."

---

## Anti-Drift

A profile that trains on generated text converges on model-average prose within a few cycles, while appearing to work. These constraints prevent that.

**Corpus purity.** Only text the user wrote enters `corpus/`. Not your drafts. Not your drafts after the user approved them — approval is not authorship. A draft the user substantially rewrote may enter, tagged `source: user-edited`, and should be weighted below `source: user` when traits conflict.

**Repetition over recency.** One sample cannot create a durable trait, no matter how recent. Mark it provisional and wait.

**Deviation is not always error.** When `--compare` flags a difference, ask whether the genre explains it before revising. A 사업계획서 with shorter sentences than the memoir corpus is correct. Record the justified deviation in the profile's transfer notes so the same question is not re-litigated next time.

**No fabrication.** If the store is empty or the mode has no coverage, say so. Do not synthesize a profile from what the user's writing "probably" looks like.

**Watch the drift markers.** These usually indicate the model, not the user:

- connective density far above the corpus average;
- every paragraph closing with a summarizing sentence;
- triads everywhere (세 개씩 나열);
- hedges added to claims the user stated plainly, or removed from claims the user hedged;
- vocabulary uplift — 활용하다 for 쓰다, 진행하다 for 하다.

---

## Health Checks

Run on 진단, or whenever the corpus changes.

- **Corpus size.** Under ~1,500 characters total, say the profile is provisional.
- **Mode coverage.** Report which of the five modes have samples and which do not.
- **Sample age.** Flag a corpus whose newest sample is over a year old.
- **Trait conflicts.** Flag traits contradicted by a later sample and not yet resolved.
- **Feedback volume.** Many rules in one mode usually means the profile itself is wrong for that mode — propose re-deriving it rather than accumulating patches.

Report health honestly. "샘플 2편, 총 700자입니다. 회고·서사만 반영되어 있어 사업 문서에서는 신뢰도가 낮습니다" is a more useful answer than a confident draft.
