# Release process

In order to speed up the start times for end users, we build a container for
each release when the release is tagged. This means we need to take an extra
step after tagging the release to verify the tagged image works with the action.

1. Determine the version tag that you will be using, following
   [SemVer](https://semver.org) conventions for the version in the
   vMAJOR.MINOR.PATCH format.
1. BEFORE YOU RELEASE, update the `image` used in [action.yaml](./action.yml)
   with the tag that you intend to use.
1. Tag the release as you would on any project. Be sure to click the "Generate
   Release Notes" button to get a roll-up of all the PRs that have been merged
   since the last release!
1. Once the release is tagged, [verify that the container-build workflow
   completes
   successfully](https://github.com/kustomize-everything/action-promote/actions).
1. Re-run the failed checks on the release and verify that they still pass.
