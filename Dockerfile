FROM python:3.11-alpine3.17

ENV USER=kustomize-everything
ENV WORKDIR=/action-promote

RUN mkdir -p ${WORKDIR}

# Copies your code file from your action repository to the filesystem path `/action-promote` of the container
COPY src/* ${WORKDIR}

RUN apk add --no-cache git bash curl jq github-cli

RUN pip install --no-cache-dir -r ${WORKDIR}/requirements.txt && \
    poetry config virtualenvs.create false --local --directory=${WORKDIR} && \
    poetry install --directory=${WORKDIR}

RUN set -eux; \
  addgroup -g 1000 ${USER}; \
  adduser -u 1000 -G ${USER} -s /bin/sh -h /home/${USER} -D ${USER}

RUN chown -R ${USER}:${USER} ${WORKDIR}

USER ${USER}

WORKDIR ${WORKDIR}

# Executes `entrypoint.sh` when the Docker container starts up
ENTRYPOINT ["./entrypoint.sh"]
