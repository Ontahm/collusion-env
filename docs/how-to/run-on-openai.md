# Run a study on OpenAI or another API

Paid API models: gpt-4.1-mini (the paper's model) and gpt-5-mini through OpenAI, Llama 3.3 70B
through Together, or any OpenAI-compatible endpoint.

## 1. Put your key in `.env`

`make install` created `.env` (not in git, readable by you only):

```bash
OPENAI_API_KEY=sk-...           # gpt-4.1-mini, gpt-5-mini
TOGETHER_API_KEY=...            # Llama 3.3 70B on Together
```

Use a key with a monthly limit. If a key leaks: [SECURITY.md](../../SECURITY.md).

## 2. Check what will run

```bash
make dry-run STUDY=configs/studies/colosseum_paper.yaml
```

Prints the episodes and the maximum number of model calls; nothing is called. Past costs:
[measured runs](../reference/studies-and-models.md#measured-runs). Summaries report the cost of a
run from the prices in its model file.

## 3. Run it

```bash
make run STUDY=configs/studies/colosseum_paper.yaml
```

It asks before calling a paid model (`ARGS=--yes` skips the question). After Ctrl+C it prints the
command to continue; finished episodes are kept. Add the options you gave the first time
(`--only`, `--models`, `--seeds`), or the run plans the whole study:

```bash
make run STUDY=configs/studies/colosseum_paper.yaml ARGS='--resume runs/<folder> --yes'
```

## Reproduce the paper

Colosseum's three Jira conditions on gpt-4.1-mini, seeds 1–10 (30 episodes). What it compares:
[the studies](../explanation/studies.md#paper-reproduction-paper).

```bash
make run STUDY=configs/studies/colosseum_paper.yaml ARGS=--yes      # 23 Oct: $3.72, 16 min
uv run python -m analysis.paper_figure runs/<folder>                # the run next to the paper
```

`analysis.paper_figure` writes in the run folder:

| File | Contents |
|---|---|
| `figures/paper_comparison.png` / `.pdf` | the run next to the paper: effect of the secret message board on team regret and coalition advantage |
| `figures/paper_comparison_conditions.png` / `.pdf` | the run alone, per condition |
| `paper_comparison.md` | the numbers, with the paper's GPT-4.1-mini values |

`--colosseum <summary.csv>` adds a run of Colosseum's own code to the table. Limits of the
comparison: [fidelity](../explanation/fidelity.md).

## Run the actions v0.4 pilot

`actions_v04.yaml`: planted boards (PSUM scenarios), 20 rounds per episode, seeds 1–10. Play it on
gpt-5-mini; gpt-4.1-mini misreads the sprint history and skips claims ([runs/](../../archive/runs/README.md)).
A pilot on 3 seeds, then the rest of the seeds in the same folder:

```bash
make run STUDY=configs/studies/actions_v04.yaml ARGS='--use-model configs/models/gpt-5-mini.yaml --seeds 1-3 --concurrency 9 --yes'
make run STUDY=configs/studies/actions_v04.yaml ARGS='--use-model configs/models/gpt-5-mini.yaml --resume runs/<pilot folder> --yes'
uv run python -m analysis.actions_v04 runs/<folder>                 # writes actions_v04.md
```

Keep `--use-model` when resuming: without it, the run plays everything again on gpt-4.1-mini.

The PLANT pilot on gpt-5-mini cost $7.45 and took 51 minutes. Its private-chat control has shown
no coalition gain so far, so the full study has not been run ([runs/](../../archive/runs/README.md)).
Measures: [actions v0.4](../explanation/measures.md#actions-design-v04).

## Use another model

`--use-model` replaces a study's models for one run; the run folder is named after the model:

```bash
make run STUDY=configs/studies/action_channel.yaml ARGS='--use-model configs/models/together-llama-3.3-70b.yaml --yes'
```

For another OpenAI-compatible endpoint, copy a file of `configs/models/` and change `label`,
`base_url`, `model` and `api_key_env` (the name of the `.env` variable that holds the key). Check
it:

```bash
make check-model MODEL=configs/models/<your file>.yaml    # ends with: result : ready
```

All model settings: [spec/15-configuration.md](../../spec/15-configuration.md).
