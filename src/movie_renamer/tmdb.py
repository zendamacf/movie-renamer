from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from .parser import MovieMetadata, extract_edition, extract_year, strip_release_tags

SEARCH_URL = 'https://api.themoviedb.org/3/search/movie'
MAX_CANDIDATES = 5
TIMEOUT_SECONDS = 15


class TmdbError(Exception):
	"""Raised when the TMDb API cannot be reached or rejects the request."""


@dataclass(frozen=True)
class TmdbMatch:
	id: int
	title: str
	year: int


# Picks one of several candidates; returns None to fall back to the filename parse.
Chooser = Callable[[str, list[TmdbMatch]], TmdbMatch | None]


class TmdbClient:
	def __init__(self, api_key: str, *, opener: Callable[..., object] = urllib.request.urlopen) -> None:
		self._api_key = api_key
		self._opener = opener
		self._cache: dict[str, list[TmdbMatch]] = {}

	def search(self, title: str) -> list[TmdbMatch]:
		key = title.casefold()
		if key in self._cache:
			return self._cache[key]
		query = urllib.parse.urlencode({'api_key': self._api_key, 'query': title, 'include_adult': 'false'})
		try:
			with self._opener(f'{SEARCH_URL}?{query}', timeout=TIMEOUT_SECONDS) as response:  # type: ignore[operator]
				data = json.loads(response.read().decode('utf-8'))
		except urllib.error.HTTPError as e:
			if e.code == 401:
				raise TmdbError('TMDb rejected the API key (HTTP 401).') from e
			raise TmdbError(f'TMDb request failed (HTTP {e.code}).') from e
		except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
			raise TmdbError(f'TMDb request failed: {e}') from e

		matches: list[TmdbMatch] = []
		for item in data.get('results', []):
			release_date = str(item.get('release_date') or '')
			if not release_date[:4].isdigit() or not isinstance(item.get('id'), int):
				continue
			matches.append(TmdbMatch(id=item['id'], title=str(item.get('title') or ''), year=int(release_date[:4])))
		self._cache[key] = matches
		return matches


def _query_from_raw(raw: str) -> str:
	stem = Path(raw).stem if Path(raw).suffix.lower() in {'.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv'} else raw
	text = strip_release_tags(stem)
	year = extract_year(text)
	if year is not None:
		text = text.split(str(year), 1)[0]
	return ' '.join(text.split())


def _normalise(title: str) -> str:
	return ''.join(c for c in title.casefold() if c.isalnum())


def pick_match(query: str, year: int | None, results: list[TmdbMatch], chooser: Chooser | None) -> TmdbMatch | None:
	candidates = results[:MAX_CANDIDATES]
	if year is not None:
		exact = [r for r in results if r.year == year]
		if len(exact) == 1:
			return exact[0]
		if exact:
			same_title = [r for r in exact if _normalise(r.title) == _normalise(query)]
			if len(same_title) == 1:
				return same_title[0]
			candidates = exact[:MAX_CANDIDATES]
	if len(candidates) == 1:
		return candidates[0]
	if not candidates or chooser is None:
		return None
	return chooser(query, candidates)


def resolve_metadata(
	client: TmdbClient,
	raw: str,
	parsed: MovieMetadata | None,
	*,
	chooser: Chooser | None = None,
	edition_phrases: list[str] | None = None,
) -> MovieMetadata | None:
	"""
	Look the release up on TMDb and return corrected metadata.

	The edition always comes from the filename (TMDb has no concept of it). When nothing
	matches, or the user declines every candidate, the filename parse is returned as-is
	(which may be None, meaning the folder is skipped).
	"""
	query = parsed.title if parsed is not None else _query_from_raw(raw)
	if not query:
		return parsed
	year = parsed.year if parsed is not None else extract_year(raw)
	match = pick_match(query, year, client.search(query), chooser)
	if match is None:
		return parsed
	edition = parsed.edition if parsed is not None else extract_edition(raw, edition_phrases=edition_phrases)
	base = parsed or MovieMetadata(title=match.title, year=match.year, edition=edition)
	return replace(base, title=match.title, year=match.year, tmdb_id=match.id)
