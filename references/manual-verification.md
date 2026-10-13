# Analyst's Notebook 9 verification

Automated validation cannot prove that Analyst's Notebook accepts or renders a chart. When Windows with Analyst's Notebook 9 is available:

1. Preserve the generated file and source specification.
2. Open the `.anx` directly. Confirm no repair or schema warning appears.
3. Confirm entity count, link count, labels, endpoint direction, types, attributes, and positions.
4. If direct open fails, use **Data > Import from File > Import XML** with **Layout Imported Items** disabled first, because coordinates already exist.
5. Record exact application version and exact error text. Do not regenerate with guessed schema changes.
6. Re-run `python3 <skill-dir>/scripts/anx_tool.py validate <file.anx>` after any manual edit.

Known limitation: current macOS workspace has no Analyst's Notebook runtime. Successful local validation means structurally valid generated-subset XML, not application acceptance.

## Compatibility note

A generated chart has been reported as opening successfully in Analyst's Notebook 9.x. The exact application build was not recorded. Treat this as user-reported compatibility, not exhaustive certification, and repeat the checklist above for release-critical workflows.
