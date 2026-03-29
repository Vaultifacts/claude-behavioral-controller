#!/bin/bash
# statusline.sh — Claude Code status line, Windows 10 + Git Bash
# Python logic is in statusline_parse.py to avoid CRLF-in-heredoc issues.
# Displays: [HH:MM:SS] model bar% Xk | $cost [branch*] dir

INPUT=$(cat)
TIME=$(date +%H:%M:%S)

PARSED=$(echo "$INPUT" | PYTHONIOENCODING=utf-8 '/c/Program Files/Python313/python' \
  'C:/Users/Matt1/.claude/statusline_parse.py' 2>/c/Users/Matt1/.claude/statusline-err.log)

if [ -z "$PARSED" ]; then
  PARSED="unknown|0|0|0.0000|~"
fi

MODEL=$(echo "$PARSED"       | cut -d'|' -f1)
PCT=$(echo "$PARSED"         | cut -d'|' -f2)
REM_K=$(echo "$PARSED"       | cut -d'|' -f3)
COST=$(echo "$PARSED"        | cut -d'|' -f4)
CWD=$(echo "$PARSED"         | cut -d'|' -f5)
STYLE_BADGE=$(echo "$PARSED" | cut -d'|' -f6)
RATE_REM=$(echo "$PARSED"    | cut -d'|' -f7)
PCT="${PCT:-0}"
REM_K="${REM_K:-0}"
CWD="${CWD:-~}"
STYLE_BADGE="${STYLE_BADGE:-}"
RATE_REM="${RATE_REM:--1}"

BRANCH=$(git --no-optional-locks branch --show-current 2>/dev/null)
DIRTY=$(git --no-optional-locks status --porcelain 2>/dev/null | head -c1)

# Use $'...' so variables contain actual ESC bytes (works in both format str and %s args)
CYAN=$'\033[36m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
BLUE=$'\033[34m'
RED=$'\033[31m'
MAGENTA=$'\033[35m'
BOLD=$'\033[1m'
RESET=$'\033[0m'

# Context bar color
if [ "$PCT" -ge 85 ]; then
  BAR_COLOR="$RED"
elif [ "$PCT" -ge 65 ]; then
  BAR_COLOR="$YELLOW"
else
  BAR_COLOR="$GREEN"
fi

FILLED=$(( (PCT * 10) / 100 ))
[ "$FILLED" -gt 10 ] && FILLED=10
EMPTY=$(( 10 - FILLED ))

BAR=""
for ((i=0; i<FILLED; i++)); do BAR="${BAR}█"; done
for ((i=0; i<EMPTY; i++)); do BAR="${BAR}░"; done

# Cost color: green < $1, yellow $1–$5, red >= $5
COST_INT=$(awk "BEGIN{printf \"%d\", $COST * 100}" 2>/dev/null || echo 0)
if [ "$COST_INT" -ge 500 ]; then
  COST_COLOR="$RED"
elif [ "$COST_INT" -ge 100 ]; then
  COST_COLOR="$YELLOW"
else
  COST_COLOR="$GREEN"
fi
COST_FMT=$(printf '$%.3f' "${COST}" 2>/dev/null || echo '$?')

# Branch with dirty indicator
if [ -n "$BRANCH" ]; then
  if [ -n "$DIRTY" ]; then
    BRANCH_DISPLAY=" ${CYAN}[${BRANCH}${YELLOW}*${CYAN}]${RESET}"
  else
    BRANCH_DISPLAY=" ${CYAN}[${BRANCH}]${RESET}"
  fi
else
  BRANCH_DISPLAY=""
fi

# Context hint
if [ "$PCT" -ge 85 ]; then
  CTX_HINT=" ${RED}/compact${RESET}"
elif [ "$PCT" -ge 65 ]; then
  CTX_HINT=" ${YELLOW}up ctx${RESET}"
else
  CTX_HINT=""
fi

# Output style badge (e.g. "L" for Learning)
if [ -n "$STYLE_BADGE" ]; then
  STYLE_DISPLAY=" ${MAGENTA}[${STYLE_BADGE}]${RESET}"
else
  STYLE_DISPLAY=""
fi

# Rate limit indicator (only show when known and low)
RATE_DISPLAY=""
if [ "$RATE_REM" -ge 0 ] 2>/dev/null; then
  if [ "$RATE_REM" -le 5 ]; then
    RATE_DISPLAY=" ${RED}rl:${RATE_REM}${RESET}"
  elif [ "$RATE_REM" -le 20 ]; then
    RATE_DISPLAY=" ${YELLOW}rl:${RATE_REM}${RESET}"
  fi
fi


printf "%s[%s]%s %s%s%s %s%s%s %s%%%s %s%sk%s | %s%s%s%s %s%s%s%s%s\n" \
  "$CYAN" "$TIME" "$RESET" \
  "$BOLD" "$MODEL" "$RESET" \
  "$BAR_COLOR" "$BAR" "$RESET" \
  "$PCT" "$CTX_HINT" \
  "$CYAN" "$REM_K" "$RESET" \
  "$COST_COLOR" "$COST_FMT" "$RESET" \
  "$BRANCH_DISPLAY" \
  "$BLUE" "$CWD" "$RESET" \
  "$STYLE_DISPLAY" \
  "$RATE_DISPLAY"
