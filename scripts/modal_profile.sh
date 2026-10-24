#!/bin/sh
# Which Modal model make modal-run uses (deploy/models/<name>.env): the name given (MODAL=<name>),
# else a choice from a menu when run in a terminal, else qwen3-8b. Prints the file's path.
dir=deploy/models
default=qwen3-8b
names=$(ls "$dir" | sed -n 's/\.env$//p')
pick=$1
if [ -z "$pick" ] && [ -t 0 ]; then
  echo "Which model? (MODAL=<name> skips this question)" >&2
  i=0
  for n in $names; do
    i=$((i + 1))
    printf '  %d) %-18s %s\n' "$i" "$n" "$(. "./$dir/$n.env"; echo "$DESCRIPTION, GPU $GPU")" >&2
  done
  printf 'number [%s]: ' "$default" >&2
  read -r answer
  case "$answer" in
    "") ;;
    *[!0-9]*) echo "not a number: $answer" >&2; exit 1 ;;
    *) pick=$(echo "$names" | sed -n "${answer}p"); [ -n "$pick" ] || { echo "no model number $answer" >&2; exit 1; } ;;
  esac
fi
pick=${pick:-$default}
[ -f "$dir/$pick.env" ] || { echo "unknown model '$pick'; one of:" $names >&2; exit 1; }
echo "$dir/$pick.env"
