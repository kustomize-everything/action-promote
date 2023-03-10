import unittest
import promote as promote

overlay_no_name_or_tag = [{"name": "foo", "overlays": ["bar"]}]
overlay_new_name = [{"name": "foo", "newName": "quz", "overlays": ["bar"]}]
overlay_new_tag = [{"name": "foo", "newTag": "whizbang", "overlays": ["bar"]}]
overlay_new_name_and_tag = [
    {"name": "foo", "newName": "quz", "newTag": "whizbang", "overlays": ["bar"]}
]


class TestValidateImagesFromOverlays(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(promote.validate_images([]), True)

    def test_only_new_name(self):
        self.assertEqual(
            promote.validate_images(
                [{"name": "foo", "newName": "quz", "overlays": ["bar"]}]
            ),
            True,
        )

    def test_only_new_tag(self):
        self.assertEqual(
            promote.validate_images(
                [{"name": "foo", "newTag": "whizbang", "overlays": ["bar"]}]
            ),
            True,
        )

    def test_missing_new_name_and_new_tag(self):
        self.assertEqual(
            promote.validate_images([{"name": "foo", "overlays": ["bar"]}]), False
        )


class TestGetImagesFromOverlays(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(promote.get_images_from_overlays([], "."), {})

    def test_missing_new_name(self):
        self.assertEqual(
            promote.get_images_from_overlays(overlay_no_name_or_tag, "."),
            {"bar": [{"name": "foo", "overlays": ["bar"]}]},
        )

    def test_new_name(self):
        self.assertEqual(
            promote.get_images_from_overlays(overlay_new_name, "."),
            {"bar": [{"name": "foo", "newName": "quz", "overlays": ["bar"]}]},
        )

    def test_new_tag(self):
        self.assertEqual(
            promote.get_images_from_overlays(overlay_new_tag, "."),
            {"bar": [{"name": "foo", "newTag": "whizbang", "overlays": ["bar"]}]},
        )

    def test_new_name_and_tag(self):
        self.assertEqual(
            promote.get_images_from_overlays(overlay_new_name_and_tag, "."),
            {
                "bar": [
                    {
                        "name": "foo",
                        "newName": "quz",
                        "newTag": "whizbang",
                        "overlays": ["bar"],
                    }
                ]
            },
        )


class TestGenerateKustomizeArgs(unittest.TestCase):
    def test_empty(self):
        # Test that an empty list of images returns an empty list of args
        self.assertEqual(promote.generate_kustomize_args("foo", [], {}), ([], {}))

    def test_new_name(self):
        self.assertEqual(
            promote.generate_kustomize_args("bar", overlay_new_name, {}),
            (["foo=quz"], {"bar": {"images": [{"name": "foo", "newName": "quz"}]}}),
        )

    def test_new_tag(self):
        self.assertEqual(
            promote.generate_kustomize_args("bar", overlay_new_tag, {}),
            (
                ["foo=foo:whizbang"],
                {
                    "bar": {
                        "images": [
                            {"name": "foo", "newName": "foo", "newTag": "whizbang"}
                        ]
                    }
                },
            ),
        )

    def test_new_name_and_tag(self):
        self.assertEqual(
            promote.generate_kustomize_args("bar", overlay_new_name_and_tag, {}),
            (
                ["foo=quz:whizbang"],
                {
                    "bar": {
                        "images": [
                            {"name": "foo", "newName": "quz", "newTag": "whizbang"}
                        ]
                    }
                },
            ),
        )
