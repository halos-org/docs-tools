#!/usr/bin/env bash
#
# Release-notes override for the shared build-release workflow (build-deb: false).
# The shared default emits APT install instructions; docs-tools is installed by
# pinning a git tag, so this emits that pin instead.
#
# Usage: generate-release-notes.sh <debian-version> <tag> <prerelease|draft>
# Writes release_notes.md in the current directory.

set -euo pipefail

# $1 is the debian version from the shared workflow's positional contract;
# unused here because nothing is packaged.
TAG="$2"
MODE="$3"

# Changelog since the last published (non-draft, non-prerelease) release.
LAST_TAG=$(gh release list --limit 100 --json tagName,isPrerelease,isDraft \
  --jq '.[] | select(.isDraft == false and .isPrerelease == false) | .tagName' | head -n1 || true)

if [ -n "$LAST_TAG" ]; then
  CHANGELOG=$(git log "${LAST_TAG}"..HEAD --pretty=format:"- %s (%h)" --no-merges -- || echo "- Release ${TAG}")
else
  CHANGELOG=$(git log -10 --pretty=format:"- %s (%h)" --no-merges)
fi

if [ "$MODE" = "prerelease" ]; then
  SHORT_SHA="${GITHUB_SHA:0:7}"
  cat > release_notes.md <<NOTES_EOF
## halos-docs-tools ${TAG} (Pre-release)

> **Pre-release build from the main branch. Do not pin this tag; pin a stable release.**

**Build Information:**
- Commit: ${SHORT_SHA} (\`${GITHUB_SHA}\`)
- Built: $(date -u '+%Y-%m-%d %H:%M:%S UTC')

### Recent Changes

${CHANGELOG}
NOTES_EOF
else
  cat > release_notes.md <<NOTES_EOF
## halos-docs-tools ${TAG}

Documentation checkers and the halos-i18n MkDocs plugin for HaLOS and Hat Labs documentation sites.

### Changes

${CHANGELOG}

### Installation

Pin this release in a documentation repository's \`pyproject.toml\`, then run \`uv sync\`:

\`\`\`toml
dependencies = [
    "halos-docs-tools @ git+https://github.com/halos-org/docs-tools@${TAG}",
]
\`\`\`
NOTES_EOF
fi

echo "Generated release_notes.md ($MODE):"
cat release_notes.md
