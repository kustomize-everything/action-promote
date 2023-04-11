# Developing the Action

In order to test out changes to the action, you will need to reconfigure [`action.yml`](./action.yml)
to build the Dockerfile when changes are pushed. You can do this by commenting out
the `.runs.image` setting in that file that is used for the released action and
replacing it with the other commented out setting above it that uses the `Dockerfile`
directly.
