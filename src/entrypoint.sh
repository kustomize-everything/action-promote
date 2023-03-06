#!/bin/bash

# Fail on non-zero exit code
set -e

# Fail on unset variables
set -o nounset

# `$#` expands to the number of arguments and `$@` expands to the supplied `args`
printf '%d args:' "$#"
printf " '%s'" "$@"
printf '\n'

env

  # steps:
  # TODO this responsibility should be moved to the caller
  #   - name: Checkout Repo
  #     uses: actions/checkout@v3
  #     with:
  #       repository: ${{ inputs.target-repo }}
  #       ref: ${{ inputs.target-branch }}
  #       ssh-key: ${{ inputs.ssh-key }}
  #       token: ${{ inputs.github-token }}
  #       path: ${{ inputs.working-directory }}

GITHUB_REF_URL="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/tree/${GITHUB_REF}"
echo "GITHUB_REF_URL=${GITHUB_REF_URL}" >> "${GITHUB_ENV}"
GITHUB_REPOSITORY_URL="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}"
echo "GITHUB_REPOSITORY_URL=${GITHUB_REPOSITORY_URL}" >> "${GITHUB_ENV}"
GITHUB_SHA_URL="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/commit/${GITHUB_SHA}"
echo "GITHUB_SHA_URL=${GITHUB_SHA_URL}" >> "${GITHUB_ENV}"
GITHUB_WORKFLOW_RUN_URL="$GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID"
echo "GITHUB_WORKFLOW_RUN_URL=${GITHUB_WORKFLOW_RUN_URL}" >> "${GITHUB_ENV}"

# Download and verify checksum on tools (kustomize)
# Expects the following environment variables to be set:
#   - KUSTOMIZE_VERSION
#   - KUSTOMIZE_CHECKSUM
#   - KUSTOMIZE_BIN_DIR
#   - KUSTOMIZE_FILENAME
/download-and-checksum.sh
PATH="${KUSTOMIZE_BIN_DIR}:${PATH}"

git config --global user.name "${GIT_COMMIT_USER}"
git config --global user.email "${GIT_COMMIT_EMAIL}"

# Update the overlays
# Expects the following environment variables to be set:
#   - DEPLOYMENT_DIR
#   - IMAGES_TO_UPDATE
export DEPLOYMENT_DIR="${GITHUB_WORKSPACE}/${DEPLOYMENT_DIR}"
poetry run python /update_images.py > images.json

# Save images json output to GITHUB_OUTPUT
EOF=$(dd if=/dev/urandom bs=15 count=1 status=none | base64)
# shellcheck disable=SC2086
echo "images-json<<$EOF" >> "${GITHUB_OUTPUT}"
cat images.json >> "${GITHUB_OUTPUT}"
echo "$EOF" >> "${GITHUB_OUTPUT}"
jq -c -r '.[] | map(.name) | join(" ")' < images.json | xargs > images.txt
echo "images=$(cat images.txt)" >> "${GITHUB_OUTPUT}"

  #   - name: Commit Changes
  #     id: commit-changes
  #     shell: bash
  #     working-directory: ${{ inputs.working-directory }}
  #     env:
  #       GITHUB_TOKEN: ${{ inputs.github-token }}
  #       IMAGES: ${{ steps.update-images.outputs.images }}
  #       IMAGES_JSON: ${{ steps.update-images.outputs.images-json }}
  #       TARGET_BRANCH: ${{ inputs.target-branch }}
  #       TARGET_REPO: ${{ inputs.target-repo }}
  #       DRY_RUN: ${{ inputs.dry-run }}
  #       PROMOTION_METHOD: ${{ inputs.promotion-method }}
  #     run: |
# If there are no changes, then we don't need to do anything
if [[ -z "$(git status --porcelain)" ]]; then
  echo "No changes to commit"
  exit 0
# Otherwise, we need to commit the changes with the relevant metadata
# in the commit message.
else
  echo "Changes to commit"
  pushd "${DEPLOYMENT_DIR}" || exit 1
  /commit-and-pull-request.sh
  popd
fi
