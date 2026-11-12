from __future__ import annotations

import io
import json
import re
import urllib.error
from pathlib import Path

import pytest
from typer.testing import CliRunner

from movie_renamer.cli import app
from movie_renamer.naming import folder_name, video_name
from movie_renamer.parser import MovieMetadata, parse_movie_name
from movie_renamer.tmdb import TmdbClient, TmdbError, TmdbMatch, resolve_metadata


class _Response(io.BytesIO):
	def __enter__(self):
		return self

	def __exit__(self, *exc):
		return False


def _client(results: list[dict], calls: list[str] | None = None) -> TmdbClient:
	def opener(url: str, timeout: int):
		if calls is not None:
			calls.append(url)
		return _Response(json.dumps({'results': results}).encode())

	return TmdbClient('key', opener=opener)


def _result(id_: int, title: str, date: str | None) -> dict:
	return {'id': id_, 'title': title, 'release_date': date}


def test_search_parses_results_skips_undated_and_caches() -> None:
	calls: list[str] = []
	client = _client([_result(1, 'Troy', '2004-05-14'), _result(2, 'Troy', ''), _result(3, 'Troy', None)], calls)
	assert client.search('Troy') == [TmdbMatch(1, 'Troy', 2004)]
	client.search('troy')
	assert len(calls) == 1
	assert 'api_key=key' in calls[0]


@pytest.mark.parametrize(
	'error',
	[
		urllib.error.HTTPError('u', 401, 'Unauthorized', {}, None),  # type: ignore[arg-type]
		urllib.error.HTTPError('u', 500, 'Boom', {}, None),  # type: ignore[arg-type]
		urllib.error.URLError('offline'),
	],
)
def test_search_wraps_errors(error: Exception) -> None:
	def opener(url: str, timeout: int):
		raise error

	with pytest.raises(TmdbError):
		TmdbClient('key', opener=opener).search('Troy')


def test_resolve_fixes_title_keeps_edition_and_adds_id() -> None:
	parsed = parse_movie_name('Troy.2004.Directors.Cut.1080p.mkv')
	client = _client([_result(652, 'Troy', '2004-05-14'), _result(9, 'Troy', '1999-01-01')])
	meta = resolve_metadata(client, 'x', parsed)
	assert meta is not None
	assert (meta.title, meta.year, meta.tmdb_id) == ('Troy', 2004, 652)


def test_resolve_finds_year_when_name_has_none() -> None:
	client = _client([_result(603, 'The Matrix', '1999-03-30')])
	meta = resolve_metadata(client, 'The.Matrix.1080p.BluRay.x264-GRP.mkv', None)
	assert meta == MovieMetadata(title='The Matrix', year=1999, edition=None, tmdb_id=603)


def test_resolve_asks_chooser_when_ambiguous() -> None:
	client = _client([_result(1, 'Dune: Part One', '2021-10-01'), _result(2, 'Dune: Part Two', '2021-12-01')])
	parsed = MovieMetadata(title='Dune', year=2021, edition=None)
	seen: list[list[TmdbMatch]] = []

	def chooser(query: str, candidates: list[TmdbMatch]) -> TmdbMatch | None:
		seen.append(candidates)
		return candidates[1]

	meta = resolve_metadata(client, 'x', parsed, chooser=chooser)
	assert meta is not None and meta.tmdb_id == 2
	assert len(seen[0]) == 2


def test_resolve_prefers_exact_title_among_same_year() -> None:
	client = _client([_result(1, 'Dune: Part Two', '2021-12-01'), _result(2, 'Dune', '2021-10-01')])
	meta = resolve_metadata(client, 'x', MovieMetadata(title='Dune', year=2021, edition=None))
	assert meta is not None and meta.tmdb_id == 2


def test_resolve_falls_back_when_no_match_declined_or_no_chooser() -> None:
	parsed = MovieMetadata(title='Dune', year=2021, edition=None)
	assert resolve_metadata(_client([]), 'x', parsed) is parsed
	ambiguous = [_result(1, 'A', '2021-01-01'), _result(2, 'B', '2021-01-01')]
	assert resolve_metadata(_client(ambiguous), 'x', parsed) is parsed
	assert resolve_metadata(_client(ambiguous), 'x', parsed, chooser=lambda q, c: None) is parsed
	assert resolve_metadata(_client([]), 'Nothing.mkv', None) is None


def test_id_tags_by_preset() -> None:
	meta = MovieMetadata(title='Troy', year=2004, edition="Director's Cut", tmdb_id=652)
	assert folder_name(meta) == 'Troy (2004) {tmdb-652}'
	assert video_name(meta, 'mkv') == "Troy (2004) {tmdb-652} {edition-Director's Cut}.mkv"
	assert video_name(meta, 'mkv', preset='jellyfin') == "Troy (2004) [tmdbid-652] - Director's Cut.mkv"
	assert folder_name(meta, 'kodi') == 'Troy (2004)'


def _movie(tmp_path: Path) -> tuple[Path, Path]:
	source = tmp_path / 'src' / 'Troy.2004.1080p'
	source.mkdir(parents=True)
	(source / 'Troy.2004.1080p.mkv').write_bytes(b'v')
	target = tmp_path / 'dst'
	target.mkdir()
	return tmp_path / 'src', target


def test_cli_requires_api_key_unless_filename_only(tmp_path: Path, monkeypatch) -> None:
	monkeypatch.chdir(tmp_path)
	monkeypatch.delenv('TMDB_API_KEY', raising=False)
	src, dst = _movie(tmp_path)
	args = ['--source-dir', str(src), '--target-dir', str(dst)]

	result = CliRunner().invoke(app, args)
	assert result.exit_code != 0
	assert 'TMDb API key' in result.output

	assert CliRunner().invoke(app, [*args, '--filename-only', '--dryrun']).exit_code == 0


def test_cli_lookup_uses_tmdb_and_tags_ids(tmp_path: Path, monkeypatch) -> None:
	monkeypatch.chdir(tmp_path)
	src, dst = _movie(tmp_path)
	monkeypatch.setattr('movie_renamer.cli_plan.TmdbClient', lambda key: _client([_result(652, 'Troy', '2004-05-14')]))

	result = CliRunner().invoke(
		app, ['--source-dir', str(src), '--target-dir', str(dst), '--tmdb-api-key', 'k', '--id-tag', '--dryrun', '-v']
	)
	assert result.exit_code == 0, result.output
	assert '-> Troy (2004) {tmdb-652}/Troy (2004) {tmdb-652}.mkv' in result.output
	assert 'tmdb_id=652' in result.output


def test_cli_reports_tmdb_failure(tmp_path: Path, monkeypatch) -> None:
	monkeypatch.chdir(tmp_path)
	src, dst = _movie(tmp_path)

	def opener(url: str, timeout: int):
		raise urllib.error.URLError('offline')

	monkeypatch.setattr('movie_renamer.cli_plan.TmdbClient', lambda key: TmdbClient(key, opener=opener))
	result = CliRunner().invoke(app, ['--source-dir', str(src), '--target-dir', str(dst), '--tmdb-api-key', 'k'])
	assert result.exit_code == 1
	assert 'TMDb request failed' in result.output


def test_cli_prompts_on_ambiguous_match(tmp_path: Path, monkeypatch) -> None:
	monkeypatch.chdir(tmp_path)
	src, dst = _movie(tmp_path)
	results = [_result(1, 'Troy: A', '2004-01-01'), _result(2, 'Troy: B', '2004-02-01')]
	monkeypatch.setattr('movie_renamer.cli_plan.TmdbClient', lambda key: _client(results))

	result = CliRunner().invoke(
		app,
		['--source-dir', str(src), '--target-dir', str(dst), '--tmdb-api-key', 'k', '--id-tag', '--dryrun'],
		input='2\n',
	)
	assert result.exit_code == 0, result.output
	assert 'Multiple TMDb matches' in result.output
	assert '{tmdb-2}' in result.output


def test_config_supplies_key_and_filename_only(tmp_path: Path, monkeypatch) -> None:
	monkeypatch.chdir(tmp_path)
	src, dst = _movie(tmp_path)
	(tmp_path / 'config.json').write_text('{"filename_only": true}', encoding='utf-8')
	assert CliRunner().invoke(app, ['--source-dir', str(src), '--target-dir', str(dst), '--dryrun']).exit_code == 0

	(tmp_path / 'config.json').write_text('{"tmdb_api_key": "abc", "id_tag": true}', encoding='utf-8')
	monkeypatch.setattr('movie_renamer.cli_plan.TmdbClient', lambda key: _client([_result(5, 'Troy', '2004-01-01')]))
	result = CliRunner().invoke(app, ['--source-dir', str(src), '--target-dir', str(dst), '--dryrun'])
	assert result.exit_code == 0 and '{tmdb-5}' in result.output


def test_id_tag_is_opt_in_and_id_stays_in_metadata(tmp_path: Path, monkeypatch) -> None:
	monkeypatch.chdir(tmp_path)
	src, dst = _movie(tmp_path)
	monkeypatch.setattr('movie_renamer.cli_plan.TmdbClient', lambda key: _client([_result(652, 'Troy', '2004-05-14')]))
	args = ['--source-dir', str(src), '--target-dir', str(dst), '--tmdb-api-key', 'k', '--dryrun', '-v']

	def target(extra: list[str]) -> tuple[str, int]:
		result = CliRunner().invoke(app, [*args, *extra])
		assert result.exit_code == 0, result.output
		dest = re.search(r'-> (.+)$', result.output, re.MULTILINE)
		tmdb_id = re.search(r'tmdb_id=(\d+)', result.output)
		assert dest and tmdb_id
		return dest.group(1), int(tmdb_id.group(1))

	assert target([]) == ('Troy (2004)/Troy (2004).mkv', 652)
	assert target(['--id-tag']) == ('Troy (2004) {tmdb-652}/Troy (2004) {tmdb-652}.mkv', 652)
	(tmp_path / 'config.json').write_text('{"id_tag": true}', encoding='utf-8')
	assert target([])[0] == 'Troy (2004) {tmdb-652}/Troy (2004) {tmdb-652}.mkv'


@pytest.mark.parametrize(
	('title', 'expected'),
	[
		('Face/Off', 'Face-Off'),
		('Mission: Impossible', 'Mission - Impossible'),
		('What?', 'What'),
		('A "Quoted" <Title> | Pipe*', 'A Quoted Title Pipe'),
		('Back\\Slash', 'Back-Slash'),
		('Ellipsis...', 'Ellipsis'),
	],
)
def test_titles_are_made_path_safe(title: str, expected: str) -> None:
	meta = MovieMetadata(title=title, year=2000, edition=None)
	assert folder_name(meta) == f'{expected} (2000)'
	assert '/' not in video_name(meta, 'mkv')


def test_prompt_reasks_on_out_of_range_choice(tmp_path: Path, monkeypatch) -> None:
	monkeypatch.chdir(tmp_path)
	src, dst = _movie(tmp_path)
	results = [_result(1, 'Troy: A', '2004-01-01'), _result(2, 'Troy: B', '2004-02-01')]
	monkeypatch.setattr('movie_renamer.cli_plan.TmdbClient', lambda key: _client(results))
	result = CliRunner().invoke(
		app,
		['--source-dir', str(src), '--target-dir', str(dst), '--tmdb-api-key', 'k', '--id-tag', '--dryrun'],
		input='9\n2\n',
	)
	assert result.exit_code == 0, result.output
	assert 'between 0 and 2' in result.output
	assert '{tmdb-2}' in result.output


def test_release_named_subtitle_still_detected_after_year_correction(tmp_path: Path) -> None:
	from movie_renamer.models import FileCandidate, FolderScan
	from movie_renamer.planner import plan_actions

	folder = tmp_path / 'Troy.2003.Extended'
	video = folder / 'Troy.2003.Extended.mkv'
	sub = folder / 'Troy.2003.en.srt'  # release-named, no edition tag
	scan = FolderScan(
		folder=folder,
		files=[FileCandidate(video, 'video', 10), FileCandidate(sub, 'subtitle', 1, subtitle_lang='en')],
	)

	def resolver(raw: str, parsed: MovieMetadata | None) -> MovieMetadata | None:
		assert parsed is not None
		return MovieMetadata(title='Troy', year=2004, edition=parsed.edition, tmdb_id=652)

	actions = plan_actions([scan], tmp_path / 'dst', resolver=resolver)
	by_source = {a.source: a.action for a in actions}
	assert by_source[video] == 'move'
	assert by_source[sub] == 'skip'
