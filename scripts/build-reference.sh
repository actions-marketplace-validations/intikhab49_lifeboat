#!/usr/bin/env bash
# Builds Bitnami's own image for one of our image directories, from the bitnami/containers
# commit recorded in its UPSTREAM file. It is only the reference side of a parity check, and it
# stops working the day Broadcom closes downloads.bitnami.com; the lifeboat build does not.
# Usage: scripts/build-reference.sh images/postgresql/18/debian-12 TAG
set -euo pipefail

dir="$1" tag="$2"
repo="$(sed -n 's/^repo=//p' "$dir/UPSTREAM")"
path="$(sed -n 's/^path=//p' "$dir/UPSTREAM")"
commit="$(sed -n 's/^commit=//p' "$dir/UPSTREAM")"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
git -C "$work" init -q
git -C "$work" config core.autocrlf false
git -C "$work" remote add origin "$repo"
git -C "$work" sparse-checkout set "$path"
git -C "$work" fetch -q --depth 1 --filter=blob:none origin "$commit"
git -C "$work" checkout -q FETCH_HEAD
docker build -t "$tag" "$work/$path"
