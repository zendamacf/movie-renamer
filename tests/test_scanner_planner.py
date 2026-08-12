from __future__ import annotations

from pathlib import Path

from movie_renamer.planner import plan_actions
from movie_renamer.scanner import scan_movie_folders


def _write(path: Path, content: bytes) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_bytes(content)


def test_planner_plans_primary_video_and_skips_promo_and_junk(tmp_path: Path) -> None:
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'

	movie_folder = source_dir / 'Single.White.Female.1992.1080p.BluRay.x265-RARBG'
	video_path = movie_folder / 'Single.White.Female.1992....mp4'
	promo_path = movie_folder / 'WWW.YTS.RE.jpg'
	_write(video_path, b'video')
	_write(promo_path, b'promo')

	# Should be ignored when recursive=False.
	junk_folder = source_dir / 'Other'
	junk_video = junk_folder / 'Junk.2000....mp4'
	_write(junk_video, b'junk')

	folder_scans = scan_movie_folders(source_dir, recursive=False)
	actions = plan_actions(
		folder_scans=folder_scans,
		target_dir=target_dir,
		default_lang='en',
		ignore_globs=[],
	)

	target_video = target_dir / 'Single White Female (1992)' / 'Single White Female (1992).mp4'
	assert any(a.action == 'move' and a.target == target_video for a in actions)

	assert any(a.action == 'skip' and a.source == promo_path for a in actions)
	assert not any(a.source == junk_video for a in actions)


def test_planner_subtitle_default_lang(tmp_path: Path) -> None:
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'

	folder = source_dir / 'Ultraviolet (2006) [1080p]'
	video_path = folder / 'Ultraviolet (2006) [1080p].mkv'
	sub_path = folder / 'Ultraviolet (2006) [1080p].srt'
	_write(video_path, b'video-bytes' * 10)
	_write(sub_path, b'subtitle-bytes')

	actions = plan_actions(
		folder_scans=scan_movie_folders(source_dir, recursive=False),
		target_dir=target_dir,
		default_lang='en',
		ignore_globs=[],
	)

	expected_subtitle_target = target_dir / 'Ultraviolet (2006)' / 'Ultraviolet (2006).en.srt'
	assert any(a.action == 'move' and a.target == expected_subtitle_target and a.source == sub_path for a in actions)


def test_planner_primary_video_selection_and_edition_suffix(tmp_path: Path) -> None:
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'

	folder = source_dir / "Troy.Director's.Cut.2004"
	video_primary = folder / "Troy.Director's.Cut.2004.2160p.WEB-DL.mkv"
	video_secondary = folder / "Troy.Director's.Cut.2004.1080p.WEB-DL.mkv"
	_write(video_primary, b'primary' * 2000)
	_write(video_secondary, b'secondary' * 10)

	actions = plan_actions(
		folder_scans=scan_movie_folders(source_dir, recursive=False),
		target_dir=target_dir,
		default_lang='en',
		ignore_globs=[],
	)

	primary_target = target_dir / 'Troy (2004)' / "Troy (2004) {edition-Director's Cut}.mkv"
	assert any(a.action == 'move' and a.target == primary_target and a.source == video_primary for a in actions)

	assert any(a.action == 'skip' and a.source == video_secondary for a in actions)


def test_planner_subtitle_matching_video_stem_uses_default_lang(tmp_path: Path) -> None:
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'

	folder = source_dir / 'Ultraviolet.2006.BluRay.1080p.x264.YIFY'
	video_path = folder / 'Ultraviolet.2006.BluRay.1080p.x264.YIFY.mp4'
	sub_path = folder / 'Ultraviolet.2006.BluRay.1080p.x264.YIFY.srt'
	_write(video_path, b'video-bytes' * 10)
	_write(sub_path, b'subtitle-bytes')

	actions = plan_actions(
		folder_scans=scan_movie_folders(source_dir, recursive=False),
		target_dir=target_dir,
		default_lang='en',
		ignore_globs=[],
	)

	expected_subtitle_target = target_dir / 'Ultraviolet (2006)' / 'Ultraviolet (2006).en.srt'
	assert any(a.action == 'move' and a.target == expected_subtitle_target and a.source == sub_path for a in actions)


def test_planner_subtitle_lang_inference_eng_and_english(tmp_path: Path) -> None:
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'

	folder = source_dir / 'Ultraviolet (2006) [1080p]'
	video_path = folder / 'Ultraviolet (2006) [1080p].mkv'
	sub_path_eng = folder / 'Ultraviolet (2006) [1080p].eng.srt'
	sub_path_english = folder / 'Ultraviolet (2006) [1080p].english.srt'

	_write(video_path, b'video-bytes' * 10)
	_write(sub_path_eng, b'subtitle-bytes-eng')
	_write(sub_path_english, b'subtitle-bytes-english')

	actions = plan_actions(
		folder_scans=scan_movie_folders(source_dir, recursive=False),
		target_dir=target_dir,
		default_lang='en',
		ignore_globs=[],
	)

	expected_target = target_dir / 'Ultraviolet (2006)' / 'Ultraviolet (2006).en.srt'
	moved_sources = {
		a.source for a in actions if a.action == 'move' and a.target == expected_target and a.source is not None
	}
	skipped_sources = {a.source for a in actions if a.action == 'skip' and a.source is not None}

	# Collision: both ENG + ENGLISH map to the same target filename; exactly one wins.
	assert moved_sources == {sub_path_eng} or moved_sources == {sub_path_english}
	assert skipped_sources == {sub_path_eng} or skipped_sources == {sub_path_english}


def test_scan_subtitles_in_subs_folder(tmp_path: Path) -> None:
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'

	folder = source_dir / 'Ultraviolet (2006) [1080p]'
	video_path = folder / 'Ultraviolet (2006) [1080p].mkv'
	subs_dir = folder / 'Subs'

	# Subs folder often uses just the language name/code (no movie basename prefix).
	english_path = subs_dir / 'English.srt'
	french_path = subs_dir / 'fre.srt'

	_write(video_path, b'video-bytes' * 10)
	_write(english_path, b'subtitle-bytes-en')
	_write(french_path, b'subtitle-bytes-fr')

	actions = plan_actions(
		folder_scans=scan_movie_folders(source_dir, recursive=False),
		target_dir=target_dir,
		default_lang='en',
		ignore_globs=[],
	)

	expected_en_target = target_dir / 'Ultraviolet (2006)' / 'Ultraviolet (2006).en.srt'
	expected_fr_target = target_dir / 'Ultraviolet (2006)' / 'Ultraviolet (2006).fr.srt'

	assert any(a.action == 'move' and a.target == expected_en_target and a.source == english_path for a in actions)
	assert any(a.action == 'move' and a.target == expected_fr_target and a.source == french_path for a in actions)


def test_planner_subtitle_forced_lang_parsing(tmp_path: Path) -> None:
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'

	folder = source_dir / 'Ultraviolet (2006) [1080p]'
	video_path = folder / 'Ultraviolet (2006) [1080p].mkv'
	sub_path_forced_eng_capital = folder / 'Forced.eng.srt'
	sub_path_forced_eng_dot_prefix = folder / 'eng.forced.srt'

	_write(video_path, b'video-bytes' * 10)
	_write(sub_path_forced_eng_capital, b'subtitle-bytes-forced-eng')
	_write(sub_path_forced_eng_dot_prefix, b'subtitle-bytes-forced-eng-dot')

	actions = plan_actions(
		folder_scans=scan_movie_folders(source_dir, recursive=False),
		target_dir=target_dir,
		default_lang='en',
		ignore_globs=[],
	)

	expected_en_target = target_dir / 'Ultraviolet (2006)' / 'Ultraviolet (2006).en.srt'
	moved_sources = {
		a.source for a in actions if a.action == 'move' and a.target == expected_en_target and a.source is not None
	}
	skipped_sources = {
		a.source
		for a in actions
		if a.action == 'skip'
		and a.source is not None
		and a.source in {sub_path_forced_eng_capital, sub_path_forced_eng_dot_prefix}
	}

	assert moved_sources == {sub_path_forced_eng_capital} or moved_sources == {sub_path_forced_eng_dot_prefix}
	assert skipped_sources == {sub_path_forced_eng_capital} or skipped_sources == {sub_path_forced_eng_dot_prefix}


def test_planner_subtitle_sdh_lang_parsing(tmp_path: Path) -> None:
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'

	folder = source_dir / 'Ultraviolet (2006) [1080p]'
	video_path = folder / 'Ultraviolet (2006) [1080p].mkv'
	sub_path_sdh_eng = folder / 'SDH.eng.HI.srt'
	sub_path_sdh_spa = folder / 'SDH.spa.HI.srt'

	_write(video_path, b'video-bytes' * 10)
	_write(sub_path_sdh_eng, b'subtitle-bytes-sdh-eng')
	_write(sub_path_sdh_spa, b'subtitle-bytes-sdh-spa')

	actions = plan_actions(
		folder_scans=scan_movie_folders(source_dir, recursive=False),
		target_dir=target_dir,
		default_lang='en',
		ignore_globs=[],
	)

	expected_en_target = target_dir / 'Ultraviolet (2006)' / 'Ultraviolet (2006).en.srt'
	expected_es_target = target_dir / 'Ultraviolet (2006)' / 'Ultraviolet (2006).es.srt'

	assert any(a.action == 'move' and a.target == expected_en_target and a.source == sub_path_sdh_eng for a in actions)
	assert any(a.action == 'move' and a.target == expected_es_target and a.source == sub_path_sdh_spa for a in actions)


def test_planner_subtitles_match_movie_edition_when_present(tmp_path: Path) -> None:
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'

	# Movie edition: Director's Cut
	folder = source_dir / "Troy.Director's.Cut.2004"
	video_primary = folder / "Troy.Director's.Cut.2004.2160p.WEB-DL.mkv"
	sub_good = folder / "Troy.Director's.Cut.2004.en.srt"
	sub_bad = folder / 'Troy.2004.en.srt'  # No edition marker in subtitle filename

	_write(video_primary, b'video-bytes' * 10)
	_write(sub_good, b'sub-good')
	_write(sub_bad, b'sub-bad')

	actions = plan_actions(
		folder_scans=scan_movie_folders(source_dir, recursive=False),
		target_dir=target_dir,
		default_lang='en',
		ignore_globs=[],
	)

	expected_target = target_dir / 'Troy (2004)' / "Troy (2004) {edition-Director's Cut}.en.srt"

	assert any(a.action == 'move' and a.target == expected_target and a.source == sub_good for a in actions)
	assert any(a.action == 'skip' and a.source == sub_bad for a in actions)
	assert not any(a.action == 'move' and a.source == sub_bad for a in actions)


def test_planner_subs_folder_subtitles_ignore_edition_filter(tmp_path: Path) -> None:
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'

	folder = source_dir / 'The.Last.Of.The.Mohicans.1992.DC.1080p.BluRay.x265-RARBG'
	video_path = folder / 'The.Last.Of.The.Mohicans.1992.DC.1080p.BluRay.x265-RARBG.mp4'
	sub_path = folder / 'Subs' / '16_English.srt'

	_write(video_path, b'video-bytes' * 10)
	_write(sub_path, b'subtitle-bytes')

	actions = plan_actions(
		folder_scans=scan_movie_folders(source_dir, recursive=False),
		target_dir=target_dir,
		default_lang='en',
		ignore_globs=[],
	)

	expected_video = (
		target_dir / 'The Last of the Mohicans (1992)' / "The Last of the Mohicans (1992) {edition-Director's Cut}.mp4"
	)
	expected_sub = (
		target_dir
		/ 'The Last of the Mohicans (1992)'
		/ "The Last of the Mohicans (1992) {edition-Director's Cut}.en.srt"
	)

	assert any(a.action == 'move' and a.target == expected_video and a.source == video_path for a in actions)
	assert any(a.action == 'move' and a.target == expected_sub and a.source == sub_path for a in actions)


def test_scan_movie_folders_recursive_finds_nested_movies(tmp_path: Path) -> None:
	from movie_renamer.scanner import scan_movie_folders

	source_dir = tmp_path / 'src'
	nested_movie = source_dir / 'Some.Parent' / 'Nested.Movie.2010'
	other_folder = source_dir / 'Other'

	nested_movie.mkdir(parents=True, exist_ok=True)
	other_folder.mkdir(parents=True, exist_ok=True)

	# Put a valid video file into each so they classify as movie folders.
	(nested_movie / 'Nested.Movie.2010.1080p.WEB-DL.mkv').write_bytes(b'video')
	(other_folder / 'Other.2011.1080p.WEB-DL.mkv').write_bytes(b'video')

	non_recursive = scan_movie_folders(source_dir, recursive=False)
	assert all(fs.folder != nested_movie for fs in non_recursive)

	recursive = scan_movie_folders(source_dir, recursive=True)
	assert any(fs.folder == nested_movie for fs in recursive)
	# "Other/" is treated as junk and should be skipped even in recursive mode.
	assert all(fs.folder != other_folder for fs in recursive)


def test_scan_picks_up_standalone_video_in_source_dir(tmp_path: Path) -> None:
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'
	video_path = source_dir / 'Minions.and.Monsters.2026.1080p.WEBRip.AAC5.1.10bits.x265-Rapta.mkv'
	_write(video_path, b'video')

	actions = plan_actions(
		folder_scans=scan_movie_folders(source_dir, recursive=False),
		target_dir=target_dir,
		default_lang='en',
		ignore_globs=[],
	)

	expected = target_dir / 'Minions and Monsters (2026)' / 'Minions and Monsters (2026).mkv'
	assert any(a.action == 'move' and a.source == video_path and a.target == expected for a in actions)


def test_scan_standalone_video_keeps_matching_subtitle(tmp_path: Path) -> None:
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'
	stem = 'Minions.and.Monsters.2026.1080p.WEBRip.AAC5.1.10bits.x265-Rapta'
	video_path = source_dir / f'{stem}.mkv'
	sub_path = source_dir / f'{stem}.srt'
	_write(video_path, b'video')
	_write(sub_path, b'subtitle')

	actions = plan_actions(
		folder_scans=scan_movie_folders(source_dir, recursive=False),
		target_dir=target_dir,
		default_lang='en',
		ignore_globs=[],
	)

	expected_video = target_dir / 'Minions and Monsters (2026)' / 'Minions and Monsters (2026).mkv'
	expected_sub = target_dir / 'Minions and Monsters (2026)' / 'Minions and Monsters (2026).en.srt'
	assert any(a.action == 'move' and a.source == video_path and a.target == expected_video for a in actions)
	assert any(a.action == 'move' and a.source == sub_path and a.target == expected_sub for a in actions)


def test_scan_standalone_videos_are_planned_separately(tmp_path: Path) -> None:
	source_dir = tmp_path / 'src'
	target_dir = tmp_path / 'dst'
	first = source_dir / 'Minions.and.Monsters.2026.1080p.WEBRip.mkv'
	second = source_dir / 'Ultraviolet.2006.BluRay.1080p.x264.YIFY.mkv'
	_write(first, b'video-one')
	_write(second, b'video-two')

	actions = plan_actions(
		folder_scans=scan_movie_folders(source_dir, recursive=False),
		target_dir=target_dir,
		default_lang='en',
		ignore_globs=[],
	)

	moved = {a.source for a in actions if a.action == 'move'}
	assert moved == {first, second}
	assert not any(a.action == 'skip' for a in actions)


def test_scan_recursive_does_not_descend_into_other_subfolders(tmp_path: Path) -> None:
	source_dir = tmp_path / 'src'
	nested_in_other = source_dir / 'Other' / 'Nested.Movie.2010'
	nested_in_other.mkdir(parents=True, exist_ok=True)
	(nested_in_other / 'Nested.Movie.2010.1080p.WEB-DL.mkv').write_bytes(b'video')

	recursive = scan_movie_folders(source_dir, recursive=True)
	assert all(fs.folder != nested_in_other for fs in recursive)
