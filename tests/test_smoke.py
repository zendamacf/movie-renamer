def test_imports() -> None:
	# Smoke test: the package + CLI module should import successfully.
	from movie_renamer.cli import app  # noqa: F401
