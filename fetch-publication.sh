#!/usr/bin/env bash
# Downloads the publication publication.json pins (the tarball of a release
# of business-plan's publication.yml), checks its sha256, and unpacks its
# objects into ./objects, which the Dockerfile copies.
#
# It reads from storage.sustenaut.eu's private publications tenant, where a
# file's address is its sha256. The bearer is STORAGE_TOKEN when set, else,
# in GitHub Actions, the job's OpenID Connect token for storage.sustenaut.eu
# (permissions: id-token: write), which storage takes from this repository.
# Without either, as on a laptop, it downloads the release itself with gh,
# which must then be able to read business-plan.
set -euo pipefail
cd "$(dirname "$0")"
repo=$(jq -r .repository publication.json)
tag=$(jq -r .tag publication.json)
want=$(jq -r .sha256 publication.json)
if [ -z "$tag" ] || [ -z "$want" ]; then
  echo "publication.json pins no release yet: set its tag and sha256 from business-plan's publication releases" >&2
  exit 1
fi
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
tarball="$work/publication-0-objects.tar.gz"
token=${STORAGE_TOKEN:-}
if [ -z "$token" ] && [ -n "${ACTIONS_ID_TOKEN_REQUEST_URL:-}" ]; then
  token=$(curl -fsS -H "Authorization: bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
    "$ACTIONS_ID_TOKEN_REQUEST_URL&audience=storage.sustenaut.eu" | jq -r .value)
fi
if [ -n "$token" ]; then
  curl -fsS -H "Authorization: Bearer $token" -o "$tarball" \
    "https://storage.sustenaut.eu/publications/f/$want/publication-0-objects.tar.gz"
else
  gh release download "$tag" --repo "$repo" --pattern publication-0-objects.tar.gz --dir "$work"
fi
have=$(sha256sum "$tarball" | cut -d' ' -f1)
if [ "$have" != "$want" ]; then
  echo "$tag's publication-0-objects.tar.gz has sha256 $have, not the $want publication.json pins" >&2
  exit 1
fi
rm -rf objects
tar -xzf "$tarball"
echo "objects/ holds $tag ($(find objects -type f | wc -l) files, sha256 $want)"
