#!/usr/bin/env bash

TOP="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd )"

if [[ $(docker images | grep "wayne_backend_development" | wc -l) -eq 0 ]]; then
  ${TOP}/scripts/build-dev-server.sh
fi

# make sure the test-log directory is created
mkdir -p "${TOP}/server/tests/backend/test-log"

export COMPOSE_PROJECT_NAME="wayne_test"
export TOP="${TOP}"
export TEST_DIR="/app/tests"
export TEST_TO_RUN=${1}

docker compose -f "${TOP}/docker/development/docker-compose-test.yml" up --abort-on-container-exit --exit-code-from wayne_test
docker compose -f "${TOP}/docker/development/docker-compose-test.yml"  down -v
