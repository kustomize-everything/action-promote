FROM python:3.11-alpine3.17

ENV USER=kustomize-everything

# Copies your code file from your action repository to the filesystem path `/` of the container
COPY src/* /action-promote

RUN apk add --no-cache git bash curl jq github-cli

RUN pip install --no-cache-dir -r /requirements.txt && \
    poetry config virtualenvs.create false --local && \
    poetry install

RUN set -eux; \
  addgroup -g 1000 ${USER}; \
  adduser -u 1000 -G ${USER} -s /bin/sh -h /home/${USER} -D ${USER}

RUN chown -R ${USER}:${USER} /action-promote

USER ${USER}

# Executes `entrypoint.sh` when the Docker container starts up
ENTRYPOINT ["/entrypoint.sh"]
