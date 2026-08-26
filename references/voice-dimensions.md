# Voice Dimensions — the analysis rubric

Load this when building or updating a profile. Each dimension has a question, an observable signal, and a note on how much it transfers across genres.

A trait is **durable** if it appears in more than one sample. A trait seen once is **provisional** and must be labeled as such in `profile.md`.

---

## 1. Sentence length and rhythm

**Question:** How long is a typical sentence, and how much does the length vary?

Measured by `scripts/voice_stats.py` as `sent_len_mean`, `sent_len_sd`, `short_ratio`, `long_ratio`.

Variance matters more than the mean. A writer whose sentences are uniformly 40 characters reads very differently from one who alternates 15 and 90. Record the pattern of alternation, not just the average.

**Transfers across genres:** partially. The mean shifts with genre; the *habit of alternating* usually survives.

## 2. 종결어미 and speech level

**Question:** How do sentences end, and at what level of formality?

The strongest single signal in Korean. Track the mix of 합니다체 / 해요체 / 해라체(한다) / 명사형 종결(~함, ~임) and the smaller endings a writer favors: ~것이다, ~곤 한다, ~는 셈이다, ~기도 하다.

Note whether the writer mixes levels deliberately (a 한다체 essay that drops into 해요체 for one aside) — that mix is often the most recognizable thing about them.

**Transfers:** poorly. Speech level is genre-bound. Carry the *sub-endings*, not the level.

## 3. Information order

**Question:** In what order does a paragraph deliver scene, context, interpretation, and conclusion?

Some writers open with a concrete image and interpret last. Some state the claim first and support it. Some circle: claim, scene, restated claim. This is a structural habit and one of the most transferable dimensions.

**Transfers:** well. Worth carrying into every mode.

## 4. Concrete versus abstract diction

**Question:** Does the writer reach for named things or for categories?

Look at the nouns. 논, 두렁길, 족대 versus 환경, 요소, 측면. Look at the verbs: specific movement verbs versus 하다-compounds (진행하다, 수행하다, 실시하다).

Record the ratio and the writer's *preferred register of specificity*, not a rule to always be concrete.

**Transfers:** well. Concreteness survives into business writing and improves it.

## 5. Metaphor and figuration

**Question:** Where does imagery come from, and how often?

Note the *source domain* — does the writer draw comparisons from machinery, nature, food, sport, work? Note the density. A writer who uses one strong figure per page is different from one who uses three per paragraph.

Never reuse a specific metaphor from the corpus in unrelated work. Carry the habit and the source domain, not the image.

**Transfers:** the habit yes, the specific figures never.

## 6. Enumeration and repetition

**Question:** Does the writer build with lists, parallel clauses, or anaphora?

Signals: comma density (`comma_per_sent`), repeated sentence openings, triads, 그리고-chains, 반복되는 구문.

**Transfers:** well, but density should drop in formal modes.

## 7. Connectives and transitions

**Question:** How are sentences joined, and how explicitly?

Some writers signal every turn (그러나, 따라서, 즉, 다만). Some juxtapose with no connective at all. Measured as `connectives_per_100_sent` with the top items listed.

An over-connected draft is the most common sign of model drift. If the corpus averages 8 connectives per 100 sentences and the draft has 40, the draft is not in the user's voice.

**Transfers:** well; expect a modest increase in 설명·분석 and 공식·사업.

## 8. Narrator distance and certainty

**Question:** How close is the narrator, and how sure?

Watch for hedges (아마, ~인 듯하다, ~일 수 있다), assertions (~이다, 분명히), first-person frequency, and whether the writer addresses the reader directly.

Record the *default certainty level*. Preserving it matters: a hedging writer rendered confident sounds like someone else, and may be made to claim things they did not.

**Transfers:** well, and must be preserved — this is a factual-integrity issue, not only a style one.

## 9. Emotional register

**Question:** Is feeling named, or carried by detail?

Restraint is itself a voice. If the corpus never says 아름다웠다 and instead shows the scene, do not add sentimental conclusions.

**Transfers:** well.

## 10. Humor and irony

**Question:** Is there any, and what kind — understatement, self-deprecation, absurdity, wordplay?

Note that humor is the trait most often *over*-applied in imitation. Under-apply it rather than caricature it.

**Transfers:** cautiously. Drop it in 공식·사업 unless the user asks.

## 11. Paragraph shape

**Question:** How long are paragraphs, how do they open, and how do they land?

Signals: `sents_per_para`, opening moves (time marker? question? claim?), closing moves (summary? image? cut-off?).

**Transfers:** moderately. Formal and community modes both shorten paragraphs.

## 12. Punctuation and typography

**Question:** What are the writer's mechanical habits?

Em dashes, ellipses, parentheticals, quotation-mark style, numerals versus 한글 숫자, spacing around units.

Separate deliberate habits from errors. A writer who consistently uses parentheticals for asides has a habit. A writer with inconsistent quotation marks has a typo.

**Transfers:** well, except where a publication imposes house style.

---

## Do Not Treat as Voice

These are editing concerns, never identity markers. Correct them silently:

- 맞춤법 and 띄어쓰기 errors;
- inconsistent quotation marks (’ ‘ vs “ ”) and mixed dash styles;
- wrong or missing 조사, broken 호응;
- unclear antecedents and dangling modifiers;
- factual mistakes and inconsistent dates, names, or numbers;
- accidental repetition of a word within a sentence.

If the user insists a "mistake" is intentional, record it in `feedback.md` as an explicit rule. Explicit beats inferred.

---

## Recording a Trait

Write traits as instructions a drafter can follow, with the evidence attached:

```markdown
### 짧은 문장으로 끊고 긴 문장으로 이어간다  [durable · 4/5 samples]
25자 이하 문장과 80자 이상 문장이 번갈아 나타난다. 긴 문장은 이동이나
열거를 담고, 짧은 문장은 그 뒤에서 장면을 고정한다.
- 근거: 2026-08-26-회고서사-01, 2026-09-02-설명분석-01
- 전이: 공식·사업에서는 긴 문장을 60자 수준으로 낮춘다.
```

Bad trait entries are unfalsifiable ("따뜻하고 진솔한 문체"). Good ones name a signal, cite samples, and say what happens in other modes.
