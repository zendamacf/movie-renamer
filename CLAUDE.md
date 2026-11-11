# CLAUDE.md

CLI (`movie-renamer`, Typer) that scans release-style movie folders and moves them into a Plex/Jellyfin/Emby/Kodi-friendly layout. Python 3.12+. See `README.md` for user-facing behaviour.

## Commands

Use the Makefile; it runs tools from `.venv`.

- `make install` — create `.venv` and install with dev extras
- `make test` — pytest (coverage enforced, `--cov-fail-under=79`)
- `make lint` / `make lint-fix` — ruff check + format
- `make typecheck` — `ty check` (diagnostics are warnings only)
- `make run ARGS="--source-dir ./src --target-dir ./lib"` — run the CLI

Run `make lint test` before suggesting a commit.

## Layout

- `src/movie_renamer/` — `cli.py` (entry point), `cli_config.py`, `cli_plan.py`, `cli_history.py`, `scanner.py`, `parser.py` (release-name parsing, editions), `planner.py`, `naming.py` (presets), `executor.py`, `history.py` (undo), `cleanup.py`, `models.py`, `terminal.py`
- `tests/` — one `test_*.py` per module area; shared fixtures in `conftest.py`

## Code style

- Ruff: line length 120, **single quotes, tab indentation**, rules `E,F,I,UP,B`.
- Safety invariants (don't weaken): dry-run by default, move-only (never copy), never overwrite existing destinations.
- Add or update tests alongside behaviour changes.

## Changelog fragments

User-visible changes need a Towncrier fragment in `changes/`:

```bash
make changelog-create NAME=+short-slug.feature   # types: feature, bugfix, doc, misc
```

Use `+slug` names when there is no issue number. Fragments are one sentence, written for users. Releases are cut with `make release VERSION=x.y.z` (don't run unless asked).

## Git workflow: conventional commits and branches

Never commit, push, or open PRs unless explicitly asked. When work is ready, suggest a commit message instead. Do not add agent attribution (`Co-Authored-By`, "Generated with…") to commits or PR descriptions.

### Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/): `<type>(<optional scope>): <description>`

- Types: `feat`, `fix`, `docs`, `refactor`, `test`, `perf`, `build`, `ci`, `chore`
- Imperative mood, lowercase description, no trailing period, subject ≤ 72 chars
- Breaking changes: `!` after the type/scope (`feat!: ...`) and a `BREAKING CHANGE:` footer
- Suggested scopes: `parser`, `naming`, `planner`, `executor`, `history`, `cli`
- Reference issues/PRs in the footer or as `(#123)` when applicable
- Dependency bumps use `chore(deps): ...`

Examples:

```text
feat(parser): recognize IMAX and Final Cut editions
fix(executor): skip move when destination already exists
docs: link episode-renamer in README
```

### Branches

Branch from `main` using `<type>/<short-kebab-description>`, with the same types as commits:

- `feat/naming-presets`
- `fix/forced-subtitle-replacement`
- `docs/readme-episode-renamer`
- `chore/release-1.0.2`

Keep one logical change per branch; PRs target `main` and their titles follow the commit format.
