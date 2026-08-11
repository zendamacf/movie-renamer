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
	copies: int = 0
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
	Execute planned `copy`/`move` operations.

	Safety defaults:
	- never overwrite an existing target path; collision => skip-with-warning
	- errors executing a single file => skip and continue (but counted in summary)
	"""

	copies = 0
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

		source = a.source.resolve()
		target = a.target.resolve()

		if _target_exists(target):
			skips += 1
			print(
				f'{label("WARN", color="yellow", stream=sys.stderr)}: target exists, skipping: {target}',
				file=sys.stderr,
			)
			continue

		target.parent.mkdir(parents=True, exist_ok=True)

		try:
			if a.action == 'copy':
				shutil.copy2(source, target)
				copies += 1
				executed.append(HistoryOperation(action='copy', source=source, target=target))
				if verbose:
					print(f'{label("COPY", color="green", stream=sys.stderr)}: {source} -> {target}')
			elif a.action == 'move':
				shutil.move(source, target)
				moves += 1
				executed.append(HistoryOperation(action='move', source=source, target=target))
				if verbose:
					print(f'{label("MOVE", color="yellow", stream=sys.stderr)}: {source} -> {target}')
			else:
				# Defensive: unknown action kind => skip.
				skips += 1
		except FileNotFoundError:
			skips += 1
			print(
				f'{label("WARN", color="yellow", stream=sys.stderr)}: source missing, skipping: {source}',
				file=sys.stderr,
			)
		except OSError as e:
			errors += 1
			print(
				f'{label("ERROR", color="red", stream=sys.stderr)}: failed to {a.action} {source} -> {target}: '
				f'{type(e).__name__}: {e}',
				file=sys.stderr,
			)

	return ExecutionResult(
		summary=ExecutionSummary(copies=copies, moves=moves, skips=skips, errors=errors),
		executed=executed,
	)
