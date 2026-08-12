from __future__ import annotations

import shutil
from pathlib import Path

from .history import ArchivedFile, HistoryOperation
from .models import FolderScan


def handled_movie_folders(
	source_dir: Path,
	folder_scans: list[FolderScan],
	executed: list[HistoryOperation],
) -> set[Path]:
	"""Movie folders that had at least one successful move."""
	source_dir = source_dir.resolve()
	handled: set[Path] = set()
	for scan in folder_scans:
		folder = scan.folder.resolve()
		if folder == source_dir:
			continue
		if any(op.source.resolve().is_relative_to(folder) for op in executed):
			handled.add(folder)
	return handled


def archive_and_remove_movie_folders(
	source_dir: Path,
	folders: set[Path],
	*,
	archive_dir: Path,
) -> list[ArchivedFile]:
	"""
	Archive any remaining files under handled movie folders, then delete the folders.
	"""
	source_dir = source_dir.resolve()
	archive_dir.mkdir(parents=True, exist_ok=True)
	archived: list[ArchivedFile] = []

	for folder in sorted(folders, key=str):
		if not folder.exists():
			continue
		for file_path in sorted(folder.rglob('*'), key=str):
			if not file_path.is_file():
				continue
			rel = file_path.relative_to(source_dir)
			dest = archive_dir / rel
			dest.parent.mkdir(parents=True, exist_ok=True)
			shutil.copy2(file_path, dest)
			archived.append(ArchivedFile(source=file_path.resolve(), archive=dest.resolve()))
		shutil.rmtree(folder)

	return archived
