from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import typer

from . import executor
from .history import BatchRecord
from .models import FolderScan, PlannedAction
from .naming import DEFAULT_PRESET
from .parser import MovieMetadata
from .planner import MetadataResolver, plan_actions
from .scanner import scan_movie_folders
from .terminal import label
from .tmdb import TmdbClient, TmdbError, TmdbMatch, resolve_metadata

VIDEO_EXT_HINT = 'Videos: mkv/mp4/avi/etc. Subtitles: .srt'
SILENT_SKIP_EXTS = {'.txt', '.jpg', '.exe'}


def _display_target(target: Path | None, target_dir: Path) -> str:
	if target is None:
		return ''
	try:
		return str(target.relative_to(target_dir))
	except ValueError:
		return str(target)


def _choose_match(query: str, candidates: list[TmdbMatch]) -> TmdbMatch | None:
	typer.echo(f'Multiple TMDb matches for {query!r}:')
	for i, c in enumerate(candidates, start=1):
		typer.echo(f'  {i}. {c.title} ({c.year}) [tmdb-{c.id}]')
	typer.echo('  0. None of these (use the name parsed from the filename)')
	while True:
		choice = typer.prompt('Choose a match', type=int, default=1)
		if 0 <= choice <= len(candidates):
			return candidates[choice - 1] if choice else None
		typer.echo(f'Enter a number between 0 and {len(candidates)}.')


def _build_resolver(
	api_key: str | None, *, filename_only: bool, edition_phrases: list[str] | None
) -> MetadataResolver | None:
	if filename_only:
		return None
	if not api_key:
		raise typer.BadParameter(
			'A TMDb API key is required for lookups. Provide --tmdb-api-key, set TMDB_API_KEY or `tmdb_api_key` '
			'in config.json, or pass --filename-only to use release-name parsing only.'
		)
	client = TmdbClient(api_key)

	def resolve(raw: str, parsed: MovieMetadata | None) -> MovieMetadata | None:
		return resolve_metadata(client, raw, parsed, chooser=_choose_match, edition_phrases=edition_phrases)

	return resolve


def run_plan_and_apply(
	source_dir: Path,
	target_dir: Path,
	*,
	dryrun: bool,
	recursive: bool,
	ignore_globs: list[str],
	edition_phrases: list[str] | None,
	default_lang: str,
	verbose: bool,
	preset: str = DEFAULT_PRESET,
	tmdb_api_key: str | None = None,
	filename_only: bool = False,
	id_tag: bool = False,
) -> None:
	resolver = _build_resolver(tmdb_api_key, filename_only=filename_only, edition_phrases=edition_phrases)
	folder_scans = scan_movie_folders(source_dir, recursive=recursive)
	try:
		actions = plan_actions(
			folder_scans=folder_scans,
			target_dir=target_dir,
			default_lang=default_lang,
			ignore_globs=ignore_globs,
			edition_phrases=edition_phrases,
			preset=preset,
			resolver=resolver,
			id_tag=id_tag,
		)
	except TmdbError as e:
		typer.echo(f'Error: {e}', err=True)
		raise typer.Exit(code=1) from e

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
			m = a.metadata
			typer.echo(f'  metadata: title={m.title!r} year={m.year} edition={m.edition!r} tmdb_id={m.tmdb_id}')

	typer.echo('')

	misc_count = _print_skip_logging(source_dir, folder_scans, actions)
	misc_suffix = f' MISC={misc_count}' if misc_count else ''
	if dryrun:
		typer.echo(f'Summary (dry-run): MOVE={counts["move"]} SKIP={counts["skip"]}{misc_suffix} ({VIDEO_EXT_HINT})')
		return

	typer.echo(f'Summary (planned): MOVE={counts["move"]} SKIP={counts["skip"]}{misc_suffix} ({VIDEO_EXT_HINT})')
	if counts['move'] == 0:
		typer.echo('Nothing to move.')
		return

	if not typer.confirm('Apply these changes?', default=False):
		typer.echo('Cancelled. No changes were made.')
		return

	typer.echo('Applying planned operations...')
	result = _apply_actions(source_dir, target_dir, actions, folder_scans, verbose=verbose)
	summary = result.summary
	typer.echo(f'Summary (executed): MOVE={summary.moves} SKIP={summary.skips} ERRORS={summary.errors}')
	if result.batch is not None:
		batch_status = result.batch.status
		typer.echo(f'Batch recorded ({batch_status}): {result.batch.id} ({result.operation_count} operations)')
		if batch_status == 'partial':
			typer.echo('Warning: batch had errors; undo will only revert successful operations.')
	if summary.errors > 0:
		raise typer.Exit(code=1)


@dataclass(frozen=True)
class _ApplyResult:
	summary: executor.ExecutionSummary
	batch: BatchRecord | None
	operation_count: int


def _apply_actions(
	source_dir: Path,
	target_dir: Path,
	actions: list[PlannedAction],
	folder_scans: list[FolderScan],
	*,
	verbose: bool,
) -> _ApplyResult:
	from .cleanup import archive_and_remove_movie_folders, handled_movie_folders
	from .history import append_batch, archive_dir_for_batch, new_batch_id

	exec_result = executor.execute_actions(actions, verbose=verbose)
	summary = exec_result.summary
	if not exec_result.executed:
		return _ApplyResult(summary=summary, batch=None, operation_count=0)

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
	return _ApplyResult(summary=summary, batch=batch, operation_count=len(exec_result.executed))


def _print_skip_logging(source_dir: Path, folder_scans: list[FolderScan], actions: list[PlannedAction]) -> int:
	skips, misc_count = _collect_skips(source_dir, folder_scans, actions)
	skip_label = label('SKIP', color='bright_black')
	subtitle_skip_label = label('SKIP', color='orange')
	for kind, rel_path in skips:
		tag = subtitle_skip_label if kind == 'subtitle' else skip_label
		typer.echo(f'- {tag} {rel_path}')
	return misc_count


def _collect_skips(
	source_dir: Path, folder_scans: list[FolderScan], actions: list[PlannedAction]
) -> tuple[list[tuple[str, str]], int]:
	"""Return ordered (kind, relative path) skips plus the count of silently ignored misc files."""
	moved_sources = {
		a.source.resolve() for a in actions if a.action == 'move' and a.source is not None and a.target is not None
	}
	movie_folders = {fs.folder.resolve() for fs in folder_scans}
	subtitle_exts = {'.srt', '.vtt'}
	skips: list[tuple[str, str]] = []
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

		skips.extend(('subtitle', p) for p in subtitle_skips)
		skips.extend(('other', p) for p in other_skips)

	return skips, misc_count
