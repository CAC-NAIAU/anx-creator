#!/usr/bin/env python3
"""Create and validate compact IBM i2 Analyst's Notebook ANX chart XML."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import math
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


class AnxError(ValueError):
    pass


ROOT_KEYS = {"chart", "entity_types", "link_types", "attribute_classes", "entities", "links"}
CHART_KEYS = {"title"}
ENTITY_TYPE_KEYS = {"name", "icon", "colour"}
LINK_TYPE_KEYS = {"name", "colour"}
ATTRIBUTE_CLASS_KEYS = {
    "name", "type", "visible", "show_class_name", "prefix", "suffix", "decimal_places"
}
ENTITY_KEYS = {
    "id", "label", "identity", "type", "description", "source_reference", "datetime",
    "attributes", "style", "x", "y",
}
LINK_KEYS = {
    "id", "source", "target", "label", "type", "description", "source_reference",
    "datetime", "attributes", "style", "directed",
}
ENTITY_STYLE_KEYS = {"icon", "colour"}
LINK_STYLE_KEYS = {"line_width", "line_colour", "arrow_style"}
ATTRIBUTE_TYPES = {"text": "AttText", "number": "AttNumber", "date": "AttTime", "flag": "AttFlag"}
ARROW_STYLES = {"ArrowNone", "ArrowOnBoth", "ArrowOnHead", "ArrowOnTail"}
XML_ATTRIBUTE_TYPES = {value: key for key, value in ATTRIBUTE_TYPES.items()}


def fail(message: str) -> None:
    raise AnxError(message)


def require_object(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{where} must be an object")
    return value


def require_list(value: Any, where: str) -> list[Any]:
    if not isinstance(value, list):
        fail(f"{where} must be an array")
    return value


def check_keys(value: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        fail(f"{where} has unsupported field(s): {', '.join(unknown)}")


def text_value(value: Any, where: str, *, required: bool = False) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str):
        fail(f"{where} must be a string")
    if required and not value.strip():
        fail(f"{where} must not be empty")
    return value


def bool_value(value: Any, where: str) -> bool:
    if not isinstance(value, bool):
        fail(f"{where} must be a boolean")
    return value


def number_value(value: Any, where: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        fail(f"{where} must be a finite number")
    return value


def int_value(value: Any, where: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        fail(f"{where} must be an integer from {minimum} to {maximum}")
    return value


def validate_datetime(value: Any, where: str) -> str:
    raw = text_value(value, where, required=True)
    assert raw is not None
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            dt.date.fromisoformat(raw)
        else:
            dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        fail(f"{where} must be an ISO 8601 date or date-time: {exc}")
    return raw


def normalize_colour(value: Any, where: str) -> int:
    if isinstance(value, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        # ANB stores Windows COLORREF values: 0x00BBGGRR.
        red, green, blue = int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)
        return red | (green << 8) | (blue << 16)
    return int_value(value, where, 0, 4294967295)


def merge_value(existing: Any, incoming: Any, where: str) -> Any:
    if incoming is None or incoming == "":
        return existing
    if existing is None or existing == "":
        return copy.deepcopy(incoming)
    if isinstance(existing, dict) and isinstance(incoming, dict):
        merged = copy.deepcopy(existing)
        for key, value in incoming.items():
            merged[key] = merge_value(merged.get(key), value, f"{where}.{key}")
        return merged
    if existing != incoming:
        fail(f"conflicting duplicate value at {where}: {existing!r} != {incoming!r}")
    return existing


def normalize_named_records(
    raw: Any, where: str, allowed: set[str], required_name: str = "name"
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(require_list(raw, where)):
        record = require_object(item, f"{where}[{index}]")
        check_keys(record, allowed, f"{where}[{index}]")
        name = text_value(record.get(required_name), f"{where}[{index}].{required_name}", required=True)
        assert name is not None
        if name in seen:
            fail(f"duplicate {where} name: {name}")
        seen.add(name)
        records.append(copy.deepcopy(record))
    return records


def normalize_spec(raw: Any) -> dict[str, Any]:
    spec = require_object(raw, "spec")
    check_keys(spec, ROOT_KEYS, "spec")
    chart = require_object(spec.get("chart", {}), "chart")
    check_keys(chart, CHART_KEYS, "chart")
    if "title" in chart:
        text_value(chart["title"], "chart.title", required=True)

    entity_types = normalize_named_records(spec.get("entity_types", []), "entity_types", ENTITY_TYPE_KEYS)
    for index, record in enumerate(entity_types):
        if "icon" in record:
            text_value(record["icon"], f"entity_types[{index}].icon", required=True)
        if "colour" in record:
            record["colour"] = normalize_colour(record["colour"], f"entity_types[{index}].colour")
    link_types = normalize_named_records(spec.get("link_types", []), "link_types", LINK_TYPE_KEYS)
    for index, record in enumerate(link_types):
        if "colour" in record:
            record["colour"] = normalize_colour(record["colour"], f"link_types[{index}].colour")

    attribute_classes = normalize_named_records(
        spec.get("attribute_classes", []), "attribute_classes", ATTRIBUTE_CLASS_KEYS
    )
    attribute_map: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(attribute_classes):
        attr_type = text_value(record.get("type"), f"attribute_classes[{index}].type", required=True)
        if attr_type not in ATTRIBUTE_TYPES:
            fail(f"attribute_classes[{index}].type must be one of: {', '.join(ATTRIBUTE_TYPES)}")
        for key in ("visible", "show_class_name"):
            if key in record:
                bool_value(record[key], f"attribute_classes[{index}].{key}")
        for key in ("prefix", "suffix"):
            if key in record:
                text_value(record[key], f"attribute_classes[{index}].{key}")
        if "decimal_places" in record:
            int_value(record["decimal_places"], f"attribute_classes[{index}].decimal_places", 0, 15)
        attribute_map[record["name"]] = record

    entities: list[dict[str, Any]] = []
    entity_by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(require_list(spec.get("entities", []), "entities")):
        record = require_object(item, f"entities[{index}]")
        check_keys(record, ENTITY_KEYS, f"entities[{index}]")
        entity_id = text_value(record.get("id"), f"entities[{index}].id", required=True)
        assert entity_id is not None
        normalized = copy.deepcopy(record)
        normalized["id"] = entity_id
        if entity_id in entity_by_id:
            merged = merge_value(entity_by_id[entity_id], normalized, f"entity {entity_id}")
            entity_by_id[entity_id].clear()
            entity_by_id[entity_id].update(merged)
        else:
            entity_by_id[entity_id] = normalized
            entities.append(normalized)

    if not entities:
        fail("entities must contain at least one entity")

    entity_ids = set(entity_by_id)
    links: list[dict[str, Any]] = []
    link_by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(require_list(spec.get("links", []), "links")):
        record = require_object(item, f"links[{index}]")
        check_keys(record, LINK_KEYS, f"links[{index}]")
        link_id = text_value(record.get("id"), f"links[{index}].id", required=True)
        source = text_value(record.get("source"), f"links[{index}].source", required=True)
        target = text_value(record.get("target"), f"links[{index}].target", required=True)
        assert link_id is not None and source is not None and target is not None
        if source not in entity_ids or target not in entity_ids:
            missing = [value for value in (source, target) if value not in entity_ids]
            fail(f"link {link_id} references missing entity ID(s): {', '.join(missing)}")
        normalized = copy.deepcopy(record)
        normalized.update({"id": link_id, "source": source, "target": target})
        if link_id in link_by_id:
            merged = merge_value(link_by_id[link_id], normalized, f"link {link_id}")
            link_by_id[link_id].clear()
            link_by_id[link_id].update(merged)
        else:
            link_by_id[link_id] = normalized
            links.append(normalized)

    for kind, records, allowed_style in (
        ("entities", entities, ENTITY_STYLE_KEYS), ("links", links, LINK_STYLE_KEYS)
    ):
        for index, record in enumerate(records):
            for key in ("label", "identity", "type", "description", "source_reference"):
                if key in record:
                    text_value(record[key], f"{kind}[{index}].{key}")
            if "datetime" in record:
                record["datetime"] = validate_datetime(record["datetime"], f"{kind}[{index}].datetime")
            attrs = require_object(record.get("attributes", {}), f"{kind}[{index}].attributes")
            for name, value in attrs.items():
                if name not in attribute_map:
                    fail(f"{kind}[{index}] uses undeclared attribute class: {name}")
                validate_attribute_value(value, attribute_map[name]["type"], f"{kind}[{index}].attributes.{name}")
            style = require_object(record.get("style", {}), f"{kind}[{index}].style")
            check_keys(style, allowed_style, f"{kind}[{index}].style")
            if kind == "entities":
                if "icon" in style:
                    text_value(style["icon"], f"{kind}[{index}].style.icon", required=True)
                if "colour" in style:
                    style["colour"] = normalize_colour(style["colour"], f"{kind}[{index}].style.colour")
                has_x, has_y = "x" in record, "y" in record
                if has_x != has_y:
                    fail(f"{kind}[{index}] must provide both x and y")
                if has_x:
                    record["x"] = number_value(record["x"], f"{kind}[{index}].x")
                    record["y"] = number_value(record["y"], f"{kind}[{index}].y")
            else:
                if "directed" in record:
                    bool_value(record["directed"], f"{kind}[{index}].directed")
                if "line_width" in style:
                    int_value(style["line_width"], f"{kind}[{index}].style.line_width", 1, 20)
                if "line_colour" in style:
                    style["line_colour"] = normalize_colour(
                        style["line_colour"], f"{kind}[{index}].style.line_colour"
                    )
                if "arrow_style" in style:
                    arrow = text_value(style["arrow_style"], f"{kind}[{index}].style.arrow_style", required=True)
                    if arrow not in ARROW_STYLES:
                        fail(f"{kind}[{index}].style.arrow_style must be one of: {', '.join(sorted(ARROW_STYLES))}")

    declared_entity_types = {record["name"] for record in entity_types}
    for record in entities:
        type_name = record.get("type") or "General"
        record["type"] = type_name
        if type_name not in declared_entity_types:
            entity_types.append({"name": type_name, "icon": "General"})
            declared_entity_types.add(type_name)

    declared_link_types = {record["name"] for record in link_types}
    for record in links:
        type_name = record.get("type") or "Link"
        record["type"] = type_name
        if type_name not in declared_link_types:
            link_types.append({"name": type_name})
            declared_link_types.add(type_name)

    assign_positions(entities, links)
    return {
        "chart": copy.deepcopy(chart),
        "entity_types": entity_types,
        "link_types": link_types,
        "attribute_classes": attribute_classes,
        "entities": entities,
        "links": links,
    }


def validate_attribute_value(value: Any, attr_type: str, where: str) -> None:
    if attr_type == "text":
        text_value(value, where)
    elif attr_type == "number":
        number_value(value, where)
    elif attr_type == "date":
        validate_datetime(value, where)
    elif attr_type == "flag":
        bool_value(value, where)


def assign_positions(entities: list[dict[str, Any]], links: list[dict[str, Any]]) -> None:
    order = {record["id"]: index for index, record in enumerate(entities)}
    adjacency = {entity_id: set() for entity_id in order}
    for link in links:
        adjacency[link["source"]].add(link["target"])
        adjacency[link["target"]].add(link["source"])

    visited: set[str] = set()
    components: list[list[str]] = []
    for entity_id in order:
        if entity_id in visited:
            continue
        stack, component = [entity_id], []
        visited.add(entity_id)
        while stack:
            current = stack.pop()
            component.append(current)
            for neighbor in sorted(adjacency[current], key=order.get, reverse=True):
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        component.sort(key=order.get)
        components.append(component)

    records = {record["id"]: record for record in entities}
    cursor_x = 0.0
    spacing_x, spacing_y, columns = 160.0, 120.0, 5
    occupied = {
        (float(record["x"]), float(record["y"]))
        for record in entities if "x" in record and "y" in record
    }
    for component in components:
        unplaced = [entity_id for entity_id in component if "x" not in records[entity_id]]
        cell = 0
        for entity_id in unplaced:
            while True:
                x = cursor_x + (cell % columns) * spacing_x
                y = (cell // columns) * spacing_y
                cell += 1
                if (x, y) not in occupied:
                    break
            records[entity_id]["x"], records[entity_id]["y"] = x, y
            occupied.add((x, y))
        explicit_x = [float(records[value]["x"]) for value in component]
        grid_width = max(1, min(columns, len(component))) * spacing_x
        cursor_x = max(cursor_x + grid_width + spacing_x, max(explicit_x) + spacing_x)


def xml_bool(value: bool) -> str:
    return "true" if value else "false"


def xml_number(value: int | float) -> str:
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    return format(value, ".15g")


def serialize_attribute(value: Any, attr_type: str) -> str:
    if attr_type == "flag":
        return xml_bool(value)
    if attr_type == "number":
        return xml_number(value)
    return str(value)


def set_optional(attributes: dict[str, str], name: str, value: Any) -> None:
    if value is not None and value != "":
        attributes[name] = str(value)


def build_xml(spec: dict[str, Any]) -> bytes:
    root = ET.Element("Chart", {"Rigorous": "true", "IdReferenceLinking": "false"})

    if spec["attribute_classes"]:
        collection = ET.SubElement(root, "AttributeClassCollection")
        for record in spec["attribute_classes"]:
            attrs = {"Name": record["name"], "Type": ATTRIBUTE_TYPES[record["type"]]}
            if "visible" in record:
                attrs["Visible"] = xml_bool(record["visible"])
            if "show_class_name" in record:
                attrs["ShowClassName"] = xml_bool(record["show_class_name"])
            if "prefix" in record:
                attrs["Prefix"] = record["prefix"]
            if "suffix" in record:
                attrs["Suffix"] = record["suffix"]
            if "decimal_places" in record:
                attrs["DecimalPlaces"] = str(record["decimal_places"])
            ET.SubElement(collection, "AttributeClass", attrs)

    entity_types = ET.SubElement(root, "EntityTypeCollection")
    for record in spec["entity_types"]:
        attrs = {
            "Name": record["name"],
            "IconFile": record.get("icon", "General"),
            "PreferredRepresentation": "RepresentAsIcon",
            "Colour": str(record.get("colour", 0)),
        }
        ET.SubElement(entity_types, "EntityType", attrs)

    link_types = ET.SubElement(root, "LinkTypeCollection")
    for record in spec["link_types"]:
        ET.SubElement(link_types, "LinkType", {"Name": record["name"], "Colour": str(record.get("colour", 0))})

    title = spec["chart"].get("title")
    if title:
        summary = ET.SubElement(root, "Summary")
        fields = ET.SubElement(summary, "FieldCollection")
        ET.SubElement(fields, "Field", {"Field": title, "Type": "SummaryFieldTitle"})

    chart_items = ET.SubElement(root, "ChartItemCollection")
    attribute_types = {record["name"]: record["type"] for record in spec["attribute_classes"]}
    for record in spec["entities"]:
        item_attrs = {"Label": record.get("label") or record.get("identity") or record["id"]}
        add_item_metadata(item_attrs, record)
        item_attrs["XPosition"] = xml_number(record["x"])
        chart_item = ET.SubElement(chart_items, "ChartItem", item_attrs)
        end = ET.SubElement(chart_item, "End", {
            "X": xml_number(record["x"]), "Y": xml_number(record["y"]), "Z": "0"
        })
        label = record.get("label") or record.get("identity") or record["id"]
        identity = record.get("identity") or label
        entity = ET.SubElement(end, "Entity", {
            "EntityId": record["id"],
            "Identity": identity,
            "LabelIsIdentity": xml_bool(identity == label),
        })
        icon = ET.SubElement(entity, "Icon")
        style_attrs = {"Type": record["type"]}
        style = record.get("style", {})
        if "icon" in style:
            style_attrs.update({"OverrideTypeIcon": "true", "TypeIconName": style["icon"]})
        if "colour" in style:
            style_attrs["IconShadingColour"] = str(style["colour"])
        ET.SubElement(icon, "IconStyle", style_attrs)
        add_attributes(chart_item, record.get("attributes", {}), attribute_types)

    for record in spec["links"]:
        item_attrs = {"Label": record.get("label") or record["type"]}
        add_item_metadata(item_attrs, record)
        chart_item = ET.SubElement(chart_items, "ChartItem", item_attrs)
        link = ET.SubElement(chart_item, "Link", {"End1Id": record["source"], "End2Id": record["target"]})
        style = record.get("style", {})
        arrow_style = style.get("arrow_style")
        if arrow_style is None:
            arrow_style = "ArrowOnHead" if record.get("directed", False) else "ArrowNone"
        style_attrs = {"Type": record["type"], "ArrowStyle": arrow_style}
        if "line_width" in style:
            style_attrs["LineWidth"] = str(style["line_width"])
        if "line_colour" in style:
            style_attrs["LineColour"] = str(style["line_colour"])
        ET.SubElement(link, "LinkStyle", style_attrs)
        add_attributes(chart_item, record.get("attributes", {}), attribute_types)

    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    body = re.sub(r" />", "/>", body).replace("\n", "\r\n")
    document = '<?xml version="1.0" encoding="UTF-16"?>\r\n' + body + "\r\n"
    return b"\xff\xfe" + document.encode("utf-16le")


def add_item_metadata(attributes: dict[str, str], record: dict[str, Any]) -> None:
    set_optional(attributes, "Description", record.get("description"))
    set_optional(attributes, "SourceReference", record.get("source_reference"))
    if record.get("datetime"):
        value = record["datetime"]
        attributes["DateTime"] = value
        attributes["DateSet"] = "true"
        attributes["TimeSet"] = xml_bool("T" in value)


def add_attributes(parent: ET.Element, values: dict[str, Any], types: dict[str, str]) -> None:
    if not values:
        return
    collection = ET.SubElement(parent, "AttributeCollection")
    for name, value in values.items():
        ET.SubElement(collection, "Attribute", {
            "AttributeClass": name,
            "Value": serialize_attribute(value, types[name]),
        })


def parse_anx(path: Path) -> ET.Element:
    data = path.read_bytes()
    if not data.startswith((b"\xff\xfe", b"\xfe\xff")):
        fail("ANX must be UTF-16 with a byte-order mark")
    try:
        text = data.decode("utf-16")
    except UnicodeDecodeError as exc:
        fail(f"invalid UTF-16: {exc}")
    if "<!DOCTYPE" in text.upper():
        fail("DOCTYPE is not allowed")
    if not re.match(r"\s*<\?xml[^>]+encoding=[\"']UTF-16[\"']", text, re.IGNORECASE):
        fail("XML declaration must specify UTF-16")
    try:
        return ET.fromstring(text)
    except ET.ParseError as exc:
        fail(f"invalid XML: {exc}")


def validate_anx(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"file does not exist: {path}")
    root = parse_anx(path)
    if root.tag != "Chart":
        fail("root element must be Chart")
    if root.get("Rigorous") != "true" or root.get("IdReferenceLinking") != "false":
        fail('Chart must have Rigorous="true" and IdReferenceLinking="false"')

    entity_types = {node.get("Name") for node in root.findall("./EntityTypeCollection/EntityType")}
    link_types = {node.get("Name") for node in root.findall("./LinkTypeCollection/LinkType")}
    attribute_classes = {
        node.get("Name"): XML_ATTRIBUTE_TYPES.get(node.get("Type", ""))
        for node in root.findall("./AttributeClassCollection/AttributeClass")
    }
    if None in entity_types or None in link_types or None in attribute_classes:
        fail("type and attribute-class definitions require names")

    items = root.findall("./ChartItemCollection/ChartItem")
    entity_ids: set[str] = set()
    saw_link = False
    entity_count = link_count = 0
    for index, item in enumerate(items):
        entity = item.find("./End/Entity")
        link = item.find("./Link")
        if (entity is None) == (link is None):
            fail(f"ChartItem[{index}] must contain exactly one End/Entity or Link")
        if entity is not None:
            if saw_link:
                fail("entity ChartItems must precede link ChartItems")
            entity_id = entity.get("EntityId")
            if not entity_id:
                fail(f"entity ChartItem[{index}] requires EntityId")
            if entity_id in entity_ids:
                fail(f"duplicate EntityId: {entity_id}")
            entity_ids.add(entity_id)
            entity_count += 1
            icon_style = entity.find("./Icon/IconStyle")
            if icon_style is None or icon_style.get("Type") not in entity_types:
                fail(f"entity {entity_id} uses undeclared entity type")
            end = item.find("./End")
            assert end is not None
            for coordinate in ("X", "Y"):
                try:
                    number_value(float(end.get(coordinate, "")), f"entity {entity_id} {coordinate}")
                except ValueError:
                    fail(f"entity {entity_id} has invalid {coordinate} coordinate")
        else:
            saw_link = True
            link_count += 1
            style = link.find("./LinkStyle")
            if style is None or style.get("Type") not in link_types:
                fail(f"link ChartItem[{index}] uses undeclared link type")
            if style.get("ArrowStyle") not in ARROW_STYLES:
                fail(f"link ChartItem[{index}] has invalid ArrowStyle")

        for attribute in item.findall("./AttributeCollection/Attribute"):
            name, value = attribute.get("AttributeClass"), attribute.get("Value")
            if name not in attribute_classes or attribute_classes[name] is None:
                fail(f"ChartItem[{index}] uses undeclared or invalid attribute class: {name}")
            validate_xml_attribute(value, attribute_classes[name], f"ChartItem[{index}] attribute {name}")

    for index, item in enumerate(items):
        link = item.find("./Link")
        if link is None:
            continue
        missing = [link.get(name) for name in ("End1Id", "End2Id") if link.get(name) not in entity_ids]
        if missing:
            fail(f"link ChartItem[{index}] has dangling endpoint(s): {', '.join(str(x) for x in missing)}")

    return {
        "path": str(path.resolve()),
        "entities": entity_count,
        "links": link_count,
        "entity_types": len(entity_types),
        "link_types": len(link_types),
        "attribute_classes": len(attribute_classes),
        "valid": True,
    }


def validate_xml_attribute(value: str | None, attr_type: str, where: str) -> None:
    if value is None:
        fail(f"{where} requires Value")
    if attr_type == "number":
        try:
            number_value(float(value), where)
        except ValueError:
            fail(f"{where} must be numeric")
    elif attr_type == "date":
        validate_datetime(value, where)
    elif attr_type == "flag" and value not in {"true", "false"}:
        fail(f"{where} must be true or false")


def write_output(path: Path, data: bytes, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        fail(f"output already exists: {path}; pass --overwrite only with explicit authorization")
    if path.suffix.lower() != ".anx":
        fail("output filename must end with .anx")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def load_spec(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"spec file does not exist: {path}")
    except UnicodeDecodeError as exc:
        fail(f"spec must be UTF-8: {exc}")
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON spec: {exc}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create", help="create an ANX file from canonical JSON")
    create.add_argument("--spec", required=True, type=Path)
    create.add_argument("--output", required=True, type=Path)
    create.add_argument("--overwrite", action="store_true")
    validate = subparsers.add_parser("validate", help="validate an ANX file")
    validate.add_argument("path", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "create":
            spec = normalize_spec(load_spec(args.spec))
            write_output(args.output, build_xml(spec), args.overwrite)
            summary = validate_anx(args.output)
        else:
            summary = validate_anx(args.path)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0
    except (AnxError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
