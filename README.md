# action-promote

This GitHub action provides a standard promotion pattern using Kustomize.

It supports injecting multiple new images or helm charts into target overlays
via a JSON config file. For examples, refer to [example](./example).

Within a JSON config for your image promotions, you have two (mutually exclusive
on a per-image name basis) ways of providing the promotion information. Either
you can give the `newName` or `newTag` keys directly in the
image configuration OR you can give a `fromOverlay` key, which will find
the overlay provided as the value in your deployment repo and extract the value
of the image `name` from it.

For each image, you can promote multiple target overlays in your deployment
repo by providing multiple values to the `overlays` key.

Within a JSON config for your Helm chart promotions, you have two (also mutually
exclusive on a per-image name basis) ways of providing the promotion
information. Either you can give the new `version` for the chart directly (along
with an optional update to the `releaseName`) or, similar to the images
promotion configuration, you can provide a `fromOverlay` key, which will find
the overlay provided and extract the helm chart information from that overlay
for use in the provided `overlay`.

After making all of the changes specified in the JSON configuration, the GitHub
action will automatically commit and either push the branch directly or open
a pull request, depending on what you define.

## Usage

### Pre-requisites

- Github repo where your code resides e.g. [kustomize-everything/guestbook](https://github.com/kustomize-everything/guestbook)
- CI process that results in a container image and tag
- Github repo where your Kustomize deployment files reside e.g. [kustomize-everything/guestbook-deploy](https://github.com/kustomize-everything/guestbook-deploy)

### Inputs

Refer to [action.yml](./action.yml)

### Outputs

Refer to [action.yml](./action.yml)

### Example Workflow

For a complete example, please refer to [kustomize-everything/guestbook](https://github.com/kustomize-everything/guestbook).

```yaml
---

name: CI/CD
on:
  push:
    branches:
      - main

jobs:
  build-image:
    name: Build and Push Docker images
    runs-on: ubuntu-latest
    outputs:
      image-name: ${{ steps.push-image.outputs.image-name }}
      image-tag: ${{ steps.push-image.outputs.image-tag }}
    steps:
      - name: Checkout
        uses: actions/checkout@v3
        with:
          fetch-depth: 0
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v1
      - name: Push Image
        id: push-image
        run: make push-latest

  deploy:
    needs: build-image
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Deployment Repo
        uses: actions/checkout@v3
        with:
          fetch-depth: 0
          repository: kustomize-everything/guestbook-deploy
          ref: main
          path: deployment
          token: ${{ secrets.GITHUB_TOKEN }}
      - name: Push promoted image to deployment repo
        uses: kustomize-everything/action-promote@v1.0.6
        with:
          target-repo: kustomize-everything/guestbook-deploy
          target-branch: main
          working-directory: deployment
          images: |-
            [
              {
                "name": "nginx",
                "newName": "${{ needs.build-image.outputs.image-name }}",
                "newTag": "${{ needs.build-image.outputs.image-tag }}",
                "overlays": ["env/dev"]
              }
            ]
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

## Contributing

We would love for you to contribute to kustomize-everything/actions-promote,
pull requests are welcome!

## License

The scripts and documentation in this project are released under the [MIT License](LICENSE).
