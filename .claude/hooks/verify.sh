#!/bin/bash
# Stop hook: run the validation matrix and block the turn from ending if it fails.
# No-ops cleanly while the project is pre-scaffold, so it is safe to enable from day one.
# Exit 2 blocks the stop and feeds stderr back to Claude; exit 0 lets the turn end.

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

failures=""

# --- Node stack ---------------------------------------------------------
if [ -f package.json ]; then
  # Only verify when source files actually changed this turn.
  if git rev-parse --git-dir >/dev/null 2>&1; then
    changed=$(git status --porcelain -- '*.ts' '*.tsx' '*.js' '*.jsx' 2>/dev/null)
    [ -z "$changed" ] && exit 0
  fi

  has_script() { node -e "process.exit(require('./package.json').scripts?.['$1']?0:1)" 2>/dev/null; }

  for s in typecheck lint; do
    if has_script "$s"; then
      if ! out=$(npm run --silent "$s" 2>&1); then
        failures+=$'\n=== npm run '"$s"$' failed ===\n'"$(printf '%s' "$out" | tail -40)"
      fi
    fi
  done

# --- Python stack -------------------------------------------------------
elif [ -f Makefile ] && grep -qE '^(typecheck|lint):' Makefile; then
  if git rev-parse --git-dir >/dev/null 2>&1; then
    changed=$(git status --porcelain -- '*.py' 2>/dev/null)
    [ -z "$changed" ] && exit 0
  fi

  for s in typecheck lint; do
    if grep -qE "^${s}:" Makefile; then
      if ! out=$(make "$s" 2>&1); then
        failures+=$'\n=== make '"$s"$' failed ===\n'"$(printf '%s' "$out" | tail -40)"
      fi
    fi
  done

else
  # Pre-scaffold: nothing to verify.
  exit 0
fi

if [ -n "$failures" ]; then
  printf 'Validation failed — do not report this work as complete until it passes.%s\n' "$failures" >&2
  exit 2
fi

exit 0
