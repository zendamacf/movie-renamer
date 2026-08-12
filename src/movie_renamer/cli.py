from __future__ import annotations

import json
from pathlib import Path

import typer

from .terminal import label

app = typer.Typer(add_completion=False)

VIDEO_EXT_HINT = 'Videos: mkv/mp4/avi/etc. Subtitles: .srt'
DEFAULT_CONFIG_PATH = Path('config.json')

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
CONFIRM_EACH_OPT = typer.Option(
	False, '--confirm', help='When applying, prompt for each move before executing.'
)
LIST_BATCHES_OPT = typer.Option(
	False, '--list-batches', help='List rename batch history for the target directory.'
)
UNDO_LAST_OPT = typer.Option(
	False, '--undo-last', help='Undo the most recent rename batch in the target directory.'
)
UNDO_OPT = typer.Option(
	None, '--undo', help='Undo a rename batch by id (see --list-batches).'
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
	list_batches: bool = LIST_BATCHES_OPT,
	undo_last: bool = UNDO_LAST_OPT,
	undo: str | None = UNDO_OPT,
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

	if DEFAULT_CONFIG_PATH.exists():
		typer.echo(f'Using settings from {DEFAULT_CONFIG_PATH}')
		try:
			data = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding='utf-8'))
		except json.JSONDecodeError as e:
			raise typer.BadParameter(
				f'Invalid JSON in config {DEFAULT_CONFIG_PATH}: {e}'
			) from e
		if not isinstance(data, dict):
			raise typer.BadParameter(
				f'Config root must be a JSON object: {DEFAULT_CONFIG_PATH}'
			)
		config_source = data.get('source_dir')
		config_target = data.get('target_dir')
		if source_dir is None and isinstance(config_source, str) and config_source.strip():
			source_dir = Path(config_source)
		if target_dir is None and isinstance(config_target, str) and config_target.strip():
			target_dir = Path(config_target)
		if isinstance(data.get('ignore_globs'), list):
			ignore_globs.extend(str(g) for g in data['ignore_globs'])

	# After config overrides, validate target_dir (required for all modes).
	if target_dir is None:
		raise typer.BadParameter(
			'Missing `target_dir` (provide --target-dir or set `target_dir` in config.json).'
		)
	if not target_dir.exists() or not target_dir.is_dir():
		raise typer.BadParameter(f'`target_dir` must be an existing directory: {target_dir}')

	if undo_last and undo is not None:
		raise typer.BadParameter('Flags --undo-last and --undo are mutually exclusive.')

	if list_batches or undo_last or undo is not None:
		from .history import latest_undoable_batch, load_batches, undo_batch

		if list_batches:
			batches = load_batches(target_dir)
			if not batches:
				typer.echo('No rename batches recorded.')
				return
			for batch in batches:
				status = 'undone' if batch.undone_at else batch.status
				moves = sum(1 for op in batch.operations if op.action == 'move')
				typer.echo(
					f'{batch.id} [{status}] created={batch.created_at} '
					f'move={moves} ops={len(batch.operations)}'
				)
			return

		batch_id = undo
		if undo_last:
			latest = latest_undoable_batch(target_dir)
			if latest is None:
				raise typer.BadParameter('No undoable rename batches found.')
			batch_id = latest.id

		assert batch_id is not None
		typer.echo(f'Undoing batch {batch_id}...')
		undo_result = undo_batch(target_dir, batch_id, verbose=verbose)
		typer.echo(
			f'Summary (undo): REVERTED={undo_result.reverted} SKIP={undo_result.skips} '
			f'ERRORS={undo_result.errors}'
		)
		if undo_result.errors > 0:
			raise typer.Exit(code=1)
		return

	if source_dir is None:
		raise typer.BadParameter(
			'Missing `source_dir` (provide --source-dir or set `source_dir` in config.json).'
		)
	if not source_dir.exists() or not source_dir.is_dir():
		raise typer.BadParameter(f'`source_dir` must be an existing directory: {source_dir}')

	folder_scans = scan_movie_folders(source_dir, recursive=recursive)
	actions = plan_actions(
		folder_scans=folder_scans,
		target_dir=target_dir,
		default_lang=default_lang,
		ignore_globs=ignore_globs,
		edition_phrases=edition_phrases,
	)

	counts: dict[str, int] = {'move': 0, 'skip': 0}
	for a in actions:
		counts[a.action] = counts.get(a.action, 0) + 1

	typer.echo('Planned operations (move):')
	for a in actions:
		src_name = a.source.name if a.source else ''
		if a.action == 'skip':
			if a.source is None:
				skip_label = label('SKIP', color='bright_black')
				reason = (a.reason or '').strip()
				typer.echo(f'- {skip_label} {reason}'.strip())
			else:
				reason = a.reason or 'skipped'
				skip_label = label('SKIP', color='bright_black')
				if reason == 'target collision':
					skip_label = label('SKIP', color='red')
				typer.echo(f'- {skip_label} {src_name} ({reason})')
			continue

		if a.action == 'move':
			action_label = label('MOVE', color='yellow')
		else:
			action_label = label(a.action.upper(), color='white')
		typer.echo(f'- {action_label} {src_name} -> {a.target}')
		if verbose and a.metadata is not None:
			typer.echo(
				f'  metadata: title={a.metadata.title!r} year={a.metadata.year} '
				f'edition={a.metadata.edition!r}'
			)

	typer.echo('')

	if not apply:
		typer.echo(
			f'Summary (dry-run): MOVE={counts["move"]} SKIP={counts["skip"]} '
			f'({VIDEO_EXT_HINT})'
		)
		return

	if confirm_each:
		from .models import PlannedAction

		# Convert unapproved move actions into skips before execution.
		approved: list[PlannedAction] = []
		for a in actions:
			if a.action == 'move' and a.source is not None and a.target is not None:
				prompt = f'Execute {a.action.upper()}: {a.source.name} -> {a.target}?'
				if not typer.confirm(prompt, default=False):
					approved.append(
						PlannedAction(
							source=a.source,
							target=a.target,
							action='skip',
							reason='user declined',
							metadata=a.metadata,
						)
					)
					continue
			approved.append(a)
		actions = approved

	typer.echo('Applying planned operations...')
	from .history import append_batch

	exec_result = execute_actions(actions, verbose=verbose)
	summary = exec_result.summary
	typer.echo(
		f'Summary (executed): MOVE={summary.moves} SKIP={summary.skips} '
		f'ERRORS={summary.errors}'
	)
	exit_code = 0
	if summary.errors > 0:
		exit_code = 1

	if exec_result.executed:
		batch_status = 'completed' if summary.errors == 0 else 'partial'
		batch = append_batch(
			target_dir,
			source_dir=source_dir,
			operations=exec_result.executed,
			status=batch_status,
		)
		typer.echo(
			f'Batch recorded ({batch_status}): {batch.id} ({len(exec_result.executed)} operations)'
		)
		if batch_status == 'partial':
			typer.echo('Warning: batch had errors; undo will only revert successful operations.')

	if exit_code:
		raise typer.Exit(code=exit_code)


if __name__ == '__main__':
	app()
