#!/usr/bin/env bash

TOP="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd )"

if ! docker --version; then
  echo "You need to isntall docker first"
  exit 1
fi

if ! ollama -v; then
  echo "You need to install ollama first"
  exit 1
fi

"${TOP}/scripts/build-image.sh"

echo "Pulling ollama models"
if ! ollama pull nomic-embed-text; then
  echo "Failed to pull the nomic-embed-test model"
  exit 1
fi

if ! ollama pull qwen2.5:7b-instruct-q4_0; then
  echo "Failed to pull the qwen2.5:7b-instruct-q4_0 model"
  exit 1
fi

echo "finished installation setup"
echo "You can now run 'start-server.sh and either run cli.sh"
echo " or you can open a browser window to http:127.0.0.1/18080"


