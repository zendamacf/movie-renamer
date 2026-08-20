from __future__ import annotations

from movie_renamer.naming import folder_name, subtitle_name, video_name
from movie_renamer.parser import MovieMetadata


def test_video_name_no_edition() -> None:
	meta = MovieMetadata(title='Single White Female', year=1992, edition=None)
	assert folder_name(meta) == 'Single White Female (1992)'
	assert video_name(meta, ext='mp4') == 'Single White Female (1992).mp4'


def test_video_name_with_edition() -> None:
	meta = MovieMetadata(title='Troy', year=2004, edition="Director's Cut")
	assert video_name(meta, ext='mkv') == "Troy (2004) {edition-Director's Cut}.mkv"


def test_subtitle_name_default_lang() -> None:
	meta = MovieMetadata(title='Ultraviolet', year=2006, edition=None)
	assert subtitle_name(meta) == 'Ultraviolet (2006).en.srt'


def test_subtitle_name_with_edition() -> None:
	meta = MovieMetadata(title='Troy', year=2004, edition="Director's Cut")
	assert subtitle_name(meta) == "Troy (2004) {edition-Director's Cut}.en.srt"


def test_subtitle_name_forced_and_sdh() -> None:
	meta = MovieMetadata(title='Ultraviolet', year=2006, edition=None)
	assert subtitle_name(meta, lang='en', forced=True) == 'Ultraviolet (2006).en.forced.srt'
	assert subtitle_name(meta, lang='es', sdh=True) == 'Ultraviolet (2006).es.sdh.srt'
