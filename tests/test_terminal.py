from __future__ import annotations

import io

from movie_renamer.terminal import label


def test_label_returns_plain_text_for_non_tty_stream() -> None:
	stream = io.StringIO()
	assert label('SKIP', color='red', stream=stream) == 'SKIP'


def test_label_adds_ansi_for_tty_stream() -> None:
	class FakeTTY:
		def isatty(self) -> bool:
			return True

	result = label('COPY', color='green', stream=FakeTTY())
	assert result.startswith('\033[32;1m')
	assert result.endswith('\033[0m')
	assert 'COPY' in result
