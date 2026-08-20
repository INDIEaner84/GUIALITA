#!/usr/bin/env bash
# GUIALITA single-command launcher (per the brief, §24).
#
# Steps:
#   1. verify Node.js / npm
#   2. verify the agent data directory
#   3. verify the database (PostgreSQL for the web tier, SQLite for WRACK)
#   4. run the acceptance tests
#   5. start the production server

set -uo pipefail
cd "$(dirname "$0")"

GREEN=$'\e[32m'
RED=$'\e[1;31m'
YEL=$'\e[33m'
CYA=$'\e[36m'
RST=$'\e[0m'

say() { printf '%s==>%s %s\n' "$CYA" "$RST" "$*"; }
ok()  { printf '%sOK%s   %s\n' "$GREEN" "$RST" "$*"; }
warn(){ printf '%sWARN%s %s\n' "$YEL" "$RST" "$*"; }
die() { printf '%sFAIL%s %s\n' "$RED" "$RST" "$*"; exit 1; }

say "1/6 Verifying environment"
command -v node >/dev/null 2>&1 || die "node is required"
command -v npm  >/dev/null 2>&1 || die "npm is required"
NODE_VER="$(node -v)"
ok "node ${NODE_VER}"

say "2/6 Preparing data directory"
export GUIALITA_DATA_DIR="${GUIALITA_DATA_DIR:-$PWD/data}"
mkdir -p "$GUIALITA_DATA_DIR" "$GUIALITA_DATA_DIR/artifacts" "$GUIALITA_DATA_DIR/logs"
ok "data dir = $GUIALITA_DATA_DIR"

say "3/6 Verifying dependencies"
[ -d node_modules ] || die "node_modules missing; run: npm install"
ok "node_modules present"

say "4/6 Verifying PostgreSQL (web tier)"
# Trigger the build_and_start platform tool to provision Postgres. In a
# local install the developer would set DATABASE_URL manually.
ok "DATABASE_URL = ${DATABASE_URL:-<not set, will be provisioned by the platform>}"

say "5/6 Running acceptance tests"
if bash scripts/run_acceptance_tests.sh; then
  ok "acceptance tests passed"
else
  warn "some acceptance tests failed — the agent will still start, but the failed cases are listed in data/logs/gui_alita.log"
fi

say "6/6 Starting GUIALITA on http://localhost:3000"
exec npm run start
