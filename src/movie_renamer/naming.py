from __future__ import annotations

import re

from .parser import MovieMetadata

PRESETS = ('plex', 'jellyfin', 'emby', 'kodi')
DEFAULT_PRESET = 'plex'


def _edition_suffix(meta: MovieMetadata, preset: str) -> str:
	"""
	Return the edition text that goes after `Title (Year)`.

	- plex: ` {edition-X}`
	- jellyfin, emby: ` - X` (their "version label" format)
	- kodi: nothing (no edition naming)
	"""
	if not meta.edition:
		return ''
	if preset == 'plex':
		return f' {{edition-{meta.edition}}}'
	if preset in ('jellyfin', 'emby'):
		return f' - {meta.edition}'
	return ''


def _id_tag(meta: MovieMetadata, preset: str) -> str:
	"""Return the TMDb id tag that media servers use to match the movie (kodi has none)."""
	if meta.tmdb_id is None:
		return ''
	if preset == 'plex':
		return f' {{tmdb-{meta.tmdb_id}}}'
	if preset in ('jellyfin', 'emby'):
		return f' [tmdbid-{meta.tmdb_id}]'
	return ''


def safe_title(title: str) -> str:
	"""
	Make a title safe to use as a path component.

	TMDb titles can contain characters that are path separators or invalid on Windows/SMB
	(`Face/Off`, `Mission: Impossible`). Colons become ` -` and separators become `-`; the
	remaining reserved characters are dropped.
	"""
	title = title.replace(':', ' -').replace('/', '-').replace('\\', '-')
	title = re.sub(r'[*?"<>|]', '', title)
	title = re.sub(r'\s+', ' ', title).strip().rstrip('.')
	return title.strip()


def folder_name(meta: MovieMetadata, preset: str = DEFAULT_PRESET) -> str:
	return f'{safe_title(meta.title)} ({meta.year}){_id_tag(meta, preset)}'


def video_name(meta: MovieMetadata, ext: str, *, preset: str = DEFAULT_PRESET) -> str:
	ext = ext.lstrip('.')
	return f'{folder_name(meta, preset)}{_edition_suffix(meta, preset)}.{ext}'


def subtitle_name(
	meta: MovieMetadata,
	lang: str = 'en',
	*,
	ext: str = 'srt',
	forced: bool = False,
	sdh: bool = False,
	preset: str = DEFAULT_PRESET,
) -> str:
	ext = ext.lstrip('.')
	flags = ''
	if forced:
		flags += '.forced'
	if sdh:
		flags += '.sdh'
	return f'{folder_name(meta, preset)}{_edition_suffix(meta, preset)}.{lang}{flags}.{ext}'
