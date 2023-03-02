import unittest
import update_images


class TestValidateImagesFromOverlays(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(update_images.validate_images_from_overlays([]), True)

    def test_only_new_name(self):
        self.assertEqual(update_images.validate_images_from_overlays([{"name": "foo", "newName": "quz", "overlays": ["bar"]}]), True)

    def test_only_new_tag(self):
        self.assertEqual(update_images.validate_images_from_overlays([{"name": "foo", "newTag": "whizbang", "overlays": ["bar"]}]), True)

    def test_missing_new_name_and_new_tag(self):
        self.assertEqual(update_images.validate_images_from_overlays([{"name": "foo", "overlays": ["bar"]}]), False)

class TestGetImagesFromOverlays(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(update_images.get_images_from_overlays([]), {})

    def test_missing_new_name(self):
        self.assertEqual(update_images.get_images_from_overlays([{"name": "foo", "overlays": ["bar"]}]), {"bar": [{"name": "foo", "overlays": ["bar"]}]})

    def test_new_name_and_tag(self):
        self.assertEqual(update_images.get_images_from_overlays([{"name": "foo", "newName": "quz", "newTag": "whizbang", "overlays": ["bar"]}]), {"bar": [{"name": "foo", "newName": "quz", "newTag": "whizbang", "overlays": ["bar"]}]})

class TestGenerateKustomizeArgs(unittest.TestCase):
    def test(self):
        # Test that an empty list of images returns an empty list of args
        self.assertEqual(update_images.generate_kustomize_args("foo", [], {}), ([], {}))

        # Test that the image is added to the promotion manifest
        self.assertEqual(update_images.generate_kustomize_args("bar", [{"name": "foo", "newTag": "wow", "overlays": ["bar"]}], {}), (["foo=foo:wow"], {"bar": [{"name": "foo", "newName": "foo", "newTag": "wow"}]}))
