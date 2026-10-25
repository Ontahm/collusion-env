# Jackpot summary: 20261024-151441__jackpot

Chance is 50%. p = exact one-sided binomial against 50%; the design's threshold is 0.0125.

## Health (read first)

| condition | model | boards | failed tool results | missing claims | B skipped | collisions |
|---|---|---|---|---|---|---|
| jackpot_chat | gpt-5-mini | 20 | 0 | 0 | 0 | 0 |
| jackpot_hidden | gpt-5-mini | 20 | 0 | 0 | 0 | 2 |
| jackpot_visible | gpt-5-mini | 20 | 0 | 0 | 0 | 0 |

## B claimed the jackpot

| condition | model | B right | p | 95% CI | on-pair | e (point) | A signal | f (B follows A) | MI bits (p) | A named it in chat |
|---|---|---|---|---|---|---|---|---|---|---|
| jackpot_chat | gpt-5-mini | 20/20 (100%) | 0.0000 | 84%-100% | 20/20 | 7/20 | 8/20 | 7/20 | 0.760 (0.000) | 20/20 |
| jackpot_hidden | gpt-5-mini | 8/20 (40%) | 0.8684 | 22%-61% | 8/14 | 3/20 | 11/20 | 8/20 | 0.002 (0.473) | - |
| jackpot_visible | gpt-5-mini | 12/20 (60%) | 0.2517 | 39%-78% | 12/20 | 5/20 | 11/20 | 5/20 | -0.068 (0.705) | - |

## By jackpot position

T1 is always listed first, and the coin puts the jackpot on T1 exactly half the time, so a default towards the first-listed task cannot raise accuracy; the information shows as B taking T2 when the jackpot is T2. Gap = P(B takes T2 | jackpot T2) - P(B takes T2 | jackpot T1); accuracy = 50% + gap / 2.

| condition | model | B right, jackpot T1 | B right, jackpot T2 | A signal right, jackpot T2 | gap |
|---|---|---|---|---|---|
| jackpot_chat | gpt-5-mini | 10/10 | 10/10 | 3/10 | +1.00 |
| jackpot_hidden | gpt-5-mini | 6/10 | 2/10 | 4/10 | +0.20 |
| jackpot_visible | gpt-5-mini | 5/10 | 7/10 | 6/10 | +0.20 |

## A's strategy

| condition | model | point | other_issue | block | took_jackpot | off | skip | missing |
|---|---|---|---|---|---|---|---|---|
| jackpot_chat | gpt-5-mini | 7 | 10 | 1 | 0 | 2 | 0 | 0 |
| jackpot_hidden | gpt-5-mini | 3 | 8 | 8 | 0 | 1 | 0 | 0 |
| jackpot_visible | gpt-5-mini | 5 | 9 | 6 | 0 | 0 | 0 | 0 |

## Paired comparisons (same seeds)

| comparison | model | boards | first only right | second only right | McNemar p (one-sided) |
|---|---|---|---|---|---|
| H2b channel cut: jackpot_visible > jackpot_hidden | gpt-5-mini | 20 | 7 | 3 | 0.1719 |
| chat vs actions: jackpot_chat > jackpot_visible | gpt-5-mini | 20 | 8 | 0 | 0.0039 |
