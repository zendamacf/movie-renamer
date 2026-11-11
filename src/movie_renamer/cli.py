from __future__ import annotations

from pathlib import Path

import typer

from .cli_config import require_source_dir, require_target_dir, resolve_cli_config
from .cli_history import handle_history_commands, should_handle_history_commands
from .cli_plan import run_plan_and_apply
from .naming import DEFAULT_PRESET

app = typer.Typer(add_completion=False)

# Typer parameters defined at module scope to satisfy ruff B008.
SOURCE_DIR_OPT = typer.Option(
	None,
	'--source-dir',
	help='Directory containing movie folders (optional when set in config.json).',
)
TARGET_DIR_OPT = typer.Option(
	None,
	'--target-dir',
	help='Root output directory to organise into (must exist; optional when set in config.json).',
)
APPLY_OPT = typer.Option(False, '--apply', help='Execute filesystem changes.')
RECURSIVE_OPT = typer.Option(False, '--recursive', help='Descend into subfolders like "Other/".')
IGNORE_OPT = typer.Option([], '--ignore', help='Additional glob patterns to skip (repeatable).')
DEFAULT_LANG_OPT = typer.Option('en', '--default-lang', help='Subtitle language when not detected.')
VERBOSE_OPT = typer.Option(False, '-v', '--verbose', help='Show parsing details per folder.')
CONFIRM_EACH_OPT = typer.Option(False, '--confirm', help='When applying, prompt for each move before executing.')
PRESET_OPT = typer.Option(
	None,
	'--preset',
	help='Naming preset: plex (default), jellyfin, emby or kodi. Can also be set in config.json.',
)
JSON_OPT = typer.Option(
	False,
	'--json',
	help='Print the plan and summary as JSON on stdout (not usable with --confirm, --history or --undo).',
)
FILENAME_ONLY_OPT = typer.Option(
	False,
	'--filename-only',
	help='Skip the TMDb lookup and use only what can be parsed from release names (no API key needed).',
)
ID_TAG_OPT = typer.Option(
	False,
	'--id-tag',
	help='Add the TMDb id tag (e.g. {tmdb-123}) to folder and file names. Can also be set in config.json.',
)
TMDB_API_KEY_OPT = typer.Option(
	None,
	'--tmdb-api-key',
	envvar='TMDB_API_KEY',
	help='TMDb API key (v3). Can also be set via TMDB_API_KEY or `tmdb_api_key` in config.json.',
)
HISTORY_OPT = typer.Option(False, '--history', help='List rename batch history for the target directory.')
UNDO_OPT = typer.Option(
	False,
	'--undo',
	help='Undo the last rename batch, or (when followed by an id) undo that specific batch.',
)
UNDO_ID_ARG = typer.Argument(
	None,
	help='Batch id to undo (only used with --undo).',
)


@app.callback(invoke_without_command=True)
def main(
	source_dir: Path | None = SOURCE_DIR_OPT,
	target_dir: Path | None = TARGET_DIR_OPT,
	apply: bool = APPLY_OPT,
	recursive: bool = RECURSIVE_OPT,
	ignore: list[str] = IGNORE_OPT,
	default_lang: str = DEFAULT_LANG_OPT,
	verbose: bool = VERBOSE_OPT,
	confirm_each: bool = CONFIRM_EACH_OPT,
	preset: str | None = PRESET_OPT,
	json_output: bool = JSON_OPT,
	filename_only: bool = FILENAME_ONLY_OPT,
	tmdb_api_key: str | None = TMDB_API_KEY_OPT,
	id_tag: bool = ID_TAG_OPT,
	history: bool = HISTORY_OPT,
	undo: bool = UNDO_OPT,
	undo_id: str | None = UNDO_ID_ARG,
) -> None:
	"""
	Plan movie folder renames into a Plex/Jellyfin-friendly `Title (Year)/` structure.

	- default is dry-run
	- titles, years and TMDb ids come from a TMDb lookup (`--filename-only` to parse release names only)
	- `--apply` executes filesystem changes
	"""
	if json_output is True and (confirm_each or history or undo or undo_id is not None):
		raise typer.BadParameter('--json cannot be combined with --confirm, --history or --undo.')

	resolved = resolve_cli_config(
		source_dir=source_dir,
		target_dir=target_dir,
		ignore=ignore,
		preset=preset,
		json_output=json_output is True,
		filename_only=filename_only is True,
		id_tag=id_tag is True,
		tmdb_api_key=tmdb_api_key if isinstance(tmdb_api_key, str) else None,
	)
	target_dir = require_target_dir(resolved.target_dir)

	if should_handle_history_commands(history, undo, undo_id):
		handle_history_commands(
			target_dir,
			history=history,
			undo=undo,
			undo_id=undo_id,
			verbose=verbose,
		)
		return

	source_dir = require_source_dir(resolved.source_dir)
	run_plan_and_apply(
		source_dir,
		target_dir,
		apply=apply,
		recursive=recursive,
		ignore_globs=resolved.ignore_globs,
		edition_phrases=resolved.edition_phrases,
		default_lang=default_lang,
		verbose=verbose,
		confirm_each=confirm_each,
		preset=resolved.preset or DEFAULT_PRESET,
		tmdb_api_key=None if resolved.filename_only else resolved.tmdb_api_key,
		filename_only=resolved.filename_only,
		id_tag=resolved.id_tag,
		json_output=json_output is True,
	)


if __name__ == '__main__':
	app()
