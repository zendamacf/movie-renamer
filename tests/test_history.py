from __future__ import annotations

from pathlib import Path

from movie_renamer.executor import execute_actions
from movie_renamer.history import append_batch, latest_undoable_batch, load_batches, undo_batch
from movie_renamer.planner import plan_actions
from movie_renamer.scanner import scan_movie_folders


def _write(path: Path, content: bytes) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_bytes(content)


def test_history_undo_copy_batch(tmp_path: Path) -> None:
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'
	target_dir.mkdir(parents=True, exist_ok=True)

	movie_folder = source_dir / 'Single.White.Female.1992.1080p.BluRay.x265-RARBG'
	video_path = movie_folder / 'Single.White.Female.1992....mp4'
	_write(video_path, b'video-content')

	actions = plan_actions(
		folder_scans=scan_movie_folders(source_dir, recursive=False),
		target_dir=target_dir,
		operation='copy',
		default_lang='en',
		ignore_globs=[],
	)
	exec_result = execute_actions(actions)
	assert exec_result.summary.copies == 1

	expected = target_dir / 'Single White Female (1992)' / 'Single White Female (1992).mp4'
	assert expected.exists()

	batch = append_batch(target_dir, source_dir=source_dir, operations=exec_result.executed)
	undo_summary = undo_batch(target_dir, batch.id)
	assert undo_summary.reverted == 1
	assert not expected.exists()
	assert video_path.exists()

	updated = load_batches(target_dir)
	assert updated[0].undone_at is not None
	assert latest_undoable_batch(target_dir) is None


def test_history_undo_move_batch(tmp_path: Path) -> None:
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'
	target_dir.mkdir(parents=True, exist_ok=True)

	movie_folder = source_dir / 'Ultraviolet (2006) [1080p]'
	video_path = movie_folder / 'Ultraviolet (2006) [1080p].mkv'
	_write(video_path, b'video-content')

	actions = plan_actions(
		folder_scans=scan_movie_folders(source_dir, recursive=False),
		target_dir=target_dir,
		operation='move',
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
