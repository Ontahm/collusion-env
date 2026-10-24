#!/bin/sh
# Main jackpot run on gpt-5-mini, as frozen in spec/jackpot/PREREG.md:
#   1. all six conditions of configs/studies/jackpot.yaml on boards 1-150;
#   2. JP-2, JP-3 and JP-4 (the conditions in the confirmatory tests) also on boards 151-300;
#   3. the summary, jackpot.md, written into the run folder.
# Everything goes into ONE run folder (run.py --resume creates it when it does not exist yet), so
# analysis.jackpot sees 300 matched boards for JP-2/3/4 and 150 for the others.
#
# Start, from the repo folder, laptop plugged in and lid open:
#   caffeinate -i sh scripts/jackpot_main.sh
# If it stops, run it again with the folder it printed; finished games are skipped:
#   RUN=runs/<folder it printed> caffeinate -i sh scripts/jackpot_main.sh
set -u
STUDY=configs/studies/jackpot.yaml
RUN=${RUN:-runs/$(date +%Y%m%d-%H%M%S)__jackpot}
echo "[jackpot] run folder: $RUN"
make run STUDY=$STUDY ARGS="--resume $RUN --yes"
make run STUDY=$STUDY ARGS="--resume $RUN --seeds 151-300 --only jackpot_visible,jackpot_hidden,jackpot_untold --yes"
uv run --locked python -m analysis.jackpot "$RUN"
echo "[jackpot] done. Upload this file: $RUN/jackpot.md"
