from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import typer

DEFAULT_CONFIG_PATH = Path('config.json')


@dataclass(frozen=True)
class ResolvedCliConfig:
	source_dir: Path | None
	target_dir: Path | None
	ignore_globs: list[str]
	edition_phrases: list[str] | None


def resolve_cli_config(
	*,
	source_dir: Path | None,
	target_dir: Path | None,
	ignore: list[str],
	config_path: Path = DEFAULT_CONFIG_PATH,
) -> ResolvedCliConfig:
	ignore_globs: list[str] = list(ignore)
	edition_phrases: list[str] | None = None

	if config_path.exists():
		typer.echo(f'Using settings from {config_path}')
		try:
			data = json.loads(config_path.read_text(encoding='utf-8'))
		except json.JSONDecodeError as e:
			raise typer.BadParameter(f'Invalid JSON in config {config_path}: {e}') from e
		if not isinstance(data, dict):
			raise typer.BadParameter(f'Config root must be a JSON object: {config_path}')
		config_source = data.get('source_dir')
		config_target = data.get('target_dir')
		if source_dir is None and isinstance(config_source, str) and config_source.strip():
			source_dir = Path(config_source)
		if target_dir is None and isinstance(config_target, str) and config_target.strip():
			target_dir = Path(config_target)
		if isinstance(data.get('ignore_globs'), list):
			ignore_globs.extend(str(g) for g in data['ignore_globs'])

	return ResolvedCliConfig(
		source_dir=source_dir,
		target_dir=target_dir,
		ignore_globs=ignore_globs,
		edition_phrases=edition_phrases,
	)


def require_target_dir(target_dir: Path | None) -> Path:
	if target_dir is None:
		raise typer.BadParameter('Missing `target_dir` (provide --target-dir or set `target_dir` in config.json).')
	if not target_dir.exists() or not target_dir.is_dir():
		raise typer.BadParameter(f'`target_dir` must be an existing directory: {target_dir}')
	return target_dir


def require_source_dir(source_dir: Path | None) -> Path:
	if source_dir is None:
		raise typer.BadParameter('Missing `source_dir` (provide --source-dir or set `source_dir` in config.json).')
	if not source_dir.exists() or not source_dir.is_dir():
		raise typer.BadParameter(f'`source_dir` must be an existing directory: {source_dir}')
	return source_dir
