#!/usr/bin/env python3

# This python script takes a JSON list of images provided either by the IMAGES_TO_UPDATE
# Environment Variable or via stdin.
#
# It then runs the kustomize edit set image command for each image in the list, updating
# the image in the kustomize directory for the specified env.
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
#   "env": "TARGET_DIR"
# }
#
# The script assumes that the pwd is the root of the kustomize directory, but
# this directory can be overridden by the DEPLOYMENT_DIR env variable.
#
# The script is designed to run idempotently, so if the image is already set to the
# desired value, the script will not fail. Additionally, all of the kustomize edits
# will be batched together and run once per env, so that the kustomize edit set image
# command is only run once per env. This prevents an env from ending in a half-updated
# state if the script fails partway through.
import os
import json
import subprocess

# Validate that the kustomize command is available
try:
    print("Validating that kustomize is available...")
    subprocess.run(["kustomize", "version"], check=True)
except subprocess.CalledProcessError:
    print("kustomize is not available. Please install kustomize before running this script.")
    exit(1)

# Validate that the kustomize directory exists
deployment_dir = os.getenv("DEPLOYMENT_DIR", ".")
if not os.path.isdir(deployment_dir):
    print(f"Deployment directory {deployment_dir} does not exist.")
    exit(1)

# Read in the images to update from stdin or the IMAGES_TO_UPDATE env variable
images_to_update = None
if os.getenv("IMAGES_TO_UPDATE"):
    try:
        images_to_update = json.loads(os.getenv("IMAGES_TO_UPDATE"))
    except json.JSONDecodeError as e:
        print(f"Provided JSON object failed to parse. Please provide a valid JSON object. Error: {e}")
        exit(1)

    try:
        images_to_update = json.loads(input())
    except json.JSONDecodeError as e:
        print(f"Provided JSON object failed to parse. Please provide a valid JSON object. Error: {e}")
        exit(1)

# Exit with failure if there are no images to update, printing usage information.
if not images_to_update:
    print("No images to update. Please provide a JSON object of images to update via the IMAGES_TO_UPDATE env var or via stdin.")
    print("The JSON object should be in the following format:")
    print(
        """
        [
            {
                "name": "image-name",
                "newName": "new-image-name",
                "newTag": "new-image-tag",
                "env": "TARGET_ENV"
            }
        ]
        """
    )
    exit(1)

# Iterate through the images to update, building a dictionary of envs to images
envs_to_images = {}
for image in images_to_update:
    env = image["env"]
    if env not in envs_to_images:
        envs_to_images[env] = []
    envs_to_images[env].append(image)

# Iterate through the envs to images, updating the images in each env
for env, images in envs_to_images.items():
    # Change to the kustomize directory for the env
    os.chdir(os.path.join(deployment_dir, env))

    # Iterate through the images to collect them into one list of arguments that
    # will be passed as a group to kustomize edit

    # The kustomize edit set image command takes the following format:
    # kustomize edit set image <name>=<new-name>:<new-tag>
    # If the new-name and new-tag are not provided, ignore the image.
    # If the name is not provided, fail.
    # If the new-name is not provided, use the name.

    # The kustomize edit set image command can take multiple images at once, so
    # we will collect all of the images for an env and pass them all at once.
    kustomize_args = []
    for image in images:
        name = image["name"]
        new_name = image.get("newName", name)
        new_tag = image.get("newTag")
        if new_tag:
            kustomize_args.append(f"{name}={new_name}:{new_tag}")
        else:
            print(f"Skipping image {name} because no new tag was provided.")

    # Run the kustomize edit set image command, failing the script if it fails
    if kustomize_args:
        try:
            subprocess.run(["kustomize", "edit", "set", "image", *kustomize_args], check=True)
        except subprocess.CalledProcessError:
            print(f"Failed to update images in {env}.")
            exit(1)
    else:
        print(f"No images to update in {env}.")

    # Change back to the original directory
    os.chdir(deployment_dir)

# If we made it this far, all of the images were updated successfully.
# Print a summary of the images that were updated in each environment and exit.
for env, images in envs_to_images.items():
    print(f"Updated images in {env}:")
    for image in images:
        name = image["name"]
        new_name = image.get("newName", name)
        new_tag = image.get("newTag")
        print(f"{name} -> {new_name}:{new_tag}")
