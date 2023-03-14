#!/bin/bash

# Fail on non-zero exit code
set -e

# Fail on unset variables
set -o nounset

if [[ "${DEBUG}" == "true" ]]; then
  echo "Debug mode enabled in commit-and-pull-request.sh"
  set -x

  env
fi

# If we have both images and charts, the title should reflect that.
if [[ "${IMAGES}" != "[]" && "${CHARTS}" != "[]" ]]; then
  TITLE="Promote images ${IMAGES_NAMES} and charts ${CHARTS_NAMES}"
else
  if [[ "${IMAGES}" != "[]" ]]; then
    TITLE="Promote images ${IMAGES_NAMES}"
  fi
  if [[ "${CHARTS}" != "[]" ]]; then
    TITLE="Promote charts ${CHARTS_NAMES}"
  fi
fi
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
MANIFEST_JSON: ${MANIFEST_JSON}"

if [[ "${PROMOTION_METHOD}" == "pull_request" ]]; then
  BRANCH="$(echo "promotion/${GITHUB_REPOSITORY:?}/${TARGET_BRANCH:?}/${GITHUB_SHA:?}" | tr "/" "-")"
  git checkout -B "${BRANCH}"

  git add .
  git commit -m "${TITLE}

  ${METADATA}
  "
  git show

  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "Dry run is enabled. Not pushing changes."
    exit 0
  fi

  git push origin "${BRANCH}" -f
  set +e
  PR="$(gh pr view 2>&1)"
  set -e
  # We're just looking for the sub-string here, not a regex
  # shellcheck disable=SC2076
  if [[ "${PR}" =~ "no pull requests found" ]]; then
    gh pr create --fill
  else
    echo "PR Already exists:"
    gh pr view
  fi

  echo
  echo "Waiting for status checks to complete..."
  set +e
  CHECK_RESULT="$(gh pr checks 2>&1)";
  set -e
  ATTEMPTS=3
  echo "result"
  echo "${CHECK_RESULT}"
  while [[ "${CHECK_RESULT}" =~ "no checks reported" && $ATTEMPTS -gt 0 ]]; do
    sleep 10
    echo "No status checks found or checks are just slow to start."

    # If non-zero, then we have a failure
    set +e
    CHECK_RESULT="$(gh pr checks 2>&1)"
    set -e
    # Decrement the number of attempts
    ATTEMPTS=$((ATTEMPTS - 1))
    echo "${ATTEMPTS} attempts remaining"
  done

  echo "result"
  echo "${CHECK_RESULT}"
  ATTEMPTS=5
  while [[ "${CHECK_RESULT}" =~ "Waiting for status checks to start" && $ATTEMPTS -gt 0 ]]; do
    sleep 10

    # If non-zero, then we have a failure
    set +e
    if ! CHECK_RESULT="$(gh pr checks 2>&1)"; then
      echo "Status checks have failed. Exiting."
      exit 1
    fi
    set -e
    # Decrement the number of attempts
    ATTEMPTS=$((ATTEMPTS - 1))
    echo "${ATTEMPTS} attempts remaining"
  done
  echo
  if [[ "${AUTO_MERGE}" == "true" ]]; then
    echo "Status checks have all passed. Merging PR..."
    gh pr merge --squash --admin
    echo
    echo "Promotion PR has been merged. Details below."
  else
    echo
    echo "Promotion PR has been created and has passed checks. Details below."
  fi
  gh pr view
elif [[ "${PROMOTION_METHOD}" == "push" ]]; then
  git add .
  git commit -m "${TITLE}

  ${METADATA}
  "
  git show

  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "Dry run is enabled. Not pushing changes."
    exit 0
  fi

  git push origin "${TARGET_BRANCH}"
  echo
  # If we have both images and charts, the output should reflect that.
  if [[ "${IMAGES}" != "[]" && "${CHARTS}" != "[]" ]]; then
    echo "Images ${IMAGES_NAMES} and charts ${CHARTS_NAMES} from ${GITHUB_GHA} have been promoted to ${TARGET_REPO} on branch ${TARGET_BRANCH}."
  else
    if [[ "${IMAGES}" != "[]" ]]; then
      echo "Images ${IMAGES_NAMES} from ${GITHUB_GHA} have been promoted to ${TARGET_REPO} on branch ${TARGET_BRANCH}."
    fi
    if [[ "${CHARTS}" != "[]" ]]; then
      echo "Charts ${CHARTS_NAMES} from ${GITHUB_GHA} have been promoted to ${TARGET_REPO} on branch ${TARGET_BRANCH}."
    fi
  fi
  echo
  echo "${DEPLOYMENT_REPO_SHA_URL}"
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
