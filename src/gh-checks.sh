#!/bin/bash
# Helpers for interpreting `gh pr checks` output when deciding whether an
# auto-merge should proceed.

# Classify the output of `gh pr checks` into a single word on stdout:
#   proceed - nothing to wait on: the PR has no status checks
#             ("no checks reported") or all checks have concluded.
#   pending - one or more checks are still running; keep waiting.
#
# `gh pr checks` prints "no checks reported on the '<branch>' branch" (and exits
# non-zero) when a PR has no status checks. The original auto-merge wait treated
# the word "reported" as a pending signal, so promotion PRs targeting a repo
# whose promotion branch has no checks waited out every attempt and then failed
# the whole promotion. Treat "no checks reported" as "nothing to wait on" so the
# caller can proceed to merge (`gh pr merge --admin` bypasses required checks).
function pr_checks_state {
  local output="${1:-}"
  if printf '%s' "${output}" | grep -q "no checks reported"; then
    echo "proceed"
  elif printf '%s' "${output}" | grep -qiE "pending|in progress|queued|waiting"; then
    # Any not-yet-concluded state (pending / in progress / queued / waiting)
    # means checks are still running, so keep waiting. Checked *after* the
    # "no checks reported" case above, so a repo with no checks still proceeds.
    echo "pending"
  else
    echo "proceed"
  fi
}
