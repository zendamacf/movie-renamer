#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:-${VERSION:-}}"

if [[ -z "${VERSION}" ]]; then
	echo "Usage: scripts/release.sh <version>" >&2
	echo "   or: make release VERSION=<version>" >&2
	exit 1
fi

cd "${ROOT}"

pyproject_version="$(
	"${ROOT}/.venv/bin/python" - <<'PY'
import tomllib
from pathlib import Path

with Path("pyproject.toml").open("rb") as f:
    print(tomllib.load(f)["project"]["version"])
PY
)"

init_version="$(
	"${ROOT}/.venv/bin/python" - <<'PY'
from importlib.metadata import version

print(version("movie-renamer"))
PY
)"

if [[ "${pyproject_version}" != "${VERSION}" ]]; then
	echo "pyproject.toml version is ${pyproject_version}, expected ${VERSION}" >&2
	exit 1
fi

if [[ "${init_version}" != "${VERSION}" ]]; then
	echo "movie_renamer.__version__ is ${init_version}, expected ${VERSION}" >&2
	exit 1
fi

"${ROOT}/.venv/bin/towncrier" build --yes --version "${VERSION}"

echo "Updated CHANGELOG.md for ${VERSION}."
echo "Next: commit, tag v${VERSION}, and push."
