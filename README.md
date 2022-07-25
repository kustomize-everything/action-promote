# action-promote

GitHub action providing a standard promotion pattern using Kustomize.

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
      image: ${{ steps.push-image.outputs.image }}
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
          target-dir: env/dev
          working-directory: guestbook-deploy
          image-name-tag: ${{ needs.build-image.outputs.image }}
          ssh-key: ${{ secrets.GUESTBOOK_DEPLOY_KEY }}
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

## Contributing

We would love for you to contribute to kustomize-everything/actions-promote, pull requests are welcome!

## License

The scripts and documentation in this project are released under the [MIT License](LICENSE).
