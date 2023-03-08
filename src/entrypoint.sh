#!/bin/bash

# Fail on non-zero exit code
set -e

# Fail on unset variables
set -o nounset

if [[ "${DEBUG}" == "true" ]]; then
  echo "Debug mode enabled in entrypoint.sh"
  set -x

  # `$#` expands to the number of arguments and `$@` expands to the supplied `args`
  printf '%d args:' "$#"
  printf " '%s'" "$@"
  printf '\n'

  env
fi

GITHUB_REF_URL="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/tree/${GITHUB_REF}"
export GITHUB_REF_URL
echo "GITHUB_REF_URL=${GITHUB_REF_URL}" >> "${GITHUB_ENV}"
GITHUB_REPOSITORY_URL="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}"
export GITHUB_REPOSITORY_URL
echo "GITHUB_REPOSITORY_URL=${GITHUB_REPOSITORY_URL}" >> "${GITHUB_ENV}"
GITHUB_SHA_URL="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/commit/${GITHUB_SHA}"
export GITHUB_SHA_URL
echo "GITHUB_SHA_URL=${GITHUB_SHA_URL}" >> "${GITHUB_ENV}"
GITHUB_WORKFLOW_RUN_URL="$GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID"
export GITHUB_WORKFLOW_RUN_URL
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
DEPLOYMENT_DIR="${GITHUB_WORKSPACE}/${DEPLOYMENT_DIR}"
export DEPLOYMENT_DIR

# Set IMAGES to empty array if it is not set
if [[ -z "${IMAGES:-}" ]]; then
  IMAGES="[]"
fi

# If IMAGES is not an empty string or empty array, then we need to promote the images
if [[ "${IMAGES}" != "[]" ]]; then
  IMAGES_TO_UPDATE="${IMAGES}" poetry run python /promote.py > images.json
else
  echo "No images to promote"
  echo "{}" > images.json
fi

# Set CHARTS to empty array if it is not set
if [[ -z "${CHARTS:-}" ]]; then
  CHARTS="[]"
fi

# If CHARTS is not an empty string or empty array, then we need to promote the charts
if [[ "${CHARTS}" != "[]" ]]; then
  CHARTS_TO_UPDATE="${CHARTS}" poetry run python /promote.py > charts.json
else
  echo "No charts to promote"
  echo "{}" > charts.json
fi

# Save images json output to GITHUB_OUTPUT
EOF=$(dd if=/dev/urandom bs=15 count=1 status=none | base64)
# shellcheck disable=SC2129
echo "images-json<<$EOF" >> "${GITHUB_OUTPUT}"
jq -c -r '.images' images.json >> "${GITHUB_OUTPUT}"
echo "$EOF" >> "${GITHUB_OUTPUT}"
IMAGES_JSON="$(cat images.json)"
export IMAGES_JSON
jq -c -r '.images.[] | map(.name) | join(" ")' < images.json | xargs > images.txt
echo "images=$(cat images.txt)" >> "${GITHUB_OUTPUT}"
IMAGES_NAMES="$(cat images.txt)"
export IMAGES_NAMES

# shellcheck disable=SC2129
echo "charts-json<<$EOF" >> "${GITHUB_OUTPUT}"
jq -c -r '.charts' charts.json >> "${GITHUB_OUTPUT}"
echo "$EOF" >> "${GITHUB_OUTPUT}"
CHARTS_JSON="$(cat charts.json)"
export CHARTS_JSON
jq -c -r '.charts.[] | map(.name) | join(" ")' < charts.json | xargs > charts.txt
echo "charts=$(cat charts.txt)" >> "${GITHUB_OUTPUT}"
CHARTS_NAMES="$(cat charts.txt)"
export CHARTS_NAMES

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
# Because the parent workflow is the one who has run the `checkout` action,
# we need to tell configure git to consider that directory as "safe" in order
# to be able to commit changes to it without errors. Specifically, the
# "dubious ownership" error.
git config --global --add safe.directory "${DEPLOYMENT_DIR}"
pushd "${DEPLOYMENT_DIR}" || exit 1
# If there are no changes, then we don't need to do anything
if [[ -z "$(git status --porcelain)" ]]; then
  echo "No changes to commit"
# Otherwise, we need to commit the changes with the relevant metadata
# in the commit message.
else
  echo "Changes to commit"
  /commit-and-pull-request.sh
fi
popd

exit 0
