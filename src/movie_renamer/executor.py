from __future__ import annotations

import shutil
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .history import HistoryOperation
from .models import PlannedAction
from .terminal import label


@dataclass(frozen=True)
class ExecutionSummary:
	moves: int = 0
	skips: int = 0
	errors: int = 0


@dataclass(frozen=True)
class ExecutionResult:
	summary: ExecutionSummary
	executed: list[HistoryOperation]


def _target_exists(path: Path) -> bool:
	# Treat both files and directories as collisions.
	return path.exists()


def execute_actions(actions: Iterable[PlannedAction], *, verbose: bool = False) -> ExecutionResult:
	"""
	Execute planned move operations.

	Safety defaults:
	- never overwrite an existing target path; collision => skip-with-warning
	- errors executing a single file => skip and continue (but counted in summary)
	"""

	moves = 0
	skips = 0
	errors = 0
	executed: list[HistoryOperation] = []

	for a in actions:
		if a.action == 'skip':
			skips += 1
			continue

		if a.source is None or a.target is None:
			# Should not happen; treat as a skip for robustness.
			skips += 1
			continue

		if a.action != 'move':
			skips += 1
			continue

		source = a.source.resolve()
		target = a.target.resolve()

		if _target_exists(target):
			skips += 1
			warn = label('WARN', color='yellow', stream=sys.stderr)
			print(f'{warn}: target exists, skipping: {target}', file=sys.stderr)
			continue

		target.parent.mkdir(parents=True, exist_ok=True)

		try:
			shutil.move(source, target)
			moves += 1
			executed.append(HistoryOperation(action='move', source=source, target=target))
			if verbose:
				tag = label('MOVE', color='blue', stream=sys.stderr)
				print(f'{tag}: {source} -> {target}')
		except FileNotFoundError:
			skips += 1
			warn = label('WARN', color='yellow', stream=sys.stderr)
			print(f'{warn}: source missing, skipping: {source}', file=sys.stderr)
		except OSError as e:
			errors += 1
			err = label('ERROR', color='red', stream=sys.stderr)
			print(
				f'{err}: failed to move {source} -> {target}: {type(e).__name__}: {e}',
				file=sys.stderr,
			)

	return ExecutionResult(
		summary=ExecutionSummary(moves=moves, skips=skips, errors=errors),
		executed=executed,
	)
