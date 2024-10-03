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
# Sets images-updated early so that it is always set, even if promote fails
echo "images-updated=[]" >> "${GITHUB_OUTPUT}"

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

# If IMAGES is not an empty string or empty array, then we need to promote the images
if [[ "${IMAGES}" != "[]" || "${CHARTS}" != "[]" ]]; then
  IMAGES_TO_UPDATE="${IMAGES}" CHARTS_TO_UPDATE="${CHARTS}" poetry run python /promote.py > manifest.json
else
  echo "No images or charts to promote"
  echo "{}" > manifest.json
fi

MANIFEST_JSON="$(jq -c -r '.' manifest.json)"
export MANIFEST_JSON

# Save images json output to GITHUB_OUTPUT
EOF=$(dd if=/dev/urandom bs=15 count=1 status=none | base64)
# shellcheck disable=SC2129
echo "manifest-json<<$EOF" >> "${GITHUB_OUTPUT}"
echo "${MANIFEST_JSON}" >> "${GITHUB_OUTPUT}"
echo "$EOF" >> "${GITHUB_OUTPUT}"

jq -c -r 'keys | join(", ")' < manifest.json | xargs > overlays.txt
echo "overlays=$(cat overlays.txt)" >> "${GITHUB_OUTPUT}"
OVERLAY_NAMES="$(cat overlays.txt)"
export OVERLAY_NAMES

jq -c -r 'keys | join("-") | gsub("/"; "-")' < manifest.json | xargs > overlays-joined.txt
echo "overlays-joined=$(cat overlays-joined.txt)" >> "${GITHUB_OUTPUT}"
OVERLAY_NAMES_NO_SLASH="$(cat overlays-joined.txt)"
export OVERLAY_NAMES_NO_SLASH

jq -c -r '[.[] | .images | map(.name)] | unique | sort | flatten | join(", ")' < manifest.json | xargs > images.txt
echo "images=$(cat images.txt)" >> "${GITHUB_OUTPUT}"
IMAGES_NAMES="$(cat images.txt)"
export IMAGES_NAMES

# xargs ignores errors from jq, but also strips quotes. we handle errors differently for images-updated
# since we need the file to be a proper json object
jq -c -r '[.[] | .images | unique| .[] | "\(.newName):\(.newTag)"]' manifest.json  > images-updated.txt  2>/dev/null || echo "Error setting images-updated. Continuing"
echo "images-updated=$(cat images-updated.txt)" >> "${GITHUB_OUTPUT}"
IMAGES_UPDATED="$(cat images-updated.txt)"
export IMAGES_UPDATED

# shellcheck disable=SC2129
jq -c -r '[.[] | .charts | map(.name)] | unique | sort | flatten | join(", ")' < manifest.json | xargs > charts.txt
echo "charts=$(cat charts.txt)" >> "${GITHUB_OUTPUT}"
CHARTS_NAMES="$(cat charts.txt)"
export CHARTS_NAMES

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
