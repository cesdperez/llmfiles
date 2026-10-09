#!/bin/bash
# Statusline approximating the oh-my-zsh "agnoster" theme.
# Zones, left to right: path ❯ git │ model │ context
# Zones are split by a dim │, stats inside a zone by a dim ·.

input=$(cat)
cwd=$(echo "$input" | jq -r '.workspace.current_dir')
model=$(echo "$input" | jq -r '.model.display_name')
ctx_used=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
effort=$(echo "$input" | jq -r '.effort.level // empty')
thinking_enabled=$(echo "$input" | jq -r '.thinking.enabled')

DIM="\033[2m"
RESET="\033[0m"
CYAN="\033[36m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"

# dim label, value colored green below warn, yellow below crit, red at/above crit
render_stat() {
  local label="$1" pct="$2" warn="$3" crit="$4" color
  if awk -v v="$pct" -v c="$crit" 'BEGIN{exit !(v>=c)}'; then
    color="$RED"
  elif awk -v v="$pct" -v w="$warn" 'BEGIN{exit !(v>=w)}'; then
    color="$YELLOW"
  else
    color="$GREEN"
  fi
  printf "${DIM}%s${RESET} ${color}%.0f%%${RESET}" "$label" "$pct"
}

tilde='~'
dir_display="${cwd/#$HOME/$tilde}"

# "Opus 5 (1M context)" -> "Opus 5 [1M]"
model_display=$(printf '%s' "$model" | sed -E 's/ \(([0-9]+[KM]) context\)/ [\1]/')

zone_path=$(printf "\033[1;34m %s \033[0m" "$dir_display")

zone_git=""
if git -C "$cwd" --no-optional-locks rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  branch=$(git -C "$cwd" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null)
  [ -z "$branch" ] && branch=$(git -C "$cwd" --no-optional-locks rev-parse --short HEAD 2>/dev/null)

  if [ -n "$(git -C "$cwd" --no-optional-locks status --porcelain 2>/dev/null)" ]; then
    git_color="33" # yellow: dirty
    dirty=" ✗"
  else
    git_color="32" # green: clean
    dirty=" ✓"
  fi

  zone_git=$(printf "${DIM}❯${RESET} \033[1;%sm %s%s ${RESET}" "$git_color" "$branch" "$dirty")
fi

model_extra=""
[ -n "$effort" ] && model_extra="$model_extra $effort"
[ "$thinking_enabled" = "false" ] && model_extra="$model_extra no-think"
zone_model=$(printf "${CYAN}%s${RESET}${DIM}%s${RESET}" "$model_display" "$model_extra")

zone_ctx=""
[ -n "$ctx_used" ] && zone_ctx=$(render_stat "ctx" "$ctx_used" 70 85)

out="${zone_path}${zone_git}"
for zone in "$zone_model" "$zone_ctx"; do
  [ -n "$zone" ] && out=$(printf "%s ${DIM}│${RESET} %s" "$out" "$zone")
done

printf "%s\n" "$out"
