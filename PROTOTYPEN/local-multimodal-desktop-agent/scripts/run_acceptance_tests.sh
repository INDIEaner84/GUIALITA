#!/usr/bin/env bash
# Run the GUIALITA acceptance tests headlessly. The brief explicitly
# requires us to actually run the tests, not just claim they work.

set -uo pipefail
cd "$(dirname "$0")/.."

export GUIALITA_DATA_DIR="${GUIALITA_DATA_DIR:-$PWD/data}"
mkdir -p "$GUIALITA_DATA_DIR"

# Use tsx so we can run TypeScript directly without a build step.
if [ -x node_modules/.bin/tsx ]; then
  exec ./node_modules/.bin/tsx src/scripts/run_tests.ts "$@"
else
  echo "tsx not installed; falling back to ts-node"
  exec ./node_modules/.bin/ts-node --transpile-only src/scripts/run_tests.ts "$@"
fi
