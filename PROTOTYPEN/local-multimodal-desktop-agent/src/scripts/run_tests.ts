/**
 * Test entry script. Runs the acceptance tests and prints a summary.
 * Used by `bash scripts/run_acceptance_tests.sh` and by `npm run test:acceptance`.
 */

import { runAll } from "../tests/acceptance";

async function main() {
  const out = await runAll();
  // eslint-disable-next-line no-console
  console.log("\n=========================================");
  // eslint-disable-next-line no-console
  console.log(`GUIALITA acceptance: ${out.passed}/${out.total} passed`);
  // eslint-disable-next-line no-console
  console.log("=========================================");
  for (const r of out.results) {
    // eslint-disable-next-line no-console
    console.log(`${r.passed ? "✅" : "❌"} ${r.name}`);
    if (!r.passed) {
      // eslint-disable-next-line no-console
      console.log(`   ${r.detail}`);
    }
  }
  process.exit(out.passed === out.total ? 0 : 1);
}

void main();
