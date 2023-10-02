#!/usr/bin/env python3

# This python script takes a JSON list of images or helm charts provided either
# by the IMAGES_TO_UPDATE/CHARTS_TO_UPDATE Environment Variable.
#
# It then runs the kustomize edit set image command for each image in the list, updating
# the image in the kustomize directory for the specified overlays.
#
# For each chart, the script will find the chart declaration in the kustomization.yaml
# and update it to point to the new chart version.
#
# The script will generally be run as a GitHub Action. The GitHub Action will take the
# JSON list of images as an input and pass it to the script via the IMAGES_TO_UPDATE
# Environment Variable.
#
# Each image in the IMAGES_TO_UPDATE JSON list should have the following format,
# which corresponds to the kustomize edit set image command:
# {
#   "name": "image-name",
#   # Either newName or newTag must be specified.
#   "newName": "new-image-name",
#   "newTag": "new-image-tag",
#   # If from is specified, the image will be updated using the values found for
#   # the image with the specified name in the fromOverlay.
#   "fromOverlay": "overlay-name",
#   "overlays": ["TARGET_DIR", "TARGET_DIR2"]
# }
#
# Each chart in the CHARTS_TO_UPDATE JSON list should have the following format,
# which corresponds to the kustomize helmGenerator declaration:
# {
#     "name": "chart-name",
#     # Either version is required
#     "version": "new-chart-version",
#     # ... or fromOverlay is required
#     "fromOverlay": "overlay-name",
#     # Optionally, update the release name
#     "releaseName": "new-release-name",
#     "overlays": ["target-env", "target-env2"]
# }
#
# The script assumes that the pwd is the root of the kustomize directory, but
# this directory can be overridden by the DEPLOYMENT_DIR env variable.
#
# The script is designed to run idempotently, so if the image is already set to the
# desired value, the script will not fail. Additionally, all of the kustomize edits
# will be batched together and run once per overlay, so that the kustomize edit set image
# command is only run once per overlay. This prevents an overlay from ending in a half-updated
# state if the script fails partway through.
import json
import logging
import os
import subprocess
import sys
import yaml

from typing import Callable, Iterator, Union, Optional  # noqa: F401

# Initialize logger
logger = logging.getLogger()
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)


def run(args: list[str]) -> int:
    """
    Run the given command and log the output.

    Args:
        args (list): The command to run.

    Returns:
        int: The return code of the command.
    """
    logger.debug(f"Running command: {' '.join(args)}")
    # Run the command, capturing the output and printing it to the stderr
    # This is done so that the output of the command is printed to the GitHub Action log
    # and not just the stdout of the script
    output = subprocess.run(args, capture_output=True, text=True)
    if output.stderr:
        logger.error(output.stderr)
    if output.stdout:
        logger.info(output.stdout)

    try:
        output.check_returncode()
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with return code {e.returncode}")
        raise e

    return output.returncode


def merge_manifests(a: dict, b: dict) -> dict:
    """
    Merge the images and charts for each overlay provided in the manifests.

    Args:
        a (dict): A dictionary representing the initial manifests.
        b (dict): A dictionary representing the additional manifests to be merged.

    Returns:
        dict: The merged manifests with images and charts combined for each overlay.
    """
    for overlay in b:
        if overlay not in a:
            a[overlay] = b[overlay]
        else:
            if "images" not in a[overlay]:
                a[overlay]["images"] = []
            if "charts" not in a[overlay]:
                a[overlay]["charts"] = []
            if "images" in b[overlay]:
                a[overlay]["images"] += b[overlay]["images"]
            if "charts" in b[overlay]:
                a[overlay]["charts"] += b[overlay]["charts"]

    return a


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
    originally_dict = False
    # Convert to list if it is a dict (which is the case when we are validating
    # images from a promotion file)
    if isinstance(images, dict):
        originally_dict = True
        images = list(images.values())

    # Ensure that all image names are unique
    duplicates = find_duplicates(images, "name")
    if len(duplicates) > 0:
        logger.fatal(
            f"Found duplicate image names: {' '.join(duplicates)}. Images must have unique names."
        )
        sys.exit(1)

    # Ensure that all image newNames are unique
    duplicates = find_duplicates(images, "newName")
    if len(duplicates) > 0:
        logger.fatal(
            f"Found duplicate image newNames: {' '.join(duplicates)}. Image newNames must have unique names."
        )
        sys.exit(1)

    for image in images:
        # Validate that the image has the required fields
        if "name" not in image:
            logger.fatal(f"Image {image} is missing the required 'name' field.")
            return False
        if "fromOverlay" in image:
            if "newName" in image:
                logger.fatal(
                    f"Image {image} cannot set newName when fromOverlay is set."
                )
                return False
            if "newTag" in image:
                logger.fatal(
                    f"Image {image} cannot set newTag when fromOverlay is set."
                )
                return False
        else:
            if ("newTag" not in image) and ("newName" not in image):
                logger.fatal(f"Image {image} must set newName, newTag or both.")
                return False
        # Validate that the image has the required fields if it was not a dict,
        # which means that it is coming from a promotion file and not from a
        # kustomization.yaml file.
        if not originally_dict and "overlays" not in image:
            logger.fatal(f"Image {image} is missing the required 'overlays' field.")
            return False

    return True


def validate_charts(charts):
    """
    Validate that the charts to update have the required fields.

    Args:
        charts (list): The list of charts to update.

    Returns:
        bool: True if all charts are valid, False otherwise.
    """
    originally_dict = False
    # Convert to list if it is a dict (which is the case when we are validating
    # charts from a promotion file)
    if isinstance(charts, dict):
        originally_dict = True
        charts = list(charts.values())

    # Ensure that all chart names are unique
    duplicates = find_duplicates(charts, "name")
    if len(duplicates) > 0:
        logger.fatal(
            f"Found duplicate chart names: {' '.join(duplicates)}. Charts must have unique names."
        )
        sys.exit(1)

    for chart in charts:
        # Validate that the chart has the required fields
        if "name" not in chart:
            logger.fatal(f"Chart {chart} is missing the required 'name' field.")
            return False
        if "fromOverlay" in chart:
            if "version" in chart:
                logger.fatal(
                    f"Chart {chart} cannot set version when fromOverlay is set."
                )
                return False
        else:
            if "version" not in chart:
                logger.fatal(f"Chart {chart} must set version.")
                return False
        # Validate that the chart has the required fields if it was not a dict,
        # which means that it is coming from a promotion file and not from a
        # kustomization.yaml file.
        if not originally_dict and "overlays" not in chart:
            logger.fatal(f"Chart {chart} is missing the required 'overlays' field.")
            return False

    return True


def read_images_from_overlay(overlay: str, deployment_dir: str) -> dict[str, dict]:
    """
    Read the images from the specified overlay in a deployment directory and return a dictionary mapping image names to their corresponding image dictionaries.

    Args:
        overlay (str): The name of the overlay to read the images from.
        deployment_dir (str): The directory containing the overlays.

    Returns:
        dict: A dictionary mapping image names to their corresponding image dictionaries.
    """
    images = {}
    kustomization_file = os.path.join(deployment_dir, overlay, "kustomization.yaml")
    try:
        # Open the kustomization.yaml file for the overlay
        with open(kustomization_file) as f:
            # Read the images from the kustomization.yaml file
            kustomize = yaml.safe_load(f)
            if "images" not in kustomize:
                logger.fatal(
                    f"Overlay {overlay} ({kustomization_file}) does not have any images."
                )
                sys.exit(1)
            for image in kustomize["images"]:
                if "name" not in image:
                    logger.fatal(
                        f"Image {image} ({kustomization_file}) is missing the required 'name' field."
                    )
                    sys.exit(1)
                # Add the image to the list of images
                images[image["name"]] = image
    except FileNotFoundError:
        logger.fatal(f"Kustomization file {kustomization_file} does not exist.")
        sys.exit(1)
    except yaml.YAMLError as e:
        logger.fatal(f"Kustomization file {kustomization_file} is invalid: {e}")
        sys.exit(1)

    # Validate that the images have the required fields
    if not validate_images(images):
        logger.fatal(f"Overlay {overlay} has invalid images.")
        sys.exit(1)

    return images


def read_charts_from_overlay(overlay: str, deployment_dir: str) -> dict[str, dict]:
    """
    Read the charts from the specified overlay by opening the kustomization.yaml file of the overlay and extracting the chart information.

    Args:
        overlay (str): The name of the overlay to read the charts from.
        deployment_dir (str): The directory path containing the overlays.

    Returns:
        dict: A dictionary mapping chart names to the chart dictionary.

    Raises:
        FileNotFoundError: If the kustomization.yaml file does not exist.
        yaml.YAMLError: If the kustomization.yaml file is invalid.
    """
    charts = {}
    kustomization_file = os.path.join(deployment_dir, overlay, "kustomization.yaml")
    try:
        # Open the kustomization.yaml file for the overlay
        with open(kustomization_file) as f:
            # Read the charts from the kustomization.yaml file
            kustomize = yaml.safe_load(f)
            if "helmCharts" not in kustomize:
                logger.fatal(
                    f"Overlay {overlay} ({kustomization_file}) does not have any charts."
                )
                sys.exit(1)
            for chart in kustomize["helmCharts"]:
                if "name" not in chart:
                    logger.fatal(
                        f"Chart {chart} ({kustomization_file}) is missing the required 'name' field."
                    )
                    sys.exit(1)
                # Add the chart to the list of charts
                charts[chart["name"]] = chart
    except FileNotFoundError:
        logger.fatal(f"Kustomization file {kustomization_file} does not exist.")
        sys.exit(1)
    except yaml.YAMLError as e:
        logger.fatal(f"Kustomization file {kustomization_file} is invalid: {e}")
        sys.exit(1)

    # Validate that the charts have the required fields
    if not validate_charts(charts):
        logger.fatal(f"Overlay {overlay} has invalid charts.")
        sys.exit(1)

    return charts


def get_images_from_overlays(images_to_update, deployment_dir):
    """
    Get the list of images to update for each overlay.

    Args:
        images_to_update (list): The list of images to update, where each image is represented as a dictionary with the following keys:
            - name (str): The name of the image.
            - newName (str): The new name of the image.
            - newTag (str): The new tag of the image.
            - fromOverlay (str): The name of the overlay to get the image from.
            - overlays (list): The list of overlays to update the image in.
        deployment_dir (str): The directory containing the overlays.

    Returns:
        dict: A dictionary mapping overlays to the list of images to update for each overlay.
    """
    overlays_to_images = {}
    for image in images_to_update:
        # Add the image to the list of images for each env
        for overlay in image["overlays"]:
            if overlay not in overlays_to_images:
                overlays_to_images[overlay] = []
            # If the image has a fromOverlay, get the image from that overlay
            if "fromOverlay" in image:
                images = read_images_from_overlay(image["fromOverlay"], deployment_dir)
                overlays_to_images[overlay].append(images[image["name"]])
            else:
                overlays_to_images[overlay].append(image)

    return overlays_to_images


def get_charts_from_overlays(charts_to_update, deployment_dir):
    """
    Get the list of charts to update for each overlay.

    Args:
        charts_to_update (list): The list of charts to update, where each chart is represented as a dictionary with the following keys:
            - name (str): The name of the chart.
            - version (str): The new version of the chart.
            - overlays (list): The list of overlays to update the chart in.
        deployment_dir (str): The directory containing the overlays.

    Returns:
        dict: A dictionary mapping overlays to the list of charts to update for each overlay.
    """
    overlays_to_charts = {}
    for chart in charts_to_update:
        # Add the chart to the list of charts for each overlay
        for overlay in chart["overlays"]:
            if overlay not in overlays_to_charts:
                overlays_to_charts[overlay] = []

            if "fromOverlay" in chart:
                charts = read_charts_from_overlay(chart["fromOverlay"], deployment_dir)
                logger.debug(charts)
                for overlayChart in charts.values():
                    logger.debug(overlayChart)
                    if overlayChart["name"] == chart["name"]:
                        overlays_to_charts[overlay].append(overlayChart)
            else:
                overlays_to_charts[overlay].append(chart)

    return overlays_to_charts


def generate_kustomize_args(
    overlay: str, images: list, promotion_manifest: dict
) -> tuple[list[str], dict]:
    """
    Generate the arguments to pass to the `kustomize edit set image` command for a given overlay and list of images.
    It also updates the promotion manifest with the images that are being passed to `kustomize`.

    Args:
        overlay (str): The overlay to generate the kustomize arguments for.
        images (list): The list of images to generate the kustomize arguments for.
        promotion_manifest (dict): The promotion manifest to add the images to.

    Returns:
        tuple: A tuple containing the generated kustomize arguments (list) and the updated promotion manifest (dict).

    Example Usage:
        overlay = "dev"
        images = [
            {"name": "app1", "newName": "new-app1", "newTag": "v2"},
            {"name": "app2", "newName": "new-app2"},
            {"name": "app3"}
        ]
        promotion_manifest = {}

        kustomize_args, updated_manifest = generate_kustomize_args(overlay, images, promotion_manifest)

        print(kustomize_args)
        # Output: ['app1=new-app1:v2', 'app2=new-app2', 'app3=app3']

        print(updated_manifest)
        # Output: {'dev': {'images': [{'name': 'app1', 'newName': 'new-app1', 'newTag': 'v2'}, {'name': 'app2', 'newName': 'new-app2'}, {'name': 'app3'}]}}
    """

    kustomize_args = []
    for image in images:
        name = image["name"]
        new_name = image.get("newName", name)
        new_tag = image.get("newTag")
        if overlay not in promotion_manifest:
            promotion_manifest[overlay] = {}
        if "images" not in promotion_manifest[overlay]:
            promotion_manifest[overlay]["images"] = []

        if new_name and new_tag:
            kustomize_args.append(f"{name}={new_name}:{new_tag}")
            promotion_manifest[overlay]["images"].append(
                {"name": name, "newName": new_name, "newTag": new_tag}
            )
        elif new_name:
            kustomize_args.append(f"{name}={new_name}")
            promotion_manifest[overlay]["images"].append(
                {"name": name, "newName": new_name}
            )
        else:
            raise ValueError(f"Image {image} is missing required fields.")

    return kustomize_args, promotion_manifest


def update_kustomize_images(
    env: str, deployment_dir: str, images: list, promotion_manifest: dict
) -> dict[str, dict[str, list]]:
    """
    Uses kustomize to update the images for the given environment.

    Args:
        env (str): The environment to update the images for.
        deployment_dir (str): The directory containing the kustomize directories.
        images (list): The list of images to update.
        promotion_manifest (dict): The promotion manifest to add the images to.

    Returns:
        dict: The updated promotion manifest.
    """
    kustomize_dir = os.path.join(deployment_dir, env)

    # Validate that the kustomize directory for the env exists
    if not os.path.isdir(kustomize_dir):
        logger.fatal(f"Kustomize directory for {env} does not exist. ({kustomize_dir})")
        exit(1)
    else:
        logger.info(f"Updating images for {env}...")

    # Change to the kustomize directory for the env
    os.chdir(kustomize_dir)

    kustomize_args, promotion_manifest = generate_kustomize_args(
        env, images, promotion_manifest
    )

    # Run the kustomize edit set image command, failing the script if it fails
    if kustomize_args:
        try:
            run(["kustomize", "edit", "set", "image", *kustomize_args])
        except subprocess.CalledProcessError:
            logger.fatal(f"Failed to update images in {env}.")
            exit(1)
    else:
        logger.info(f"No images to update in {env}.")

    # Change back to the original directory
    os.chdir(deployment_dir)

    return promotion_manifest


def update_kustomize_charts(
    overlay: str, deployment_dir: str, charts: list, promotion_manifest: dict
) -> dict:
    """
    Update the charts in a kustomization.yaml file for a specific overlay in a deployment directory.

    Args:
        overlay (str): The name of the overlay for which the charts need to be updated.
        deployment_dir (str): The path to the deployment directory.
        charts (list): A list of dictionaries containing the name and version of the charts to be updated.
        promotion_manifest (dict): A dictionary to store the promotion manifest.

    Returns:
        dict: The updated promotion manifest containing the updated charts for the overlay.
    """
    kustomize_dir = os.path.join(deployment_dir, overlay)

    # Validate that the kustomize directory for the env exists
    if not os.path.isdir(kustomize_dir):
        logger.fatal(
            f"Kustomize directory for {overlay} does not exist. ({kustomize_dir})"
        )
        exit(1)
    else:
        logger.info(f"Updating charts for {overlay}...")

    # Change to the kustomize directory for the env
    os.chdir(kustomize_dir)

    # Read in existing kustomization.yaml file
    with open("kustomization.yaml", "r") as kustomization_file:
        kustomization = yaml.safe_load(kustomization_file)

    # If the helmCharts key is not present, fail
    if "helmCharts" not in kustomization:
        logger.fatal(f"helmCharts key not found in {kustomize_dir}/kustomization.yaml.")
        exit(1)

    # Using the existing kustomization file, update the charts
    for chart in charts:
        logger.debug(chart)
        found = False

        # Search kustomize["helmCharts"] for the chart
        for i, helm_chart in enumerate(kustomization["helmCharts"]):
            if helm_chart["name"] == chart["name"]:
                found = True
                # Update the chart
                kustomization["helmCharts"][i]["version"] = chart["version"]

                # Add to promotion manifest
                if overlay not in promotion_manifest:
                    promotion_manifest[overlay] = {}
                if "charts" not in promotion_manifest[overlay]:
                    promotion_manifest[overlay]["charts"] = []
                promotion_manifest[overlay]["charts"].append(chart)

        if not found:
            logger.fatal(
                f"Chart {chart['name']} not found in {kustomize_dir}/kustomization.yaml."
            )
            exit(1)

    # Write the updated kustomization file
    with open("kustomization.yaml", "w") as kustomization_file:
        yaml.dump(kustomization, kustomization_file)

    # Since pyYAML doesn't care at all about formatting,
    # Run kustomize fmt to format the kustomization.yaml file
    run(["kustomize", "cfg", "fmt", "kustomization.yaml"])

    # Change back to the original directory
    os.chdir(deployment_dir)

    return promotion_manifest


def validate_runtime_environment() -> None:
    """
    Validate that the runtime environment has the tools we need and provided directories exist.

    This function validates the runtime environment by checking if the `kustomize` command is available.

    Example Usage:
    ```python
    validate_runtime_environment()
    ```

    Raises:
        CalledProcessError: If the `kustomize` command is not available.

    Returns:
        None
    """

    # Validate that the kustomize command is available
    try:
        logger.debug("Validating that kustomize is available...")
        run(["kustomize", "version"])
    except subprocess.CalledProcessError:
        logger.fatal(
            "kustomize is not available. Please install kustomize before running this script."
        )
        exit(1)


def get_deployment_dir() -> str:
    """
    Get the deployment directory from the DEPLOYMENT_DIR env variable.

    Args:
    """

    # Validate that the kustomize directory exists
    deployment_dir = os.getenv("DEPLOYMENT_DIR", ".")
    if not os.path.isdir(deployment_dir):
        logger.fatal(f"Deployment directory {deployment_dir} does not exist.")
        exit(1)
    else:
        logger.info(f"Using deployment directory: {deployment_dir}")

    # Convert deployment_dir to an absolute path
    deployment_dir = os.path.abspath(deployment_dir)

    return deployment_dir


def load_promotion_json(type: str) -> dict:
    """
    Loads the promotion JSON for images or helm charts

    Args:
        type (str): images or charts

    Returns:
        dict: The promotion JSON
    """

    # Read in the images to update from stdin or the IMAGES_TO_UPDATE env variable
    promotion_json = None
    promotion_input = None
    if os.environ.get(f"{type.upper()}_TO_UPDATE"):
        promotion_input = os.environ.get(f"{type.upper()}_TO_UPDATE")

    if promotion_input:
        try:
            promotion_json = json.loads(promotion_input)
        except json.JSONDecodeError as e:
            logger.fatal(f"Provided {type} JSON object failed to parse.")
            logger.fatal(f"Please provide a valid JSON list. Error: {e}")
            logger.fatal(f"The input received was: {promotion_input}")
            exit(1)
    else:
        logger.info(f"No {type} to update.")
        promotion_json = []

    return promotion_json


def validate_promotion_lists(
    images_to_update: list[dict], charts_to_update: list[dict]
) -> None:
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
    validate_images(images_to_update)

    # Validate that the charts to update have the required fields
    validate_charts(charts_to_update)


def main():
    validate_runtime_environment()

    deployment_dir = get_deployment_dir()

    # Read in the images to update from stdin or the IMAGES_TO_UPDATE env variable
    images_to_update = load_promotion_json("images")

    # Read in the helm charts to update from stdin or the HELM_CHARTS_TO_UPDATE env variable
    charts_to_update = load_promotion_json("charts")

    # Exit with failure if there are no images or charts to update, printing usage information.
    validate_promotion_lists(images_to_update, charts_to_update)

    # Get the list of images for each overlay
    overlays_to_images = get_images_from_overlays(images_to_update, deployment_dir)

    # Get the list of charts for each overlay
    overlays_to_charts = get_charts_from_overlays(charts_to_update, deployment_dir)

    # Create promotion manifest dictionary to store the promotion manifest
    promotion_manifest = {}

    # Iterate through the overlays to images, updating the images in each env
    for env, images in overlays_to_images.items():
        promotion_manifest = update_kustomize_images(
            env, deployment_dir, images, promotion_manifest
        )

        if promotion_manifest[env]["images"] != {}:
            logger.info(f"Images in {env} updated successfully.")

    # Iterate through the overlays to charts, updating the charts in each env
    for env, charts in overlays_to_charts.items():
        promotion_manifest = update_kustomize_charts(
            env, deployment_dir, charts, promotion_manifest
        )

        if promotion_manifest[env]["charts"] != {}:
            logger.info(f"Charts in {env} updated successfully.")

    # If we made it this far, all of the images and/or charts were updated successfully.
    # Write the promotion manifest to stdout so it can be captured by the caller.
    print(json.dumps(promotion_manifest))

    exit(0)


if __name__ == "__main__":
    main()
