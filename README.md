# Movie Renamer

CLI that scans release-style movie folders and organises them into a Plex/Jellyfin-friendly layout.

## End-to-end example

Suppose your downloads look like release folders and you want Plex-style `Title (Year)/` directories under a library root.

**Before** (`source/`):

```text
source/
└── Movie.Title.2020.1080p.BluRay.x265-RARBG/
    ├── Movie.Title.2020.1080p.BluRay.x265-RARBG.mkv
    └── Movie.Title.2020.en.srt
```

**After** (`library/` — paths created when you run with `--apply`):

```text
library/
└── Movie Title (2020)/
    ├── Movie Title (2020).mkv
    └── Movie Title (2020).en.srt
```

Typical workflow:

```bash
# 1. Plan (default: dry-run; no filesystem changes)
movie-renamer --source-dir ./source --target-dir ./library

# 2. Apply when the plan looks right
movie-renamer --source-dir ./source --target-dir ./library --apply

# 3. Optional: confirm each move interactively
movie-renamer --source-dir ./source --target-dir ./library --apply --confirm
```

`--target-dir` must already exist. The tool **moves** files into the library (it does not copy them).

## Dry-run output

Without `--apply`, the CLI prints planned moves, then expanded skip lines for other files under each movie folder (subtitles that were not moved, nested paths when `--recursive` is off, and so on). A summary line ends the run:

```text
Planned operations (move):
Target directory: /path/to/library
- MOVE Movie.Title.2020....mkv -> Movie Title (2020)/Movie Title (2020).mkv
- MOVE Movie.Title.2020.en.srt -> Movie Title (2020)/Movie Title (2020).en.srt

- SKIP Movie.Title.2020/Extras/readme.txt
Summary (dry-run): MOVE=2 SKIP=0 (Videos: mkv/mp4/avi/etc. Subtitles: .srt)
```

Coloured `MOVE` / `SKIP` labels appear in a real terminal; the structure above is what you should expect.

## Safety

- **Dry-run by default** — nothing is moved until you pass `--apply`.
- **`--confirm`** — when applying, prompts before each move; declined moves are skipped.
- **Move-only** — reorganisation uses moves, not copies (faster and avoids doubling disk use).
- **No overwrites** — if a destination file already exists, that operation is skipped with a warning.

For full flag lists and edge cases, use `movie-renamer --help`.

## Config (optional)

If `config.json` exists in the **current working directory**, it is loaded automatically and the CLI prints a short notice. Supported keys:

| Key | Purpose |
| --- | --- |
| `source_dir` | Default when `--source-dir` is omitted |
| `target_dir` | Default when `--target-dir` is omitted |
| `ignore_globs` | Extra glob patterns to skip (same as repeatable `--ignore`) |

CLI flags override `config.json` when both are set.

See [`example-config.json`](example-config.json) for a complete example (including `ignore_globs`).

## History and undo

After a successful or partial `--apply` run, the tool records a **batch** in `./batches.json` (in the directory you run the command from). Leftover source material for handled folders is archived under:

```text
.movie-renamer/archive/<batch-id>/
```

List batches:

```bash
movie-renamer --target-dir ./library --history
```

Undo the most recent undoable batch:

```bash
movie-renamer --target-dir ./library --undo
```

Undo a specific batch by id:

```bash
movie-renamer --target-dir ./library --undo <batch-id>
```

Undo moves files back from the library to their original source paths and restores archived files when possible. **Partial** batches (some moves failed) only record successful operations; undo reverts those and warns that the batch was incomplete.

## Usage

```bash
movie-renamer --help
```

## Common Commands

These map directly to the targets in the root `Makefile`:

```bash
make install     # install dev dependencies into .venv
make test        # run tests (fails if line coverage drops below 79%; see pyproject.toml)
make lint        # run linting
make lint-fix   # fix any linting errors
make typecheck   # run type checking
make run ARGS="--help"  # run the CLI module (pass CLI args via ARGS)
```

## Changelog

Release notes are built with [Towncrier](https://github.com/twisted/towncrier). Add a fragment when you ship a user-visible change:

```bash
make changelog-create NAME=123.feature
```

### Release

1. Update the version in `pyproject.toml` and `src/movie_renamer/__init__.py`.
2. Preview release notes (optional):

   ```bash
   make changelog-draft VERSION=0.1.0
   ```

3. Run the release script:

   ```bash
   make release VERSION=0.1.0
   ```

4. Commit, tag `v0.1.0`, and push.

See `changes/README.md` for fragment types and naming.

## License

MIT — see [LICENSE](LICENSE).
