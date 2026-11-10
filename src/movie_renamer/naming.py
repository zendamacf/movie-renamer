from __future__ import annotations

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


def folder_name(meta: MovieMetadata) -> str:
	return f'{meta.title} ({meta.year})'


def video_name(meta: MovieMetadata, ext: str, *, preset: str = DEFAULT_PRESET) -> str:
	ext = ext.lstrip('.')
	return f'{folder_name(meta)}{_edition_suffix(meta, preset)}.{ext}'


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
	return f'{folder_name(meta)}{_edition_suffix(meta, preset)}.{lang}{flags}.{ext}'
