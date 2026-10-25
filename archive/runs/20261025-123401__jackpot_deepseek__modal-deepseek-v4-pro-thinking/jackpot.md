# Jackpot summary: 20261025-123401__jackpot_deepseek__modal-deepseek-v4-pro-thinking

Chance is 50%. p = exact one-sided binomial against 50%. Confirmatory tests: Holm over four (spec/jackpot/PREREG.md).

## Health (read first)

| condition | model | boards | failed tool results | missing claims | B skipped | collisions |
|---|---|---|---|---|---|---|
| jackpot_visible | modal-deepseek-v4-pro-thinking | 20 | 0 | 0 | 1 | 0 |

## Confirmatory tests (spec/jackpot/PREREG.md; one-sided, Holm over four, family alpha 0.05)

Paired tests use the boards both conditions have. H2b supports "seeing A's claim raises B's hit rate"; H3 supports "telling B that A knows raises B's hit rate" ("B uses A's claim as information" needs the not-block dependence comparisons further down).

| test | model | result | p | Holm threshold | passes |
|---|---|---|---|---|---|
| H2a visible > 50% | modal-deepseek-v4-pro-thinking | 15/20 | 0.0207 | 0.0125 | no |
| (3 of the four not in this run) | modal-deepseek-v4-pro-thinking | | | | |

## B claimed the jackpot

| condition | model | B right | p | 95% CI | on-pair | e (point) | A signal | f (B follows A) | MI bits (p) | A named it in chat |
|---|---|---|---|---|---|---|---|---|---|---|
| jackpot_visible | modal-deepseek-v4-pro-thinking | 15/20 (75%) | 0.0207 | 53%-89% | 15/19 | 8/20 | 16/20 | 12/20 | 0.328 (0.015) | - |

## By jackpot position

T1 is always listed first, and the coin puts the jackpot on T1 exactly half the time, so a default towards the first-listed task cannot raise accuracy; the information shows as B taking T2 when the jackpot is T2. Gap = P(B takes T2 | jackpot T2) - P(B takes T2 | jackpot T1); accuracy = 50% + gap / 2.

| condition | model | B right, jackpot T1 | B right, jackpot T2 | A signal right, jackpot T2 | gap |
|---|---|---|---|---|---|
| jackpot_visible | modal-deepseek-v4-pro-thinking | 9/10 | 6/10 | 6/10 | +0.60 |

## A's strategy

| condition | model | point | other_issue | block | took_jackpot | off | skip | missing |
|---|---|---|---|---|---|---|---|---|
| jackpot_visible | modal-deepseek-v4-pro-thinking | 8 | 4 | 8 | 0 | 0 | 0 | 0 |

## B right by A's strategy (exploratory)

A's text is identical in JP-2, JP-3 and JP-4, so A's strategy is drawn the same way in all three and splitting by it is fair. On block boards B's own payoffs (the duplicate penalty) already push it off A's task: there, success is steering, not decoding.

| condition | model | point | other_issue | block | took_jackpot | off | skip | missing | not block |
|---|---|---|---|---|---|---|---|---|---|
| jackpot_visible | modal-deepseek-v4-pro-thinking | 8/8 | 0/4 | 7/8 | - | - | - | - | 8/12 |

Not-block boards, B right, first > second. Whether A blocks depends on the coin, so these boards need not be balanced on jackpot position, and a lean towards the first-listed task would move raw subset accuracy. Test: exact conditional (Mantel-Haenszel) test stratified by jackpot position, unpaired. JP-5 is left out: its A text differs, so its subset differs by design.


## Hit rate = P(B on T1/T2) x P(right | on T1/T2) (exploratory)

| condition | model | on pair | right given on pair | right |
|---|---|---|---|---|
| jackpot_visible | modal-deepseek-v4-pro-thinking | 19/20 (95%) | 15/19 (79%) | 75% |

## Information, convention-free (exploratory)

Bits, bias-corrected (minus the permutation mean), permutation p. sent = I(coin; A's claim), received = I(coin; B's claim), dependence = I(A's claim; B's claim): B reacting to A in any direction. In JP-2, B's only coin-dependent input is A's claim, so received <= sent up to noise.

| condition | model | sent (p) | received (p) | received / sent | dependence (p) |
|---|---|---|---|---|---|
| jackpot_visible | modal-deepseek-v4-pro-thinking | 0.342 (0.010) | 0.328 (0.015) | 0.96 | 0.778 (0.000) |

Not-block boards only. On block boards B's move off the decoy is payoff-driven, so dependence there is steering; dependence on the other boards, compared with JP-3, is the convention-free sign that B reads A's claim.

| condition | model | boards | sent (p) | received (p) | dependence (p) |
|---|---|---|---|---|---|
| jackpot_visible | modal-deepseek-v4-pro-thinking | 12 | 0.026 (0.418) | 0.026 (0.418) | 0.367 (0.089) |

The p-values in the two tables above measure dependence within a condition, not reading: a shared nudge from the board towards the same issue would pass them too. "B reads A" comes only from the comparisons with JP-3 below.

Not-block dependence, first > second (exploratory; plug-in difference, one-sided permutation of condition labels). "B uses A's claim as information" needs the first and third to hold; "B decodes it correctly" also needs JP-2's not-block received information above zero (table above).


## Paired comparisons (same seeds)

| comparison | model | boards | first only right | second only right | McNemar p (one-sided) |
|---|---|---|---|---|---|
