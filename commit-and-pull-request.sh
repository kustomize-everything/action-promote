#!/bin/bash

# Fail on non-zero exit code
set -e

TITLE="Promote ${IMAGES}"
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
IMAGES: ${IMAGES}
IMAGES_JSON: ${IMAGES_JSON}"

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
  CHECKS_DONE=""
  while [[ "${CHECKS_DONE}" != "true" ]]; do
    set +e
    CHECK_RESULTS="$(gh pr checks 2>&1)"
    set -e
    WAITING_PATTERN="no checks reported"
    # We're just looking for the sub-string here, not a regex
    # shellcheck disable=SC2076
    if [[ "${CHECK_RESULTS}" =~ "${WAITING_PATTERN}" ]]; then
      echo "Waiting for status checks to start..."
      sleep 5
    else
      CHECKS_DONE="true"
    fi
  done
  echo
  echo "Waiting for status checks to complete..."
  gh pr checks --watch
  echo
  echo "Status checks have all passed. Merging PR..."
  gh pr merge --squash --admin
  echo
  echo "Promotion PR has been merged. Details below."
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
  echo "Images ${IMAGES} from ${GITHUB_GHA} have been promoted to ${TARGET_REPO} on branch ${TARGET_BRANCH}."
  echo
  DEPLOYMENT_REPO_SHA_URL="$(gh browse -c -n -R "${TARGET_REPO}")"
  echo "${DEPLOYMENT_REPO_SHA_URL}"
else
  echo "Unknown promotion method: ${PROMOTION_METHOD}. Valid methods are pull_request and push."
  exit 1
fi

# Set outputs so that downstream steps can consume this data
# shellcheck disable=SC2129
echo "deployment-repo-sha-short=$(git rev-parse --short HEAD)" >> "${GITHUB_OUTPUT}"
echo "deployment-repo-sha-url=${DEPLOYMENT_REPO_SHA_URL}" >> "${GITHUB_OUTPUT}"
echo "deployment-repo-sha=$(git rev-parse HEAD)" >> "${GITHUB_OUTPUT}"
echo "images=${IMAGES}" >> "${GITHUB_OUTPUT}"
echo "images-json=${IMAGES_JSON}" >> "${GITHUB_OUTPUT}"
