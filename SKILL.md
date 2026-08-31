---
name: my-writing-voice
description: Measure, store, and reproduce the user's own writing voice, verifying each draft against measured statistics of their real corpus rather than against a remembered impression. Distinct from style presets: this skill keeps a local corpus, computes a fingerprint, and checks drafts against it, improving with every session. Use when the user asks to write in their voice, keep their tone, make text sound like them, register or update a writing sample, give feedback on a draft's style, or check their voice profile. Korean-first, works for any language. Triggers include 내 문체로, 내 스타일로 써줘, 톤 유지해줘, 문체 등록, 문체 학습, 이 문장 나답게.
---

# My Writing Voice

Apply the user's recognizable writing voice while preserving the requested meaning, factual accuracy, audience, and genre — and get measurably better at it each time it is used.

This skill is a system with memory, not a one-shot prompt. Everything it learns lives in the user's local voice store, outside this skill package.

## The Voice Store

```text
~/.claude/my-writing-voice/          (Windows: %USERPROFILE%\.claude\my-writing-voice\)
├── profile.md        # the living voice profile + 학습 기록 (changelog)
├── metrics.json      # measured statistics of the corpus
├── corpus/           # the user's own writing, one file per sample
└── feedback.md       # accepted and rejected style decisions, with reasons
```

Check whether this store exists before anything else. `ls ~/.claude/my-writing-voice/` decides which path below applies. Bootstrap it from `references/profile-template.md`.

The store is user data. Never commit it to this skill's repository, and never ship one user's profile to another user.

## Two Entry Paths

### Cold start — the store is empty or missing

Ask once, concisely, for everything needed:

> 문체 기준으로 삼을 본인 글을 붙여 주세요. 300~1,000자 정도면 충분하고, 여러 편이면 더 정확해집니다. 목표 글의 종류도 알려 주시면 좋습니다: 회고·서사, 설명·분석, 설득·제안, 공식·사업, 커뮤니티·홍보. 종류를 생략하면 글의 목적과 독자를 보고 판단하겠습니다. 새로 쓸 주제나 다듬을 원문도 함께 보내 주세요.

Then register the sample before drafting. 1,000 characters is a recommendation, not a rejection threshold — accept anything that reveals a usable voice, and say so plainly when a sample is too thin to support confident inference.

If the user supplies a sample but no task, acknowledge receipt, name the likely mode, and ask what to write. Do not generate an unsolicited piece to demonstrate the style.

### Warm start — the store has a profile

Do not demand a fresh sample. Read `profile.md`, `feedback.md`, and `metrics.json`, then work. Request a new sample only when one of these holds:

- the target mode has no corpus coverage (`profile.md` records coverage per mode);
- the corpus is roughly a year old and the user's writing has visibly changed;
- the user explicitly wants to recalibrate.

When coverage is missing, say so instead of silently guessing:

> 이 종류(공식·사업)로 쓰신 샘플이 아직 없습니다. 회고·서사 프로필에서 옮겨 쓸 수 있는 특성만 적용하고, 나머지는 장르 관례를 따르겠습니다.

## Five Operations

Route on what the user is asking for. Most requests are 쓰기 or 다듬기.

| Operation | User says | What to do |
| --- | --- | --- |
| 등록 | 이 글 문체 샘플로 등록해줘 | Save to `corpus/`, recompute metrics, update `profile.md` |
| 쓰기 | 내 문체로 ~ 써줘 | Draft in the target mode, then run the verify loop |
| 다듬기 | 이 글 나답게 다듬어줘 | Minimal edits toward the profile; keep good original sentences |
| 학습 | 이건 내 톤이 아니야 / 이 표현 좋다 | Append a rule to `feedback.md` with the reason |
| 진단 | 내 문체 프로필 보여줘 | Report profile, per-mode coverage, corpus size, recent learning |

### 등록 (register a sample)

1. Confirm the text is the user's own writing. Quotations, source material, and another author's prose are never voice sources.
2. Save as `corpus/YYYY-MM-DD-<mode>-<n>.md` with front matter: `mode`, `date`, `source: user`, `chars`.
3. Recompute metrics. Use the absolute path — the working directory is the user's, not the skill's — and `--out`, never a `>` redirect, which empties the baseline before the script runs:
   ```bash
   python3 ~/.claude/skills/my-writing-voice/scripts/voice_stats.py ~/.claude/my-writing-voice/corpus/*.md --out ~/.claude/my-writing-voice/metrics.json
   ```
   If the skill is installed somewhere else, resolve the path from this file's own location before running it. If `python3` is missing, say so rather than falling through to a silent qualitative check.
4. Update `profile.md` using traits that repeat across samples, not one-off expressions. Append a dated line to 학습 기록.

### 쓰기 and 다듬기 (the verify loop)

This is the difference between imitation and transfer. Do not skip step 3.

1. Draft for the selected mode and reader, applying only the strongest supported traits.
2. Measure the draft:
   ```bash
   python3 ~/.claude/skills/my-writing-voice/scripts/voice_stats.py draft.md --compare ~/.claude/my-writing-voice/metrics.json
   ```
3. Read the flags as questions, not instructions. For each one, ask whether the genre justifies it (a 사업계획서 should have shorter sentences than a memoir) or whether it is model drift toward generic prose. Change a sentence only when you can name which of the two it is. Record the reason either way.
4. Return the finished text.

**What the flags do not license.** The metrics are a small, shallow sample of what makes prose sound like a person, and moving a draft toward the corpus mean on every flagged row is itself a kind of drift — a flatter one. Three rules keep the loop honest:

- `근거 없음` means the baseline was 0 or the corpus was too thin. It is not a deviation. Do not act on it.
- `구별 안 됨` means the draft is too short to tell a real shift from noise. Do not act on it either.
- A **fall** in `sent_len_sd` is worse than a rise. Variance is the writer; the mean is the genre. Never edit toward lower variance to clear a flag.

The exit code says the same thing: `0` clean, `2` something to ask about, `1` the tool itself failed.

If `python3` or the script is unavailable, do step 2 by reading — compare sentence length, 종결어미, and connective habits against `profile.md` by eye — and say plainly that the check was qualitative. Do not describe an unverified draft as verified.

### 학습 (capture feedback)

Every correction the user gives is training data that would otherwise be lost. When the user rejects, praises, or rewrites a phrase, append to `feedback.md`:

```markdown
## 2026-08-26 — 공식·사업
- 규칙: "~하고자 합니다" 대신 "~하겠습니다"를 쓴다.
- 이유: 사용자가 과도한 격식체를 자기 목소리가 아니라고 지적함.
- 적용: 공식·사업, 설득·제안.
```

Read `feedback.md` before every draft. Explicit user rules outrank inferred profile traits, and both outrank this file's defaults.

## Writing Modes

| Mode | Typical uses | Adaptation principle |
| --- | --- | --- |
| 회고·서사 | 에세이, 자전적 장면, 기억 기록 | Preserve scene, movement, sensory detail, emotional restraint. |
| 설명·분석 | 해설, 기술 설명, 시장 분석 | Keep cadence but foreground definitions, causality, clarity. |
| 설득·제안 | 주장문, 기획 제안, 의견문 | State the thesis early; keep only voice features that strengthen the case. |
| 공식·사업 | 사업계획서, 보고서, 심사 문서 | Prioritize evidence and scanability; reduce metaphor and conversational drift. |
| 커뮤니티·홍보 | Reddit, 소개문, 출시 글, SNS | Preserve naturalness and specificity; shorten setup, avoid hype. |

Honor an explicitly selected mode; otherwise infer from purpose, audience, and output format. Ask only when genuine ambiguity would change the result.

When the corpus mode and the target mode differ, transfer durable traits rather than forcing the sample's surface form onto the target. Carry concrete observation and restrained judgment into a business document without copying long narrative sentences.

Load `references/mode-playbooks.md` when a mode is unfamiliar or the transfer is difficult.

Load `references/essay-craft.md` when the user asks for help with the structure or material of a personal essay — diagnosing a draft, ordering episodes, deciding what a chapter is for. That file covers craft, not voice, and labels how far each claim is from the research behind it. Keep the two separate: voice work never overrides what the user chose to say.

## Building the Profile

Load `references/voice-dimensions.md` for the full rubric. In short, examine:

- sentence length distribution and changes in pace;
- 종결어미 and speech level (합니다 / 해요 / 한다 / 명사형);
- preferred order of scene, context, interpretation, conclusion;
- concrete versus abstract diction;
- enumeration, repetition, dialogue, metaphor;
- narrator distance, certainty, warmth, humor, restraint;
- paragraph openings, transitions, endings, punctuation habits.

Distinguish voice from accidental defects. Never reproduce typos, spacing errors, inconsistent quotation marks, awkward particles, factual mistakes, or unclear antecedents just because they appear in a sample. Grammar and orthography are editing concerns, not identity markers.

## Anti-Drift Rules

A learning system that learns from its own output degrades. These rules keep the profile anchored to the human.

1. Only user-authored text enters `corpus/`. Never register a draft this skill produced, even after the user approves it. A user-rewritten draft may be registered only if the user confirms they changed it substantially, tagged `source: user-edited`.
2. Repetition over recency. A trait needs support in more than one sample before it enters `profile.md` as durable. Single-sample observations stay marked provisional.
3. Explicit beats inferred. A rule in `feedback.md` wins over a statistic.
4. Deviation is not always error. Genre-driven differences are correct; record the reason rather than "fixing" them.
5. Never fabricate corpus. If the store is empty, say so; do not invent a profile.

Load `references/learning-protocol.md` for the full update procedure and the conflict rules.

## Applying the Voice

1. Preserve the user's requested facts, position, intent, and level of certainty.
2. Separate style from subject. Do not import the samples' places, images, characters, memories, or claims into unrelated work.
3. Apply only the strongest supported traits. Avoid caricature, catchphrases, and repetitive imitation.
4. Correct grammar and readability without polishing away individuality.
5. When editing, make the smallest changes that improve clarity, rhythm, or genre fit.

## Response Behavior

Return the finished writing first. Add a short note about major voice or genre decisions only when it helps the user evaluate the result, or when asked.

When evidence is missing, keep the uncertainty rather than turning a personal tone into false confidence. Keep this skill focused on voice; leave legal, medical, financial, and current-fact verification to the appropriate process.
