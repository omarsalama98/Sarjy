---
name: code-review
description: Review a diff in the Sarjy codebase. Use after completing a feature, before asking Omar to commit, and before submission — with the extra bar that this code gets read aloud by a reviewer.
argument-hint: [what to review; defaults to the working tree diff]
---

# Code review

Normal review rigor, plus one bar this project adds: **a stranger will read this code with Omar and ask him why it's there.** Unexplainable code is a defect here even when it works.

## Scope

Default to the uncommitted working tree (`git diff` + `git status`). If asked for something else, review that.

## Blocking issues

These fail the review outright:

- **A provider API key reachable from client code**, or any path by which one could be (`AGENTS.md` §Invariant 1). The deployment URL goes to a stranger.
- **A provider SDK, model id, or provider-shaped DTO outside its adapter** (§Invariant 3). Providers get swapped and A/B'd; this is what makes that possible.
- **An external call with no timeout**, or with no defined behavior for failure and empty results.
- **Anything that could let Sarjy invent tool data** on a failed call (§Invariant 6).
- **A user-visible path that can hang** with no state change or recovery (§Invariant 7).
- **Transcribed speech or an API response treated as instructions** rather than data (§Invariant 5).
- **A secret in a file, a log, a doc, or a drafted commit message.**

## Also check

- **Explainability.** For each non-obvious block: could Omar defend this live? Flag generated-looking code, unjustified magic numbers, and dependencies doing the interesting work.
- **Latency path.** Did this add a stage, a round trip, or a blocking await on the voice path? If so, is it instrumented, and has it been measured?
- **Conversation state.** Are the in-between states modelled — listening, thinking, speaking, interrupted — or is state implicit in whatever happens to be running?
- **Error paths get the same scrutiny as happy paths.** They are what breaks in the demo.
- **Fit.** Does this look like the rest of the codebase, or like it came from somewhere else?
- **Scope.** Anything here that isn't in the plan? Anything refactored in passing?
- **Dead weight.** Unused deps, abandoned experiments, commented-out code. Every one is a question in the walkthrough with no good answer.

## Output

Findings ranked most-severe first. For each: file:line, what's wrong, the concrete failure it causes. Separate blocking from worth-fixing. Say plainly if there are no blocking issues — don't manufacture findings to seem thorough.

Then: draft a conventional-commit message for Omar. **Never commit.**

## Anti-patterns in the review itself

- Style nits ranked alongside a leaked credential
- Approving code nobody has walked through
- Reviewing the diff without checking whether a voice turn still works end to end
