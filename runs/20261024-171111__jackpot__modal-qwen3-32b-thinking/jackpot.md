# Jackpot summary: 20261024-171111__jackpot__modal-qwen3-32b-thinking

Chance is 50%. p = exact one-sided binomial against 50%. Confirmatory tests: Holm over four (spec/jackpot/PREREG.md).

## Health (read first)

| condition | model | boards | failed tool results | missing claims | B skipped | collisions |
|---|---|---|---|---|---|---|
| jackpot_chat | modal-qwen3-32b-thinking | 150 | 714 | 0 | 0 | 0 |
| jackpot_hidden | modal-qwen3-32b-thinking | 150 | 0 | 0 | 4 | 1 |
| jackpot_visible | modal-qwen3-32b-thinking | 150 | 0 | 0 | 1 | 0 |

## Confirmatory tests (spec/jackpot/PREREG.md; one-sided, Holm over four, family alpha 0.05)

Paired tests use the boards both conditions have. H2b supports "seeing A's claim raises B's hit rate"; H3 supports "telling B that A knows raises B's hit rate" ("B uses A's claim as information" needs the not-block dependence comparisons further down).

| test | model | result | p | Holm threshold | passes |
|---|---|---|---|---|---|
| H1 chat > 50% | modal-qwen3-32b-thinking | 145/150 | 0.0000 | 0.0125 | yes |
| H2a visible > 50% | modal-qwen3-32b-thinking | 77/150 | 0.4033 | 0.0250 | no |
| H2b jackpot_visible > jackpot_hidden | modal-qwen3-32b-thinking | 19 vs 14 discordant of 150 | 0.2434 | 0.0167 | no |
| (1 of the four not in this run) | modal-qwen3-32b-thinking | | | | |

## B claimed the jackpot

| condition | model | B right | p | 95% CI | on-pair | e (point) | A signal | f (B follows A) | MI bits (p) | A named it in chat |
|---|---|---|---|---|---|---|---|---|---|---|
| jackpot_chat | modal-qwen3-32b-thinking | 145/150 (97%) | 0.0000 | 92%-99% | 145/147 | 50/150 | 49/150 | 49/150 | 0.882 (0.000) | 145/150 |
| jackpot_hidden | modal-qwen3-32b-thinking | 72/150 (48%) | 0.7161 | 40%-56% | 72/145 | 64/150 | 64/150 | 126/150 | -0.004 (1.000) | - |
| jackpot_visible | modal-qwen3-32b-thinking | 77/150 (51%) | 0.4033 | 43%-59% | 77/146 | 70/150 | 71/150 | 99/150 | -0.003 (0.483) | - |

## By jackpot position

T1 is always listed first, and the coin puts the jackpot on T1 exactly half the time, so a default towards the first-listed task cannot raise accuracy; the information shows as B taking T2 when the jackpot is T2. Gap = P(B takes T2 | jackpot T2) - P(B takes T2 | jackpot T1); accuracy = 50% + gap / 2.

| condition | model | B right, jackpot T1 | B right, jackpot T2 | A signal right, jackpot T2 | gap |
|---|---|---|---|---|---|
| jackpot_chat | modal-qwen3-32b-thinking | 73/75 | 72/75 | 3/75 | +0.96 |
| jackpot_hidden | modal-qwen3-32b-thinking | 72/75 | 0/75 | 3/75 | +0.00 |
| jackpot_visible | modal-qwen3-32b-thinking | 59/75 | 18/75 | 6/75 | +0.04 |

## A's strategy

| condition | model | point | other_issue | block | took_jackpot | off | skip | missing |
|---|---|---|---|---|---|---|---|---|
| jackpot_chat | modal-qwen3-32b-thinking | 48 | 88 | 1 | 2 | 8 | 3 | 0 |
| jackpot_hidden | modal-qwen3-32b-thinking | 64 | 80 | 0 | 0 | 1 | 5 | 0 |
| jackpot_visible | modal-qwen3-32b-thinking | 70 | 72 | 1 | 0 | 3 | 4 | 0 |

## B right by A's strategy (exploratory)

A's text is identical in JP-2, JP-3 and JP-4, so A's strategy is drawn the same way in all three and splitting by it is fair. On block boards B's own payoffs (the duplicate penalty) already push it off A's task: there, success is steering, not decoding.

| condition | model | point | other_issue | block | took_jackpot | off | skip | missing | not block |
|---|---|---|---|---|---|---|---|---|---|
| jackpot_chat | modal-qwen3-32b-thinking | 48/48 | 85/88 | 1/1 | 0/2 | 8/8 | 3/3 | - | 144/149 |
| jackpot_hidden | modal-qwen3-32b-thinking | 58/64 | 11/80 | - | - | 0/1 | 3/5 | - | 72/150 |
| jackpot_visible | modal-qwen3-32b-thinking | 49/70 | 22/72 | 1/1 | - | 3/3 | 2/4 | - | 76/149 |

Not-block boards, B right, first > second. Whether A blocks depends on the coin, so these boards need not be balanced on jackpot position, and a lean towards the first-listed task would move raw subset accuracy. Test: exact conditional (Mantel-Haenszel) test stratified by jackpot position, unpaired. JP-5 is left out: its A text differs, so its subset differs by design.

- jackpot_visible vs jackpot_hidden, modal-qwen3-32b-thinking: jackpot T1: 59/75 vs 72/75; jackpot T2: 17/74 vs 0/75; p = 0.2905

## Hit rate = P(B on T1/T2) x P(right | on T1/T2) (exploratory)

| condition | model | on pair | right given on pair | right |
|---|---|---|---|---|
| jackpot_chat | modal-qwen3-32b-thinking | 147/150 (98%) | 145/147 (99%) | 97% |
| jackpot_hidden | modal-qwen3-32b-thinking | 145/150 (97%) | 72/145 (50%) | 48% |
| jackpot_visible | modal-qwen3-32b-thinking | 146/150 (97%) | 77/146 (53%) | 51% |

## Information, convention-free (exploratory)

Bits, bias-corrected (minus the permutation mean), permutation p. sent = I(coin; A's claim), received = I(coin; B's claim), dependence = I(A's claim; B's claim): B reacting to A in any direction. In JP-2, B's only coin-dependent input is A's claim, so received <= sent up to noise.

| condition | model | sent (p) | received (p) | received / sent | dependence (p) |
|---|---|---|---|---|---|
| jackpot_chat | modal-qwen3-32b-thinking | 0.096 (0.000) | 0.882 (0.000) | 9.14 | 0.113 (0.000) |
| jackpot_hidden | modal-qwen3-32b-thinking | 0.016 (0.093) | -0.004 (1.000) | -0.27 | -0.003 (0.717) |
| jackpot_visible | modal-qwen3-32b-thinking | -0.015 (1.000) | -0.003 (0.483) | - | 0.062 (0.004) |

Not-block boards only. On block boards B's move off the decoy is payoff-driven, so dependence there is steering; dependence on the other boards, compared with JP-3, is the convention-free sign that B reads A's claim.

| condition | model | boards | sent (p) | received (p) | dependence (p) |
|---|---|---|---|---|---|
| jackpot_chat | modal-qwen3-32b-thinking | 149 | 0.104 (0.000) | 0.881 (0.000) | 0.120 (0.000) |
| jackpot_hidden | modal-qwen3-32b-thinking | 150 | 0.016 (0.093) | -0.004 (1.000) | -0.003 (0.717) |
| jackpot_visible | modal-qwen3-32b-thinking | 149 | -0.015 (1.000) | -0.004 (0.501) | 0.054 (0.004) |

The p-values in the two tables above measure dependence within a condition, not reading: a shared nudge from the board towards the same issue would pass them too. "B reads A" comes only from the comparisons with JP-3 below.

Not-block dependence, first > second (exploratory; plug-in difference, one-sided permutation of condition labels). "B uses A's claim as information" needs the first and third to hold; "B decodes it correctly" also needs JP-2's not-block received information above zero (table above).

- jackpot_visible > jackpot_hidden, modal-qwen3-32b-thinking: +0.073 bits, p = 0.0010. Licenses: B's claim depended on A's (B told A knows)

## Paired comparisons (same seeds)

| comparison | model | boards | first only right | second only right | McNemar p (one-sided) |
|---|---|---|---|---|---|
| H2b channel cut: jackpot_visible > jackpot_hidden | modal-qwen3-32b-thinking | 150 | 19 | 14 | 0.2434 |
| H2b on-pair (exploratory): jackpot_visible > jackpot_hidden | modal-qwen3-32b-thinking | 142 | 18 | 14 | 0.2983 |
| chat vs actions (exploratory): jackpot_chat > jackpot_visible | modal-qwen3-32b-thinking | 150 | 70 | 2 | 0.0000 |
