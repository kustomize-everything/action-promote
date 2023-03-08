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

# Initialize logger
logger = logging.getLogger()
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)


def run(args):
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

    return output.check_returncode()


def find_duplicates(images, field):
    """
    Find duplicate fields in images in the list of images.

    Args:
        images (list): The list of images to check for duplicates.

    Returns:
        set: The set of duplicate images.
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
    Validate that the images to update have the required fields.

    Args:
        images_to_update (list): The list of images to update.

    Returns:
        bool: True if the images are valid, False otherwise.
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
        charts_to_update (list): The list of charts to update.

    Returns:
        bool: True if the charts are valid, False otherwise.
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


def read_images_from_overlay(overlay, deployment_dir):
    """
    Read the images from the given overlay.

    Args:
        overlay (str): The overlay to read the images from.
        deployment_dir (str): The directory containing the overlays.

    Returns:
        dict: A dictionary mapping image names to the image dictionary.
    """
    images = {}
    kustomization_file = os.path.join(deployment_dir, overlay, "kustomization.yaml")
    try:
        # Open the kustomize.yaml file for the overlay
        with open(kustomization_file) as f:
            # Read the images from the kustomize.yaml file
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


def read_charts_from_overlay(overlay, deployment_dir):
    """
    Read the charts from the given overlay.

    Args:
        overlay (str): The overlay to read the charts from.
        deployment_dir (str): The directory containing the overlays.

    Returns:
        dict: A dictionary mapping chart names to the chart dictionary.
    """
    charts = {}
    kustomization_file = os.path.join(deployment_dir, overlay, "kustomization.yaml")
    try:
        # Open the kustomize.yaml file for the overlay
        with open(kustomization_file) as f:
            # Read the charts from the kustomize.yaml file
            kustomize = yaml.safe_load(f)
            if "charts" not in kustomize:
                logger.fatal(
                    f"Overlay {overlay} ({kustomization_file}) does not have any charts."
                )
                sys.exit(1)
            for chart in kustomize["charts"]:
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
        images_to_update (list): The list of images to update.
        deployment_dir (str): The directory containing the overlays.

    Returns:
        dict: A dictionary mapping overlays to the list of images to update for that overlay.
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
        charts_to_update (list): The list of charts to update.
        deployment_dir (str): The directory containing the overlays.

    Returns:
        dict: A dictionary mapping overlays to the list of charts to update for that overlay.
    """
    overlays_to_charts = {}
    for chart in charts_to_update:
        # Add the chart to the list of charts for each env
        for overlay in chart["overlays"]:
            if overlay not in overlays_to_charts:
                overlays_to_charts[overlay] = []

            if "fromOverlay" in chart:
                charts = read_images_from_overlay(chart["fromOverlay"], deployment_dir)
                overlays_to_charts[overlay].append(charts[chart["name"]])
            else:
                overlays_to_charts[overlay].append(chart)

    return overlays_to_charts


def generate_kustomize_args(overlay, images, promotion_manifest):
    """
    Generate the arguments to pass to kustomize edit set image for the given overlay and images.

    Args:
        overlay (str): The overlay to generate the kustomize args for.
        images (list): The list of images to generate the kustomize args for.
        promotion_manifest (dict): The promotion manifest to add the images to.

    Returns:
        list: The list of arguments to pass to kustomize edit set image.
    """

    # Iterate through the images to collect them into one list of arguments that
    # will be passed as a group to kustomize edit

    # The kustomize edit set image command takes the following format:
    # kustomize edit set image <name>=<new-name>:<new-tag>
    # If the new-name and new-tag are not provided, ignore the image.
    # If the name is not provided, fail.
    # If the new-name is not provided, use the name.

    # The kustomize edit set image command can take multiple images at once, so
    # we will collect all of the images for an overlay and pass them all at once.
    kustomize_args = []
    for image in images:
        name = image["name"]
        new_name = image.get("newName", name)
        new_tag = image.get("newTag")
        if new_name and new_tag:
            kustomize_args.append(f"{name}={new_name}:{new_tag}")
            # Add to promotion manifest
            if overlay not in promotion_manifest:
                promotion_manifest[overlay] = []
            promotion_manifest[overlay].append(
                {"name": name, "newName": new_name, "newTag": new_tag}
            )
        elif new_name:
            kustomize_args.append(f"{name}={new_name}")
            # Add to promotion manifest
            if overlay not in promotion_manifest:
                promotion_manifest[overlay] = []
            promotion_manifest[overlay].append({"name": name, "newName": new_name})
        else:
            raise ValueError(f"Image {image} is missing required fields.")

    return kustomize_args, promotion_manifest


def update_kustomize_images(env, deployment_dir, images, promotion_manifest):
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

    kustomize_args, env_promotion_manifest = generate_kustomize_args(
        env, images, promotion_manifest["images"]
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

    if "images" not in promotion_manifest:
        promotion_manifest["images"] = []

    promotion_manifest["images"] += env_promotion_manifest

    return promotion_manifest


def update_kustomize_charts(overlay, deployment_dir, charts, promotion_manifest):
    """
    Update the"""
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

    # TODO Write a function to update the charts in the kustomization.yaml file
    env_promotion_manifest = []

    # Change back to the original directory
    os.chdir(deployment_dir)

    if "charts" not in promotion_manifest:
        promotion_manifest["charts"] = []

    promotion_manifest["charts"] += env_promotion_manifest

    return promotion_manifest


def validate_runtime_environment():
    """
    Validate that the runtime environment has the tools we need and provided directories exist.
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


def get_deployment_dir():
    """
    Get the deployment directory from the DEPLOYMENT_DIR env variable.
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


def main():
    validate_runtime_environment()

    deployment_dir = get_deployment_dir()

    # Read in the images to update from stdin or the IMAGES_TO_UPDATE env variable
    images_to_update = None
    images_input = None
    if os.getenv("IMAGES_TO_UPDATE"):
        images_input = os.getenv("IMAGES_TO_UPDATE")
    else:
        images_input = sys.stdin.read()

    if images_input:
        try:
            images_to_update = json.loads(images_input)
        except json.JSONDecodeError as e:
            logger.fatal("Provided images JSON object failed to parse.")
            logger.fatal(f"Please provide a valid JSON list. Error: {e}")
            logger.fatal(f"The input received was: {images_input}")
            exit(1)
    else:
        logger.info("No images to update.")
        images_to_update = []

    # Read in the helm charts to update from stdin or the HELM_CHARTS_TO_UPDATE env variable
    charts_to_update = None
    charts_input = None
    if os.getenv("CHARTS_TO_UPDATE"):
        charts_input = os.getenv("CHARTS_TO_UPDATE")
    else:
        charts_input = sys.stdin.read()

    if charts_input:
        try:
            charts_to_update = json.loads(charts_input)
        except json.JSONDecodeError as e:
            logger.fatal("Provided charts JSON object failed to parse.")
            logger.fatal(f"Please provide a valid JSON list. Error: {e}")
            logger.fatal(f"The input received was: {charts_input}")
            exit(1)
    else:
        logger.info("No charts to update.")
        charts_to_update = []

    # Exit with failure if there are no images or charts to update, printing usage information.
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

    # Get the list of images for each overlay
    overlays_to_images = get_images_from_overlays(images_to_update, deployment_dir)

    # Get the list of charts for each overlay
    overlays_to_charts = get_charts_from_overlays(charts_to_update, deployment_dir)

    # Create promotion manifest dictionary to store the promotion manifest
    promotion_manifest = {"images": {}, "charts": {}}

    # Iterate through the overlays to images, updating the images in each env
    for env, images in overlays_to_images.items():
        promotion_manifest = update_kustomize_images(
            env, deployment_dir, images, promotion_manifest
        )

    if promotion_manifest["images"] != {}:
        logger.info("Images updated successfully.")

    # Iterate through the overlays to charts, updating the charts in each env
    for env, charts in overlays_to_charts.items():
        promotion_manifest = update_kustomize_charts(
            env, deployment_dir, charts, promotion_manifest
        )

    if promotion_manifest["charts"] != {}:
        logger.info("Charts updated successfully.")

    # If we made it this far, all of the images and/or charts were updated successfully.
    # Write the promotion manifest to stdout so it can be captured by the caller.
    print(json.dumps(promotion_manifest))

    exit(0)


if __name__ == "__main__":
    main()
