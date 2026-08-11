from __future__ import annotations

from pathlib import Path

from movie_renamer.executor import execute_actions
from movie_renamer.planner import plan_actions
from movie_renamer.scanner import scan_movie_folders


def _write(path: Path, content: bytes) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_bytes(content)


def test_executor_copy_executes_video_and_subtitle(tmp_path: Path) -> None:
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'

	movie_folder = source_dir / 'Ultraviolet (2006) [1080p]'
	video_path = movie_folder / 'Ultraviolet (2006) [1080p].mkv'
	sub_path = movie_folder / 'Ultraviolet (2006) [1080p].eng.srt'
	promo_path = movie_folder / 'WWW.YTS.RE.jpg'

	_write(video_path, b'video-bytes' * 10)
	_write(sub_path, b'subtitle-bytes')
	_write(promo_path, b'promo-bytes')

	actions = plan_actions(
		folder_scans=scan_movie_folders(source_dir, recursive=False),
		target_dir=target_dir,
		operation='copy',
		default_lang='en',
		ignore_globs=[],
	)

	summary = execute_actions(actions)
	assert summary.copies == 2
	assert summary.moves == 0

	expected_dir = target_dir / 'Ultraviolet (2006)'
	assert (expected_dir / 'Ultraviolet (2006).mkv').exists()
	assert (expected_dir / 'Ultraviolet (2006).en.srt').exists()
	assert not (expected_dir / 'WWW.YTS.RE.jpg').exists()


def test_executor_skips_non_primary_video(tmp_path: Path) -> None:
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'

	folder = source_dir / "Troy.Director's.Cut.2004"
	video_primary = folder / "Troy.Director's.Cut.2004.2160p.WEB-DL.mkv"
	video_secondary = folder / "Troy.Director's.Cut.2004.1080p.WEB-DL.mkv"

	# Planner picks largest file as primary.
	_write(video_primary, b'primary' * 2000)
	_write(video_secondary, b'secondary' * 10)

	actions = plan_actions(
		folder_scans=scan_movie_folders(source_dir, recursive=False),
		target_dir=target_dir,
		operation='copy',
		default_lang='en',
		ignore_globs=[],
	)

	summary = execute_actions(actions)
	assert summary.copies == 1

	expected_video = target_dir / 'Troy (2004)' / "Troy (2004) {edition-Director's Cut}.mkv"
	assert expected_video.exists()
	assert not (expected_video.parent / 'Troy (2004).mkv').exists()


def test_executor_collision_skips_without_overwriting(tmp_path: Path) -> None:
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'

	folder = source_dir / 'Single.White.Female.1992.1080p.BluRay.x265-RARBG'
	video_path = folder / 'Single.White.Female.1992....mp4'

	_write(video_path, b'NEW-CONTENT')

	expected_target = target_dir / 'Single White Female (1992)' / 'Single White Female (1992).mp4'
	expected_target.parent.mkdir(parents=True, exist_ok=True)
	# Pre-existing file simulates collision from a previous run.
	_write(expected_target, b'OLD-CONTENT')

	actions = plan_actions(
		folder_scans=scan_movie_folders(source_dir, recursive=False),
		target_dir=target_dir,
		operation='copy',
		default_lang='en',
		ignore_globs=[],
	)

	summary = execute_actions(actions)
	assert summary.copies == 0
	assert summary.skips >= 1

	assert expected_target.read_bytes() == b'OLD-CONTENT'
	# Copy mode should not delete sources.
	assert video_path.exists()
