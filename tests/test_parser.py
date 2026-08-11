from __future__ import annotations

import pytest

from movie_renamer.naming import folder_name
from movie_renamer.parser import MovieMetadata, parse_movie_name


@pytest.mark.parametrize(
	'raw,title,year,edition',
	[
		(
			'Single.White.Female.1992.1080p.BluRay.x265-RARBG',
			'Single White Female',
			1992,
			None,
		),
		(
			'The Hand That Rocks the Cradle (1992) [1080p]',
			'The Hand That Rocks the Cradle',
			1992,
			None,
		),
		(
			"Troy Director's Cut 2004 Bluray 1080p AV1 OPUS 5.1-DECK",
			'Troy',
			2004,
			"Director's Cut",
		),
		(
			"Troy.Director's.Cut.2004....mkv",
			'Troy',
			2004,
			"Director's Cut",
		),
		(
			'Ultraviolet (2006) [1080p]',
			'Ultraviolet',
			2006,
			None,
		),
	],
)
def test_parse_movie_name(raw: str, title: str, year: int, edition: str | None) -> None:
	meta = parse_movie_name(raw)
	assert meta == MovieMetadata(title=title, year=year, edition=edition)


def test_folder_name_convention() -> None:
	meta = MovieMetadata(title='Single White Female', year=1992, edition=None)
	assert folder_name(meta) == 'Single White Female (1992)'
