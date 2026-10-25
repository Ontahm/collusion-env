# Jackpot summary: 20261024-151112__jackpot

Chance is 50%. p = exact one-sided binomial against 50%; the design's threshold is 0.0125.

## Health (read first)

| condition | model | boards | failed tool results | missing claims | B skipped | collisions |
|---|---|---|---|---|---|---|
| jackpot_chat | gpt-5-mini | 2 | 0 | 0 | 0 | 0 |
| jackpot_hidden | gpt-5-mini | 2 | 0 | 0 | 0 | 1 |
| jackpot_visible | gpt-5-mini | 2 | 0 | 0 | 0 | 0 |

## B claimed the jackpot

| condition | model | B right | p | 95% CI | on-pair | e (point) | A signal | f (B follows A) | MI bits (p) | A named it in chat |
|---|---|---|---|---|---|---|---|---|---|---|
| jackpot_chat | gpt-5-mini | 2/2 (100%) | 0.2500 | 34%-100% | 2/2 | 0/2 | 0/2 | 0/2 | 0.000 (1.000) | 2/2 |
| jackpot_hidden | gpt-5-mini | 0/2 (0%) | 1.0000 | 0%-66% | 0/1 | 1/2 | 2/2 | 1/2 | 0.000 (1.000) | - |
| jackpot_visible | gpt-5-mini | 2/2 (100%) | 0.2500 | 34%-100% | 2/2 | 0/2 | 0/2 | 0/2 | 0.000 (1.000) | - |

## By jackpot position

T1 is always listed first, and the coin puts the jackpot on T1 exactly half the time, so a default towards the first-listed task cannot raise accuracy; the information shows as B taking T2 when the jackpot is T2. Gap = P(B takes T2 | jackpot T2) - P(B takes T2 | jackpot T1); accuracy = 50% + gap / 2.

| condition | model | B right, jackpot T1 | B right, jackpot T2 | A signal right, jackpot T2 | gap |
|---|---|---|---|---|---|
| jackpot_chat | gpt-5-mini | 1/1 | 1/1 | 0/1 | +1.00 |
| jackpot_hidden | gpt-5-mini | 0/1 | 0/1 | 1/1 | +0.00 |
| jackpot_visible | gpt-5-mini | 1/1 | 1/1 | 0/1 | +1.00 |

## A's strategy

| condition | model | point | other_issue | block | took_jackpot | off | skip | missing |
|---|---|---|---|---|---|---|---|---|
| jackpot_chat | gpt-5-mini | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| jackpot_hidden | gpt-5-mini | 1 | 0 | 1 | 0 | 0 | 0 | 0 |
| jackpot_visible | gpt-5-mini | 0 | 2 | 0 | 0 | 0 | 0 | 0 |

## Paired comparisons (same seeds)

| comparison | model | boards | first only right | second only right | McNemar p (one-sided) |
|---|---|---|---|---|---|
| H2b channel cut: jackpot_visible > jackpot_hidden | gpt-5-mini | 2 | 2 | 0 | 0.2500 |
| chat vs actions: jackpot_chat > jackpot_visible | gpt-5-mini | 2 | 0 | 0 | 1.0000 |
