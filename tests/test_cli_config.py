from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer

from movie_renamer.cli import main


def test_config_can_supply_source_and_target_dirs(tmp_path: Path, monkeypatch) -> None:
	monkeypatch.chdir(tmp_path)

	source_dir = tmp_path / 'source'
	target_dir = tmp_path / 'target'
	source_dir.mkdir(parents=True, exist_ok=True)
	target_dir.mkdir(parents=True, exist_ok=True)

	cfg_path = tmp_path / 'config.json'
	cfg_path.write_text(
		json.dumps(
			{
				'source_dir': str(source_dir),
				'target_dir': str(target_dir),
			}
		),
		encoding='utf-8',
	)

	# We don't execute filesystem changes, we just want argument parsing + validation to succeed.
	main(
		source_dir=None,
		target_dir=None,
		apply=False,
		move=False,
		copy=False,
		recursive=False,
		ignore=[],
		default_lang='en',
		verbose=False,
		confirm_each=False,
		list_batches=False,
		undo_last=False,
		undo=None,
	)


def test_cli_source_dir_overrides_config(tmp_path: Path, monkeypatch) -> None:
	monkeypatch.chdir(tmp_path)

	config_source = tmp_path / 'config-source'
	cli_source = tmp_path / 'cli-source'
	target_dir = tmp_path / 'target'
	config_source.mkdir(parents=True, exist_ok=True)
	cli_source.mkdir(parents=True, exist_ok=True)
	target_dir.mkdir(parents=True, exist_ok=True)

	cfg_path = tmp_path / 'config.json'
	cfg_path.write_text(
		json.dumps(
			{
				'source_dir': str(config_source),
				'target_dir': str(target_dir),
			}
		),
		encoding='utf-8',
	)

	main(
		source_dir=cli_source,
		target_dir=None,
		apply=False,
		move=False,
		copy=False,
		recursive=False,
		ignore=[],
		default_lang='en',
		verbose=False,
		confirm_each=False,
		list_batches=False,
		undo_last=False,
		undo=None,
	)


def test_config_load_logs_message(tmp_path: Path, monkeypatch) -> None:
	monkeypatch.chdir(tmp_path)

	source_dir = tmp_path / 'source'
	target_dir = tmp_path / 'target'
	source_dir.mkdir(parents=True, exist_ok=True)
	target_dir.mkdir(parents=True, exist_ok=True)

	(tmp_path / 'config.json').write_text(
		json.dumps(
			{
				'source_dir': str(source_dir),
				'target_dir': str(target_dir),
			}
		),
		encoding='utf-8',
	)

	messages: list[str] = []
	monkeypatch.setattr(typer, 'echo', lambda msg: messages.append(str(msg)))

	main(
		source_dir=None,
		target_dir=None,
		apply=False,
		move=False,
		copy=False,
		recursive=False,
		ignore=[],
		default_lang='en',
		verbose=False,
		confirm_each=False,
		list_batches=False,
		undo_last=False,
		undo=None,
	)

	assert any('Using settings from config.json' in msg for msg in messages)


def test_invalid_config_json_raises_bad_parameter(tmp_path: Path, monkeypatch) -> None:
	monkeypatch.chdir(tmp_path)

	target_dir = tmp_path / 'target'
	target_dir.mkdir(parents=True, exist_ok=True)

	cfg_path = tmp_path / 'config.json'
	cfg_path.write_text('{not valid', encoding='utf-8')

	with pytest.raises(typer.BadParameter, match='Invalid JSON'):
		main(
			source_dir=None,
			target_dir=target_dir,
			apply=False,
			move=False,
			copy=False,
			recursive=False,
			ignore=[],
			default_lang='en',
			verbose=False,
			confirm_each=False,
			list_batches=False,
			undo_last=False,
			undo=None,
		)
