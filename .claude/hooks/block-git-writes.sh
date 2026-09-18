#!/bin/bash
# PreToolUse(Bash): hard-enforce the "agents never write to git or GitHub" policy.
# Advisory AGENTS.md lines are not enough; this makes the rule actually hold.
# Exit 0 always — the JSON on stdout carries the deny decision.

input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty')
[ -z "$cmd" ] && exit 0

deny() {
  jq -n --arg reason "$1" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $reason
    }
  }'
  exit 0
}

# Strip quoted strings so a commit *message* mentioning "git push" cannot trip this,
# then scan each command in a chain (;, &&, ||, |).
scan=$(printf '%s' "$cmd" | sed "s/'[^']*'//g; s/\"[^\"]*\"//g")

while IFS= read -r part; do
  part=$(printf '%s' "$part" | sed 's/^[[:space:]]*//')

  if printf '%s' "$part" | grep -Eq '^(sudo[[:space:]]+)?git[[:space:]]+(commit|push|merge|rebase|reset|revert|cherry-pick|stash|tag|am|apply|restore|clean|rm|mv|init)([[:space:]]|$)' \
     || printf '%s' "$part" | grep -Eq '^(sudo[[:space:]]+)?git[[:space:]]+checkout[[:space:]]+--([[:space:]]|$)' \
     || printf '%s' "$part" | grep -Eq '^(sudo[[:space:]]+)?git[[:space:]]+branch[[:space:]]+-[dDm]([[:space:]]|$)'; then
    deny "Blocked by project policy (AGENTS.md §Git rules): agents never write to git. Omar runs all git write operations himself — including 'git init'. Do the file work, draft the commit message, report what changed, and stop. Read-only git (status/log/diff/branch/show) is allowed."
  fi

  if printf '%s' "$part" | grep -Eq '^(sudo[[:space:]]+)?gh[[:space:]]+' \
     && ! printf '%s' "$part" | grep -Eq '^(sudo[[:space:]]+)?gh[[:space:]]+[a-z-]+[[:space:]]+(view|list|diff|status|checks)([[:space:]]|$)'; then
    deny "Blocked by project policy (AGENTS.md §Git rules): agents never run GitHub write commands — this includes 'gh repo create'. Draft the content and show it instead of running it. Read-only gh (view/list/diff/status/checks) is allowed."
  fi

  if printf '%s' "$part" | grep -Eq -- '--no-verify'; then
    deny "Blocked: --no-verify is never acceptable on this project. Fix the underlying failure instead."
  fi
done < <(printf '%s\n' "$scan" | tr ';|&' '\n')

exit 0
