FROM python:3.12-alpine3.17

# Copies your code file from your action repository to the filesystem path `/` of the container
COPY src/* /

RUN apk add --no-cache git bash curl jq github-cli

RUN pip install --no-cache-dir -r /requirements.txt && \
    poetry config virtualenvs.create false --local && \
    poetry install

# Executes `entrypoint.sh` when the Docker container starts up
ENTRYPOINT ["/entrypoint.sh"]
