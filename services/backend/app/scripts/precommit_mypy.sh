#!/usr/bin/env bash
# Pre-commit: run mypy from services/backend/app with paths relative to that dir.
# Pre-commit passes repo-root paths like services/backend/app/foo/bar.py — strip the prefix.
set -euo pipefail

APP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="services/backend/app/"

rel_paths=()
for arg in "$@"; do
  case "$arg" in
    "$PREFIX"*)
      rel_paths+=("${arg#"$PREFIX"}")
      ;;
    *)
      # Already relative to app root or unexpected; pass through
      rel_paths+=("$arg")
      ;;
  esac
done

cd "$APP_ROOT"
if [ "${#rel_paths[@]}" -eq 0 ]; then
  exec uv run --active mypy .
fi
exec uv run --active mypy "${rel_paths[@]}"
