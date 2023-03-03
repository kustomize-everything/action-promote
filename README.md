# action-promote

GitHub action providing a standard promotion patterns using Kustomize.

It supports injecting multiple new images into target overlays via a JSON config
file. For examples, refer to [example](./example).

Within a JSON config for you image promotions, you have two (mutually exclusive
on a per image name basis) ways of providing the promotion information. Either
you can provide the `newName` and/or `newTag` directly keys directly in the
image configuration OR you can provide a `fromOverlay` key, which will find
the overlay provided as the value in your deployment repo and extract the value
of the image `name` from it.

For each image, you can promote into multiple target overlays in your deployment
repo by providing multiple values to the `overlays` key.

After making all of the changes specified in the JSON configuration, the GitHub
action will automatically commit and either push the branch directly or open
a pull request, depending on what you specify.

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
      - name: Push promoted image to deployment repo
        uses: kustomize-everything/action-promote@v1.0.6
        with:
          target-repo: kustomize-everything/guestbook-deploy
          target-branch: main
          working-directory: guestbook-deploy
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
