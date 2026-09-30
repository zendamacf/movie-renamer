# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier -->
## 1.0.0 (2026-09-30)

### Features

- Add --confirm to prompt for approval before each copy or move when applying changes.
- Handle subtitle files inside `Subs/` folders and recognize forced/SDH language tokens (e.g. `Forced.eng.srt`, `SDH.eng.HI.srt`).
- Improve skipped-file logging: list all files under each movie folder recursively (including nested subdirectories) without per-file skip metadata so it’s easier to spot missed files.
- Initial MVP: scan release-style movie folders and organise them into a Plex/Jellyfin-friendly `Title (Year)` layout, with dry-run and --apply.
- Load `config.json` automatically when present in the working directory (with a notice on stdout), remove `--config`, and replace positional source/target paths with `--source-dir` and `--target-dir`.
- Maps "DC" edition alias to "Director's Cut".
- Print the target directory once in the planned-operations list, and show each move as a path relative to it.
- Record rename batches under the target directory and support listing and undoing them via --list-batches/--history and --undo (last) / --undo <id> (specific).
- Removes copy functionality, as copying was significantly slower than moving.
- Store rename history (`batches.json`) in the current project directory (`./batches.json`) instead of under each `target_dir`.

### Bug Fixes

- Keep regular language subtitles when a forced track is also present. Forced/SDH files are renamed with `.forced`/`.sdh` suffixes instead of replacing `Movie (Year).en.srt`.
- Map common ISO 639-2/B subtitle language tokens (e.g. `por`, `ger`, `dut`, `gre`) to ISO 639-1 codes instead of truncating them to two letters.
- Pick up standalone video files sitting directly in the source directory, not only movies nested in subfolders.
- Use default subtitle language when the `.srt` basename matches the primary video (e.g. release-name.srt), instead of mis-parsing release tokens like `YIFY` as a language code.

### Misc

- Bump actions/checkout from 4 to 7. (#3)
- Bump actions/setup-python from 5 to 7. (#4)
- Bump softprops/action-gh-release from 2 to 3. (#5)
- Bump typer from 0.12.0 to 0.27.1. (#6)
- Bump towncrier from 24.8.0 to 25.8.0. (#7)
- Bump pytest-cov from 0.0.0 to 7.1.0. (#8)
- Bump ruff from 0.0.0 to 0.16.2. (#9)
- Bump codecov/codecov-action from 4 to 7. (#17)
- Bump filelock from 3.13.0 to 3.29.7. (#19)
- Adds webm support. (#20)
- Bump filelock from 3.29.7 to 3.31.0. (#31)
- Bump filelock from 3.31.2 to 3.32.2. (#33)
- Bump ty from 0.0.70 to 0.0.72. (#35)
- Bump filelock from 3.32.2 to 3.32.3. (#36)
- Bump ruff from 0.16.2 to 0.16.3. (#37)
- Bump ty from 0.0.72 to 0.0.74. (#38)
- Bump ruff from 0.16.3 to 0.16.4. (#39)
- Split `cli.py` into `cli_config`, `cli_history`, and `cli_plan` modules. (#48)
- Bump ruff from 0.16.4 to 0.16.5. (#53)
- Bump typer from 0.27.1 to 0.27.2. (#54)
- Bump ty from 0.0.74 to 0.0.75. (#55)
- Bump filelock from 3.32.3 to 3.32.4. (#56)
- Add Towncrier-based changelog fragment workflow for releases.
