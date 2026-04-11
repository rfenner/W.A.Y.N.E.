#!/usr/bin/env bash

TOP="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd )"

source "${TOP}/scripts/support/questions.sh"

if ! ask_question REPO_DIR "Enter the path to the repositories to use: "; then
  echo "Failed to repositories path"
  exit 1
fi

IMAGE_NAME="wayne_backend_development"
if [[ $(docker images | grep "wayne_backend_development" | wc -l) -eq 0 ]] || \
  [[ $(docker images | grep "wayne_frontend_development" | wc -l) -eq 0 ]]; then
  ${TOP}/scripts/build-dev-server.sh
fi

export COMPOSE_PROJECT_NAME="wayne_development"
export TOP="${TOP}"
export REPOSITORIES_DIR="${REPO_DIR}"

docker compose -f "${TOP}/docker/development/docker-compose-dev.yml" --profile all up  --renew-anon-volumes