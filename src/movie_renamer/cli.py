from __future__ import annotations

import json
from pathlib import Path

import typer

from .terminal import label

app = typer.Typer(add_completion=False)

VIDEO_EXT_HINT = 'Videos: mkv/mp4/avi/etc. Subtitles: .srt'
SILENT_SKIP_EXTS = {'.txt', '.jpg', '.exe'}
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


def _display_target(target: Path | None, target_dir: Path) -> str:
	if target is None:
		return ''
	try:
		return str(target.relative_to(target_dir))
	except ValueError:
		return str(target)


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
			raise typer.BadParameter(f'Invalid JSON in config {DEFAULT_CONFIG_PATH}: {e}') from e
		if not isinstance(data, dict):
			raise typer.BadParameter(f'Config root must be a JSON object: {DEFAULT_CONFIG_PATH}')
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
		raise typer.BadParameter('Missing `target_dir` (provide --target-dir or set `target_dir` in config.json).')
	if not target_dir.exists() or not target_dir.is_dir():
		raise typer.BadParameter(f'`target_dir` must be an existing directory: {target_dir}')

	if history and (undo or undo_id is not None):
		raise typer.BadParameter('Flags --history and --undo are mutually exclusive.')

	if history or undo or undo_id is not None:
		from .history import latest_undoable_batch, load_batches, undo_batch

		if history:
			batches = load_batches()
			if not batches:
				typer.echo('No rename batches recorded.')
				return
			for batch in batches:
				status = 'undone' if batch.undone_at else batch.status
				moves = sum(1 for op in batch.operations if op.action == 'move')
				typer.echo(f'{batch.id} [{status}] created={batch.created_at} move={moves} ops={len(batch.operations)}')
			return

		batch_id: str | None = None
		if undo_id is not None:
			if not undo:
				raise typer.BadParameter('Batch id provided but --undo flag was not set.')
			batch_id = undo_id
		elif undo:
			latest = latest_undoable_batch()
			if latest is None:
				raise typer.BadParameter('No undoable rename batches found.')
			batch_id = latest.id

		assert batch_id is not None
		typer.echo(f'Undoing batch {batch_id}...')
		undo_result = undo_batch(target_dir, batch_id, verbose=verbose)
		typer.echo(
			f'Summary (undo): REVERTED={undo_result.reverted} SKIP={undo_result.skips} ERRORS={undo_result.errors}'
		)
		if undo_result.errors > 0:
			raise typer.Exit(code=1)
		return

	if source_dir is None:
		raise typer.BadParameter('Missing `source_dir` (provide --source-dir or set `source_dir` in config.json).')
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
	typer.echo(f'Target directory: {target_dir}')
	for a in actions:
		src_name = a.source.name if a.source else ''
		if a.action == 'skip':
			continue

		if a.action == 'move':
			action_label = label('MOVE', color='blue')
		else:
			action_label = label(a.action.upper(), color='white')
		dest = _display_target(a.target, target_dir)
		typer.echo(f'- {action_label} {src_name} -> {dest}')
		if verbose and a.metadata is not None:
			typer.echo(f'  metadata: title={a.metadata.title!r} year={a.metadata.year} edition={a.metadata.edition!r}')

	typer.echo('')

	# Extra skip logging:
	# Print every file found under each movie folder (including nested directories) that
	# was not part of the planned MOVE sources. This helps spot when files are missed.
	moved_sources = {
		a.source.resolve() for a in actions if a.action == 'move' and a.source is not None and a.target is not None
	}
	movie_folders = {fs.folder.resolve() for fs in folder_scans}
	subtitle_exts = {'.srt', '.vtt'}
	skip_label = label('SKIP', color='bright_black')
	subtitle_skip_label = label('SKIP', color='orange')
	misc_count = 0
	# Keep output stable/deterministic for tests and diffability.
	for movie_folder in sorted(movie_folders, key=lambda p: str(p)):
		subtitle_skips: list[str] = []
		other_skips: list[str] = []

		for file_path in sorted(movie_folder.rglob('*'), key=lambda p: str(p)):
			if not file_path.is_file():
				continue
			if file_path.resolve() in moved_sources:
				continue
			try:
				rel_path = file_path.relative_to(source_dir).as_posix()
			except ValueError:
				# Should not happen, but keep output usable if paths are oddly mounted.
				rel_path = str(file_path)

			ext = file_path.suffix.lower()
			if ext in SILENT_SKIP_EXTS:
				misc_count += 1
				continue

			if ext in subtitle_exts:
				subtitle_skips.append(rel_path)
			else:
				other_skips.append(rel_path)

		# Print subtitle skips in orange first, then the remaining skips.
		# This keeps the overall output grouped: MOVE (above) -> subtitle SKIP (this block) -> other SKIP (below).
		for rel_path in subtitle_skips:
			typer.echo(f'- {subtitle_skip_label} {rel_path}')
		for rel_path in other_skips:
			typer.echo(f'- {skip_label} {rel_path}')

	misc_suffix = f' MISC={misc_count}' if misc_count else ''
	if not apply:
		typer.echo(f'Summary (dry-run): MOVE={counts["move"]} SKIP={counts["skip"]}{misc_suffix} ({VIDEO_EXT_HINT})')
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
							metadata=a.metadata,
						)
					)
					continue
			approved.append(a)
		actions = approved

	typer.echo('Applying planned operations...')
	from .cleanup import archive_and_remove_movie_folders, handled_movie_folders
	from .history import append_batch, archive_dir_for_batch, new_batch_id

	exec_result = execute_actions(actions, verbose=verbose)
	summary = exec_result.summary
	typer.echo(f'Summary (executed): MOVE={summary.moves} SKIP={summary.skips} ERRORS={summary.errors}')
	exit_code = 0
	if summary.errors > 0:
		exit_code = 1

	if exec_result.executed:
		batch_status = 'completed' if summary.errors == 0 else 'partial'
		batch_id = new_batch_id()
		handled_folders = handled_movie_folders(source_dir, folder_scans, exec_result.executed)
		archived_files = archive_and_remove_movie_folders(
			source_dir,
			handled_folders,
			archive_dir=archive_dir_for_batch(batch_id),
		)
		batch = append_batch(
			target_dir,
			source_dir=source_dir,
			operations=exec_result.executed,
			batch_id=batch_id,
			archived_files=archived_files,
			removed_directories=sorted(handled_folders, key=str),
			status=batch_status,
		)
		typer.echo(f'Batch recorded ({batch_status}): {batch.id} ({len(exec_result.executed)} operations)')
		if batch_status == 'partial':
			typer.echo('Warning: batch had errors; undo will only revert successful operations.')

	if exit_code:
		raise typer.Exit(code=exit_code)


if __name__ == '__main__':
	app()
