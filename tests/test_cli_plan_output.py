from __future__ import annotations

from pathlib import Path

import typer

from movie_renamer.cli import main


def _write(path: Path, content: bytes) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_bytes(content)


def test_planned_operations_print_target_dir_once(tmp_path: Path, monkeypatch) -> None:
	monkeypatch.chdir(tmp_path)
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'
	target_dir.mkdir(parents=True, exist_ok=True)

	movie_folder = source_dir / 'Single.White.Female.1992.1080p.BluRay.x265-RARBG'
	_write(movie_folder / 'Single.White.Female.1992....mp4', b'video')
	_write(movie_folder / 'Single.White.Female.1992.en.srt', b'sub')

	messages: list[str] = []
	monkeypatch.setattr(typer, 'echo', lambda msg: messages.append(str(msg)))

	main(
		source_dir=source_dir,
		target_dir=target_dir,
		apply=False,
		recursive=False,
		ignore=[],
		default_lang='en',
		verbose=False,
		confirm_each=False,
		history=False,
		undo=False,
		undo_id=None,
	)

	target_lines = [m for m in messages if m.startswith('Target directory:')]
	assert target_lines == [f'Target directory: {target_dir}']

	move_lines = [m for m in messages if m.startswith('- MOVE ')]
	assert len(move_lines) == 2
	assert all(str(target_dir) not in m for m in move_lines)
	assert any('-> Single White Female (1992)/Single White Female (1992).mp4' in m for m in move_lines)
	assert any('-> Single White Female (1992)/Single White Female (1992).en.srt' in m for m in move_lines)


def test_planned_operations_skip_logs_all_nested_files(tmp_path: Path, monkeypatch) -> None:
	monkeypatch.chdir(tmp_path)
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'
	target_dir.mkdir(parents=True, exist_ok=True)

	movie_folder = source_dir / 'Movie.Title.2020.1080p.BluRay.x265-RARBG'
	video_path = movie_folder / 'Movie.Title.2020.1080p.BluRay.x265-RARBG....mp4'
	sub_path = movie_folder / 'Movie.Title.2020.en.srt'
	_write(video_path, b'video')
	_write(sub_path, b'sub')

	# Nested files aren't scanned/planned for moves when --recursive is off, so they should
	# appear in the expanded "skip all files under the movie folder" logging.
	nested_dir = movie_folder / 'Nested'
	nested_sub_path = nested_dir / 'Movie.Title.2020.en.srt'
	nested_junk_path = nested_dir / 'something.jpg'
	_write(nested_sub_path, b'nested sub')
	_write(nested_junk_path, b'jpg')

	messages: list[str] = []
	monkeypatch.setattr(typer, 'echo', lambda msg: messages.append(str(msg)))

	main(
		source_dir=source_dir,
		target_dir=target_dir,
		apply=False,
		recursive=False,
		ignore=[],
		default_lang='en',
		verbose=False,
		confirm_each=False,
		history=False,
		undo=False,
		undo_id=None,
	)

	skip_lines = [m for m in messages if m.startswith('- SKIP ')]
	assert any('Movie.Title.2020.1080p.BluRay.x265-RARBG/Nested/Movie.Title.2020.en.srt' in m for m in skip_lines)
	assert any('Movie.Title.2020.1080p.BluRay.x265-RARBG/Nested/something.jpg' in m for m in skip_lines)

	video_rel = video_path.relative_to(source_dir).as_posix()
	sub_rel = sub_path.relative_to(source_dir).as_posix()
	assert all(video_rel not in m for m in skip_lines)
	assert all(sub_rel not in m for m in skip_lines)

	# Skip lines should not include a reason like "(promo image)".
	assert all('(' not in m for m in skip_lines)
	assert all('promo image' not in m.lower() for m in skip_lines)
