#!/usr/bin/env bash

TOP="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd )"

echo "Building server image"
if ! docker build --target prod -t wayne_server:latest -f \
  "${TOP}/docker/server/Dockerfile" "${TOP}"; then
  echo "Failed to build the server"
  exit 1
fi

