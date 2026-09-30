from __future__ import annotations

from pathlib import Path

import typer

from . import executor
from .models import FolderScan, PlannedAction
from .planner import plan_actions
from .scanner import scan_movie_folders
from .terminal import label

VIDEO_EXT_HINT = 'Videos: mkv/mp4/avi/etc. Subtitles: .srt'
SILENT_SKIP_EXTS = {'.txt', '.jpg', '.exe'}


def _display_target(target: Path | None, target_dir: Path) -> str:
	if target is None:
		return ''
	try:
		return str(target.relative_to(target_dir))
	except ValueError:
		return str(target)


def run_plan_and_apply(
	source_dir: Path,
	target_dir: Path,
	*,
	apply: bool,
	recursive: bool,
	ignore_globs: list[str],
	edition_phrases: list[str] | None,
	default_lang: str,
	verbose: bool,
	confirm_each: bool,
) -> None:
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

	misc_count = _print_skip_logging(source_dir, folder_scans, actions)
	misc_suffix = f' MISC={misc_count}' if misc_count else ''
	if not apply:
		typer.echo(f'Summary (dry-run): MOVE={counts["move"]} SKIP={counts["skip"]}{misc_suffix} ({VIDEO_EXT_HINT})')
		return

	if confirm_each:
		actions = _confirm_each_moves(actions)

	typer.echo('Applying planned operations...')
	from .cleanup import archive_and_remove_movie_folders, handled_movie_folders
	from .history import append_batch, archive_dir_for_batch, new_batch_id

	exec_result = executor.execute_actions(actions, verbose=verbose)
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


def _print_skip_logging(source_dir: Path, folder_scans: list[FolderScan], actions: list[PlannedAction]) -> int:
	moved_sources = {
		a.source.resolve() for a in actions if a.action == 'move' and a.source is not None and a.target is not None
	}
	movie_folders = {fs.folder.resolve() for fs in folder_scans}
	subtitle_exts = {'.srt', '.vtt'}
	skip_label = label('SKIP', color='bright_black')
	subtitle_skip_label = label('SKIP', color='orange')
	misc_count = 0

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
				rel_path = str(file_path)

			ext = file_path.suffix.lower()
			if ext in SILENT_SKIP_EXTS:
				misc_count += 1
				continue

			if ext in subtitle_exts:
				subtitle_skips.append(rel_path)
			else:
				other_skips.append(rel_path)

		for rel_path in subtitle_skips:
			typer.echo(f'- {subtitle_skip_label} {rel_path}')
		for rel_path in other_skips:
			typer.echo(f'- {skip_label} {rel_path}')

	return misc_count


def _confirm_each_moves(actions: list[PlannedAction]) -> list[PlannedAction]:
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
	return approved
