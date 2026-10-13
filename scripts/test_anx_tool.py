#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import anx_tool


def base_spec() -> dict:
    return {
        "chart": {"title": "Unicode & <test> — Київ"},
        "entity_types": [{"name": "Person", "icon": "Person", "colour": "#112233"}],
        "link_types": [{"name": "Contact"}],
        "attribute_classes": [
            {"name": "Note", "type": "text"},
            {"name": "Score", "type": "number", "decimal_places": 1},
            {"name": "Seen", "type": "date"},
            {"name": "Reviewed", "type": "flag"},
        ],
        "entities": [
            {
                "id": "p1", "label": "Alice & Bob", "type": "Person", "x": -10, "y": 20,
                "attributes": {
                    "Note": "A < B", "Score": 7.5, "Seen": "2026-10-11", "Reviewed": True,
                },
            },
            {"id": "p2", "label": "Богдан", "type": "Person"},
        ],
        "links": [
            {"id": "l1", "source": "p1", "target": "p2", "label": "called", "type": "Contact"},
            {
                "id": "l2", "source": "p1", "target": "p2", "label": "emailed",
                "type": "Contact", "directed": True, "style": {"line_width": 2},
            },
        ],
    }


class AnxToolTests(unittest.TestCase):
    def test_deterministic_generation_and_validation(self) -> None:
        normalized_a = anx_tool.normalize_spec(base_spec())
        normalized_b = anx_tool.normalize_spec(base_spec())
        output_a = anx_tool.build_xml(normalized_a)
        output_b = anx_tool.build_xml(normalized_b)
        self.assertEqual(output_a, output_b)
        self.assertTrue(output_a.startswith(b"\xff\xfe"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "chart.anx"
            path.write_bytes(output_a)
            summary = anx_tool.validate_anx(path)
        self.assertEqual(summary["entities"], 2)
        self.assertEqual(summary["links"], 2)
        text = output_a.decode("utf-16")
        self.assertIn("Alice &amp; Bob", text)
        self.assertIn("Київ", text)
        self.assertIn('ArrowStyle="ArrowNone"', text)
        self.assertIn('ArrowStyle="ArrowOnHead"', text)
        self.assertIn('X="-10" Y="20"', text)

    def test_duplicate_entities_merge_compatible_values(self) -> None:
        spec = base_spec()
        spec["entities"].append({"id": "p2", "description": "Merged"})
        normalized = anx_tool.normalize_spec(spec)
        self.assertEqual(len(normalized["entities"]), 2)
        self.assertEqual(normalized["entities"][1]["description"], "Merged")

    def test_identity_can_differ_from_label(self) -> None:
        spec = base_spec()
        spec["entities"][0]["identity"] = "person:canonical-alice"
        text = anx_tool.build_xml(anx_tool.normalize_spec(spec)).decode("utf-16")
        self.assertIn('Identity="person:canonical-alice" LabelIsIdentity="false"', text)

    def test_inferred_type_uses_general_icon(self) -> None:
        spec = base_spec()
        spec["entity_types"] = []
        text = anx_tool.build_xml(anx_tool.normalize_spec(spec)).decode("utf-16")
        self.assertIn('EntityType Name="Person" IconFile="General"', text)

    def test_duplicate_entities_reject_conflicts(self) -> None:
        spec = base_spec()
        spec["entities"].append({"id": "p2", "label": "Different"})
        with self.assertRaisesRegex(anx_tool.AnxError, "conflicting duplicate"):
            anx_tool.normalize_spec(spec)

    def test_dangling_endpoint_rejected(self) -> None:
        spec = base_spec()
        spec["links"][0]["target"] = "missing"
        with self.assertRaisesRegex(anx_tool.AnxError, "missing entity"):
            anx_tool.normalize_spec(spec)

    def test_unknown_and_invalid_attribute_rejected(self) -> None:
        spec = base_spec()
        spec["entities"][0]["unknown"] = 1
        with self.assertRaisesRegex(anx_tool.AnxError, "unsupported field"):
            anx_tool.normalize_spec(spec)
        spec = base_spec()
        spec["entities"][0]["attributes"]["Score"] = "high"
        with self.assertRaisesRegex(anx_tool.AnxError, "finite number"):
            anx_tool.normalize_spec(spec)

    def test_coordinates_require_pair(self) -> None:
        spec = base_spec()
        del spec["entities"][0]["y"]
        with self.assertRaisesRegex(anx_tool.AnxError, "both x and y"):
            anx_tool.normalize_spec(spec)

    def test_overwrite_refused(self) -> None:
        data = anx_tool.build_xml(anx_tool.normalize_spec(base_spec()))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "chart.anx"
            anx_tool.write_output(path, data, False)
            with self.assertRaisesRegex(anx_tool.AnxError, "already exists"):
                anx_tool.write_output(path, data, False)

    def test_bad_encoding_and_dangling_generated_xml_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "bad.anx"
            bad.write_text("<Chart/>", encoding="utf-8")
            with self.assertRaisesRegex(anx_tool.AnxError, "UTF-16"):
                anx_tool.validate_anx(bad)

            normalized = anx_tool.normalize_spec(base_spec())
            text = anx_tool.build_xml(normalized).decode("utf-16").replace('End2Id="p2"', 'End2Id="missing"', 1)
            dangling = Path(directory) / "dangling.anx"
            dangling.write_bytes(b"\xff\xfe" + text.encode("utf-16le"))
            with self.assertRaisesRegex(anx_tool.AnxError, "dangling endpoint"):
                anx_tool.validate_anx(dangling)

    def test_external_source_fixtures_are_readable(self) -> None:
        fixtures = Path(__file__).resolve().parents[1] / "references" / "fixtures"
        self.assertIn("record_type", (fixtures / "contacts.csv").read_text(encoding="utf-8"))
        self.assertIn("relationships", json.loads((fixtures / "contacts.json").read_text(encoding="utf-8")))
        self.assertEqual(ET.parse(fixtures / "contacts.xml").getroot().tag, "contacts")

    def test_generated_shape_matches_vendor_examples(self) -> None:
        configured = os.environ.get("ANX_VENDOR_EXAMPLES_DIR")
        if not configured:
            self.skipTest("set ANX_VENDOR_EXAMPLES_DIR to run vendor comparison")
        examples = Path(configured)
        if not examples.is_dir():
            self.skipTest("ANX_VENDOR_EXAMPLES_DIR is not a directory")
        generated = ET.fromstring(anx_tool.build_xml(anx_tool.normalize_spec(base_spec())).decode("utf-16"))
        sample = ET.parse(examples / "Fraud transformed.anx").getroot()
        for path in (
            "./ChartItemCollection/ChartItem/End/Entity/Icon/IconStyle",
            "./ChartItemCollection/ChartItem/Link/LinkStyle",
        ):
            self.assertIsNotNone(generated.find(path))
            self.assertIsNotNone(sample.find(path))


if __name__ == "__main__":
    unittest.main()
