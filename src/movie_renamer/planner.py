from __future__ import annotations

import fnmatch
from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from movie_renamer.models import FolderScan, PlannedAction
from movie_renamer.naming import folder_name, subtitle_name, video_name
from movie_renamer.parser import MovieMetadata, parse_movie_name

Operation = Literal['copy', 'move']


def _matches_any_glob(path: Path, globs: Iterable[str]) -> bool:
	if not globs:
		return False
	s = str(path)
	name = path.name
	for g in globs:
		if fnmatch.fnmatch(name, g) or fnmatch.fnmatch(s, g):
			return True
	return False


def _pick_primary_video(folder_scan: FolderScan) -> tuple[Path, int] | None:
	videos = [(f.path, f.size_bytes or -1) for f in folder_scan.files if f.kind == 'video']
	if not videos:
		return None
	# Pick the largest video file as the primary.
	return max(videos, key=lambda t: t[1])


def _try_parse_metadata_from_video_or_folder(folder_scan: FolderScan) -> MovieMetadata | None:
	primary = _pick_primary_video(folder_scan)
	if primary:
		video_path, _size = primary
		try:
			return parse_movie_name(video_path.name)
		except ValueError:
			return None

	# Fall back to folder name.
	try:
		return parse_movie_name(folder_scan.folder.name)
	except ValueError:
		return None


def plan_actions(
	folder_scans: list[FolderScan],
	target_dir: Path,
	operation: Operation,
	default_lang: str = 'en',
	ignore_globs: list[str] | None = None,
	edition_phrases: list[str] | None = None,
) -> list[PlannedAction]:
	ignore_globs = ignore_globs or []
	edition_phrases = edition_phrases

	actions: list[PlannedAction] = []
	used_targets: set[Path] = set()

	for folder_scan in folder_scans:
		# Parse title/year/edition based on primary video file (or folder name fallback).
		meta: MovieMetadata | None
		try:
			primary = _pick_primary_video(folder_scan)
			if primary:
				video_path, _size = primary
				meta = parse_movie_name(video_path.name, edition_phrases=edition_phrases)
			else:
				meta = parse_movie_name(folder_scan.folder.name, edition_phrases=edition_phrases)
		except ValueError:
			meta = None
		if meta is None:
			actions.append(
				PlannedAction(
					source=None,
					target=None,
					action='skip',
					reason=f'could not parse metadata for folder {folder_scan.folder.name!r}',
				)
			)
			continue

		folder_target = target_dir / folder_name(meta)

		# Plan primary artifacts first (video + subtitle).
		primary = _pick_primary_video(folder_scan)
		primary_path = primary[0] if primary else None

		for f in folder_scan.files:
			if _matches_any_glob(f.path, ignore_globs):
				actions.append(
					PlannedAction(
						source=f.path,
						target=None,
						action='skip',
						reason='ignored by glob pattern',
						metadata=meta,
					)
				)
				continue

			if f.kind == 'promo':
				actions.append(
					PlannedAction(
						source=f.path,
						target=None,
						action='skip',
						reason='promo image',
						metadata=meta,
					)
				)
				continue

			if f.kind == 'video':
				if primary_path is None or f.path != primary_path:
					actions.append(
						PlannedAction(
							source=f.path,
							target=None,
							action='skip',
							reason='non-primary video',
							metadata=meta,
						)
					)
					continue

				target = folder_target / video_name(meta, ext=f.path.suffix.lstrip('.'))
			elif f.kind == 'subtitle':
				lang = f.subtitle_lang or default_lang
				target = folder_target / subtitle_name(meta, lang=lang)
			else:
				continue

			if target in used_targets:
				actions.append(
					PlannedAction(
						source=f.path,
						target=target,
						action='skip',
						reason='target collision',
						metadata=meta,
					)
				)
				continue

			used_targets.add(target)
			actions.append(
				PlannedAction(
					source=f.path,
					target=target,
					action=operation,
					reason=None,
					metadata=meta,
				)
			)

	return actions
