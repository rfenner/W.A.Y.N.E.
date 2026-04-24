#!/usr/bin/env bash

TOP="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd )"

if [[ $(docker images | grep "wayne_backend_development" | wc -l) -eq 0 ]]; then
  ${TOP}/scripts/build-dev-server.sh
fi

# make sure the test-log directory is created
mkdir -p "${TOP}/server/tests/backend/test-log"

OLLAMA_RUNNING=0
# check if ollama is running se we can run tests that need it
if curl -s http://localhost:11434/api/tags; then
  OLLAMA_RUNNING=1
fi

export COMPOSE_PROJECT_NAME="wayne_test"
export TOP="${TOP}"
export TEST_DIR="/app/tests"
if [[ -n "${1}" ]]; then
  export TEST_DIR="/app/${1}"
fi

export OLLAMA_RUNNING=${OLLAMA_RUNNING}

docker compose -f "${TOP}/docker/development/docker-compose-test.yml" up --abort-on-container-exit --exit-code-from wayne_test
docker compose -f "${TOP}/docker/development/docker-compose-test.yml"  down -v

if [[ ${OLLAMA_RUNNING} -eq 0 ]]; then
  echo "Test that need Ollama to be running were skipped."
  echo "If you want to run these tests start the Ollama server"
fi