#!/usr/bin/env bash

TOP="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd )"

source "${TOP}/scripts/support/questions.sh"


if ! ask_yes_no_question BUILD "Build the backend image?"; then
  echo "Failed to get whether to build the backend image"
  exit 1
fi

if [[ ${BUILD} -eq 1 ]]; then
  DEF_VERSION=253.32098.74
  if ! ask_question VERSION "Enter the version of pydevd_pycharm to install(default:${DEF_VERSION})?"; then
    echo "Failed to get the pydevd version"
    exit 1
  fi

  if [[ -z "${VERSION}" ]]; then
    VERSION="${DEF_VERSION}"
  fi

  echo "Building development backend server image"
  if ! docker build -t wayne_backend_development:latest \
    --build-arg PYDEVD_VER="${VERSION}" \
    -f "${TOP}/docker/development/Dockerfile-backend" \
    "${TOP}/server/backend/"; then
    echo "Failed to build the server"
    exit 1
  fi
fi

if ! ask_yes_no_question BUILD "Build the frontend image?"; then
  echo "Failed to get whether to build the frontend image"
  exit 1
fi

if [[ ${BUILD} -eq 1 ]]; then
  echo "Building development frontend server image"
  if ! docker build -t wayne_frontend_development:latest \
    --build-arg PYDEVD_VER="${VERSION}" \
    -f "${TOP}/docker/development/Dockerfile-frontend" \
    "${TOP}/server/frontend/"; then
    echo "Failed to build the server"
    exit 1
  fi
fi
