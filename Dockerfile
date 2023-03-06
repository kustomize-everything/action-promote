FROM python:3.11-alpine3.17

# Copies your code file from your action repository to the filesystem path `/` of the container
COPY src/entrypoint.sh /entrypoint.sh

# Executes `entrypoint.sh` when the Docker container starts up
ENTRYPOINT ["/entrypoint.sh"]
