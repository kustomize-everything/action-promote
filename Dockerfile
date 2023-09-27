FROM python:3.11-alpine3.17

# Copies your code file from your action repository to the filesystem path `/` of the container
COPY src/* /

RUN apk add --no-cache git bash curl jq github-cli

RUN pip install --no-cache-dir -r /requirements.txt && \
    poetry config virtualenvs.create false --local && \
    poetry install

RUN set -eux; \
  addgroup -g 1000 kustomize-everything; \
  adduser -u 1000 -G kustomize-everything -s /bin/sh -h /home/yq -D kustomize-everything

USER kustomize-everything

# Executes `entrypoint.sh` when the Docker container starts up
ENTRYPOINT ["/entrypoint.sh"]
