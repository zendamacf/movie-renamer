from __future__ import annotations

import shutil
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .models import PlannedAction


@dataclass(frozen=True)
class ExecutionSummary:
	copies: int = 0
	moves: int = 0
	skips: int = 0
	errors: int = 0


def _target_exists(path: Path) -> bool:
	# Treat both files and directories as collisions.
	return path.exists()


def execute_actions(actions: Iterable[PlannedAction], *, verbose: bool = False) -> ExecutionSummary:
	"""
	Execute planned `copy`/`move` operations.

	Safety defaults:
	- never overwrite an existing target path; collision => skip-with-warning
	- errors executing a single file => skip and continue (but counted in summary)
	"""

	copies = 0
	moves = 0
	skips = 0
	errors = 0

	for a in actions:
		if a.action == 'skip':
			skips += 1
			continue

		if a.source is None or a.target is None:
			# Should not happen; treat as a skip for robustness.
			skips += 1
			continue

		if _target_exists(a.target):
			skips += 1
			print(f'WARN: target exists, skipping: {a.target}', file=sys.stderr)
			continue

		a.target.parent.mkdir(parents=True, exist_ok=True)

		try:
			if a.action == 'copy':
				shutil.copy2(a.source, a.target)
				copies += 1
				if verbose:
					print(f'Copied: {a.source} -> {a.target}')
			elif a.action == 'move':
				shutil.move(a.source, a.target)
				moves += 1
				if verbose:
					print(f'Moved: {a.source} -> {a.target}')
			else:
				# Defensive: unknown action kind => skip.
				skips += 1
		except FileNotFoundError:
			skips += 1
			print(f'WARN: source missing, skipping: {a.source}', file=sys.stderr)
		except Exception as e:  # noqa: BLE001 - we want a best-effort summary
			errors += 1
			print(
				f'ERROR: failed to {a.action} {a.source} -> {a.target}: {type(e).__name__}: {e}',
				file=sys.stderr,
			)

	return ExecutionSummary(copies=copies, moves=moves, skips=skips, errors=errors)
