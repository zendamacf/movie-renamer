from __future__ import annotations

from .parser import MovieMetadata


def folder_name(meta: MovieMetadata) -> str:
	return f'{meta.title} ({meta.year})'


def video_name(meta: MovieMetadata, ext: str) -> str:
	ext = ext.lstrip('.')
	base = folder_name(meta)
	if meta.edition:
		return f'{base} {{edition-{meta.edition}}}.{ext}'
	return f'{base}.{ext}'


def subtitle_name(meta: MovieMetadata, lang: str = 'en') -> str:
	return f'{folder_name(meta)}.{lang}.srt'
