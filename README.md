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

**After** (`library/` — paths created when you run with `--apply`):

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
# 1. Plan (default: dry-run; no filesystem changes)
movie-renamer

# 2. Apply when the plan looks right
movie-renamer --apply

# 3. Optional: confirm each move interactively
movie-renamer --apply --confirm
```

Command-line options are still supported and override `config.json` for a single run, for example `movie-renamer --source-dir ./other`.

`target_dir` must already exist. The tool **moves** files into the library (it does not copy them).

## TMDb lookup (default)

Titles, years and IDs come from [TMDb](https://www.themoviedb.org/) by default. For each movie the tool searches TMDb using the name parsed from the release, then:

- corrects wrong titles and years, and finds the year when the release name has none;
- optionally adds a TMDb ID tag so Plex, Jellyfin and Emby match the movie (off by default; enable with `"id_tag": true` in `config.json` or `--id-tag`): `Movie Title (2020) {tmdb-123}` (plex) or `Movie Title (2020) [tmdbid-123]` (jellyfin, emby). The kodi preset has no ID tag. Without the tag, titles and years are still corrected and the ID still appears in `--json` output;
- asks you to choose when there is more than one plausible match (option `0` keeps the name parsed from the filename). With `--json` there is no prompt, so ambiguous movies keep the filename parse.

An API key is required. Get a free v3 key from your TMDb account and set `tmdb_api_key` in `config.json` (or use the `TMDB_API_KEY` environment variable or `--tmdb-api-key`). If TMDb cannot be reached the run stops before anything is moved.

To skip TMDb entirely (no API key, no network), set `"filename_only": true` in `config.json` (or pass `--filename-only`). Titles and years are then parsed from the release name alone and no ID tag is added.

```bash
movie-renamer --filename-only
```

Editions such as `Director's Cut` always come from the file name.

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

## JSON output

Pass `--json` to print the plan and summary as a single JSON document on stdout (the "Using settings from" notice goes to stderr). It works with dry-run and `--apply`, and cannot be combined with `--confirm`, `--history` or `--undo`.

```bash
movie-renamer --json | jq '.summary'
```

Example output (dry-run):

```json
{
  "mode": "dry-run",
  "source_dir": "/path/to/source",
  "target_dir": "/path/to/library",
  "preset": "plex",
  "actions": [
    {
      "action": "move",
      "source": "/path/to/source/Movie.Title.2020.1080p.BluRay.x265-RARBG/Movie.Title.2020.1080p.BluRay.x265-RARBG.mkv",
      "target": "Movie Title (2020)/Movie Title (2020).mkv",
      "metadata": { "title": "Movie Title", "year": 2020, "edition": null, "tmdb_id": null }
    },
    {
      "action": "move",
      "source": "/path/to/source/Movie.Title.2020.1080p.BluRay.x265-RARBG/Movie.Title.2020.en.srt",
      "target": "Movie Title (2020)/Movie Title (2020).en.srt",
      "metadata": { "title": "Movie Title", "year": 2020, "edition": null, "tmdb_id": null }
    }
  ],
  "skipped": [
    { "path": "Movie.Title.2020.1080p.BluRay.x265-RARBG/Extras/readme.nfo", "kind": "other" }
  ],
  "summary": { "move": 2, "skip": 0, "misc": 0 }
}
```

- `target` is relative to `target_dir`. `skipped[].kind` is `subtitle` or `other`.
- With `--apply`, `mode` is `apply` and two keys are added:

  ```json
  {
    "executed": { "move": 2, "skip": 0, "errors": 0 },
    "batch": { "id": "<batch-id>", "status": "completed", "operations": 2 }
  }
  ```

  `batch` is `null` when nothing was moved, and `status` is `partial` if some moves failed.
- The exit code is 1 if any move errored.

## Safety

- **Dry-run by default** — nothing is moved until you pass `--apply`.
- **`--confirm`** — when applying, prompts before each move; declined moves are skipped.
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

After a successful or partial `--apply` run, the tool records a **batch** in `./batches.json` (in the directory you run the command from). Leftover source material for handled folders is archived under:

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
