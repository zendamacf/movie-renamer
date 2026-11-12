# Movie Renamer

CLI that scans release-style movie folders and organises them into a Plex/Jellyfin-friendly layout.

To rename TV episodes, use [episode-renamer](https://github.com/zendamacf/episode-renamer).

**Python:** requires 3.12+ (`requires-python` in `pyproject.toml`). CI runs the test suite on **3.12** and **3.13**.

## End-to-end example

Suppose your downloads look like release folders and you want Plex-style `Title (Year)/` directories under a library root.

**Before** (`source/`):

```text
source/
└── Movie.Title.2020.1080p.BluRay.x265-RARBG/
    ├── Movie.Title.2020.1080p.BluRay.x265-RARBG.mkv
    └── Movie.Title.2020.en.srt
```

**After** (`library/` — paths created when you run and confirm the plan):

```text
library/
└── Movie Title (2020)/
    ├── Movie Title (2020).mkv
    └── Movie Title (2020).en.srt
```

Settings live in a [`config.json`](#config) in the directory you run the command from. Typical `config.json` (see [TMDb lookup](#tmdb-lookup-default) for the API key):

```json
{
  "source_dir": "./source",
  "target_dir": "./library",
  "tmdb_api_key": "your-tmdb-v3-api-key"
}
```

Typical workflow:

```bash
# 1. Optional: preview only (no prompt, no filesystem changes)
movie-renamer --dryrun

# 2. Show the plan, then answer y at the prompt to apply it (default is N)
movie-renamer

```

Command-line options are still supported and override `config.json` for a single run, for example `movie-renamer --source-dir ./other`.

`target_dir` must already exist. The tool **moves** files into the library (it does not copy them).

## TMDb lookup (default)

Titles, years and IDs come from [TMDb](https://www.themoviedb.org/) by default. For each movie the tool searches TMDb using the name parsed from the release, then:

- corrects wrong titles and years, and finds the year when the release name has none;
- optionally adds a TMDb ID tag so Plex, Jellyfin and Emby match the movie (off by default; enable with `"id_tag": true` in `config.json` or `--id-tag`): `Movie Title (2020) {tmdb-123}` (plex) or `Movie Title (2020) [tmdbid-123]` (jellyfin, emby). The kodi preset has no ID tag. Without the tag, titles and years are still corrected;
- asks you to choose when there is more than one plausible match (option `0` keeps the name parsed from the filename).

An API key is required. Get a free v3 key from your TMDb account and set `tmdb_api_key` in `config.json` (or use the `TMDB_API_KEY` environment variable or `--tmdb-api-key`). If TMDb cannot be reached the run stops before anything is moved.

To skip TMDb entirely (no API key, no network), set `"filename_only": true` in `config.json` (or pass `--filename-only`). Titles and years are then parsed from the release name alone and no ID tag is added.

```bash
movie-renamer --filename-only
```

Editions such as `Director's Cut` always come from the file name.

## Plan output

The CLI prints planned moves, then expanded skip lines for other files under each movie folder (subtitles that were not moved, nested paths when `--recursive` is off, and so on). A summary line follows. With `--dryrun` the run ends there; otherwise you are asked `Apply these changes? [y/N]` and the moves only happen on `y`:

```text
Planned operations (move):
Target directory: /path/to/library
- MOVE Movie.Title.2020....mkv -> Movie Title (2020)/Movie Title (2020).mkv
- MOVE Movie.Title.2020.en.srt -> Movie Title (2020)/Movie Title (2020).en.srt

- SKIP Movie.Title.2020/Extras/readme.txt
Summary (planned): MOVE=2 SKIP=0 (Videos: mkv/mp4/avi/etc. Subtitles: .srt)
Apply these changes? [y/N]:
```

With `--dryrun` the summary line reads `Summary (dry-run): ...` and there is no prompt.

Coloured `MOVE` / `SKIP` labels appear in a real terminal; the structure above is what you should expect.

## Safety

- **Confirmation required** — the plan is always shown first and nothing is moved unless you answer `y` (default is no). `--dryrun` never moves anything.
- **Move-only** — reorganisation uses moves, not copies (faster and avoids doubling disk use).
- **No overwrites** — if a destination file already exists, that operation is skipped with a warning.

For full flag lists and edge cases, use `movie-renamer --help`.

## Config

`config.json` is the expected way to set the tool up. It is loaded automatically from the **current working directory** and the CLI prints a short notice. If `source_dir` or `target_dir` is set in neither `config.json` nor on the command line, the run stops with an error. Supported keys:

| Key | Purpose |
| --- | --- |
| `source_dir` | Directory containing movie folders (`--source-dir` overrides) |
| `target_dir` | Library root to organise into (`--target-dir` overrides) |
| `ignore_globs` | Extra glob patterns to skip (same as repeatable `--ignore`) |
| `preset` | Naming preset (same as `--preset`) |
| `tmdb_api_key` | TMDb API key (same as `--tmdb-api-key`) |
| `id_tag` | `true` to add the TMDb ID tag to names (same as `--id-tag`) |
| `filename_only` | `true` to skip the TMDb lookup (same as `--filename-only`) |

Command-line options are an additional way to set the same values and override `config.json` when both are set (`--ignore` patterns are added to `ignore_globs`). `--history` and `--undo` use `target_dir` from `config.json` too.

See [`example-config.json`](example-config.json) for a complete example (including `ignore_globs`).

## Naming presets

Use `--preset` to choose the naming format. The default is `plex`.

| Preset | Edition in file name | Example |
| --- | --- | --- |
| `plex` | `{edition-X}` | `Troy (2004) {edition-Director's Cut}.mkv` |
| `jellyfin` | ` - X` | `Troy (2004) - Director's Cut.mkv` |
| `emby` | ` - X` | `Troy (2004) - Director's Cut.mkv` |
| `kodi` | Not supported, so it is skipped | `Troy (2004).mkv` |

All presets use the `Title (Year)/` folder. Kodi has no edition naming, so the edition is left out.

## History and undo

After a successful or partial run, the tool records a **batch** in `./batches.json` (in the directory you run the command from). Leftover source material for handled folders is archived under:

```text
.movie-renamer/archive/<batch-id>/
```

List batches:

```bash
movie-renamer --history
```

Undo the most recent undoable batch:

```bash
movie-renamer --undo
```

Undo a specific batch by id:

```bash
movie-renamer --undo <batch-id>
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
make test        # run tests (fails if line coverage drops below threhold in pyproject.toml)
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
