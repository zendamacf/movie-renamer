from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from movie_renamer.cli import app


def _make_movie(tmp_path: Path) -> tuple[Path, Path]:
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'
	target_dir.mkdir()
	folder = source_dir / 'Movie.Title.2020.1080p.BluRay.x265-RARBG'
	folder.mkdir(parents=True)
	(folder / 'Movie.Title.2020.1080p.BluRay.x265-RARBG.mkv').write_bytes(b'video')
	return source_dir, target_dir


def _invoke(tmp_path: Path, monkeypatch, *extra: str, input: str | None = None):
	monkeypatch.chdir(tmp_path)
	monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'state'))
	monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'data'))
	source_dir, target_dir = _make_movie(tmp_path)
	args = ['--source-dir', str(source_dir), '--target-dir', str(target_dir), '--filename-only', *extra]
	return CliRunner().invoke(app, args, input=input), source_dir, target_dir


def test_yes_applies_plan(tmp_path: Path, monkeypatch) -> None:
	result, source_dir, target_dir = _invoke(tmp_path, monkeypatch, input='y\n')

	assert result.exit_code == 0, result.output
	assert 'Apply these changes? [y/N]' in result.output
	assert 'Summary (executed): MOVE=1' in result.output
	assert (target_dir / 'Movie Title (2020)' / 'Movie Title (2020).mkv').exists()


def test_no_leaves_files_untouched(tmp_path: Path, monkeypatch) -> None:
	result, source_dir, target_dir = _invoke(tmp_path, monkeypatch, input='n\n')

	assert result.exit_code == 0, result.output
	assert 'Cancelled. No changes were made.' in result.output
	assert (source_dir / 'Movie.Title.2020.1080p.BluRay.x265-RARBG').exists()
	assert not (target_dir / 'Movie Title (2020)').exists()


def test_empty_input_defaults_to_no(tmp_path: Path, monkeypatch) -> None:
	result, source_dir, target_dir = _invoke(tmp_path, monkeypatch, input='\n')

	assert 'Cancelled.' in result.output
	assert not (target_dir / 'Movie Title (2020)').exists()


def test_dryrun_does_not_prompt_or_move(tmp_path: Path, monkeypatch) -> None:
	result, source_dir, target_dir = _invoke(tmp_path, monkeypatch, '--dryrun')

	assert result.exit_code == 0, result.output
	assert 'Apply these changes?' not in result.output
	assert 'Summary (dry-run): MOVE=1' in result.output
	assert not (target_dir / 'Movie Title (2020)').exists()


def test_nothing_to_move_skips_prompt(tmp_path: Path, monkeypatch) -> None:
	monkeypatch.chdir(tmp_path)
	source_dir = tmp_path / 'src'
	source_dir.mkdir()
	target_dir = tmp_path / 'dst'
	target_dir.mkdir()
	args = ['--source-dir', str(source_dir), '--target-dir', str(target_dir), '--filename-only']
	result = CliRunner().invoke(app, args)

	assert result.exit_code == 0, result.output
	assert 'Nothing to move.' in result.output
	assert 'Apply these changes?' not in result.output
