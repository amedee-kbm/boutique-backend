#!/usr/bin/env bash
#
# Fail when a Python source file grows past its ceiling.
#
# Why this exists: ruff has no file-length rule, and a 1500-line module is not a
# style problem, it is a design problem — several things live in one file and
# nobody has been forced to name the seam. The ceiling forces the question.
#
# The ceiling is a RATCHET. It only ever moves down. Never raise it to make a
# red build green; split the file instead.
#
# A per-file override IS the ceiling for that file, and every override carries a
# rationale. An override without one is a bug in this config, not an exemption.
#
# Migrations are excluded: generated, append-only, never read.
#
# Usage: ./scripts/check-file-length.sh [default_max]

set -euo pipefail

DEFAULT_MAX="${1:-500}"
SOURCE_ROOT="src"

# path -> ceiling. Add an entry only with a comment saying why the file earns it.
declare -A OVERRIDES=(
	# A flat, sectioned configuration file. Splitting it into a settings package
	# buys indirection, not clarity, at this size.
	["src/boutique/settings.py"]=250
)

fail=0

while IFS= read -r file; do
	lines=$(wc -l <"$file")
	ceiling="${OVERRIDES[$file]:-$DEFAULT_MAX}"

	if ((lines > ceiling)); then
		printf '  %-52s %5d lines  (ceiling %d)\n' "$file" "$lines" "$ceiling"
		fail=1
	fi
done < <(find "$SOURCE_ROOT" -name '*.py' -not -path '*/migrations/*' | sort)

if ((fail)); then
	echo
	echo "File(s) over the ceiling. Split them — do not raise the limit."
	exit 1
fi

echo "OK: no file exceeds its length ceiling (default ${DEFAULT_MAX})"
