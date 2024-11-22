import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from promote import validate_charts, get_charts_from_overlays

overlay_no_name_or_version = [{"name": "lighthouse", "overlays": ["bar"]}]
overlay_new_name = [
    {"name": "lighthouse", "releaseName": "tillamook", "overlays": ["bar"]}
]
overlay_new_version = [{"name": "lighthouse", "version": "1.0.0", "overlays": ["bar"]}]
overlay_new_name_and_version = [
    {
        "name": "lighthouse",
        "releaseName": "tillamook",
        "version": "1.0.0",
        "overlays": ["bar"],
    }
]


class TestValidateChartsFromOverlays(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(validate_charts([]), True)

    def test_only_new_name(self):
        self.assertEqual(
            validate_charts(overlay_new_name),
            False,
        )

    def test_only_new_version(self):
        self.assertEqual(
            validate_charts(overlay_new_version),
            True,
        )

    def test_missing_new_name_and_version(self):
        self.assertEqual(validate_charts(overlay_no_name_or_version), False)

    def test_new_name_and_version(self):
        self.assertEqual(validate_charts(overlay_new_name_and_version), True)


class TestGetChartsFromOverlays(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(get_charts_from_overlays([], "."), {})

    def test_missing_new_name(self):
        self.assertEqual(
            get_charts_from_overlays(overlay_no_name_or_version, "."),
            {"bar": [{"name": "lighthouse", "overlays": ["bar"]}]},
        )

    def test_new_name(self):
        self.assertEqual(
            get_charts_from_overlays(overlay_new_name, "."),
            {
                "bar": [
                    {
                        "name": "lighthouse",
                        "releaseName": "tillamook",
                        "overlays": ["bar"],
                    }
                ]
            },
        )

    def test_new_tag(self):
        self.assertEqual(
            get_charts_from_overlays(overlay_new_version, "."),
            {"bar": [{"name": "lighthouse", "version": "1.0.0", "overlays": ["bar"]}]},
        )

    def test_new_name_and_tag(self):
        self.assertEqual(
            get_charts_from_overlays(overlay_new_name_and_version, "."),
            {
                "bar": [
                    {
                        "name": "lighthouse",
                        "releaseName": "tillamook",
                        "version": "1.0.0",
                        "overlays": ["bar"],
                    }
                ]
            },
        )
