from __future__ import annotations

import json
from pathlib import Path

from movie_renamer.cli import main


def test_config_can_supply_source_and_target_dirs(tmp_path: Path) -> None:
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
		config=cfg_path,
		verbose=False,
		confirm_each=False,
		list_batches=False,
		undo_last=False,
		undo=None,
	)


def test_config_overrides_stale_cli_source_dir(tmp_path: Path) -> None:
	source_dir = tmp_path / 'source'
	target_dir = tmp_path / 'target'
	source_dir.mkdir(parents=True, exist_ok=True)
	target_dir.mkdir(parents=True, exist_ok=True)

	stale_cli_path = tmp_path / 'does-not-exist'

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

	main(
		source_dir=stale_cli_path,
		target_dir=None,
		apply=False,
		move=False,
		copy=False,
		recursive=False,
		ignore=[],
		default_lang='en',
		config=cfg_path,
		verbose=False,
		confirm_each=False,
		list_batches=False,
		undo_last=False,
		undo=None,
	)


def test_invalid_config_json_raises_bad_parameter(tmp_path: Path) -> None:
	import pytest
	import typer

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
			config=cfg_path,
			verbose=False,
			confirm_each=False,
			list_batches=False,
			undo_last=False,
			undo=None,
		)
