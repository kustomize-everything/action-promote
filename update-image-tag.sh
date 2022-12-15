#!/bin/bash

# Fail on non-zero exit code
set -e

if [[ "${IMAGE_NAME}" && "${IMAGE_TAG}" ]]; then
  IMAGE_NAME_TAG="${IMAGE_NAME}:${IMAGE_TAG}"
elif [[ "${IMAGE_NAME_TAG}" ]]; then
  echo "Using provided image-name-tag ${IMAGE_NAME_TAG}."
else
  echo "No image was specified for promotion. You must provide one of the following inputs to the action:"
  echo "- image-name and image-tag e.g. image-name = nginx and image-tag = 1.0.0"
  echo "- image-name-tag e.g image-name-tag = nginx:1.0.0"
  exit 1
fi

IMAGE_ID="${IMAGE_NAME_TAG}"

cd "${TARGET_DIR}"
TITLE="Promote ${IMAGE_ID} to ${TARGET_DIR}"
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
IMAGE_NAME_TAG: ${IMAGE_NAME_TAG}
IMAGE_TAGS: ${IMAGE_ADDITIONAL_TAGS}"

if [[ "${PROMOTION_METHOD}" == "pull_request" ]]; then
  BRANCH="$(echo "promotion/${GITHUB_REPOSITORY:?}/${TARGET_BRANCH:?}/${TARGET_DIR:?}/${IMAGE_NAME:?}/${IMAGE_TAG:?}" | tr "/" "-")"
  git checkout -B "${BRANCH}"
  if [[ -z "${TARGET_NAME}" ]]; then
    kustomize edit set image "${IMAGE_NAME_TAG}"
  else
    kustomize edit set image "${TARGET_NAME}=${IMAGE_NAME_TAG}"
  fi

  git add .
  git commit -m "${TITLE}

  ${METADATA}
  "
  git show
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
  kustomize edit set image "${IMAGE_NAME_TAG}"
  git add .
  git commit -m "${TITLE}

  ${METADATA}
  "
  git show
  git push origin "${TARGET_BRANCH}"
  echo
  echo "Image ${IMAGE_NAME_TAG} has been promoted to ${TARGET_REPO} on branch ${TARGET_BRANCH} in directory ${TARGET_DIR}."
  echo
  DEPLOYMENT_REPO_SHA_URL="$(gh browse -c -n -R "${TARGET_REPO}")"
  echo "${DEPLOYMENT_REPO_SHA_URL}"
else
  echo "Unknown promotion method: ${PROMOTION_METHOD}. Valid methods are pull_request and push."
  exit 1
fi

# Set outputs so that downstream steps can consume this data
echo "::set-output deployment-repo-sha-short=$(git rev-parse --short HEAD)"
echo "::set-output deployment-repo-sha-url=${DEPLOYMENT_REPO_SHA_URL}"
echo "::set-output deployment-repo-sha=$(git rev-parse HEAD)"
echo "::set-output image-additional-tags=${IMAGE_ADDITIONAL_TAGS}"
echo "::set-output image-name-tag=${IMAGE_NAME_TAG}"
