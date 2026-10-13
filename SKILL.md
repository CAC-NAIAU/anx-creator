---
name: anx-creator
description: Create or validate IBM i2 Analyst's Notebook `.anx` chart files from natural-language descriptions or CSV, JSON, and XML data. Use for entity-link charts targeting Analyst's Notebook 9; not for complete saved-chart features such as palettes, themes, cards, database proxies, or time bars.
---

# ANX Creator

Create compact Analyst's Notebook chart XML with the `.anx` extension. Target the conservative Analyst's Notebook 7 XML subset observed in Analyst's Notebook 9-compatible samples.

## Workflow

1. Inspect the user's prompt and source files. For unfamiliar tabular or XML shapes, identify candidate entity IDs, labels, types, relationship endpoints, and metadata.
2. Infer a mapping when one interpretation is clearly strongest. Report the mapping and assumptions briefly. Ask only when different interpretations would materially change graph meaning.
3. Read [references/canonical-spec.md](references/canonical-spec.md), create a canonical JSON specification, resolve `<skill-dir>` to the directory containing this `SKILL.md`, and run:

   ```bash
   python3 <skill-dir>/scripts/anx_tool.py create --spec <spec.json> --output <chart.anx>
   ```

4. Validate the result:

   ```bash
   python3 <skill-dir>/scripts/anx_tool.py validate <chart.anx>
   ```

5. Return the `.anx` path plus entity/link counts and any assumptions. Never claim direct-open verification unless the file was actually opened in Analyst's Notebook.

## Mapping Rules

- Preserve explicit source IDs. When none exist, create deterministic IDs from stable source values and document the choice.
- Merge repeated entities by ID only. Combine equal or missing values; stop on conflicting non-empty values.
- Preserve parallel relationships. Reject conflicting duplicate link IDs.
- Default links to undirected. Set `directed: true` only from explicit source data or user instruction.
- Preserve supplied coordinates. Let the generator place remaining entities deterministically.
- Preserve source order in the canonical specification; the generator uses stable ordering for repeatable bytes.
- Use `General` as missing entity icon/type fallback and `Link` as missing link type.
- Never overwrite an existing output unless the user explicitly requests replacement and `--overwrite` is passed.

## Supported Surface

Support entities, links, labels, types, descriptions, source references, ISO 8601 date/time values, typed attributes, basic icon/colour/line styles, direction, and coordinates. For precise field shapes and limits, read [references/canonical-spec.md](references/canonical-spec.md). For generated XML behavior, read [references/anx-format.md](references/anx-format.md).

Do not generate palettes, themes, cards, database proxies, time bars, or other full saved-chart state. If requested, explain this v1 boundary rather than silently dropping data.

## Validation Boundary

The bundled validator checks encoding, XML structure, generated-subset rules, IDs, endpoint references, type declarations, attribute declarations, and value types. Some vendor XSD distributions depend on `i2 Semantic Type Library.xsd`, which is not bundled; therefore do not describe validation as complete XSD validation.

For manual application verification, read [references/manual-verification.md](references/manual-verification.md). Vendor schemas, binaries, documentation, and large examples are not bundled. If independently licensed vendor material is available locally, inspect it only when deeper schema detail is needed.
