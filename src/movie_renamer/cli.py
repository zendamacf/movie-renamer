from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import typer

app = typer.Typer(add_completion=False)

VIDEO_EXT_HINT = 'Videos: mkv/mp4/avi/etc. Subtitles: .srt'

# Typer parameters defined at module scope to satisfy ruff B008.
SOURCE_DIR_ARG = typer.Argument(
	None, help='Directory containing movie folders (optional when provided via --config).'
)
TARGET_DIR_ARG = typer.Argument(
	None, help='Root output directory to organise into (optional when provided via --config).'
)
APPLY_OPT = typer.Option(False, '--apply', help='Execute filesystem changes.')
MOVE_OPT = typer.Option(False, '--move', help='When applying, move files instead of copying.')
COPY_OPT = typer.Option(False, '--copy', help='When applying, copy files instead of moving.')
RECURSIVE_OPT = typer.Option(False, '--recursive', help='Descend into subfolders like "Other/".')
IGNORE_OPT = typer.Option([], '--ignore', help='Additional glob patterns to skip (repeatable).')
DEFAULT_LANG_OPT = typer.Option('en', '--default-lang', help='Subtitle language when not detected.')
VERBOSE_OPT = typer.Option(False, '-v', '--verbose', help='Show parsing details per folder.')
CONFIG_OPT = typer.Option(None, '--config', help='Optional JSON config.')


@app.callback(invoke_without_command=True)
def main(
	source_dir: Path | None = SOURCE_DIR_ARG,
	target_dir: Path | None = TARGET_DIR_ARG,
	apply: bool = APPLY_OPT,
	move: bool = MOVE_OPT,
	copy: bool = COPY_OPT,
	recursive: bool = RECURSIVE_OPT,
	ignore: list[str] = IGNORE_OPT,
	default_lang: str = DEFAULT_LANG_OPT,
	config: Path | None = CONFIG_OPT,
	verbose: bool = VERBOSE_OPT,
) -> None:
	"""
	Plan movie folder renames into a Plex/Jellyfin-friendly `Title (Year)/` structure.

	- default is dry-run
	- `--apply` executes filesystem changes
	"""
	from .executor import execute_actions
	from .planner import plan_actions
	from .scanner import scan_movie_folders

	ignore_globs: list[str] = list(ignore)
	edition_phrases: list[str] | None = None
	if source_dir is not None and not source_dir.exists():
		raise typer.BadParameter(f'`source_dir` does not exist: {source_dir}')
	if target_dir is not None and target_dir.exists():
		# Keep behavior aligned with earlier `exists=False` argument: collisions are errors.
		raise typer.BadParameter(f'`target_dir` already exists: {target_dir}')

	if config is not None:
		data = json.loads(config.read_text(encoding='utf-8'))
		config_source = data.get('source_dir')
		config_target = data.get('target_dir')
		if isinstance(config_source, str) and config_source.strip():
			source_dir = Path(config_source)
		if isinstance(config_target, str) and config_target.strip():
			target_dir = Path(config_target)

	# After config overrides, validate required paths.
	if source_dir is None:
		raise typer.BadParameter(
			'Missing `source_dir` (provide it as an argument or via --config).'
		)
	if not source_dir.exists() or not source_dir.is_dir():
		raise typer.BadParameter(f'`source_dir` must be an existing directory: {source_dir}')
	if target_dir is None:
		raise typer.BadParameter(
			'Missing `target_dir` (provide it as an argument or via --config).'
		)
	if target_dir.exists():
		raise typer.BadParameter(f'`target_dir` already exists: {target_dir}')

	if move and copy:
		raise typer.BadParameter('Flags --move and --copy are mutually exclusive.')

	operation: Literal['copy', 'move'] = 'copy'
	if move:
		operation = 'move'
	elif copy:
		operation = 'copy'

	folder_scans = scan_movie_folders(source_dir, recursive=recursive)
	actions = plan_actions(
		folder_scans=folder_scans,
		target_dir=target_dir,
		operation=operation,
		default_lang=default_lang,
		ignore_globs=ignore_globs,
		edition_phrases=edition_phrases,
	)

	counts: dict[str, int] = {'copy': 0, 'move': 0, 'skip': 0}
	for a in actions:
		counts[a.action] += 1

	typer.echo(f'Planned operations (operation={operation}):')
	for a in actions:
		src_name = a.source.name if a.source else ''
		if a.action == 'skip':
			if a.source is None:
				typer.echo(f'- SKIP {a.reason or ""}'.strip())
			else:
				typer.echo(f'- SKIP {src_name} ({a.reason or "skipped"})')
			continue

		typer.echo(f'- {a.action.upper()} {src_name} -> {a.target}')
		if verbose and a.metadata is not None:
			typer.echo(
				f'  metadata: title={a.metadata.title!r} year={a.metadata.year} '
				f'edition={a.metadata.edition!r}'
			)

	typer.echo('')

	if not apply:
		typer.echo(
			f'Summary (dry-run): COPY={counts["copy"]} MOVE={counts["move"]} SKIP={counts["skip"]} '
			f'({VIDEO_EXT_HINT})'
		)
		return

	typer.echo('Applying planned operations...')
	result = execute_actions(actions, verbose=verbose)
	typer.echo(
		f'Summary (executed): COPY={result.copies} MOVE={result.moves} SKIP={result.skips} '
		f'ERRORS={result.errors}'
	)


if __name__ == '__main__':
	app()
