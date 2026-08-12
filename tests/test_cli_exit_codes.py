from __future__ import annotations

from pathlib import Path

import pytest
import typer

from movie_renamer.cli import main
from movie_renamer.executor import ExecutionResult, ExecutionSummary
from movie_renamer.history import HistoryOperation, load_batches


def _write(path: Path, content: bytes) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_bytes(content)


def test_apply_exits_nonzero_on_execution_errors(tmp_path: Path, monkeypatch) -> None:
	monkeypatch.chdir(tmp_path)
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'
	target_dir.mkdir(parents=True, exist_ok=True)

	movie_folder = source_dir / 'Single.White.Female.1992.1080p.BluRay.x265-RARBG'
	video_path = movie_folder / 'Single.White.Female.1992....mp4'
	_write(video_path, b'video')
	expected_target = target_dir / 'Single White Female (1992)' / 'Single White Female (1992).mp4'

	from movie_renamer import executor as executor_mod

	def fake_execute_actions(actions, *, verbose: bool = False) -> ExecutionResult:
		return ExecutionResult(
			summary=ExecutionSummary(moves=1, skips=0, errors=1),
			executed=[
				HistoryOperation(
					action='move',
					source=video_path,
					target=expected_target,
				)
			],
		)

	monkeypatch.setattr(executor_mod, 'execute_actions', fake_execute_actions)

	with pytest.raises(typer.Exit) as exc_info:
		main(
			source_dir=source_dir,
			target_dir=target_dir,
			apply=True,
			recursive=False,
			ignore=[],
			default_lang='en',
			verbose=False,
			confirm_each=False,
			history=False,
			undo=False,
			undo_id=None,
		)

	assert exc_info.value.exit_code == 1

	batches = load_batches()
	assert len(batches) == 1
	assert batches[0].status == 'partial'
