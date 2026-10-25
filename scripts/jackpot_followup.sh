#!/bin/sh
# Follow-up runs on gpt-5-mini, pre-registered in spec/jackpot/PREREG.md (Amendment 1). One stage at a time,
# from the repo folder, laptop plugged in and lid open:
#   caffeinate -i sh scripts/jackpot_followup.sh code      # JP-6, agreed code, boards 1-150     (F1)
#   caffeinate -i sh scripts/jackpot_followup.sh naive     # JP-5 replicated, boards 151-300   (F2, F3)
#   caffeinate -i sh scripts/jackpot_followup.sh monitor   # JP-7, auditor told to A, boards 1-150 (F4, F5)
# Every stage writes into the same folder (the first stage creates it, later ones find it), then rewrites
# that folder's jackpot.md with the main run's rows alongside (--with) for the paired tests.
# If a stage stops, run the same command again: finished games are skipped.
set -u
MAIN=runs/20261024-175907__jackpot
STUDY=configs/studies/jackpot_followup.yaml
case "${1:-}" in
  code)    ONLY=jackpot_code;      SEEDS=1-150 ;;
  naive)   ONLY=jackpot_naive;     SEEDS=151-300 ;;
  monitor) ONLY=jackpot_monitor;   SEEDS=1-150 ;;
  *) echo "usage: sh scripts/jackpot_followup.sh code | naive | monitor"; exit 2 ;;
esac
RUN=${RUN:-$(ls -d runs/*__jackpot_followup 2>/dev/null | tail -1)}
[ -n "$RUN" ] || RUN=runs/$(date +%Y%m%d-%H%M%S)__jackpot_followup
echo "[followup] stage $1 into $RUN"
make run STUDY=$STUDY ARGS="--resume $RUN --only $ONLY --seeds $SEEDS --yes"
uv run --locked python -m analysis.jackpot "$RUN" --with "$MAIN" | tail -1
echo "[followup] done. Upload $RUN/jackpot.md (and index.csv) if you want it read."
