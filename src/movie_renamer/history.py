from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from filelock import FileLock

HistoryAction = Literal['move']


@dataclass(frozen=True)
class ArchivedFile:
	source: Path
	archive: Path

	@staticmethod
	def from_dict(data: dict[str, str]) -> ArchivedFile:
		return ArchivedFile(
			source=Path(data['source']),
			archive=Path(data['archive']),
		)

	def to_dict(self) -> dict[str, str]:
		return {
			'source': str(self.source),
			'archive': str(self.archive),
		}


@dataclass(frozen=True)
class HistoryOperation:
	action: HistoryAction
	source: Path
	target: Path

	@staticmethod
	def from_dict(data: dict[str, str]) -> HistoryOperation:
		action = data.get('action')
		if action != 'move':
			raise ValueError(f'Invalid history action: {action!r}')
		return HistoryOperation(
			action='move',
			source=Path(data['source']),
			target=Path(data['target']),
		)

	def to_dict(self) -> dict[str, str]:
		return {
			'action': self.action,
			'source': str(self.source),
			'target': str(self.target),
		}


@dataclass(frozen=True)
class BatchRecord:
	id: str
	created_at: str
	source_dir: Path
	target_dir: Path
	operations: list[HistoryOperation]
	archived_files: list[ArchivedFile]
	removed_directories: list[Path]
	undone_at: str | None = None
	status: Literal['completed', 'partial'] = 'completed'

	@staticmethod
	def from_dict(data: dict) -> BatchRecord:
		return BatchRecord(
			id=data['id'],
			created_at=data['created_at'],
			source_dir=Path(data['source_dir']),
			target_dir=Path(data['target_dir']),
			operations=[HistoryOperation.from_dict(op) for op in data['operations']],
			archived_files=[ArchivedFile.from_dict(f) for f in data.get('archived_files', [])],
			removed_directories=[Path(p) for p in data.get('removed_directories', [])],
			undone_at=data.get('undone_at'),
			status=data.get('status', 'completed'),
		)

	def to_dict(self) -> dict:
		return {
			'id': self.id,
			'created_at': self.created_at,
			'source_dir': str(self.source_dir),
			'target_dir': str(self.target_dir),
			'operations': [op.to_dict() for op in self.operations],
			'archived_files': [f.to_dict() for f in self.archived_files],
			'removed_directories': [str(p) for p in self.removed_directories],
			'undone_at': self.undone_at,
			'status': self.status,
		}


@dataclass(frozen=True)
class UndoSummary:
	reverted: int = 0
	skips: int = 0
	errors: int = 0


def history_dir() -> Path:
	return Path.cwd()


def history_file() -> Path:
	return history_dir() / 'batches.json'


def _lock_path() -> Path:
	return history_dir() / 'batches.json.lock'


def _load_store() -> dict:
	path = history_file()
	if not path.exists():
		return {'batches': []}
	try:
		return json.loads(path.read_text(encoding='utf-8'))
	except json.JSONDecodeError as e:
		raise ValueError(f'Corrupt history file: {path}') from e


def _save_store(store: dict) -> None:
	path = history_file()
	path.parent.mkdir(parents=True, exist_ok=True)
	payload = json.dumps(store, indent=2)
	with tempfile.NamedTemporaryFile(
		mode='w',
		encoding='utf-8',
		dir=path.parent,
		delete=False,
	) as tmp:
		tmp.write(payload)
		tmp.flush()
		os.fsync(tmp.fileno())
		tmp_path = Path(tmp.name)
	tmp_path.replace(path)


def load_batches() -> list[BatchRecord]:
	store = _load_store()
	return [BatchRecord.from_dict(b) for b in store.get('batches', [])]


def archive_dir_for_batch(batch_id: str) -> Path:
	return history_dir() / '.movie-renamer' / 'archive' / batch_id


def new_batch_id() -> str:
	now = datetime.now(UTC).isoformat()
	return f'{now}-{uuid4().hex[:8]}'


def append_batch(
	target_dir: Path,
	*,
	source_dir: Path,
	operations: list[HistoryOperation],
	batch_id: str | None = None,
	archived_files: list[ArchivedFile] | None = None,
	removed_directories: list[Path] | None = None,
	status: Literal['completed', 'partial'] = 'completed',
) -> BatchRecord:
	now = datetime.now(UTC).isoformat()
	batch = BatchRecord(
		id=batch_id or new_batch_id(),
		created_at=now,
		source_dir=source_dir,
		target_dir=target_dir,
		operations=operations,
		archived_files=archived_files or [],
		removed_directories=removed_directories or [],
		status=status,
	)
	lock = FileLock(_lock_path())
	with lock:
		store = _load_store()
		store.setdefault('batches', []).append(batch.to_dict())
		_save_store(store)
	return batch


def _mark_batch_undone(batch_id: str) -> None:
	lock = FileLock(_lock_path())
	with lock:
		store = _load_store()
		now = datetime.now(UTC).isoformat()
		for batch in store.get('batches', []):
			if batch['id'] == batch_id:
				batch['undone_at'] = now
				break
		_save_store(store)


def _remove_empty_parents(path: Path, *, stop_at: Path) -> None:
	current = path.parent
	stop_at = stop_at.resolve()
	while current.resolve() != stop_at:
		try:
			current.rmdir()
		except OSError:
			break
		current = current.parent


def undo_batch(
	target_dir: Path,
	batch_id: str,
	*,
	verbose: bool = False,
) -> UndoSummary:
	batches = load_batches()
	batch = next((b for b in batches if b.id == batch_id), None)
	if batch is None:
		raise ValueError(f'Batch not found: {batch_id!r}')
	if batch.undone_at is not None:
		raise ValueError(f'Batch already undone: {batch_id!r}')

	reverted = 0
	skips = 0
	errors = 0

	for op in reversed(batch.operations):
		try:
			if not op.target.exists():
				skips += 1
				if verbose:
					print(f'SKIP: target missing: {op.target}', file=sys.stderr)
				continue

			op.source.parent.mkdir(parents=True, exist_ok=True)
			if op.source.exists():
				skips += 1
				if verbose:
					print(f'SKIP: source already exists: {op.source}', file=sys.stderr)
				continue
			shutil.move(str(op.target), str(op.source))
			_remove_empty_parents(op.target, stop_at=target_dir)
			reverted += 1
			if verbose:
				print(f'UNDO MOVE: {op.target} -> {op.source}')
		except Exception as e:  # noqa: BLE001
			errors += 1
			print(
				f'ERROR: failed to undo {op.action} {op.target}: {type(e).__name__}: {e}',
				file=sys.stderr,
			)

	if errors == 0:
		errors += _restore_archived_files(batch, verbose=verbose)

	if errors == 0:
		_mark_batch_undone(batch_id)

	return UndoSummary(reverted=reverted, skips=skips, errors=errors)


def _restore_archived_files(batch: BatchRecord, *, verbose: bool = False) -> int:
	errors = 0
	for archived in batch.archived_files:
		try:
			if not archived.archive.exists():
				if verbose:
					print(f'SKIP: archived file missing: {archived.archive}', file=sys.stderr)
				continue
			if archived.source.exists():
				if verbose:
					print(f'SKIP: source already exists: {archived.source}', file=sys.stderr)
				continue
			archived.source.parent.mkdir(parents=True, exist_ok=True)
			shutil.copy2(archived.archive, archived.source)
			archived.archive.unlink()
			if verbose:
				print(f'UNDO ARCHIVE: {archived.archive} -> {archived.source}')
		except Exception as e:  # noqa: BLE001
			errors += 1
			print(
				f'ERROR: failed to restore archived file {archived.source}: {type(e).__name__}: {e}',
				file=sys.stderr,
			)

	archive_root = archive_dir_for_batch(batch.id)
	if archive_root.exists() and errors == 0:
		try:
			shutil.rmtree(archive_root)
		except OSError:
			pass

	return errors


def latest_undoable_batch() -> BatchRecord | None:
	for batch in reversed(load_batches()):
		if batch.undone_at is None and batch.operations:
			return batch
	return None
