#!/usr/bin/env bash

TOP="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd )"

source "${TOP}/scripts/support/questions.sh"

python "${TOP}/cli.py"