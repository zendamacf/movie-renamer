from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer

from movie_renamer.cli import main
from movie_renamer.cli_config import resolve_cli_config


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
		recursive=False,
		ignore=[],
		default_lang='en',
		verbose=False,
		confirm_each=False,
		preset=None,
		filename_only=True,
		history=False,
		undo=False,
		undo_id=None,
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
		recursive=False,
		ignore=[],
		default_lang='en',
		verbose=False,
		confirm_each=False,
		preset=None,
		filename_only=True,
		history=False,
		undo=False,
		undo_id=None,
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
		recursive=False,
		ignore=[],
		default_lang='en',
		verbose=False,
		confirm_each=False,
		preset=None,
		filename_only=True,
		history=False,
		undo=False,
		undo_id=None,
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
			recursive=False,
			ignore=[],
			default_lang='en',
			verbose=False,
			confirm_each=False,
			preset=None,
			filename_only=True,
			history=False,
			undo=False,
			undo_id=None,
		)


def test_preset_from_config_and_cli_override(tmp_path: Path) -> None:
	cfg = tmp_path / 'config.json'
	cfg.write_text('{"preset": "kodi"}', encoding='utf-8')
	assert resolve_cli_config(source_dir=None, target_dir=None, ignore=[], config_path=cfg).preset == 'kodi'
	resolved = resolve_cli_config(source_dir=None, target_dir=None, ignore=[], preset='Emby', config_path=cfg)
	assert resolved.preset == 'emby'


def test_unknown_preset_rejected(tmp_path: Path) -> None:
	with pytest.raises(typer.BadParameter):
		resolve_cli_config(source_dir=None, target_dir=None, ignore=[], preset='nope', config_path=tmp_path / 'x.json')
