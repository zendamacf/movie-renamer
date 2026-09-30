from __future__ import annotations

from pathlib import Path

import typer

from .cli_config import require_source_dir, require_target_dir, resolve_cli_config
from .cli_history import handle_history_commands, should_handle_history_commands
from .cli_plan import run_plan_and_apply

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
	history: bool = HISTORY_OPT,
	undo: bool = UNDO_OPT,
	undo_id: str | None = UNDO_ID_ARG,
) -> None:
	"""
	Plan movie folder renames into a Plex/Jellyfin-friendly `Title (Year)/` structure.

	- default is dry-run
	- `--apply` executes filesystem changes
	"""
	resolved = resolve_cli_config(source_dir=source_dir, target_dir=target_dir, ignore=ignore)
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
	)


if __name__ == '__main__':
	app()
