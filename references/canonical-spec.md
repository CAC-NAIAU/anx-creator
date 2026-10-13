# Canonical JSON specification

Create this UTF-8 JSON before invoking `scripts/anx_tool.py create`.

```json
{
  "chart": {"title": "Example investigation"},
  "entity_types": [
    {"name": "Person", "icon": "Person", "colour": "#4472C4"}
  ],
  "link_types": [
    {"name": "Contact", "colour": "#666666"}
  ],
  "attribute_classes": [
    {"name": "Risk score", "type": "number", "decimal_places": 1},
    {"name": "Reviewed", "type": "flag"}
  ],
  "entities": [
    {
      "id": "person-1",
      "label": "Alice",
      "identity": "Alice Example",
      "type": "Person",
      "description": "Primary subject",
      "source_reference": "Source A",
      "datetime": "2026-10-11T09:30:00Z",
      "attributes": {"Risk score": 7.5, "Reviewed": true},
      "style": {"icon": "Person", "colour": "#4472C4"},
      "x": 0,
      "y": 0
    }
  ],
  "links": [
    {
      "id": "contact-1",
      "source": "person-1",
      "target": "person-2",
      "label": "called",
      "type": "Contact",
      "directed": true,
      "description": "Recorded call",
      "source_reference": "Call log 1",
      "attributes": {},
      "style": {"line_width": 2, "line_colour": "#666666"}
    }
  ]
}
```

## Top-level fields

- `chart`: optional object. `title` becomes `SummaryFieldTitle`.
- `entity_types`, `link_types`, `attribute_classes`: optional definition arrays. Missing entity/link types used by records are declared automatically.
- `entities`: required non-empty array.
- `links`: optional array.

Unknown fields are errors. Strings used as IDs or names must not be empty.

## Definitions

Entity type fields:

- `name`: required and unique.
- `icon`: installed Analyst's Notebook icon name without extension. Default `General`.
- `colour`: integer `0..4294967295` or `#RRGGBB`. Hex is converted to Windows COLORREF.

Generated v1 entities use icon representation. Other Analyst's Notebook representations are outside this skill's supported subset.

Link type fields:

- `name`: required and unique.
- `colour`: integer or `#RRGGBB`.

Attribute class fields:

- `name`: required and unique.
- `type`: required; `text`, `number`, `date`, or `flag`.
- `visible`, `show_class_name`: optional booleans.
- `prefix`, `suffix`: optional strings.
- `decimal_places`: optional integer `0..15` for numeric attributes.

Every key used in an entity or link `attributes` object must have a declaration. Values must match the declared type. Dates accept ISO 8601 dates or date-times.

## Entities

- `id`: required stable identity used by link endpoints.
- `label`, `identity`, `type`, `description`, `source_reference`, `datetime`: optional strings. Defaults are ID for label/identity and `General` for type.
- `attributes`: optional object keyed by attribute-class name.
- `style`: optional object with `icon` and `colour`.
- `x`, `y`: optional finite numbers. Supply both or neither.

Repeated IDs merge only when their non-empty values agree. Conflicts are errors.

## Links

- `id`, `source`, `target`: required strings. Endpoints must name entities.
- `label`, `type`, `description`, `source_reference`, `datetime`: optional strings. Type defaults to `Link`.
- `directed`: optional boolean, default `false`. Directed links use `ArrowOnHead`, pointing to `target`.
- `attributes`: optional object keyed by attribute-class name.
- `style`: optional `line_width` (`1..20`), `line_colour`, and `arrow_style`.
- `arrow_style`: `ArrowNone`, `ArrowOnBoth`, `ArrowOnHead`, or `ArrowOnTail`; explicit value overrides `directed` rendering.

Parallel links are preserved. Duplicate link IDs merge only when values agree.

## Mapping external data

- CSV/TSV: identify entity rows versus relationship rows or build entities from endpoint columns. Preserve original record IDs when stable.
- JSON: map object keys directly; expand nested endpoint objects into entities before links.
- XML: map repeated business elements, not formatting/container elements. Preserve namespaces only as source context; canonical JSON has no namespaces.
- Free text: use only explicit facts. Do not invent relationships, dates, IDs, or direction.

When IDs are absent, derive deterministic IDs from stable values, for example `person:alice-example`. Report that choice before generation.
