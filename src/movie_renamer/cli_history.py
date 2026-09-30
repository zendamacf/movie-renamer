from __future__ import annotations

from pathlib import Path

import typer

from . import history as history_mod


def should_handle_history_commands(history: bool, undo: bool, undo_id: str | None) -> bool:
	return history or undo or undo_id is not None


def validate_history_undo_flags(history: bool, undo: bool, undo_id: str | None) -> None:
	if history and (undo or undo_id is not None):
		raise typer.BadParameter('Flags --history and --undo are mutually exclusive.')


def handle_history_commands(
	target_dir: Path,
	*,
	history: bool,
	undo: bool,
	undo_id: str | None,
	verbose: bool,
) -> None:
	validate_history_undo_flags(history, undo, undo_id)
	if history:
		list_history()
		return
	run_undo(target_dir, undo=undo, undo_id=undo_id, verbose=verbose)


def list_history() -> None:
	batches = history_mod.load_batches()
	if not batches:
		typer.echo('No rename batches recorded.')
		return
	for batch in batches:
		status = 'undone' if batch.undone_at else batch.status
		moves = sum(1 for op in batch.operations if op.action == 'move')
		typer.echo(f'{batch.id} [{status}] created={batch.created_at} move={moves} ops={len(batch.operations)}')


def run_undo(
	target_dir: Path,
	*,
	undo: bool,
	undo_id: str | None,
	verbose: bool,
) -> None:
	batch_id: str | None = None
	if undo_id is not None:
		if not undo:
			raise typer.BadParameter('Batch id provided but --undo flag was not set.')
		batch_id = undo_id
	elif undo:
		latest = history_mod.latest_undoable_batch()
		if latest is None:
			raise typer.BadParameter('No undoable rename batches found.')
		batch_id = latest.id

	assert batch_id is not None
	typer.echo(f'Undoing batch {batch_id}...')
	undo_result = history_mod.undo_batch(target_dir, batch_id, verbose=verbose)
	typer.echo(f'Summary (undo): REVERTED={undo_result.reverted} SKIP={undo_result.skips} ERRORS={undo_result.errors}')
	if undo_result.errors > 0:
		raise typer.Exit(code=1)
