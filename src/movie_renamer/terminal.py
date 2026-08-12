from __future__ import annotations

import sys


def label(text: str, *, color: str, stream: object = sys.stdout) -> str:
	"""Return ANSI-colored text when the stream is a TTY."""
	color_codes = {
		'red': '31',
		'yellow': '33',
		'orange': '33',
		'blue': '34',
		'green': '32',
		'bright_black': '90',
		'white': '37',
	}
	code = color_codes.get(color)
	is_tty = hasattr(stream, 'isatty') and stream.isatty()
	if code is None or not is_tty:
		return text
	return f'\033[{code};1m{text}\033[0m'
