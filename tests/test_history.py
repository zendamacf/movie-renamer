from __future__ import annotations

from pathlib import Path

import pytest

from movie_renamer.executor import execute_actions
from movie_renamer.history import (
	append_batch,
	history_file,
	latest_undoable_batch,
	load_batches,
	undo_batch,
)
from movie_renamer.planner import plan_actions
from movie_renamer.scanner import scan_movie_folders


def _write(path: Path, content: bytes) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_bytes(content)


def test_history_undo_move_batch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# Ensure history file is written under the temp dir.
	# `history.py` uses `Path.cwd() / batches.json` for storage.
	monkeypatch.chdir(tmp_path)
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'
	target_dir.mkdir(parents=True, exist_ok=True)

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
	assert exec_result.summary.moves == 1

	expected = target_dir / 'Ultraviolet (2006)' / 'Ultraviolet (2006).mkv'
	assert expected.exists()
	assert not video_path.exists()

	batch = append_batch(target_dir, source_dir=source_dir, operations=exec_result.executed)
	undo_summary = undo_batch(target_dir, batch.id)
	assert undo_summary.reverted == 1
	assert not expected.exists()
	assert video_path.exists()
	assert video_path.read_bytes() == b'video-content'

	updated = load_batches()
	assert updated[0].undone_at is not None
	assert latest_undoable_batch() is None


def test_load_batches_raises_on_corrupt_history_file(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	monkeypatch.chdir(tmp_path)
	target_dir = tmp_path / 'dst'
	target_dir.mkdir(parents=True, exist_ok=True)
	history_file().parent.mkdir(parents=True, exist_ok=True)
	history_file().write_text('{not valid json', encoding='utf-8')

	with pytest.raises(ValueError, match='Corrupt history file'):
		load_batches()
