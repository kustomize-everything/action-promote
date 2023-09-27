FROM python:3.11-alpine3.17

ENV USER=kustomize-everything
ENV WORKING_DIR=/action-promote

RUN mkdir -p ${WORKING_DIR}

# Copies your code file from your action repository to the filesystem path `/action-promote` of the container
COPY src/* ${WORKING_DIR}

RUN apk add --no-cache git bash curl jq github-cli

RUN pip install --no-cache-dir -r ${WORKING_DIR}/requirements.txt && \
    poetry config virtualenvs.create false --local --directory=${WORKING_DIR} && \
    poetry install --directory=${WORKING_DIR}

RUN set -eux; \
  addgroup -g 1000 ${USER}; \
  adduser -u 1000 -G ${USER} -s /bin/sh -h /home/${USER} -D ${USER}

RUN chown -R ${USER}:${USER} ${WORKING_DIR}

USER ${USER}

# Executes `entrypoint.sh` when the Docker container starts up
ENTRYPOINT ["${WORKING_DIR}/entrypoint.sh"]
