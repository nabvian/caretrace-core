import type { TerminologyConcept, TerminologySearchResult } from "./types";
import { coreTerminologyConcepts } from "./core-seed";

export function normalizeSearchText(value: string) {
  return value.normalize("NFKD").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim().replace(/\s+/g, " ");
}

function levenshtein(a: string, b: string) {
  if (!a.length) return b.length;
  if (!b.length) return a.length;
  const matrix = Array.from({ length: b.length + 1 }, (_, row) => [row, ...Array(a.length).fill(0)]);
  for (let column = 0; column <= a.length; column += 1) matrix[0][column] = column;
  for (let row = 1; row <= b.length; row += 1) {
    for (let column = 1; column <= a.length; column += 1) {
      matrix[row][column] = b[row - 1] === a[column - 1]
        ? matrix[row - 1][column - 1]
        : Math.min(matrix[row - 1][column - 1] + 1, matrix[row][column - 1] + 1, matrix[row - 1][column] + 1);
    }
  }
  return matrix[b.length][a.length];
}

export class TerminologySearchIndex {
  private readonly concepts: TerminologyConcept[];
  private readonly labels = new Map<string, TerminologyConcept[]>();
  private readonly aliases = new Map<string, TerminologyConcept[]>();
  private readonly codes = new Map<string, TerminologyConcept[]>();

  constructor(concepts: TerminologyConcept[]) {
    this.concepts = concepts.filter((concept) => concept.status === "ACTIVE");
    for (const concept of this.concepts) {
      this.add(this.labels, normalizeSearchText(concept.label), concept);
      this.add(this.codes, normalizeSearchText(concept.sourceCode), concept);
      this.add(this.codes, normalizeSearchText(concept.caretraceId), concept);
      for (const alias of concept.aliases) this.add(this.aliases, normalizeSearchText(alias), concept);
    }
  }

  private add(index: Map<string, TerminologyConcept[]>, key: string, concept: TerminologyConcept) {
    index.set(key, [...(index.get(key) ?? []), concept]);
  }

  search(query: string, limit = 8): TerminologySearchResult[] {
    const normalized = normalizeSearchText(query);
    if (!normalized) return [{ query, matchType: "UNRESOLVED", confidence: "NONE", reviewRequired: true, concept: null, reason: "A terminology query is required." }];
    const results: TerminologySearchResult[] = [];
    const seen = new Set<string>();
    const push = (concept: TerminologyConcept, matchType: TerminologySearchResult["matchType"], confidence: TerminologySearchResult["confidence"], reason: string) => {
      if (seen.has(concept.id) || results.length >= limit) return;
      seen.add(concept.id);
      results.push({ query, matchType, confidence, reviewRequired: matchType === "FUZZY", concept, reason });
    };

    for (const concept of this.codes.get(normalized) ?? []) push(concept, "EXACT", "HIGH", "Exact CARETRACE or source-code match.");
    for (const concept of this.labels.get(normalized) ?? []) push(concept, "EXACT", "HIGH", "Exact preferred-label match.");
    for (const concept of this.aliases.get(normalized) ?? []) push(concept, "ALIAS", "HIGH", "Alias explicitly supplied by the active terminology release.");
    for (const concept of this.concepts) {
      const label = normalizeSearchText(concept.label);
      if (label.startsWith(normalized) || concept.aliases.some((alias) => normalizeSearchText(alias).startsWith(normalized))) push(concept, "NORMALIZED", "MEDIUM", "Normalized prefix match.");
    }
    if (results.length < limit && normalized.length >= 4) {
      for (const concept of this.concepts) {
        const candidates = [concept.label, ...concept.aliases].map(normalizeSearchText);
        const distance = Math.min(...candidates.map((candidate) => levenshtein(normalized, candidate)));
        const threshold = Math.max(1, Math.floor(normalized.length * 0.22));
        if (distance <= threshold) push(concept, "FUZZY", "LOW", `Possible match at edit distance ${distance}; review is required.`);
      }
    }
    return results.length ? results : [{ query, matchType: "UNRESOLVED", confidence: "NONE", reviewRequired: true, concept: null, reason: "No concept was located in the validated local index. No mapping was guessed." }];
  }
}

export function resolveCoreConcept(query: string) {
  return new TerminologySearchIndex(coreTerminologyConcepts).search(query, 1)[0];
}
