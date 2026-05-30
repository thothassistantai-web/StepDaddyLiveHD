#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
version_file="$repo_root/VERSION"
version="$(tr -d '[:space:]' < "$version_file")"

if [[ -z "${version}" ]]; then
  echo "VERSION is empty" >&2
  exit 1
fi

archive_dir="$repo_root/release"
mkdir -p "$archive_dir"

name="stepdaddy-live-hd-linux-${version}"

git -C "$repo_root" archive --format=tar.gz --prefix="${name}/" -o "${archive_dir}/${name}.tar.gz" HEAD
git -C "$repo_root" archive --format=zip --prefix="${name}/" -o "${archive_dir}/${name}.zip" HEAD

cat <<EOF
Created:
  ${archive_dir}/${name}.tar.gz
  ${archive_dir}/${name}.zip
EOF
