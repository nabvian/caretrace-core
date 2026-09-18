export type TerminologySourceKey = "caretrace_core" | "loinc" | "snomed_ct" | "rxnorm" | "icd11" | "ucum" | (string & {});
export type ImportFormat = "CSV" | "TSV" | "JSON" | "JSONL" | "XML" | "ZIP" | "RF2" | "FHIR" | "RRF";
export type MatchType = "EXACT" | "ALIAS" | "NORMALIZED" | "FUZZY" | "UNRESOLVED";
export type ReleaseStatus = "STAGING" | "COMPLETE" | "FAILED_VALIDATION" | "INACTIVE" | "ROLLED_BACK";
export type LicenseStatus = "APPROVED" | "REVIEW_REQUIRED" | "REJECTED";

export interface TerminologyLicense {
  name: string;
  url: string;
  attributionRequired: boolean;
  redistributionAllowed: boolean | "REVIEW_REQUIRED";
  commercialUse: boolean | "REVIEW_REQUIRED";
  apiRequired: boolean;
  downloadRequired: boolean;
  notes: string;
}

export interface TerminologySourceDefinition {
  key: TerminologySourceKey;
  name: string;
  type: "internal" | "clinical_observation" | "clinical_terminology" | "medication" | "classification" | "unit_system" | string;
  bulkSupported: boolean;
  apiSupported: boolean;
  supportedFormats: ImportFormat[];
  officialHomepage: string;
  officialDocumentation: string;
  officialApiBase?: string;
  sourceUri: string;
  environment: {
    apiBase?: string;
    apiKey?: string;
    username?: string;
    password?: string;
    clientId?: string;
    clientSecret?: string;
    branch?: string;
    release?: string;
  };
  license: TerminologyLicense;
  maxAgeDays?: number;
}

export interface TerminologyMapping {
  system: string;
  code: string | null;
  sourceVersion: string;
  sourceUri: string;
  relationship: "exact" | "equivalent" | "related" | "broader" | "narrower" | "unverified";
  status: "VERIFIED" | "UNVERIFIED";
}

export interface TerminologyRelationship {
  type: string;
  targetSourceCode: string;
  group?: string;
  active: boolean;
}

export interface TerminologyConcept {
  id: string;
  caretraceId: string;
  sourceSystem: TerminologySourceKey;
  sourceCode: string;
  sourceVersion: string;
  sourceUri: string;
  sourceLabel: string;
  label: string;
  domain: string;
  category: string;
  semanticType: string;
  aliases: string[];
  units: string[];
  relationships: TerminologyRelationship[];
  mappings: TerminologyMapping[];
  status: "ACTIVE" | "INACTIVE";
  importedAt: string;
  releaseId: string;
}

export interface TerminologyRelease {
  id: string;
  source: TerminologySourceKey;
  version: string;
  releaseDate: string;
  importDate: string;
  licenseName: string;
  licenseStatus: LicenseStatus;
  checksumAlgorithm: "SHA-256" | "MD5" | "NONE";
  checksumExpected: string | null;
  checksumActual: string | null;
  checksumVerified: boolean | null;
  recordCount: number;
  status: ReleaseStatus;
  format: ImportFormat;
  artifactKey: string | null;
  previousReleaseId: string | null;
}

export interface ImportIssue {
  row?: number;
  code: string;
  message: string;
  severity: "ERROR" | "WARNING";
}

export interface TerminologyImportReport {
  importId: string;
  source: TerminologySourceKey | "UNRESOLVED";
  detectedSource: TerminologySourceKey | "UNRESOLVED";
  filename: string;
  format: ImportFormat | "UNRESOLVED";
  version: string | null;
  releaseDate: string | null;
  startedAt: string;
  completedAt: string;
  recordsDetected: number;
  recordsImported: number;
  rejected: number;
  unprocessed: number;
  duplicateIds: number;
  missingIds: number;
  invalidRecords: number;
  relationshipErrors: number;
  checksumAlgorithm: "SHA-256" | "MD5" | "NONE";
  checksumExpected: string | null;
  checksumActual: string | null;
  checksumStatus: "VALID" | "INVALID" | "NOT_PROVIDED";
  licenseStatus: LicenseStatus;
  issues: ImportIssue[];
  status: "COMPLETE" | "FAILED_VALIDATION";
}

export interface DetectedTerminologyFile {
  filename: string;
  format: ImportFormat | "UNRESOLVED";
  source: TerminologySourceKey | "UNRESOLVED";
  version: string | null;
  releaseDate: string | null;
  archiveEntries: string[];
  headers: string[];
  confidence: "HIGH" | "MEDIUM" | "LOW";
  importer: string | null;
}

export interface TerminologySearchResult {
  query: string;
  matchType: MatchType;
  confidence: "HIGH" | "MEDIUM" | "LOW" | "NONE";
  reviewRequired: boolean;
  concept: TerminologyConcept | null;
  reason: string;
}

export interface TerminologyHealthItem {
  source: TerminologySourceKey;
  name: string;
  status: "VALID" | "USING_LOCAL_CACHE" | "NOT_IMPORTED" | "UNAVAILABLE" | "LICENSE_REVIEW_REQUIRED";
  activeRelease: TerminologyRelease | null;
  officialApiConfigured: boolean;
  localValidatedRelease: boolean;
  operationsEnabled: boolean;
  message: string;
}

export interface ProviderConcept {
  sourceCode: string;
  label: string;
  sourceUri: string;
  version: string;
  aliases: string[];
  status: "ACTIVE" | "INACTIVE";
  raw: unknown;
}

export interface ProviderResult<T> {
  ok: boolean;
  value: T | null;
  source: "OFFICIAL_API" | "CACHE" | "NONE";
  failure?: {
    code: "NOT_CONFIGURED" | "TIMEOUT" | "RATE_LIMITED" | "AUTHENTICATION" | "CIRCUIT_OPEN" | "UNAVAILABLE" | "INVALID_RESPONSE";
    reason: string;
    retryable: boolean;
  };
}

export interface TerminologyProvider {
  readonly source: TerminologySourceDefinition;
  getMetadata(): Promise<ProviderResult<Record<string, unknown>>>;
  search(query: string): Promise<ProviderResult<ProviderConcept[]>>;
  getConcept(code: string): Promise<ProviderResult<ProviderConcept>>;
  getVersion(): Promise<ProviderResult<string>>;
  downloadRelease(version?: string): Promise<ProviderResult<{ url: string; checksum?: string; checksumAlgorithm?: "MD5" | "SHA-256" }>>;
  validateRelease?(bytes: Uint8Array, metadata: Record<string, unknown>): Promise<TerminologyImportReport>;
  importRelease?(bytes: Uint8Array, metadata: Record<string, unknown>): Promise<TerminologyImportReport>;
}

export interface ImportContext {
  source: TerminologySourceDefinition;
  version: string;
  releaseId: string;
  releaseDate: string;
  importedAt: string;
}

export interface ParsedTerminologyRecords {
  concepts: TerminologyConcept[];
  detectedRecords: number;
  rejectedRecords: number;
  unprocessedRecords: number;
  issues: ImportIssue[];
  requiredColumns: string[];
  detectedColumns: string[];
}

export interface TerminologyImporter {
  readonly name: string;
  readonly formats: ImportFormat[];
  canImport(file: DetectedTerminologyFile): boolean;
  parse(bytes: Uint8Array, context: ImportContext, filename: string): Promise<ParsedTerminologyRecords>;
}
