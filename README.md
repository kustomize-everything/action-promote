# action-promote

<!-- markdownlint-disable -->
[![CodeScene general](https://codescene.io/images/analyzed-by-codescene-badge.svg)](https://codescene.io/projects/44667) [![CodeScene Code Health](https://codescene.io/projects/44667/status-badges/code-health)](https://codescene.io/projects/44667)
<!-- markdownlint-enable -->

`action-promote` is a GitHub action designed to implement a standard promotion
pattern using Kustomize. Another FOSS tool that enables a similar workflow is
[Kargo](https://kargo.akuity.io/) from [Akuity](https://akuity.io/).

It facilitates the injection of multiple new images or helm charts into target
overlays through a JSON config file. The action supports both cross-overlay
promotions using the `fromOverlay` field and direct image/helm tag promotions.

## Promotion Configuration

For each promotion type, you can target multiple overlays in your deployment
repository by providing multiple values to the `overlays` key.

### Image Promotions

Images can be promoted in two ways:

1. **Cross-Overlay Promotion**: Extract image details from a given overlay and
   promote it to one or more target overlays.

```json
[
  {
    "name": "nginx",
    "fromOverlay": "env/dev",
    "overlays": ["env/production"]
  }
]
```

1. **Direct Image Tag Promotion**: Directly promote an image by specifying its
   new name and tag.

```json
[
  {
    "name": "nginx",
    "newName": "nginx",
    "newTag": "1.25.0",
    "overlays": ["env/dev"]
  }
]
```

### Helm Chart Promotions

Helm charts can also be promoted in two ways:

1. **Direct Helm Promotion**: Specify a new version for the helm chart directly
   (along with an optional `releaseName`).

```json
[
  {
    "name": "kube-prometheus-stack",
    "releaseName": "prometheus",
    "version": "45.5.0",
    "overlays": ["env/dev"]
  }
]
```

1. **Cross-Overlay Helm Promotion**: Extract helm details from a given overlay
   and promote it to one or more target overlays.

```json
[
  {
    "name": "kube-prometheus-stack",
    "fromOverlay": "env/dev",
    "overlays": ["env/production"]
  }
]
```

For more examples, refer to the [example](./example) directory.

After processing the specified promotions in the JSON configuration,
`action-promote` will commit the changes and either push directly or open a pull
request, based on your specification.

## Usage

### Pre-requisites

- A Github repository where your code resides, e.g.,
  [kustomize-everything/guestbook](https://github.com/kustomize-everything/guestbook).
- CI process resulting in a container image and tag.
- Github repository where your Kustomize deployment files reside, e.g.,
  [kustomize-everything/guestbook-deploy](https://github.com/kustomize-everything/guestbook-deploy).

### Inputs and Outputs

For the detailed list of action inputs and outputs, refer to
[action.yml](./action.yml).

### Example Workflow

For a complete workflow example, see
[kustomize-everything/guestbook](https://github.com/kustomize-everything/guestbook).

Note: The `images` input uses the JSON configuration specified above.

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
        uses: kustomize-everything/action-promote@v3.7.2
        id: promote
        with:
          target-repo: kustomize-everything/guestbook-deploy
          target-branch: main
          working-directory: deployment
          images: |-
            [
              {
                "name": "ghcr.io/kustomize-everything/guestbook",
                "newName": "${{ needs.build-image.outputs.image-name }}",
                "newTag": "${{ needs.build-image.outputs.image-tag }}",
                "overlays": ["env/dev"]
              }
            ]
          github-token: ${{ secrets.GITHUB_TOKEN }}
      - name: Send Changes
        if: ${{ steps.promote.outputs.images-updated != '[]' }}
        uses: slackapi/slack-github-action@v1.27.0
        with:
          channel-id: 'robots'
          slack-message: |
            "Promoted:
            ${{ join(fromJson(steps.promote.outputs.images-updated), ',') }}"
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
        
```

## Contributing

Contributions to `kustomize-everything/action-promote` are highly encouraged!
Pull requests are welcome.

## License

The scripts and documentation in this project are released under the [MIT
License](LICENSE).
