import logging
import subprocess

from typing import Callable, Iterator, Union, Optional  # noqa: F401

# Initialize logger
logger = logging.getLogger(__name__)
logger.propagate = False
logger.setLevel(logging.DEBUG)


def find_duplicates(images: list, field: str) -> set:
    """
    Find duplicate values for a specified field in a list of images.

    Args:
        images (list): The list of images to check for duplicates.
        field (str): The field name to check for duplicates.

    Returns:
        set: A set containing the duplicate values for the specified field.
    """
    duplicates = set()
    image_names = [image[field] for image in images if field in image]
    seen = set()
    for image_name in image_names:
        if image_name in seen:
            duplicates.add(image_name)
        else:
            seen.add(image_name)

    return duplicates


def validate_images(images):
    """
    Validate a list of images to ensure they have the required fields and that the names and newNames are unique.

    Args:
        images (list): The list of images to validate.

    Returns:
        bool: True if all images are valid, False otherwise.
    """
    errors = []
    originally_dict = False
    # Convert to list if it is a dict (which is the case when we are validating
    # images from a promotion file)
    if isinstance(images, dict):
        originally_dict = True
        images = list(images.values())

    # Ensure that all image names are unique
    duplicates = find_duplicates(images, "name")
    if len(duplicates) > 0:
        errors.append(
            f"Found duplicate image names: {' '.join(duplicates)}. Images must have unique names."
        )

    # Ensure that all image newNames are unique
    duplicates = find_duplicates(images, "newName")
    if len(duplicates) > 0:
        errors.append(
            f"Found duplicate image names: {' '.join(duplicates)}. Images must have unique names."
        )

    if len(images) > 0:
        errors.extend(validate_image_fields(images, originally_dict))

    for error in errors:
        logger.error(error)
    return len(errors) == 0


def validate_image_fields(images, originally_dict) -> list:
    """
    Args:
        images (list): The list of images to validate.
        originally_dict (bool): True if the images were originally a dict, False otherwise.

    Returns:
        list: A list of errors.
    """
    errors = []

    for image in images:
        # Validate that the image has the required fields
        if "name" not in image:
            errors.append(f"Image {image} is missing the required 'name' field.")
        if "fromOverlay" in image and "newName" in image:
            errors.append(f"Image {image} cannot set newName when fromOverlay is set.")
        elif "fromOverlay" in image and "newTag" in image:
            errors.append(f"Image {image} cannot set newTag when fromOverlay is set.")
        elif ("newTag" not in image) and ("newName" not in image):
            errors.append(f"Image {image} must set newName, newTag or both.")
        # Validate that the image has the required fields if it was not a dict,
        # which means that it is coming from a promotion file and not from a
        # kustomization.yaml file.
        if not originally_dict and "overlays" not in image:
            errors.append(f"Image {image} is missing the required 'overlays' field.")

    return errors


def validate_charts(charts):
    """
    Validate that the charts to update have the required fields.

    Args:
        charts (list): The list of charts to update.

    Returns:
        bool: True if all charts are valid, False otherwise.
    """
    errors = []
    originally_dict = False
    # Convert to list if it is a dict (which is the case when we are validating
    # charts from a promotion file)
    if isinstance(charts, dict):
        originally_dict = True
        charts = list(charts.values())

    # Ensure that all chart names are unique
    duplicates = find_duplicates(charts, "name")
    if len(duplicates) > 0:
        errors.append(
            f"Found duplicate chart names: {' '.join(duplicates)}. Charts must have unique names."
        )

    if len(charts) > 0:
        errors.extend(validate_chart_fields(charts, originally_dict))

    for error in errors:
        logger.error(error)

    return len(errors) == 0


def validate_chart_fields(charts, originally_dict) -> list:
    """
    Args:
        charts (list): The list of charts to validate.
        originally_dict (bool): True if the charts were originally a dict, False otherwise.

    Returns:
        list: A list of errors.
    """
    errors = []

    for chart in charts:
        # Validate that the chart has the required fields
        if "name" not in chart:
            errors.append(f"Chart {chart} is missing the required 'name' field.")
        if "fromOverlay" in chart and "version" in chart:
            errors.append(f"Chart {chart} cannot set version when fromOverlay is set.")
        elif "version" not in chart:
            errors.append(f"Chart {chart} must set version.")
        # Validate that the chart has the required fields if it was not a dict,
        # which means that it is coming from a promotion file and not from a
        # kustomization.yaml file.
        if not originally_dict and "overlays" not in chart:
            errors.append(f"Chart {chart} is missing the required 'overlays' field.")

    return errors


def validate_promotion_lists(
    images_to_update: list[dict], charts_to_update: list[dict]
) -> bool:
    """
    Validate the provided promotion configuration.

    Args:
        images_to_update (list): The list of images to update.
        charts_to_update (list): The list of charts to update.

    Returns:
        None

    Raises:
        SystemExit: If there are no images or charts to update.
    """
    if len(images_to_update) == 0 and len(charts_to_update) == 0:
        logger.fatal("No images or charts to update. Please provide either (or both):")
        logger.fatal(
            "- A JSON object of images to update via the IMAGES_TO_UPDATE env var or via stdin in the following format:"
        )
        logger.fatal(
            """
            [
                {
                    "name": "image-name",
                    # Either newTag or newName is required
                    "newName": "new-image-name",
                    "newTag": "new-image-tag",
                    # ... or fromOverlay is required
                    "fromOverlay": "overlay-name",
                    "overlays": ["target-env", "target-env2"]
                }
            ]
            """
        )
        logger.fatal(
            "- A JSON object of charts to update via the CHARTS_TO_UPDATE env var or via stdin in the following format:"
        )
        logger.fatal(
            """
            [
                {
                    "name": "chart-name",
                    # Either version is required
                    "version": "new-chart-version",
                    # ... or fromOverlay is required
                    "fromOverlay": "overlay-name",
                    # Optionally, update the release name
                    "releaseName": "new-release-name",
                    "overlays": ["target-env", "target-env2"]
                }
            ]
            """
        )
        exit(1)

    # Validate that the images to update have the required fields
    valid_images = validate_images(images_to_update)

    # Validate that the charts to update have the required fields
    valid_charts = validate_charts(charts_to_update)

    if not valid_images:
        logger.error(
            "The provided images to update are not valid. Please provide a JSON object of images to update in the following format:"
        )

    return valid_images
