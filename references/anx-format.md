# Generated ANX subset

Output is UTF-16LE XML with BOM and `.anx` extension. Root is:

```xml
<Chart Rigorous="true" IdReferenceLinking="false">
```

Children appear in conservative schema order:

1. `AttributeClassCollection` when attributes exist.
2. `EntityTypeCollection`.
3. `LinkTypeCollection`.
4. `Summary` when title exists.
5. `ChartItemCollection`.

Entity chart items precede link chart items. Entities use `EntityId`; links use `End1Id` and `End2Id`. This mirrors non-IDREF import examples while retaining rigorous, unique entity identities after deduplication.

Entity representation is an `End` containing `Entity`, `Icon`, and `IconStyle`. Link representation is `Link` containing `LinkStyle`. Basic metadata stays on `ChartItem`. Typed instances use `AttributeCollection` and `Attribute`.

## Layout

User coordinates are preserved. Remaining entities are grouped by connected component and assigned deterministic grid cells. Grid spacing is 160 world-coordinate units horizontally and 120 vertically, with five columns per component.

## Validation limits

Validator checks generated subset, not complete Analyst's Notebook schema. It verifies:

- UTF-16 BOM and declaration.
- XML well-formedness and no `DOCTYPE`.
- Expected root flags.
- Entity-before-link ordering.
- Unique entity IDs and resolved link endpoints.
- Declared entity/link types.
- Declared and correctly typed attributes.
- Numeric coordinates and supported arrow styles.

Some vendor XSD distributions import `i2 Semantic Type Library.xsd`, which is not bundled. Do not report full XSD conformance. Vendor schemas, binaries, documentation, and large samples are intentionally excluded from this project.
