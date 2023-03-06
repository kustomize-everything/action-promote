#!/bin/bash


# Fail on non-zero exit code
set -e

# Fail on unset variables
set -o nounset

mkdir -p "${KUSTOMIZE_BIN_DIR}"
pushd "${KUSTOMIZE_BIN_DIR}" || exit 1

KUSTOMIZE_DOWNLOAD_PATH="${KUSTOMIZE_BIN_DIR}/${KUSTOMIZE_FILENAME}"

if [ -f "${KUSTOMIZE_DOWNLOAD_PATH}" ]; then
    echo "Kustomize already downloaded"
else
    curl -o "${KUSTOMIZE_FILENAME}" -L "https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2Fv${KUSTOMIZE_VERSION}/${KUSTOMIZE_FILENAME}"
fi
sha256sum "${KUSTOMIZE_FILENAME}"
echo "${KUSTOMIZE_SHA256_CHECKSUM}  ${KUSTOMIZE_FILENAME}" > kustomize.SHA256
sha256sum -c kustomize.SHA256
tar xzf "${KUSTOMIZE_FILENAME}"
chmod u+x kustomize
popd

echo "${KUSTOMIZE_BIN_DIR}" >> $GITHUB_PATH
"${KUSTOMIZE_BIN_DIR}/kustomize" version
kustomize version
