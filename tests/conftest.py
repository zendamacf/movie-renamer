from __future__ import annotations

import sys
from pathlib import Path

# Ensure `import movie_renamer` works when the package is not installed
# into the environment (e.g., editable install is unavailable).
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / 'src'
sys.path.insert(0, str(SRC_ROOT))
