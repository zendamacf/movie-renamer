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
		preset=None,
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
		preset=None,
		history=False,
		undo=False,
		undo_id=None,
	)

	skip_lines = [m for m in messages if m.startswith('- SKIP ')]
	assert any('Movie.Title.2020.1080p.BluRay.x265-RARBG/Nested/Movie.Title.2020.en.srt' in m for m in skip_lines)
	assert not any('something.jpg' in m for m in skip_lines)

	summary_lines = [m for m in messages if m.startswith('Summary (dry-run):')]
	assert summary_lines
	assert 'MISC=1' in summary_lines[0]

	video_rel = video_path.relative_to(source_dir).as_posix()
	sub_rel = sub_path.relative_to(source_dir).as_posix()
	assert all(video_rel not in m for m in skip_lines)
	assert all(sub_rel not in m for m in skip_lines)

	# Skip lines should not include a reason like "(promo image)".
	assert all('(' not in m for m in skip_lines)
	assert all('promo image' not in m.lower() for m in skip_lines)


def _make_movie(tmp_path: Path) -> tuple[Path, Path]:
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'
	target_dir.mkdir(parents=True, exist_ok=True)
	movie_folder = source_dir / 'Movie.Title.2020.1080p.BluRay.x265-RARBG'
	_write(movie_folder / 'Movie.Title.2020.1080p.BluRay.x265-RARBG.mkv', b'video')
	_write(movie_folder / 'Movie.Title.2020.en.srt', b'sub')
	_write(movie_folder / 'Extras' / 'readme.nfo', b'x')
	return source_dir, target_dir


def test_json_dry_run_outputs_only_json(tmp_path: Path, monkeypatch) -> None:
	import json

	from typer.testing import CliRunner

	from movie_renamer.cli import app

	monkeypatch.chdir(tmp_path)
	source_dir, target_dir = _make_movie(tmp_path)
	(tmp_path / 'config.json').write_text('{}', encoding='utf-8')

	result = CliRunner().invoke(app, ['--source-dir', str(source_dir), '--target-dir', str(target_dir), '--json'])

	assert result.exit_code == 0
	payload = json.loads(result.stdout)
	assert payload['mode'] == 'dry-run'
	assert payload['preset'] == 'plex'
	assert payload['summary']['move'] == 2
	targets = {a['target'] for a in payload['actions']}
	assert targets == {'Movie Title (2020)/Movie Title (2020).mkv', 'Movie Title (2020)/Movie Title (2020).en.srt'}
	assert payload['actions'][0]['metadata'] == {'title': 'Movie Title', 'year': 2020, 'edition': None}
	assert [s['kind'] for s in payload['skipped']] == ['other']
	assert 'executed' not in payload
	assert (source_dir / 'Movie.Title.2020.1080p.BluRay.x265-RARBG').exists()


def test_json_apply_reports_execution_and_batch(tmp_path: Path, monkeypatch) -> None:
	import json

	from typer.testing import CliRunner

	from movie_renamer.cli import app

	monkeypatch.chdir(tmp_path)
	monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'state'))
	monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'data'))
	source_dir, target_dir = _make_movie(tmp_path)

	result = CliRunner().invoke(
		app, ['--source-dir', str(source_dir), '--target-dir', str(target_dir), '--json', '--apply', '-v']
	)

	assert result.exit_code == 0, result.output
	payload = json.loads(result.stdout)
	assert payload['mode'] == 'apply'
	assert payload['executed'] == {'move': 2, 'skip': 0, 'errors': 0}
	assert payload['batch']['status'] == 'completed'
	assert (target_dir / 'Movie Title (2020)' / 'Movie Title (2020).mkv').exists()


def test_json_rejects_incompatible_flags(tmp_path: Path) -> None:
	from typer.testing import CliRunner

	from movie_renamer.cli import app

	for flag in ('--confirm', '--history', '--undo'):
		result = CliRunner().invoke(app, ['--target-dir', str(tmp_path), '--json', flag])
		assert result.exit_code != 0, flag
