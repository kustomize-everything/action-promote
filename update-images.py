#!/usr/bin/env python3

# This python script takes a JSON list of images provided either by the IMAGES_TO_UPDATE
# Environment Variable or via stdin.
#
# It then runs the kustomize edit set image command for each image in the list, updating
# the image in the kustomize directory for the specified overlays.
#
# The script will generally be run as a GitHub Action. The GitHub Action will take the
# JSON list of images as an input and pass it to the script via the IMAGES_TO_UPDATE
# Environment Variable.
#
# Each image in the dictionary should have the following format, which corresponds
# to the kustomize edit set image command:
# {
#   "name": "image-name",
#   "newName": "new-image-name",
#   "newTag": "new-image-tag",
#   "overlays": ["TARGET_DIR", "TARGET_DIR2"]
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

# Initialize logger
logger = logging.getLogger()
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)

def run(args):
    logger.debug(f"Running command: {' '.join(args)}")
    # Run the command, capturing the output and printing it to the stderr
    # This is done so that the output of the command is printed to the GitHub Action log
    # and not just the stdout of the script
    output = subprocess.run(args, capture_output=True, text=True)
    if output.stderr:
        logger.error(output.stderr)
    if output.stdout:
        logger.info(output.stdout)
    output.check_returncode()


# Validate that the kustomize command is available
try:
    logger.debug("Validating that kustomize is available...")
    run(["kustomize", "version"])
except subprocess.CalledProcessError:
    logger.fatal("kustomize is not available. Please install kustomize before running this script.")
    exit(1)

# Validate that the kustomize directory exists
deployment_dir = os.getenv("DEPLOYMENT_DIR", ".")
if not os.path.isdir(deployment_dir):
    logger.fatal(f"Deployment directory {deployment_dir} does not exist.")
    exit(1)
else:
    logger.info(f"Using deployment directory: {deployment_dir}")

# Convert deployment_dir to an absolute path
deployment_dir = os.path.abspath(deployment_dir)

# Read in the images to update from stdin or the IMAGES_TO_UPDATE env variable
images_to_update = None
try:
    if os.getenv("IMAGES_TO_UPDATE"):
        images_to_update = json.loads(os.getenv("IMAGES_TO_UPDATE"))
    else:
        # Read the whole JSON document from stdin, parsing it as JSON and validating that it is a list
        # Fail with a useful error message if the JSON is invalid or not a list
        images_to_update = json.load(sys.stdin)
except json.JSONDecodeError as e:
    logger.fatal(f"Provided JSON object failed to parse. Please provide a valid JSON object. Error: {e}")
    exit(1)

# Exit with failure if there are no images to update, printing usage information.
if not images_to_update:
    logger.fatal("No images to update. Please provide a JSON object of images to update via the IMAGES_TO_UPDATE env var or via stdin.")
    logger.info("The JSON object should be in the following format:")
    logger.info(
        """
        [
            {
                "name": "image-name",
                "newName": "new-image-name",
                "newTag": "new-image-tag",
                "overlays": ["target-env", "target-env2"]
            }
        ]
        """
    )
    exit(1)

# Iterate through the images to update, building a dictionary of overlays to images
overlays_to_images = {}
for image in images_to_update:
    # Validate that the image has the required fields
    if "name" not in image:
        logger.fatal(f"Image {image} is missing the required 'name' field.")
        exit(1)
    if "overlays" not in image:
        logger.fatal(f"Image {image} is missing the required 'overlays' field.")
        exit(1)

    # Add the image to the list of images for each env
    for overlay in image["overlays"]:
        if overlay not in overlays_to_images:
            overlays_to_images[overlay] = []
        overlays_to_images[overlay].append(image)

# Create promotion manifest dictionary to store the promotion manifest
promotion_manifest = {}

# Iterate through the overlays to images, updating the images in each env
for env, images in overlays_to_images.items():
    kustomize_dir = os.path.join(deployment_dir, env)

    # Validate that the kustomize directory for the env exists
    if not os.path.isdir(kustomize_dir):
        logger.fatal(f"Kustomize directory for {env} does not exist. ({kustomize_dir})")
        exit(1)
    else:
        logger.info(f"Updating images for {env}...")

    # Change to the kustomize directory for the env
    os.chdir(kustomize_dir)

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
        if new_tag:
            kustomize_args.append(f"{name}={new_name}:{new_tag}")
            # Add to promotion manifest
            if env not in promotion_manifest:
                promotion_manifest[env] = []
            promotion_manifest[env].append({"name": name, "newName": new_name, "newTag": new_tag})
        else:
            logger.info(f"Skipping image {name} because no new tag was provided.")

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

# If we made it this far, all of the images were updated successfully.
# Write the promotion manifest to stdout
print(json.dumps(promotion_manifest))

logger.info("Successfully updated images.")
exit(0)
