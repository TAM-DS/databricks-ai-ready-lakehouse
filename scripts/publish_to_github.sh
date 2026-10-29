#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
remote='https://github.com/TAM-DS/databricks-ai-ready-lakehouse.git'
if [ -e .git ]; then
  echo 'STOP: This directory already contains a Git repository. Review before publishing again.' >&2
  exit 1
fi
if [ ! -f README.md ] || [ ! -f notebooks/01_bronze_silver_gold.ipynb ]; then
  echo 'STOP: The release package is incomplete.' >&2
  exit 1
fi
if ! command -v git >/dev/null 2>&1; then
  echo 'STOP: Git is not installed; install Xcode Command Line Tools and retry.' >&2
  exit 1
fi
# A dry-run local index: Git ignores local exported data, tokens, and virtual environments.
git init -b main
git add .
if git diff --cached --name-only | grep -E '(^|/)([^/]+\.csv|\.env[^/]*|[^/]+\.(pem|key|token))$' >/dev/null; then
  echo 'STOP: Sensitive or exported data file would be committed. Review the staged list.' >&2
  git diff --cached --name-only
  exit 1
fi
printf '\nFiles staged for your public GitHub repository:\n'
git diff --cached --name-only
printf '\nPublishing to %s\n' "$remote"
git commit -m 'Release tested Databricks lakehouse and read-only quality evidence portal'
git remote add origin "$remote"
git push -u origin main
printf '\nPublished: https://github.com/TAM-DS/databricks-ai-ready-lakehouse\n'
