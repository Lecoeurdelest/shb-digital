# Matrix by task type

Read this file when the next step belongs to a specific task type and you need to know its typical score and category-specific pitfalls. The main table and override rules are in `SKILL.md`; this file adds detail.

## Contents

- [Code](#code)
- [Research and collection](#research-and-collection)
- [Data and analysis](#data-and-analysis)
- [Writing and editing](#writing-and-editing)
- [Ops and infrastructure](#ops-and-infrastructure)
- [Multimodal](#multimodal)
- [Commonly mis-scored steps](#commonly-mis-scored-steps)

## Code

| Step | Typical score | Tier | Notes |
|---|---|---|---|
| Generate boilerplate, CRUD, or simple tests | A0 B1 C1 D0 = 2 | 1 | A clear specification does not need a large model |
| Write one feature in an existing file | A1 B1 C1 D1 = 4 | 2 | |
| Debug an error with a stack trace | A1 B1 C1 D1 = 4 | 2 | Evidence makes narrowing the issue straightforward |
| Debug an error that cannot be reproduced | A2 B2 C1 D2 = 7 | 4 | This is genuinely a Tier 4 task |
| Refactor across multiple modules | A1 B2 C1 D2 = 6 | 3 | D=2 because a global invariant must be maintained |
| Review architecture and choose a design direction | A2 B2 C1 D1 = 6 | 3 | Raise to Tier 4 if the decision is hard to reverse |
| Migrate a schema in production | A1 B2 C2 D1 = 6 → override | 3+ | Rule 1: increase effort by one level and confirm first |

Agentic coding—editing multiple files, running commands, and iterating until tests pass—is Anthropic's strongest area; DeepSeek V4 Pro is the closest open-weight alternative. If a step requires both coding and visual-interface judgment, consider gpt-5.6.

Pitfall: generating plausible-looking code is cheap, but making the wrong architectural **decision** makes every later step more expensive. Score the decision step high and the typing step low.

## Research and collection

| Step | Typical score | Tier |
|---|---|---|
| Look up one fact or figure | A0 B0 C0 D0 = 0 | 1 |
| Extract structured data from N independent sources | A0 B1 C1 D1 = 3 → bulk rule | 1 |
| Synthesize and reconcile conflicts among sources | A1 B2 C1 D2 = 6 | 3 |
| Evaluate a study's methodology | A2 B2 C1 D1 = 6 | 3 |
| Map an unfamiliar field | A2 B2 C1 D2 = 7 | 4 |

Separate two phases clearly: **collection** (cheap, parallel, Tier 1) and **synthesis** (expensive, performed once, Tier 3–4). Running both phases on the same heavy model is one of the most common ways to waste money in research.

If C=2 because the user will cite the figure to others, do not lower the synthesis tier just because the collection phase was processed in bulk.

## Data and analysis

| Step | Typical score | Tier |
|---|---|---|
| Clean or reformat data, or join on a clear key | A0 B1 C1 D1 = 3 | 2 |
| Produce descriptive statistics or charts | A0 B1 C1 D1 = 3 | 2 |
| Select a model and test assumptions | A2 B2 C1 D1 = 6 | 3 |
| Interpret results for a business decision | A1 B2 C2 D1 = 6 → override | 3+ |
| Prove a theorem or derive a formula | A1 B2 C1 D0 = 4 | 2–3 |

For mathematical derivations, the tier depends almost entirely on B. A three-line derivation does not need Opus; a proof that must preserve an invariant across ten steps does.

Pitfall: writing analysis code is cheap, but **reading the results** and then claiming causation is where errors are most costly. Always score interpretation at C≥1.

## Writing and editing

| Step | Typical score | Tier |
|---|---|---|
| Correct spelling or change formatting | A0 B0 C0 D0 = 0 | 1 |
| Condense text or change its tone to a clear specification | A0 B1 C1 D1 = 3 | 2 |
| Write a first draft from an existing outline | A1 B1 C1 D1 = 4 | 2 |
| Write for a sensitive audience or external distribution | A1 B1 C2 D1 = 5 → override | 3 |
| Construct an argument from scratch | A2 B2 C1 D1 = 6 | 3 |

C=2 when the text will be sent outside the organization or published under the user's name. In that case, do not lower the tier even if the text is short.

## Ops and infrastructure

| Step | Typical score | Tier |
|---|---|---|
| Run a known command, commit, or rename something | A0 B0 C1 D0 = 1 | 1 (Rule 5) |
| Write a CI configuration from a template | A0 B1 C1 D0 = 2 | 1 |
| Diagnose an ongoing production incident | A2 B2 C2 D2 = 8 | 4 |
| Plan a rollback | A1 B2 C2 D1 = 6 → override | 3+ |

Ops is where Rule 1 (irreversible actions) and Rule 5 (mechanical steps) collide most often. Distinguish between them: *deciding which command to run* may be Tier 4; *typing that command* is always Tier 1.

## Multimodal

For images, video, audio, scanned PDFs, or extremely long context that must be processed cheaply, use the Google column almost regardless of tier. Set the Effort column to `n/a (auto)`.

Exception: when multimodal content is only a secondary input and the hard part is reasoning over extracted text, split the work into two steps—extract with Gemini Flash-Lite, then reason with the column appropriate to the tier.

## Commonly mis-scored steps

**Scored too high:**

- Executing a decision that was carefully considered in the previous step—the difficult work is already done
- Repeating a pattern that has already worked several times in the same session
- A purely mechanical "double-check" step, such as running tests, comparing a diff, or counting lines

**Scored too low:**

- The first step of an ambiguous task—choosing the wrong direction here makes every later step pointless, so A is almost always 2
- Producing a final figure the user will use elsewhere—C=2
- Combining conflicting results from multiple sources—D=2 and usually B=2
- Deciding whether something should be done—this may look like a small question, but it determines the entire task

When choosing between two adjacent tiers, pick the higher tier if C=2. Otherwise, choose the lower tier and state in the "Fallback" line exactly what condition would require escalation. A lower recommendation with a clear escalation path is cheaper than a high recommendation made just in case.
