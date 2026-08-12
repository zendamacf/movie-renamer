from __future__ import annotations

from pathlib import Path

import typer

from movie_renamer.cli import main
from movie_renamer.executor import ExecutionResult, ExecutionSummary


def _write(path: Path, content: bytes) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_bytes(content)


def test_confirm_each_declines_all_actions(tmp_path: Path, monkeypatch) -> None:
	monkeypatch.chdir(tmp_path)
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'
	target_dir.mkdir(parents=True, exist_ok=True)

	# Create one folder that planner will parse and plan a move for.
	movie_folder = source_dir / 'Single.White.Female.1992.1080p.BluRay.x265-RARBG'
	video_path = movie_folder / 'Single.White.Female.1992....mp4'
	_write(video_path, b'video')

	decline_calls: list[str] = []

	def fake_confirm(prompt: str, default: bool = False) -> bool:
		decline_calls.append(prompt)
		return False

	# Avoid real filesystem writes: capture incoming actions.
	captured_actions: list[tuple[str, str]] = []

	from movie_renamer import executor as executor_mod

	def fake_execute_actions(actions, *, verbose: bool = False) -> ExecutionResult:
		for a in actions:
			if a.source is not None and a.target is not None:
				captured_actions.append((a.action, str(a.target)))
		# All actions should have been converted to skips.
		return ExecutionResult(
			summary=ExecutionSummary(
				moves=0,
				skips=sum(1 for a in actions if a.action == 'skip'),
				errors=0,
			),
			executed=[],
		)

	monkeypatch.setattr(typer, 'confirm', fake_confirm)
	monkeypatch.setattr(executor_mod, 'execute_actions', fake_execute_actions)

	main(
		source_dir=source_dir,
		target_dir=target_dir,
		apply=True,
		recursive=False,
		ignore=[],
		default_lang='en',
		verbose=False,
		confirm_each=True,
		history=False,
		undo=False,
		undo_id=None,
	)

	# We should have prompted at least once.
	assert decline_calls
	# And since we declined, nothing should be executed as move.
	assert all(action != 'move' for action, _ in captured_actions)
