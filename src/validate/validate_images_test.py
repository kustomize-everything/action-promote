import pytest
from validate import validate_images

@pytest.mark.parametrize("images, expected", [
  # Basic
  [
    [
      {"name": "img1", "newName": "new1", "overlays": ["dev"]},
      {"name": "img2", "newTag": "v2", "overlays": ["dev"]}
    ],
    True
  ],
  # Missing newTag or newName fields
  [
    [
      {"name": "img1", "overlays": ["dev"]}
    ],
    False
  ],
  # Missing name field
  [
    [
      {"newName": "new1", "overlays": ["dev"]}
    ],
    False
  ],
  # Duplicate name
  [
    [
      {"name": "img1", "newName": "new1", "overlays": ["dev"]},
      {"name": "img1", "newTag": "v2", "overlays": ["dev"]}
    ],
    False
  ],
  # Duplicate newName
  [
    [
        {"name": "img1", "newName": "new1", "overlays": ["dev"]},
        {"name": "img2", "newName": "new1", "overlays": ["dev"]}
    ],
    False
  ],
  # Duplicate newTag
  [
    [
        {"name": "img1", "newTag": "new1", "overlays": ["dev"]},
        {"name": "img2", "newTag": "new1", "overlays": ["dev"]}
    ],
    True
  ]
])
def test_validate_images(images, expected):
    assert validate_images(images) == expected
