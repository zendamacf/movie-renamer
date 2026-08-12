from __future__ import annotations

from pathlib import Path

import pytest

from movie_renamer.cleanup import archive_and_remove_movie_folders, handled_movie_folders
from movie_renamer.executor import execute_actions
from movie_renamer.history import (
	append_batch,
	archive_dir_for_batch,
	load_batches,
	new_batch_id,
	undo_batch,
)
from movie_renamer.planner import plan_actions
from movie_renamer.scanner import scan_movie_folders


def _write(path: Path, content: bytes) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_bytes(content)


def test_handled_movie_folders_excludes_source_root(tmp_path: Path) -> None:
	source_dir = tmp_path / 'src'
	video_path = source_dir / 'Movie.Title.2020.1080p.WEB-DL.mkv'
	_write(video_path, b'video')

	folder_scans = scan_movie_folders(source_dir, recursive=False)
	actions = plan_actions(
		folder_scans=folder_scans,
		target_dir=tmp_path / 'dst',
		default_lang='en',
		ignore_globs=[],
	)
	exec_result = execute_actions(actions)

	handled = handled_movie_folders(source_dir, folder_scans, exec_result.executed)
	assert handled == set()


def test_archive_and_remove_movie_folders_deletes_handled_directory(tmp_path: Path) -> None:
	source_dir = tmp_path / 'src'
	movie_folder = source_dir / 'Ultraviolet (2006) [1080p]'
	promo_path = movie_folder / 'WWW.YTS.RE.jpg'
	_write(promo_path, b'promo-bytes')

	batch_id = new_batch_id()
	archived = archive_and_remove_movie_folders(
		source_dir,
		{movie_folder},
		archive_dir=archive_dir_for_batch(batch_id),
	)

	assert not movie_folder.exists()
	assert len(archived) == 1
	assert archived[0].source == promo_path.resolve()
	assert archived[0].archive.exists()
	assert archived[0].archive.read_bytes() == b'promo-bytes'


def test_history_undo_restores_skipped_contents_and_source_directory(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	monkeypatch.chdir(tmp_path)
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'
	target_dir.mkdir(parents=True, exist_ok=True)

	movie_folder = source_dir / 'Ultraviolet (2006) [1080p]'
	video_path = movie_folder / 'Ultraviolet (2006) [1080p].mkv'
	promo_path = movie_folder / 'WWW.YTS.RE.jpg'
	_write(video_path, b'video-content')
	_write(promo_path, b'promo-content')

	folder_scans = scan_movie_folders(source_dir, recursive=False)
	actions = plan_actions(
		folder_scans=folder_scans,
		target_dir=target_dir,
		default_lang='en',
		ignore_globs=[],
	)
	exec_result = execute_actions(actions)
	assert exec_result.summary.moves == 1

	batch_id = new_batch_id()
	handled = handled_movie_folders(source_dir, folder_scans, exec_result.executed)
	archived_files = archive_and_remove_movie_folders(
		source_dir,
		handled,
		archive_dir=archive_dir_for_batch(batch_id),
	)
	assert not movie_folder.exists()

	batch = append_batch(
		target_dir,
		source_dir=source_dir,
		operations=exec_result.executed,
		batch_id=batch_id,
		archived_files=archived_files,
		removed_directories=sorted(handled, key=str),
	)

	undo_summary = undo_batch(target_dir, batch.id)
	assert undo_summary.reverted == 1
	assert undo_summary.errors == 0

	expected_video = target_dir / 'Ultraviolet (2006)' / 'Ultraviolet (2006).mkv'
	assert not expected_video.exists()
	assert video_path.exists()
	assert video_path.read_bytes() == b'video-content'
	assert promo_path.exists()
	assert promo_path.read_bytes() == b'promo-content'
	assert not archive_dir_for_batch(batch.id).exists()

	updated = load_batches()
	assert updated[0].undone_at is not None
