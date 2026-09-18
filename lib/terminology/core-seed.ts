import type { TerminologyConcept, TerminologyRelease } from "./types";
import { quantitativeRules, statusRules } from "../evidence-packs";

const importedAt = "2026-08-23T00:00:00.000Z";
const releaseId = "50000000-0000-4000-8000-000000000001";

export const coreTerminologyRelease: TerminologyRelease = {
  id: releaseId, source: "caretrace_core", version: "2026.08-multimodal.1", releaseDate: "2026-08-25", importDate: importedAt,
  licenseName: "CARETRACE deterministic evidence-pack vocabulary", licenseStatus: "APPROVED", checksumAlgorithm: "NONE", checksumExpected: null, checksumActual: null, checksumVerified: null,
  recordCount: 66, status: "COMPLETE", format: "JSON", artifactKey: null, previousReleaseId: null,
};

const concept = (index: number, slug: string, label: string, category: string, aliases: string[], units: string[], domain = "laboratory", semanticType = "quantitative_observation"): TerminologyConcept => ({
  id: `51000000-0000-4000-8000-${String(index).padStart(12, "0")}`,
  caretraceId: `caretrace:${domain === "laboratory" ? "lab" : domain}:${slug}`,
  sourceSystem: "caretrace_core",
  sourceCode: `caretrace-pack:${domain}:${slug}`,
  sourceVersion: coreTerminologyRelease.version,
  sourceUri: `urn:caretrace:evidence-pack:${domain}:${slug}`,
  sourceLabel: label,
  label,
  domain,
  category,
  semanticType,
  aliases,
  units,
  relationships: [],
  mappings: [],
  status: "ACTIVE",
  importedAt,
  releaseId,
});

export const coreTerminologyConcepts: TerminologyConcept[] = [
  concept(1, "hemoglobin", "Hemoglobin", "hematology", ["Hb", "Hgb", "Haemoglobin", "Hemoglobin level"], ["g/dL"]),
  concept(2, "rbc", "Red blood cell count", "hematology", ["RBC", "RBC total", "RBC (Total)", "Red blood cells"], ["x10^6/µL"]),
  concept(3, "hematocrit", "Hematocrit", "hematology", ["Hct", "PCV", "Packed cell volume"], ["%"]),
  concept(4, "mcv", "Mean corpuscular volume", "hematology", ["MCV"], ["fL"]),
  concept(5, "mch", "Mean corpuscular hemoglobin", "hematology", ["MCH"], ["pg"]),
  concept(6, "mchc", "Mean corpuscular hemoglobin concentration", "hematology", ["MCHC"], ["g/dL"]),
  concept(7, "rdw", "Red cell distribution width", "hematology", ["RDW"], ["%"]),
  concept(8, "wbc", "White blood cell count", "hematology", ["WBC", "WBC total", "WBC (Total)", "Total leukocyte count", "White blood cells"], ["x10^3/µL"]),
  concept(9, "platelets", "Platelet count", "hematology", ["Platelet", "Platelets", "PLT"], ["x10^3/µL"]),
  concept(10, "ferritin", "Ferritin", "iron_studies", ["Serum ferritin"], ["ng/mL"]),
  concept(11, "creatinine", "Creatinine", "chemistry", ["Serum creatinine"], ["mg/dL"]),
  concept(12, "glucose", "Glucose", "chemistry", ["Blood glucose", "Blood sugar", "Blood sugar (F)", "Fasting blood sugar"], ["mg/dL"]),
  concept(13, "sodium", "Sodium", "chemistry", ["Serum sodium"], ["mEq/L"]),
  concept(14, "potassium", "Potassium", "chemistry", ["Serum potassium"], ["mEq/L"]),
  concept(15, "chloride", "Chloride", "chemistry", ["Serum chloride"], ["mEq/L"]),
  concept(16, "calcium", "Calcium", "chemistry", ["Serum calcium"], ["mg/dL"]),
  concept(17, "urea", "Urea", "chemistry", ["Serum urea", "Blood urea"], ["mg/dL"]),
  concept(18, "uric_acid", "Uric acid", "chemistry", ["Serum uric acid"], ["mg/dL"]),
  concept(19, "total_protein", "Total protein", "chemistry", ["Serum total protein", "Serum protein (Total)", "Total proteins"], ["g/dL"]),
  concept(20, "albumin", "Albumin", "chemistry", ["Serum albumin"], ["g/dL"]),
  concept(21, "urine_specific_gravity", "Urine specific gravity", "urinalysis", ["Specific gravity"], ["1"]),
  ...quantitativeRules.map((rule, offset) => concept(22 + offset, rule.key, rule.label, rule.category, rule.aliases, rule.units, rule.domain)),
  ...statusRules.map((rule, offset) => concept(47 + offset, rule.key, rule.label, "qualitative_finding", rule.values.flatMap((item) => [item.label, ...item.phrases]), [], rule.domain, "qualitative_observation")),
];
