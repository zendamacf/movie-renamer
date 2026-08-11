from __future__ import annotations

import os
import re
from collections.abc import Iterable
from pathlib import Path

from .models import FileCandidate, FolderScan

VIDEO_EXTS = {'.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv'}
SUBTITLE_EXTS = {'.srt', '.vtt'}

# Known promo image hosts from the plan.
PROMO_HOST_PATTERNS = [
	'www.yts.re',
	'www.yify-torrents.com',
	'www.yify',
	'www.yts',
]

JUNK_FOLDER_NAMES = {'other', 'extras'}
SAMPLE_FOLDER_NAMES = {'sample', 'samples'}


def extract_subtitle_lang(subtitle_filename: str) -> str | None:
	"""
	Best-effort language extraction from filenames like:
	- `movie.en.srt` / `movie.eng.srt`
	- `movie.english.srt`
	"""
	# Match the last ".<lang>.srt" segment. Allow up to 7 letters because of "english".
	m = re.search(r'\.(?P<lang>[a-zA-Z]{2,7})\.srt$', subtitle_filename, flags=re.IGNORECASE)
	if not m:
		return None

	lang = m.group('lang').lower()
	if lang in {'eng', 'en', 'english'}:
		return 'en'
	if len(lang) == 2:
		return lang
	# Fall back to the first two letters (e.g. "portuguese" -> "po").
	return lang[:2]


def is_promo_image(filename_lower: str) -> bool:
	return any(pat in filename_lower for pat in PROMO_HOST_PATTERNS)


def is_video_file(path: Path) -> bool:
	return path.suffix.lower() in VIDEO_EXTS


def is_subtitle_file(path: Path) -> bool:
	return path.suffix.lower() in SUBTITLE_EXTS


def classify_file(path: Path) -> FileCandidate | None:
	filename_lower = path.name.lower()

	if is_promo_image(filename_lower) and path.suffix.lower() in {'.jpg', '.jpeg', '.png'}:
		return FileCandidate(path=path, kind='promo', size_bytes=path.stat().st_size)

	if is_video_file(path):
		return FileCandidate(path=path, kind='video', size_bytes=path.stat().st_size)

	if is_subtitle_file(path):
		return FileCandidate(
			path=path,
			kind='subtitle',
			size_bytes=path.stat().st_size,
			subtitle_lang=extract_subtitle_lang(path.name),
		)

	# We ignore everything else at the scanner layer; planner decides skips where appropriate.
	return None


def _iter_movie_folders(source_dir: Path, recursive: bool) -> Iterable[Path]:
	if recursive:
		for dirpath, _dirnames, _filenames in os.walk(source_dir):
			dir_path = Path(dirpath)
			if dir_path == source_dir:
				continue
			name_lower = dir_path.name.lower()
			if name_lower in SAMPLE_FOLDER_NAMES:
				continue
			if name_lower in JUNK_FOLDER_NAMES:
				continue
			yield dir_path
	else:
		for child in source_dir.iterdir():
			if not child.is_dir():
				continue
			name_lower = child.name.lower()
			if name_lower in SAMPLE_FOLDER_NAMES:
				continue
			# Per the plan, default behavior is to skip "Other/" junk folders.
			if name_lower in JUNK_FOLDER_NAMES:
				continue
			yield child


def scan_movie_folders(source_dir: Path, recursive: bool = False) -> list[FolderScan]:
	folders: list[FolderScan] = []
	for folder in _iter_movie_folders(source_dir, recursive=recursive):
		files: list[FileCandidate] = []
		for entry in folder.iterdir():
			if not entry.is_file():
				continue
			candidate = classify_file(entry)
			if candidate is None:
				continue
			files.append(candidate)
		folders.append(FolderScan(folder=folder, files=files))
	return folders
