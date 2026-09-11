from __future__ import annotations

import re
from dataclasses import dataclass

_YEAR_RE = re.compile(r'\b(19|20)\d{2}\b')

# These are known edition phrases we want to preserve (incl. punctuation).
# Order matters: longer phrases should come first.
_EDITION_PHRASES = [
	"Director's Cut",
	'Extended',
	'Unrated',
	'Theatrical',
	'Remastered',
]

# Short scene-name tokens that map onto a canonical edition phrase.
_EDITION_ALIASES = {
	'dc': "Director's Cut",
}

# Common release-noise tokens we want to remove before deriving the title.
_NOISE_TOKENS = [
	# Resolution / quality
	'2160p',
	'1080p',
	'720p',
	'480p',
	'4k',
	'hdr',
	'hdrip',
	# Encoders / codecs
	'x264',
	'x265',
	'hevc',
	'av1',
	'h.264',
	'h264',
	'h.265',
	'h265',
	# Sources / formats
	'bluray',
	'blueray',
	'blu-ray',
	'web-dl',
	'webdl',
	'web',
	'dl',
	'webrip',
	'bdrip',
	'dvdrip',
	'ddp',
	'dd5.1',
	'dd2.0',
	'atmos',
	# Release group / packaging
	'rarbg',
	'yify',
	'yts',
	'deck',
	'opus',
	'opus5.1',
	# Container formats / file extensions (often appear after dot->space normalization)
	'mkv',
	'mp4',
	'avi',
	'm4v',
	'mov',
	'webm',
	'wmv',
	# Subtitle extensions
	'srt',
	'vtt',
	# Bracket noise like [1080p]
	'[]',
]

_SMALL_WORDS_KEEP_LOWER = {
	# Keep these lowercase except at the beginning.
	'the',
	'of',
	'and',
}


@dataclass(frozen=True)
class MovieMetadata:
	title: str
	year: int
	edition: str | None


def _normalize_word_for_title(word: str) -> str:
	"""
	Title-case a single word while preserving apostrophe casing.

	Example: "Director's" -> "Director's" (not "Director'S")
	"""
	if not word:
		return word
	# Handle apostrophes: title-case each segment and keep the "after" segment lowercase.
	if "'" in word:
		left, right = word.split("'", 1)
		return f"{left[:1].upper()}{left[1:].lower()}'{right.lower()}"
	return f'{word[:1].upper()}{word[1:].lower()}'


def to_title_case(text: str) -> str:
	words = [w for w in re.split(r'\s+', text.strip()) if w]

	parts: list[str] = []
	for i, w in enumerate(words):
		if i != 0 and w.lower() in _SMALL_WORDS_KEEP_LOWER:
			parts.append(w.lower())
		else:
			parts.append(_normalize_word_for_title(w))
	return ' '.join(parts)


def extract_year(text: str) -> int | None:
	for match in _YEAR_RE.finditer(text):
		return int(match.group(0))
	return None


def _edition_needles(edition_phrases: list[str]) -> list[tuple[str, str]]:
	# (match text, canonical edition). Canonical phrases first, then aliases.
	needles = [(phrase, phrase) for phrase in edition_phrases]
	for alias, canonical in _EDITION_ALIASES.items():
		if canonical in edition_phrases:
			needles.append((alias, canonical))
	return needles


def extract_edition(text: str, *, edition_phrases: list[str] | None = None) -> str | None:
	# Case-insensitive match, but preserve the canonical punctuation/casing from our phrases.
	# Normalize common separators so `Director's.Cut` matches `Director's Cut`.
	edition_phrases = edition_phrases or _EDITION_PHRASES
	lower = text.lower().replace('.', ' ').replace('_', ' ')
	lower = re.sub(r'\s+', ' ', lower).strip()
	for needle, canonical in _edition_needles(edition_phrases):
		if re.search(rf'(?<!\w){re.escape(needle.lower())}(?!\w)', lower):
			return canonical
	return None


def strip_release_tags(text: str) -> str:
	# Remove bracketed tags like [1080p]
	text = re.sub(r'\[.*?\]', ' ', text)
	# Remove parenthesized year "(1992)" but keep the year for extraction elsewhere.
	text = re.sub(r'\(\s*(19|20)\d{2}\s*\)', ' ', text)
	# Drop leftover grouping punctuation (e.g. title text cut off before "(1992)").
	text = re.sub(r'[()\[\]]', ' ', text)

	# Remove audio channel noise like "5.1" or "7.1" before we replace '.' with spaces.
	# This avoids leaving behind "5 1" tokens that pollute the title.
	text = re.sub(r'\b\d+\.\d+\b', ' ', text)

	# Convert separators into spaces for token removal.
	text = text.replace('.', ' ').replace('_', ' ')

	# Tokenize hyphen-separated segments (e.g. `WEB-DL` -> `WEB DL`, `x265-RARBG` -> `x265 RARBG`).
	text = text.replace('-', ' ')

	# Lowercase pass for token removal while preserving remaining tokens.
	tokens = []
	for token in text.split():
		token_clean = token.strip().lower()
		if token_clean in _NOISE_TOKENS:
			continue
		tokens.append(token)

	return ' '.join(tokens)


def _cleanup_title_tokens(text: str, *, edition_phrases: list[str]) -> str:
	# Remove the detected edition (canonical phrase or alias) from the title source.
	edition = extract_edition(text, edition_phrases=edition_phrases)
	if edition:
		for needle, canonical in _edition_needles(edition_phrases):
			if canonical == edition:
				text = re.sub(
					rf'(?<!\w){re.escape(needle)}(?!\w)',
					' ',
					text,
					flags=re.IGNORECASE,
				)

	# Remove year tokens.
	year = extract_year(text)
	if year is not None:
		text = re.sub(rf'\b{year}\b', ' ', text)

	return ' '.join(text.split())


def parse_movie_name(raw: str, *, edition_phrases: list[str] | None = None) -> MovieMetadata:
	year = extract_year(raw)
	if year is None:
		raise ValueError(f'Could not extract year from: {raw!r}')

	edition_phrases = edition_phrases or _EDITION_PHRASES
	edition = extract_edition(raw, edition_phrases=edition_phrases)

	# Scene/release names put the title before the year; ignore trailing quality tags.
	year_match = _YEAR_RE.search(raw)
	title_source = raw[: year_match.start()] if year_match else raw

	# Derive title candidate.
	working = strip_release_tags(title_source)
	working = working.replace("'", "'")  # normalize odd quoting variants (best-effort)
	working = _cleanup_title_tokens(working, edition_phrases=edition_phrases)

	# Dots-to-title-casing: title is the remaining words.
	title = to_title_case(working)
	title = re.sub(r'\s{2,}', ' ', title).strip()

	if not title:
		raise ValueError(f'Could not extract title from: {raw!r}')

	return MovieMetadata(title=title, year=year, edition=edition)
