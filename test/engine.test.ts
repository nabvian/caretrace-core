// CARETRACE open core — engine test
// Runs the deterministic evidence engine over the fictional demo case and
// asserts its published invariants. No external services required.
//
// Run with:  npm test   (tsx test/engine.test.ts)

import assert from "node:assert/strict";
import { buildCaseAudit } from "../lib/case-audit";
import { demoAudit, runEvidenceAudit } from "../lib/evidence-engine";

let passed = 0;
function it(name: string, fn: () => void) {
  fn();
  passed += 1;
  console.log(`  ok  ${name}`);
}

console.log("CARETRACE core — deterministic engine");

// The engine self-validates these invariants on import; assert them explicitly
// so the test fails loudly (not just via a thrown import) if the demo drifts.
const expected = { documents: 12, facts: 42, claims: 9, changes: 7, conflicts: 4, gaps: 3 } as const;

it("runEvidenceAudit() reproduces the published demo metrics", () => {
  const audit = runEvidenceAudit();
  for (const [key, value] of Object.entries(expected)) {
    assert.equal(
      audit.metrics[key as keyof typeof expected],
      value,
      `metric ${key} expected ${value}, got ${audit.metrics[key as keyof typeof expected]}`,
    );
  }
});

it("the audit is deterministic (two runs are identical)", () => {
  assert.deepEqual(runEvidenceAudit(), runEvidenceAudit());
});

it("exported demoAudit matches a fresh run", () => {
  assert.deepEqual(demoAudit.metrics, runEvidenceAudit().metrics);
});

it("every conflict is left UNRESOLVED (the engine never picks a winner)", () => {
  for (const conflict of runEvidenceAudit().conflicts) {
    assert.equal(conflict.status, "UNRESOLVED");
  }
});

it("traceability is a percentage in [0, 100]", () => {
  const t = runEvidenceAudit().metrics.traceability;
  assert.ok(t >= 0 && t <= 100, `traceability out of range: ${t}`);
});

it("buildCaseAudit() on an empty case yields zeroed metrics, not a crash", () => {
  const empty = buildCaseAudit(
    { id: "test", name: "Empty", createdAt: new Date().toISOString() } as never,
    [],
  );
  assert.equal(empty.metrics.documents, 0);
  assert.equal(empty.metrics.conflicts, 0);
  assert.equal(empty.metrics.gaps, 0);
});

console.log(`\n${passed} passing`);
