#!/bin/bash
# validate-bash.sh
# PreToolUse hook for Bash tool.
# Blocks destructive system commands. Uses Python for JSON parsing (jq not available).

INPUT=$(cat)

# Extract command from tool_input using Python
# PYTHONIOENCODING=utf-8 required on Windows to handle Unicode without crash.
# Falls back to top-level keys if tool_input wrapper is absent.
COMMAND=$(echo "$INPUT" | PYTHONIOENCODING=utf-8 python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    ti = d.get('tool_input', d)
    print(ti.get('command', '') if isinstance(ti, dict) else '')
except Exception:
    print('')
" 2>/dev/null)

# If Python failed to parse, fail closed when input clearly had a command
if [ -z "$COMMAND" ] && echo "$INPUT" | grep -q '"command"'; then
  echo "BLOCKED: validate-bash.sh — failed to extract command. Blocking as precaution." >&2
  exit 2
fi

if [ -z "$COMMAND" ]; then
  exit 0
fi

# Normalize to lowercase for matching
CMD_LOWER=$(echo "$COMMAND" | tr '[:upper:]' '[:lower:]')

# Dangerous patterns that should always require explicit approval.
# Ordered from most to least dangerous.
DANGEROUS_PATTERNS=(
  "rm -rf /"
  "rm -rf /c"
  "rm -rf c:"
  "rm -rf ~"
  'rm -rf $HOME'
  'rm -rf ${HOME}'
  "rm -rf /home"
  "rm --no-preserve-root"
  "del /f /s /q c:\\windows"
  "del /f /s /q c:/windows"
  "shutdown /s"
  "shutdown /r"
  "shutdown -h"
  "shutdown -r"
  "format c:"
  "format /fs"
  "dd if=/dev/zero of=/dev"
  "dd if=/dev/urandom of=/dev"
  "diskpart"
  "mkfs"
  "reg delete hklm\\system"
  "reg delete hklm\\software\\microsoft\\windows"
  "reg delete hkcu\\software\\microsoft\\windows\\currentversion"
  "net user administrator"
  "net localgroup administrators"
  "icacls c:\\windows"
  "cacls c:\\windows"
  "takeown /f c:\\windows"
  "bcdedit /delete"
  "git push --force"
  "git push -f"
  "git push origin +main"
  "git push origin +master"
  "git reset --hard"
  "remove-item -recurse -force c:\\"
  "drop database"
  "drop table"
  "kubectl delete namespace"
  "find / -delete"
  "find / -exec rm"
  "gh repo delete"
  "rm -rf ./"
  "rm -rf ../"
  "docker system prune"
  "npm publish"
)

# Patterns that are OK when quoted/commented (grep, echo, etc.)
# Only block if the pattern appears as an actual command, not inside quotes after echo/grep/git log
CONTEXT_SENSITIVE_PATTERNS=(
  "drop database"
  "drop table"
  "mkfs"
  "diskpart"
  "npm publish"
)

# For context-sensitive patterns, skip if the command is clearly just searching/echoing
is_search_context() {
  local cmd="$1"
  # If the entire command starts with grep/echo/git log/cat/man/rg, it's not destructive
  if [[ "$cmd" == grep\ * ]] || [[ "$cmd" == echo\ * ]] || [[ "$cmd" == git\ log* ]] || \
     [[ "$cmd" == rg\ * ]] || [[ "$cmd" == man\ * ]] || [[ "$cmd" == cat\ * ]]; then
    return 0
  fi
  return 1
}

for pattern in "${DANGEROUS_PATTERNS[@]}"; do
  PATTERN_LOWER=$(echo "$pattern" | tr '[:upper:]' '[:lower:]')
  if [[ "$CMD_LOWER" == *"$PATTERN_LOWER"* ]]; then
    # Check if this is a context-sensitive pattern in a search context
    is_ctx_sensitive=false
    for cs in "${CONTEXT_SENSITIVE_PATTERNS[@]}"; do
      if [[ "$pattern" == "$cs" ]]; then
        is_ctx_sensitive=true
        break
      fi
    done
    if $is_ctx_sensitive && is_search_context "$CMD_LOWER"; then
      continue
    fi
    echo "BLOCKED: Command matches dangerous pattern '$pattern'." >&2
    echo "If this is intentional, run it directly in your terminal." >&2
    exit 2
  fi
done


# Block interpreter commands that wrap dangerous patterns
# Catches: python -c "...", node -e "...", sh -c "...", bash -c "...", etc.
# Handles standard quotes, $'...' ANSI-C quoting, heredocs, and unquoted args.
if echo "$CMD_LOWER" | grep -qE "(python3?|node|ruby|perl|sh|bash)\s+-[ce]\s"; then
  # Extract everything after the -c/-e flag (covers all quoting styles)
  INNER=$(echo "$COMMAND" | sed -nE "s/.*-[ce]\s+(.*)$/\1/p")
  # Strip surrounding quotes if present (handles '...', "...", $'...')
  INNER=$(echo "$INNER" | sed -E "s/^\\\$?['\"]//; s/['\"]$//" )
  INNER_LOWER=$(echo "$INNER" | tr '[:upper:]' '[:lower:]')
  for pattern in "${DANGEROUS_PATTERNS[@]}"; do
    PATTERN_LOWER=$(echo "$pattern" | tr '[:upper:]' '[:lower:]')
    if [[ "$INNER_LOWER" == *"$PATTERN_LOWER"* ]]; then
      echo "BLOCKED: Interpreter command contains dangerous pattern '$pattern'." >&2
      echo "If this is intentional, run it directly in your terminal." >&2
      exit 2
    fi
  done
  # Check for shell execution wrappers containing dangerous patterns
  if echo "$INNER_LOWER" | grep -qE "(subprocess|execsync|child_process|system\()"; then
    for pattern in "${DANGEROUS_PATTERNS[@]}"; do
      PATTERN_LOWER=$(echo "$pattern" | tr '[:upper:]' '[:lower:]')
      if [[ "$INNER_LOWER" == *"$PATTERN_LOWER"* ]]; then
        echo "BLOCKED: Interpreter shell execution contains dangerous pattern '$pattern'." >&2
        exit 2
      fi
    done
  fi
fi

if echo "$CMD_LOWER" | grep -qE "checkout -- \.([[:space:]]|$)"; then
  echo "BLOCKED: discards all unstaged changes." >&2
  echo "If this is intentional, run it directly in your terminal." >&2
  exit 2
fi

if echo "$COMMAND" | grep -q "git branch -D"; then
  echo "BLOCKED: force-deletes branch without merge check." >&2
  echo "Use -d for safe delete, or run directly in terminal." >&2
  exit 2
fi

exit 0
