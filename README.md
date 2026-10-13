# anx-creator

`anx-creator` is a Codex skill and a Python standard-library CLI for creating and validating compact IBM i2 Analyst's Notebook `.anx` charts from canonical JSON. It accepts facts mapped from natural-language instructions, CSV, JSON, or XML and emits deterministic UTF-16LE chart XML.

The project targets a conservative Analyst's Notebook 7 XML subset used by Analyst's Notebook 9. It supports entities, links, typed attributes, basic styles, direction, metadata, and deterministic layout.

## Status and compatibility

- Python 3.10 or newer.
- Runtime dependencies: Python standard library only.
- User-reported successful direct opening in Analyst's Notebook 9.x; the exact build was not recorded.
- Local validation checks the generated subset, not complete vendor XSD conformance.
- Palettes, themes, cards, database proxies, time bars, and full saved-chart state are outside the current scope.

This is an unofficial community project. It is not affiliated with, endorsed by, or supported by IBM. IBM i2 Analyst's Notebook is an IBM product. Vendor schemas, binaries, documentation, and large vendor examples are not included.

## Install globally for Codex

Replace `YOUR_GITHUB_USERNAME` with the repository owner:

```bash
git clone \
  https://github.com/YOUR_GITHUB_USERNAME/anx-creator.git \
  "$HOME/.agents/skills/anx-creator"
```

Restart or refresh Codex skill discovery if the skill does not appear immediately. Invoke it explicitly with `$anx-creator`, or ask Codex to create or validate an Analyst's Notebook `.anx` chart.

Update an existing installation with:

```bash
git -C "$HOME/.agents/skills/anx-creator" pull --ff-only
```

## Use with Codex

Example prompt:

```text
Use $anx-creator to create an Analyst's Notebook chart from contacts.csv.
Preserve source IDs, keep calls undirected, and write the canonical JSON next to the ANX file.
```

The skill maps explicit source facts into the canonical format described in [`references/canonical-spec.md`](references/canonical-spec.md), runs the generator, validates the result, and reports assumptions.

## Use the CLI directly

Create a chart from the bundled example specification:

```bash
python3 scripts/anx_tool.py create \
  --spec references/example-spec.json \
  --output sample.anx
```

Validate a generated chart:

```bash
python3 scripts/anx_tool.py validate sample.anx
```

Existing output is refused by default. Use `--overwrite` only when replacement is intentional:

```bash
python3 scripts/anx_tool.py create \
  --spec references/example-spec.json \
  --output sample.anx \
  --overwrite
```

## Test

Run the portable test suite:

```bash
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

An optional comparison against separately licensed vendor examples is enabled only when their directory is supplied:

```bash
ANX_VENDOR_EXAMPLES_DIR=/path/to/vendor/examples \
  python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

For manual application checks, follow [`references/manual-verification.md`](references/manual-verification.md).

## Publish this repository

Initialize and commit the standalone repository:

```bash
git init -b main
git config user.name "anx-creator contributors"
git config user.email "noreply@anx-creator.invalid"
git add .
git diff --cached --check
git status --short
git commit -m "feat: publish anx-creator skill"
git tag -a v0.1.0 -m "anx-creator v0.1.0"
```

Publish with GitHub CLI:

```bash
brew install gh
gh auth login --web --git-protocol https
gh auth status

gh repo create YOUR_GITHUB_USERNAME/anx-creator \
  --public \
  --source=. \
  --remote=origin \
  --push \
  --description "Create and validate IBM i2 Analyst's Notebook ANX charts."

git push origin v0.1.0
gh repo view --web
```

Optionally create a GitHub release:

```bash
gh release create v0.1.0 \
  --title "anx-creator v0.1.0" \
  --notes "Initial public release."
```

Without GitHub CLI, create an empty public repository on GitHub without a generated README, license, or `.gitignore`, then run:

```bash
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/anx-creator.git
git push -u origin main
git push origin v0.1.0
```

## Українською

`anx-creator` — skill для Codex і CLI на стандартній бібліотеці Python, який створює та перевіряє компактні `.anx`-графи для IBM i2 Analyst's Notebook 9. Вхідні факти спочатку перетворюються на канонічний JSON, після чого генератор створює детермінований UTF-16LE XML.

Глобальне встановлення:

```bash
git clone \
  https://github.com/YOUR_GITHUB_USERNAME/anx-creator.git \
  "$HOME/.agents/skills/anx-creator"
```

Виклик у Codex: `$anx-creator`. Повна XSD-валідація не заявляється; для критичних сценаріїв виконайте ручну перевірку в Analyst's Notebook 9.

## License

MIT. See [`LICENSE`](LICENSE).
