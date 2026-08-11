# Changelog fragments

This project uses [Towncrier](https://github.com/twisted/towncrier) to assemble release notes from small change fragments.

Add a fragment when you make a user-visible change:

```bash
make changelog-create NAME=123.feature
# or: towncrier create 123.feature
```

Fragment types:

- `feature` — new functionality
- `bugfix` — bug fixes
- `doc` — documentation
- `misc` — internal or minor changes

Use `+` instead of an issue id for changes without a ticket, e.g. `+batch-history.feature`.

## Release

1. Update the version in `pyproject.toml` and `src/movie_renamer/__init__.py`.
2. Preview release notes (optional):

   ```bash
   make changelog-draft VERSION=0.1.0
   ```

3. Run the release script:

   ```bash
   make release VERSION=0.1.0
   # or: ./scripts/release.sh 0.1.0
   ```

   This checks that both version fields match, updates `CHANGELOG.md`, and removes consumed fragments.

4. Commit, tag `v0.1.0`, and push.
