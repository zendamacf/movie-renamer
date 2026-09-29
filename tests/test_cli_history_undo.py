from __future__ import annotations

from pathlib import Path

import pytest
import typer

from movie_renamer.cli import main
from movie_renamer.executor import execute_actions
from movie_renamer.history import (
	HistoryOperation,
	UndoSummary,
	append_batch,
	history_file,
	load_batches,
)
from movie_renamer.planner import plan_actions
from movie_renamer.scanner import scan_movie_folders


def _write(path: Path, content: bytes) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_bytes(content)


def _target_dir_only(tmp_path: Path) -> Path:
	target_dir = tmp_path / 'dst'
	target_dir.mkdir(parents=True, exist_ok=True)
	return target_dir


def test_cli_history_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.chdir(tmp_path)
	target_dir = _target_dir_only(tmp_path)

	messages: list[str] = []
	monkeypatch.setattr(typer, 'echo', lambda msg: messages.append(str(msg)))

	main(
		source_dir=None,
		target_dir=target_dir,
		apply=False,
		recursive=False,
		ignore=[],
		default_lang='en',
		verbose=False,
		confirm_each=False,
		history=True,
		undo=False,
		undo_id=None,
	)

	assert messages == ['No rename batches recorded.']


def test_cli_history_lists_batches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.chdir(tmp_path)
	source_dir = tmp_path / 'src'
	target_dir = _target_dir_only(tmp_path)

	batch = append_batch(
		target_dir,
		source_dir=source_dir,
		operations=[],
		batch_id='batch-abc',
	)

	messages: list[str] = []
	monkeypatch.setattr(typer, 'echo', lambda msg: messages.append(str(msg)))

	main(
		source_dir=None,
		target_dir=target_dir,
		apply=False,
		recursive=False,
		ignore=[],
		default_lang='en',
		verbose=False,
		confirm_each=False,
		history=True,
		undo=False,
		undo_id=None,
	)

	assert len(messages) == 1
	assert messages[0].startswith(f'{batch.id} [completed]')
	assert 'move=0' in messages[0]
	assert history_file().exists()


def test_cli_history_and_undo_mutually_exclusive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.chdir(tmp_path)
	target_dir = _target_dir_only(tmp_path)

	with pytest.raises(typer.BadParameter, match='mutually exclusive'):
		main(
			source_dir=None,
			target_dir=target_dir,
			apply=False,
			recursive=False,
			ignore=[],
			default_lang='en',
			verbose=False,
			confirm_each=False,
			history=True,
			undo=True,
			undo_id=None,
		)


def test_cli_undo_requires_flag_when_id_given(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.chdir(tmp_path)
	target_dir = _target_dir_only(tmp_path)

	with pytest.raises(typer.BadParameter, match='--undo flag was not set'):
		main(
			source_dir=None,
			target_dir=target_dir,
			apply=False,
			recursive=False,
			ignore=[],
			default_lang='en',
			verbose=False,
			confirm_each=False,
			history=False,
			undo=False,
			undo_id='batch-abc',
		)


def test_cli_undo_without_batches_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.chdir(tmp_path)
	target_dir = _target_dir_only(tmp_path)

	with pytest.raises(typer.BadParameter, match='No undoable rename batches found'):
		main(
			source_dir=None,
			target_dir=target_dir,
			apply=False,
			recursive=False,
			ignore=[],
			default_lang='en',
			verbose=False,
			confirm_each=False,
			history=False,
			undo=True,
			undo_id=None,
		)


def test_cli_undo_last_batch_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.chdir(tmp_path)
	source_dir = tmp_path / 'src'
	target_dir = _target_dir_only(tmp_path)

	movie_folder = source_dir / 'Ultraviolet (2006) [1080p]'
	video_path = movie_folder / 'Ultraviolet (2006) [1080p].mkv'
	_write(video_path, b'video-content')

	actions = plan_actions(
		folder_scans=scan_movie_folders(source_dir, recursive=False),
		target_dir=target_dir,
		default_lang='en',
		ignore_globs=[],
	)
	exec_result = execute_actions(actions)
	expected = target_dir / 'Ultraviolet (2006)' / 'Ultraviolet (2006).mkv'
	assert expected.exists()

	batch = append_batch(target_dir, source_dir=source_dir, operations=exec_result.executed)

	messages: list[str] = []
	monkeypatch.setattr(typer, 'echo', lambda msg: messages.append(str(msg)))

	main(
		source_dir=None,
		target_dir=target_dir,
		apply=False,
		recursive=False,
		ignore=[],
		default_lang='en',
		verbose=False,
		confirm_each=False,
		history=False,
		undo=True,
		undo_id=None,
	)

	assert any(msg.startswith(f'Undoing batch {batch.id}') for msg in messages)
	assert any('Summary (undo): REVERTED=1' in msg for msg in messages)
	assert not expected.exists()
	assert video_path.exists()
	assert load_batches()[0].undone_at is not None


def test_cli_undo_specific_batch_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.chdir(tmp_path)
	source_dir = tmp_path / 'src'
	target_dir = _target_dir_only(tmp_path)

	movie_folder = source_dir / 'Movie.Title.2020.1080p'
	video_path = movie_folder / 'Movie.Title.2020.mkv'
	_write(video_path, b'video')

	actions = plan_actions(
		folder_scans=scan_movie_folders(source_dir, recursive=False),
		target_dir=target_dir,
		default_lang='en',
		ignore_globs=[],
	)
	exec_result = execute_actions(actions)
	batch = append_batch(
		target_dir,
		source_dir=source_dir,
		operations=exec_result.executed,
		batch_id='explicit-batch-id',
	)

	messages: list[str] = []
	monkeypatch.setattr(typer, 'echo', lambda msg: messages.append(str(msg)))

	main(
		source_dir=None,
		target_dir=target_dir,
		apply=False,
		recursive=False,
		ignore=[],
		default_lang='en',
		verbose=False,
		confirm_each=False,
		history=False,
		undo=True,
		undo_id='explicit-batch-id',
	)

	assert any('Undoing batch explicit-batch-id' in msg for msg in messages)
	assert load_batches()[0].id == batch.id
	assert load_batches()[0].undone_at is not None


def test_cli_undo_unknown_batch_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.chdir(tmp_path)
	target_dir = _target_dir_only(tmp_path)
	append_batch(target_dir, source_dir=tmp_path / 'src', operations=[], batch_id='real-batch')

	with pytest.raises(ValueError, match='Batch not found'):
		main(
			source_dir=None,
			target_dir=target_dir,
			apply=False,
			recursive=False,
			ignore=[],
			default_lang='en',
			verbose=False,
			confirm_each=False,
			history=False,
			undo=True,
			undo_id='missing-batch',
		)


def test_cli_undo_exits_nonzero_on_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.chdir(tmp_path)
	target_dir = _target_dir_only(tmp_path)
	src = tmp_path / 'src' / 'movie.mkv'
	dst = target_dir / 'Movie (2020)' / 'Movie (2020).mkv'
	append_batch(
		target_dir,
		source_dir=tmp_path / 'src',
		operations=[HistoryOperation(action='move', source=src, target=dst)],
		batch_id='batch-1',
	)

	def fake_undo_batch(target_dir: Path, batch_id: str, *, verbose: bool = False) -> UndoSummary:
		return UndoSummary(reverted=0, skips=0, errors=2)

	monkeypatch.setattr('movie_renamer.history.undo_batch', fake_undo_batch)

	with pytest.raises(typer.Exit) as exc_info:
		main(
			source_dir=None,
			target_dir=target_dir,
			apply=False,
			recursive=False,
			ignore=[],
			default_lang='en',
			verbose=False,
			confirm_each=False,
			history=False,
			undo=True,
			undo_id=None,
		)

	assert exc_info.value.exit_code == 1
