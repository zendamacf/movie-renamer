# Movie Renamer

CLI that scans release-style movie folders and organises them into a Plex/Jellyfin-friendly layout.

## Usage

```bash
movie-renamer --help
```

## Config (optional)

You can provide a JSON config file via `--config` to provide:

- `source_dir`: overrides the CLI `source_dir` argument
- `target_dir`: overrides the CLI `target_dir` argument

See `example-config.json` for the complete (currently supported) schema.

## Common Commands

These map directly to the targets in the root `Makefile`:

```bash
make install     # install dev dependencies into .venv
make test        # run tests
make lint        # run linting
make lint-fix   # fix any linting errors
make typecheck   # run type checking
make run ARGS="--help"  # run the CLI module (pass CLI args via ARGS)
```

