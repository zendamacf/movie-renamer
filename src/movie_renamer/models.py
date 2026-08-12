from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .parser import MovieMetadata

FileKind = Literal['video', 'subtitle', 'promo', 'other']
PlannedActionKind = Literal['move', 'skip']


@dataclass(frozen=True)
class FileCandidate:
	path: Path
	kind: FileKind
	size_bytes: int | None = None
	subtitle_lang: str | None = None


@dataclass(frozen=True)
class FolderScan:
	folder: Path
	files: list[FileCandidate]


@dataclass(frozen=True)
class PlannedAction:
	source: Path | None
	target: Path | None
	action: PlannedActionKind
	metadata: MovieMetadata | None = None
