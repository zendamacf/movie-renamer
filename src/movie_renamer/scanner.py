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


def parse_subtitle_filename(subtitle_filename: str) -> tuple[str | None, bool, bool]:
	"""
	Best-effort language and flag extraction from filenames like:
	- `movie.en.srt` / `movie.eng.srt`
	- `movie.english.srt`
	- `English.srt`
	- `English forced.eng.srt`
	- `Forced.eng.srt`
	- `fre.srt` / `spa.srt`
	- `forced.eng.srt` / `eng.forced.srt`
	- `SDH.eng.HI.srt` / `eng.sdh.srt`
	- `16_English.srt`

	Returns `(lang, forced, sdh)`.
	"""
	suffix = subtitle_filename.lower().rsplit('.', 1)[-1]
	if suffix not in {'srt', 'vtt'}:
		return None, False, False

	def normalize_lang_token(token: str) -> str | None:
		t = token.lower()
		# Common aliases we expect in the wild (and in our fixtures).
		lang_aliases = {
			'english': 'en',
			'eng': 'en',
			'en': 'en',
			'french': 'fr',
			'fre': 'fr',
			'fr': 'fr',
			'spanish': 'es',
			'spa': 'es',
			'es': 'es',
		}
		if t in lang_aliases:
			return lang_aliases[t]
		# Allow plain 2-letter codes.
		if len(t) == 2 and t.isalpha():
			return t
		# Fall back to the first two letters (e.g. "portuguese" -> "po").
		if len(t) >= 3 and t.isalpha():
			return t[:2]
		return None

	# Support "forced" and "sdh" releases in addition to basic language tagging.
	#
	# Examples we handle:
	# - `Forced.eng.srt` / `forced.eng.srt` (forced + language token)
	# - `eng.forced.srt` (language + forced token)
	# - `English forced.eng.srt` (language name + forced + language token)
	# - `SDH.eng.HI.srt` (sdh + language token, with extra tokens after)
	# - `eng.sdh.srt` (language + sdh token)
	stem = subtitle_filename[: -len(suffix) - 1]  # strip ".srt"/".vtt"
	tokens = [t for t in re.split(r'[\.\s_-]+', stem) if t]
	tokens_l = [t.lower() for t in tokens]
	forced = 'forced' in tokens_l
	sdh = 'sdh' in tokens_l

	def _pick_lang_near_marker(marker: str) -> str | None:
		for i, t in enumerate(tokens_l):
			if t != marker:
				continue
			# `forced.<lang>.srt` / `sdh.<lang>...`
			if i + 1 < len(tokens_l):
				lang = normalize_lang_token(tokens_l[i + 1])
				if lang:
					return lang
			# `<lang>.forced.srt` / `<lang>.sdh.srt`
			if i - 1 >= 0:
				lang = normalize_lang_token(tokens_l[i - 1])
				if lang:
					return lang
		return None

	lang = _pick_lang_near_marker('forced') or _pick_lang_near_marker('sdh')
	if lang:
		return lang, forced, sdh

	# Match the last ".<lang>.<ext>" segment. Keep this after forced/sdh logic so we
	# don't incorrectly parse later tokens like "HI" as the language.
	m = re.search(r'\.(?P<lang>[a-zA-Z]{2,7})\.(srt|vtt)$', subtitle_filename, flags=re.IGNORECASE)
	if m:
		return normalize_lang_token(m.group('lang')), forced, sdh

	# Subs folder naming often uses just the language name/code.
	parts = re.split(r'[^a-zA-Z]+', stem.lower())
	for part in parts:
		lang = normalize_lang_token(part)
		if lang:
			return lang, forced, sdh
	return None, forced, sdh


def extract_subtitle_lang(subtitle_filename: str) -> str | None:
	return parse_subtitle_filename(subtitle_filename)[0]


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
		lang, forced, sdh = parse_subtitle_filename(path.name)
		return FileCandidate(
			path=path,
			kind='subtitle',
			size_bytes=path.stat().st_size,
			subtitle_lang=lang,
			subtitle_forced=forced,
			subtitle_sdh=sdh,
		)

	# We ignore everything else at the scanner layer; planner decides skips where appropriate.
	return None


def _iter_movie_folders(source_dir: Path, recursive: bool) -> Iterable[Path]:
	if recursive:
		for dirpath, dirnames, _filenames in os.walk(source_dir):
			dir_path = Path(dirpath)
			# Prune junk/sample trees so we do not descend or scan them.
			dirnames[:] = [
				d for d in dirnames if d.lower() not in SAMPLE_FOLDER_NAMES and d.lower() not in JUNK_FOLDER_NAMES
			]
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


def _collect_classified_files(folder: Path) -> list[FileCandidate]:
	files: list[FileCandidate] = []
	for entry in folder.iterdir():
		if entry.is_file():
			candidate = classify_file(entry)
			if candidate is not None:
				files.append(candidate)

		# Many releases place subtitles under a dedicated "Subs/" directory.
		# Scan its *direct* children (usually language files like "English.srt").
		if entry.is_dir() and entry.name.lower() == 'subs':
			for subs_entry in entry.iterdir():
				if not subs_entry.is_file():
					continue
				candidate = classify_file(subs_entry)
				if candidate is not None:
					files.append(candidate)
	return files


def _sidecar_belongs_to_video(sidecar: FileCandidate, video: FileCandidate) -> bool:
	video_stem = video.path.stem
	other_stem = sidecar.path.stem
	return other_stem == video_stem or other_stem.startswith(f'{video_stem}.')


def _scan_loose_files(source_dir: Path) -> list[FolderScan]:
	"""Treat video files sitting directly in source_dir as their own movies."""
	files = _collect_classified_files(source_dir)
	videos = [f for f in files if f.kind == 'video']
	sidecars = [f for f in files if f.kind != 'video']

	scans: list[FolderScan] = []
	claimed: set[Path] = set()
	for video in videos:
		related = [video]
		claimed.add(video.path)
		for sidecar in sidecars:
			if sidecar.path in claimed:
				continue
			if _sidecar_belongs_to_video(sidecar, video):
				related.append(sidecar)
				claimed.add(sidecar.path)
		scans.append(FolderScan(folder=source_dir, files=related))
	return scans


def scan_movie_folders(source_dir: Path, recursive: bool = False) -> list[FolderScan]:
	folders: list[FolderScan] = []
	for folder in _iter_movie_folders(source_dir, recursive=recursive):
		folders.append(FolderScan(folder=folder, files=_collect_classified_files(folder)))
	folders.extend(_scan_loose_files(source_dir))
	return folders
