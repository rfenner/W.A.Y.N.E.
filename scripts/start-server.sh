#!/usr/bin/env bash

TOP="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd )"

source "${TOP}/scripts/support/questions.sh"

if ! ask_question REPO_DIR "Enter the path to the repositories to use: "; then
  echo "Failed to repositories path"
  exit 1
fi

IMAGE_NAME="wayne_server"
if $(docker images | grep "${IMAGE_NAME}" | wc -l) -EQ 0 ]]; then
  ${TOP}/scripts/build-dev-server.sh
fi



export COMPOSE_PROJECT_NAME=WAYNE
export REPOSITORIES_DIR="${REPO_DIR}"
docker compose -f "${TOP}/docker/docker-compose.yml" up