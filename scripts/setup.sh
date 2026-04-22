#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET_DIR="${HOME}/.agents/skills"

mkdir -p "$TARGET_DIR"

found_skill=0

for skill_dir in "$REPO_ROOT"/*; do
  [[ -d "$skill_dir" ]] || continue
  [[ -f "$skill_dir/SKILL.md" ]] || continue

  found_skill=1
  skill_name="$(basename "$skill_dir")"
  target_path="$TARGET_DIR/$skill_name"

  if [[ -e "$target_path" && ! -L "$target_path" ]]; then
    echo "ERROR: $target_path exists and is not a symlink" >&2
    exit 1
  fi

  ln -sfn "$skill_dir" "$target_path"
  echo "Linked $skill_name -> $target_path"
done

if [[ "$found_skill" -eq 0 ]]; then
  echo "ERROR: No skills found in $REPO_ROOT" >&2
  exit 1
fi