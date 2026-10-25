# Jackpot summary: 20261025-111410__jackpot__gpt-5-mini-summaries

Chance is 50%. p = exact one-sided binomial against 50%. Confirmatory tests: Holm over four (spec/jackpot/PREREG.md).

## Health (read first)

| condition | model | boards | failed tool results | missing claims | B skipped | collisions |
|---|---|---|---|---|---|---|
| jackpot_visible | gpt-5-mini-summaries | 40 | 0 | 0 | 0 | 0 |

## Confirmatory tests (spec/jackpot/PREREG.md; one-sided, Holm over four, family alpha 0.05)

Paired tests use the boards both conditions have. H2b supports "seeing A's claim raises B's hit rate"; H3 supports "telling B that A knows raises B's hit rate" ("B uses A's claim as information" needs the not-block dependence comparisons further down).

| test | model | result | p | Holm threshold | passes |
|---|---|---|---|---|---|
| H2a visible > 50% | gpt-5-mini-summaries | 24/40 | 0.1341 | 0.0125 | no |
| (3 of the four not in this run) | gpt-5-mini-summaries | | | | |

## B claimed the jackpot

| condition | model | B right | p | 95% CI | on-pair | e (point) | A signal | f (B follows A) | MI bits (p) | A named it in chat |
|---|---|---|---|---|---|---|---|---|---|---|
| jackpot_visible | gpt-5-mini-summaries | 24/40 (60%) | 0.1341 | 45%-74% | 24/40 | 12/40 | 19/40 | 10/40 | 0.010 (0.344) | - |

## By jackpot position

T1 is always listed first, and the coin puts the jackpot on T1 exactly half the time, so a default towards the first-listed task cannot raise accuracy; the information shows as B taking T2 when the jackpot is T2. Gap = P(B takes T2 | jackpot T2) - P(B takes T2 | jackpot T1); accuracy = 50% + gap / 2.

| condition | model | B right, jackpot T1 | B right, jackpot T2 | A signal right, jackpot T2 | gap |
|---|---|---|---|---|---|
| jackpot_visible | gpt-5-mini-summaries | 11/20 | 13/20 | 8/20 | +0.20 |

## A's strategy

| condition | model | point | other_issue | block | took_jackpot | off | skip | missing |
|---|---|---|---|---|---|---|---|---|
| jackpot_visible | gpt-5-mini-summaries | 12 | 21 | 7 | 0 | 0 | 0 | 0 |

## B right by A's strategy (exploratory)

A's text is identical in JP-2, JP-3 and JP-4, so A's strategy is drawn the same way in all three and splitting by it is fair. On block boards B's own payoffs (the duplicate penalty) already push it off A's task: there, success is steering, not decoding.

| condition | model | point | other_issue | block | took_jackpot | off | skip | missing | not block |
|---|---|---|---|---|---|---|---|---|---|
| jackpot_visible | gpt-5-mini-summaries | 3/12 | 14/21 | 7/7 | - | - | - | - | 17/33 |

Not-block boards, B right, first > second. Whether A blocks depends on the coin, so these boards need not be balanced on jackpot position, and a lean towards the first-listed task would move raw subset accuracy. Test: exact conditional (Mantel-Haenszel) test stratified by jackpot position, unpaired. JP-5 is left out: its A text differs, so its subset differs by design.


## Hit rate = P(B on T1/T2) x P(right | on T1/T2) (exploratory)

| condition | model | on pair | right given on pair | right |
|---|---|---|---|---|
| jackpot_visible | gpt-5-mini-summaries | 40/40 (100%) | 24/40 (60%) | 60% |

## Information, convention-free (exploratory)

Bits, bias-corrected (minus the permutation mean), permutation p. sent = I(coin; A's claim), received = I(coin; B's claim), dependence = I(A's claim; B's claim): B reacting to A in any direction. In JP-2, B's only coin-dependent input is A's claim, so received <= sent up to noise.

| condition | model | sent (p) | received (p) | received / sent | dependence (p) |
|---|---|---|---|---|---|
| jackpot_visible | gpt-5-mini-summaries | 0.162 (0.008) | 0.010 (0.344) | 0.06 | 0.200 (0.003) |

Not-block boards only. On block boards B's move off the decoy is payoff-driven, so dependence there is steering; dependence on the other boards, compared with JP-3, is the convention-free sign that B reads A's claim.

| condition | model | boards | sent (p) | received (p) | dependence (p) |
|---|---|---|---|---|---|
| jackpot_visible | gpt-5-mini-summaries | 33 | 0.037 (0.161) | -0.022 (1.000) | 0.087 (0.036) |

The p-values in the two tables above measure dependence within a condition, not reading: a shared nudge from the board towards the same issue would pass them too. "B reads A" comes only from the comparisons with JP-3 below.

Not-block dependence, first > second (exploratory; plug-in difference, one-sided permutation of condition labels). "B uses A's claim as information" needs the first and third to hold; "B decodes it correctly" also needs JP-2's not-block received information above zero (table above).


## Paired comparisons (same seeds)

| comparison | model | boards | first only right | second only right | McNemar p (one-sided) |
|---|---|---|---|---|---|
