#!/bin/zsh
set -e
cd -- "$(dirname -- "$0")"
if [[ ! -x .venv/bin/python ]]; then
  print -u2 'The project Python environment (.venv) is missing. Follow the one-time installation instructions in README.md.'
  exit 1
fi
exec .venv/bin/python -m survai.main --web
