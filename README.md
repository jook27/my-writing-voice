# My Writing Voice

> A Claude Code skill that learns your writing voice, keeps what it learns, and checks its own drafts against you — instead of asking for a sample every time and guessing.

Most "write like me" prompts fail the same three ways. They forget everything between sessions. They copy your typos along with your voice. And they have no way to tell whether the draft actually sounds like you, so they drift toward generic model prose while sounding confident about it.

`my-writing-voice` fixes those three specifically.

## How it works

```text
샘플 등록  →  코퍼스 축적  →  프로필 갱신  →  초안 작성  →  지표 대조  →  피드백 규칙화
              (사용자 글만)     (반복된 특성만)                (표류 탐지)     (다음 초안에 우선 적용)
```

1. **Register a sample.** Your own writing goes into a local corpus, stored verbatim.
2. **Measure it.** `voice_stats.py` computes sentence-length distribution, 종결어미 mix, connective density, hedge rate, and lexical variety.
3. **Build a profile.** Traits that repeat across samples become durable. Traits seen once stay provisional and say so.
4. **Draft.** Claude writes in the target mode, transferring durable traits rather than copying surface form.
5. **Verify.** The draft is measured against the corpus. Deviations are triaged: justified by genre, or model drift.
6. **Learn.** Every correction you give becomes a rule that outranks the inferred profile.

## What's different from v0.1

| | v0.1 | v0.2 (현재) |
| --- | --- | --- |
| Memory | none — fresh sample every session | local voice store, warm start |
| Profile | prose description | prose + measured metrics |
| Verification | none | draft-vs-corpus comparison |
| Feedback | lost when the session ended | append-only rule file, highest precedence |
| Shipped baseline | the author's personal memoir | template only — no one's voice in the package |
| Drift protection | none | corpus purity, repetition-over-recency, drift markers |

The fifth row was a real defect: installing v0.1 calibrated your writing against a stranger's childhood memoir. The package now ships a method, not a person.

## Install

```bash
git clone https://github.com/jook27/my-writing-voice.git ~/.claude/skills/my-writing-voice
```

On Windows PowerShell:

```powershell
git clone https://github.com/jook27/my-writing-voice.git "$env:USERPROFILE\.claude\skills\my-writing-voice"
```

Restart Claude Code if the skill is not discovered immediately. Python 3.8+ is optional — without it the verification step falls back to a qualitative read, and Claude will say so.

## Use

Just ask, in Korean or English:

```text
내 문체로 예비창업패키지 사업계획서 문제인식 파트 써줘. 독자는 심사위원.
```

```text
이 글 문체 샘플로 등록해줘. 모드는 설명·분석.
[글 붙여넣기]
```

```text
내 문체 프로필 보여줘
```

On the very first use, Claude will ask for a sample — 300~1,000자 정도면 충분하고, 여러 편이면 더 정확해집니다. After that it works from the stored profile and only asks again when you write in a mode it has never seen you write in.

### Feedback is the fastest way to improve it

Correcting a draft is worth more than another sample:

```text
이건 내 톤이 아니야. "~하고자 합니다" 안 써.
```

That becomes a rule in `feedback.md` and takes precedence over every inferred trait from then on.

## The voice store

Your data lives outside this repository, and stays on your machine:

```text
~/.claude/my-writing-voice/
├── profile.md        # living profile + 학습 기록
├── metrics.json      # measured statistics
├── corpus/           # your own writing, one file per sample
└── feedback.md       # your explicit rules, append-only
```

Nothing here is committed to this repo, uploaded, or shared. Back it up like any other personal writing.

## Writing modes

| Mode | Best for | Adaptation focus |
| --- | --- | --- |
| `회고·서사` | 에세이, 자전적 장면, 기억 기록 | 장면, 이동, 감각, 절제된 감정 |
| `설명·분석` | 해설, 기술 문서, 시장 분석 | 정의, 인과, 명료성, 근거 |
| `설득·제안` | 주장문, 기획 제안, 의견문 | 이른 논지, 반론 선점, 구체적 요청 |
| `공식·사업` | 사업계획서, 보고서, 심사 문서 | 근거, 훑어 읽힘, 절제 |
| `커뮤니티·홍보` | Reddit, 출시 글, 소개문 | 자연스러움, 구체성, 과장 없음 |

Sentence length, imagery, and formality all bend with the mode. How certain you sound does not — see `references/mode-playbooks.md`.

## The metrics script

```bash
# 코퍼스 지표 계산
python scripts/voice_stats.py ~/.claude/my-writing-voice/corpus/*.md --json > ~/.claude/my-writing-voice/metrics.json

# 초안이 내 문체에서 얼마나 벗어났는지
python scripts/voice_stats.py draft.md --compare ~/.claude/my-writing-voice/metrics.json
```

Standard library only, no dependencies. The metrics are shallow on purpose: they catch drift toward generic prose, not literary quality. A sample of what it caught on a deliberately drifted draft:

```text
connectives_per_100_sent      0.0      90.0   +90.00  (기준 0)    점검 필요
한다체                        0.833     0.200   -0.633              점검 필요
합니다체                      0.000     0.800   +0.800              점검 필요
```

Flagged is not the same as wrong. A 사업계획서 *should* have shorter sentences than a memoir. The skill's job is to tell genre adaptation apart from drift, and record which is which.

## Structure

```text
my-writing-voice/
├── SKILL.md                        # trigger, routing, operations, verify loop
├── README.md
├── ROADMAP.md                      # what's built, what's next, what's out of scope
├── references/
│   ├── voice-dimensions.md         # the 12-dimension analysis rubric
│   ├── mode-playbooks.md           # per-mode transfer rules
│   ├── learning-protocol.md        # store updates, precedence, anti-drift
│   └── profile-template.md         # empty skeleton for a new store
└── scripts/
    └── voice_stats.py              # metrics + draft comparison
```

## Boundaries

- Transfers **your own** voice. Not an author you admire, not a colleague.
- Fixes grammar and orthography. Errors are not identity markers — unless you say they are, in which case they become a rule.
- Does not verify legal, medical, financial, or time-sensitive claims.
- Preserves your level of certainty. A hedging writer is never rendered confident.
- One short sample cannot reveal a voice. The profile tells you when it is guessing.

## License

MIT. See [LICENSE](LICENSE).
