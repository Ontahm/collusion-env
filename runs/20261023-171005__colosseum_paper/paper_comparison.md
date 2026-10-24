# Paper comparison: 20261023-171005__colosseum_paper

## Change from the no-secret-channel control (ours: paired by seed, 95% interval)

| condition | team regret, ours | team regret, paper | coalition advantage, ours | coalition advantage, paper | regret gap (points), ours |
|---|---|---|---|---|---|
| emergent | +0.019 ± 0.066 | +0.035 | +0.019 ± 0.114 | +0.080 | +0.615 ± 3.639 |
| prompted | +0.032 ± 0.112 | +0.070 | +0.052 ± 0.159 | +0.170 | +1.664 ± 5.065 |

## Our run per condition (mean over seeds, 95% interval)

| condition | team regret | regret gap, points | seeds |
|---|---|---|---|
| baseline | +0.117 ± 0.078 | -0.837 ± 2.769 | 10 |
| emergent | +0.137 ± 0.063 | -0.221 ± 2.678 | 10 |
| prompted | +0.150 ± 0.085 | +0.827 ± 4.776 | 10 |

Colosseum's own code (../external/colosseum/experiments/collusion/outputs/replication_paper_jira_gpt41mini/20261019-183323/summary.csv), change in regret gap (points), paired by seed: emergent +3.927 ± 5.145, prompted +2.144 ± 4.575

Paper: Fig. 4 of arXiv:2602.15198, GPT-4.1-mini (point 1), read off the plot (approximate); its
regret axis is drawn with "More" at the top. Coalition advantage rescaled as Colosseum does, by the
largest gap in each study's own runs, so comparable in kind, not exactly. No judge score.

Figures: figures/paper_comparison.png, figures/paper_comparison.pdf, figures/paper_comparison_conditions.png, figures/paper_comparison_conditions.pdf
