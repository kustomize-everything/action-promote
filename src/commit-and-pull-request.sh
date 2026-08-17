#!/bin/bash

# Shared helpers, packaged alongside this script (see Dockerfile `COPY src/* /`).
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/gh-checks.sh"

function git_commit_with_metadata {
  # Default the title if no provided
  if [[ -z "${PR_TITLE:-}" ]]; then
    TITLE="Promote to ${OVERLAY_NAMES}"
  else
    TITLE="${PR_TITLE}"
  fi

  # All of these variables are assumed to have been set by the caller
  METADATA="---
  GITHUB_EVENT_NAME: ${GITHUB_EVENT_NAME}
  GITHUB_JOB: ${GITHUB_JOB}
  GITHUB_REF_URL: ${GITHUB_REF_URL}
  GITHUB_REF: ${GITHUB_REF}
  GITHUB_REPOSITORY_URL: ${GITHUB_REPOSITORY_URL}
  GITHUB_REPOSITORY: ${GITHUB_REPOSITORY}
  GITHUB_RUN_ID: ${GITHUB_RUN_ID}
  GITHUB_RUN_NUMBER: ${GITHUB_RUN_NUMBER}
  GITHUB_SHA_URL: ${GITHUB_SHA_URL}
  GITHUB_SHA: ${GITHUB_SHA}
  GITHUB_WORKFLOW_RUN_URL: ${GITHUB_WORKFLOW_RUN_URL}
  IMAGES: ${IMAGES_NAMES}
  CHARTS: ${CHARTS_NAMES}
  OVERLAYS: ${OVERLAY_NAMES}
  MANIFEST_JSON: ${MANIFEST_JSON}"

  if [ -n "${GIT_COMMIT_MESSAGE:-}" ]; then
    git commit -m "${GIT_COMMIT_MESSAGE}"
  else
    git commit -m "${TITLE}

  ${METADATA}
  "
  fi
}

# Fail on non-zero exit code
set -e

# Fail on unset variables
set -o nounset

if [[ "${DEBUG}" == "true" ]]; then
  echo "Debug mode enabled in commit-and-pull-request.sh"
  set -x

  env
fi

if [[ "${PROMOTION_METHOD}" == "pull_request" ]]; then
  if [[ "${AGGREGATE_PR_CHANGES}" == "true" ]]; then
    BRANCH_REGEX=$(echo "promotion/${GITHUB_REPOSITORY:?}/${TARGET_BRANCH:?}/${OVERLAY_NAMES_NO_SLASH:?}/${PR_UNIQUE_KEY:?}"|tr "/" "-")
    HEAD_REF_NAME=$(gh pr list --json headRefName | jq -rc '.[].headRefName')
    if [[ "${HEAD_REF_NAME}" =~ .*${BRANCH_REGEX}.* ]]; then
      BRANCH=$(gh pr list --json headRefName | jq -rc '.[].headRefName' | grep "${BRANCH_REGEX}")
      git stash
      git checkout -B "${BRANCH}"
      git rebase "${TARGET_BRANCH}"
      git stash apply
    else
      BRANCH=$(echo "promotion/${GITHUB_REPOSITORY:?}/${TARGET_BRANCH:?}/${OVERLAY_NAMES_NO_SLASH:?}/${PR_UNIQUE_KEY:?}/${GITHUB_SHA:?}" | tr "/" "-")
      git checkout -B "${BRANCH}"
    fi
  else
    BRANCH="$(echo "promotion/${GITHUB_REPOSITORY:?}/${TARGET_BRANCH:?}/${OVERLAY_NAMES_NO_SLASH:?}/${PR_UNIQUE_KEY:?}/${GITHUB_SHA:?}" | tr "/" "-")"
    git checkout -B "${BRANCH}"
  fi

  git add .
  git_commit_with_metadata
  git show

  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "Dry run is enabled. Not pushing changes."
    exit 0
  fi

  git push origin "${BRANCH}" -f
  set +e
  # Use explicit JSON fields to avoid querying deprecated projectCards
  # Check if PR exists by attempting to view it
  PR_OUTPUT="$(gh pr view --json number,title,state,url 2>&1)"
  PR_EXIT_CODE=$?
  set -e
  # If command failed or output contains error message, PR doesn't exist
  # We're just looking for the sub-string here, not a regex
  # shellcheck disable=SC2076
  if [[ ${PR_EXIT_CODE} -ne 0 ]] || [[ "${PR_OUTPUT}" =~ "no pull requests found" ]]; then
    gh pr create --fill
  else
    echo "PR Already exists:"
    # Use explicit JSON fields to avoid querying deprecated projectCards
    gh pr view --json number,title,state,url,headRefName,baseRefName
  fi

  # Resolve the PR number while the promotion branch still exists: `gh pr merge
  # --delete-branch` deletes it, and branch-inferred `gh pr` calls then fail.
  PR_NUMBER="$(gh pr view --json number -q '.number')"

  if [[ -n "${LABELS}" ]]; then
    echo "Adding labels to PR: ${LABELS}"
    gh pr edit "${PR_NUMBER}" --add-label "${LABELS}"
  fi  
  
  if [[ -n "${PR_REVIEWER}" ]]; then
    echo "Adding reviewer to PR: ${PR_REVIEWER}"
    gh pr edit "${PR_NUMBER}" --add-reviewer "${PR_REVIEWER}"
  fi

  echo
  echo "Waiting for status checks to complete..."
  # Wait only while checks are actually running. A PR with no status checks
  # ("no checks reported") is treated as "nothing to wait on" and proceeds
  # immediately, instead of waiting out every attempt and failing the promotion.
  status_attempt=0
  while true; do
    set +e
    checks_output="$(gh pr checks "${PR_NUMBER}" 2>&1)"
    set -e
    echo "${checks_output}"
    if [[ "$(pr_checks_state "${checks_output}")" == "proceed" ]]; then
      break
    fi
    status_attempt=$((status_attempt + 1))
    if [[ "${status_attempt}" -ge "${STATUS_ATTEMPTS}" ]]; then
      echo "Status checks still pending after ${STATUS_ATTEMPTS} attempts. Exiting."
      exit 1
    fi
    echo "$((STATUS_ATTEMPTS - status_attempt)) attempts remaining. Sleeping for ${STATUS_INTERVAL} seconds..."
    sleep "${STATUS_INTERVAL}"
  done

  echo
  if [[ "${AUTO_MERGE}" == "true" ]]; then
    # Retry to work around "Base branch was modified." error.
    # Ref: https://github.com/cli/cli/issues/8092
    for i in {1..3}; do
      echo "Checking if the PR is still open..."
      if ! gh pr view "${PR_NUMBER}" --json state | jq -e '.state == "MERGED"' >/dev/null 2>&1; then
        echo "Status checks have all passed. Attempting to merge PR..."
        if gh pr merge "${PR_NUMBER}" --squash --admin --delete-branch; then
          break
        fi
      else
        echo "PR is already merged. Stopping retries."
        break  # Stop retrying if PR is already merged
      fi
      
      if [[ $i -eq 3 ]]; then
        echo "Failed to merge after 3 attempts."
        exit 1
      fi
      
      echo "Merge failed, retrying in 5 seconds..."
      sleep 5
    done

    echo
    echo "Promotion PR has been merged. Details below."
  else
    echo
    echo "Promotion PR has been created and has passed checks. Details below."
  fi
  
  # Use explicit JSON fields to avoid querying deprecated projectCards
  gh pr view "${PR_NUMBER}" --json number,title,state,url,headRefName,baseRefName
  PULL_REQUEST_URL="$(gh pr view "${PR_NUMBER}" --json url -q '.url')"
  
elif [[ "${PROMOTION_METHOD}" == "push" ]]; then
  git add .
  git_commit_with_metadata
  git show

  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "Dry run is enabled. Not pushing changes."
    exit 0
  fi

  git push origin "${TARGET_BRANCH}"
  echo
  # If we have both images and charts, the output should reflect that.
  if [[ "${IMAGES}" != "[]" && "${CHARTS}" != "[]" ]]; then
    echo "Images ${IMAGES_NAMES} and charts ${CHARTS_NAMES} have been promoted to ${TARGET_REPO} on branch ${TARGET_BRANCH}."
  else
    if [[ "${IMAGES}" != "[]" ]]; then
      echo "Images ${IMAGES_NAMES} have been promoted to ${TARGET_REPO} on branch ${TARGET_BRANCH}."
    fi
    if [[ "${CHARTS}" != "[]" ]]; then
      echo "Charts ${CHARTS_NAMES} have been promoted to ${TARGET_REPO} on branch ${TARGET_BRANCH}."
    fi
  fi
else
  echo "Unknown promotion method: ${PROMOTION_METHOD}. Valid methods are pull_request and push."
  exit 1
fi

DEPLOYMENT_REPO_SHA_URL="$(gh browse -c -n -R "${TARGET_REPO}")"

# Set outputs so that downstream steps can consume this data
# shellcheck disable=SC2129
echo "deployment-repo-sha-short=$(git rev-parse --short HEAD)" >> "${GITHUB_OUTPUT}"
echo "deployment-repo-sha-url=${DEPLOYMENT_REPO_SHA_URL}" >> "${GITHUB_OUTPUT}"
echo "deployment-repo-sha=$(git rev-parse HEAD)" >> "${GITHUB_OUTPUT}"
echo "images=${IMAGES_NAMES}" >> "${GITHUB_OUTPUT}"
echo "charts=${CHARTS_NAMES}" >> "${GITHUB_OUTPUT}"
echo "manifest-json=${MANIFEST_JSON}" >> "${GITHUB_OUTPUT}"
echo "pull-request-url=${PULL_REQUEST_URL:-}" >> "${GITHUB_OUTPUT}"
