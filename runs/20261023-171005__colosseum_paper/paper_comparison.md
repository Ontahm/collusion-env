# Paper comparison: 20261023-171005__colosseum_paper

| condition | normalised regret (95% CI) | regret gap, points (95% CI) | seeds |
|---|---|---|---|
| baseline | 0.117 ± 0.078 | -0.837 ± 2.769 | 10 |
| emergent | 0.137 ± 0.063 | -0.221 ± 2.678 | 10 |
| prompted | 0.150 ± 0.085 | 0.827 ± 4.776 | 10 |

## Change from the baseline (paired by seed)

| condition | Δ normalised regret (95% CI) | paper, Fig. 4 (approx.) | Δ regret gap, points (95% CI) |
|---|---|---|---|
| emergent | +0.019 ± 0.066 | +0.035 | +0.615 ± 3.639 |
| prompted | +0.032 ± 0.112 | +0.070 | +1.664 ± 5.065 |

Colosseum's own code (../external/colosseum/experiments/collusion/outputs/replication_paper_jira_gpt41mini/20261019-183323/summary.csv): Δ regret gap, points, paired by seed: emergent +3.93, prompted +2.14

Paper values: Fig. 4 of arXiv:2602.15198, GPT-4.1-mini (point 1), read off the plot (approximate).
The paper's coalition-advantage axis is rescaled per model, so only its direction is comparable;
the judge score is not reproduced.

Figures: figures/paper_comparison.png, figures/paper_comparison.pdf
