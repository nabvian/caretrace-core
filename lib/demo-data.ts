import type { CaseRecord, Claim, Fact, MedicalDocument, Medication } from "./types";
import { resolveCoreConcept } from "./terminology/search-index";

const uuid = (n: number) => `10000000-0000-4000-8000-${String(n).padStart(12, "0")}`;

export const demoCase: CaseRecord = {
  id: "00000000-0000-4000-8000-000000000001",
  caseCode: "CT-DEMO-001",
  patientName: "Arjun Mehta",
  dob: "1988-05-15",
  address: "Synthetic address · Bengaluru, India",
  contactNumber: "+91 90000 00001",
  email: "arjun.mehta@example.test",
  lifecycleState: "AUDITED",
  lifecycleUpdatedAt: "2026-06-30T09:00:00.000Z",
  synthetic: true,
  createdAt: "2026-06-30T09:00:00.000Z",
};

export const demoDocuments: MedicalDocument[] = [
  { id: uuid(1), name: "01_CBC_Jan.pdf", type: "LAB_REPORT", date: "2026-01-18", pages: 2, uploadStatus: "DEMO", processingStatus: "PROCESSED", pageText: { 1: "COMPLETE BLOOD COUNT\nHemoglobin: 9.2 g/dL\nRBC: 3.6 x10^6/µL\nHematocrit: 29.4 %\nMCV: 68 fL\nMCH: 21 pg\nMCHC: 30.9 g/dL\nRDW: 18.0 %\nWBC: 6.3 x10^3/µL\nPlatelets: 390 x10^3/µL", 2: "Report generated 18 Jan 2026. Synthetic demonstration record." } },
  { id: uuid(2), name: "02_Prescription_Jan.pdf", type: "PRESCRIPTION", date: "2026-01-20", pages: 1, uploadStatus: "DEMO", processingStatus: "PROCESSED", pageText: { 1: "PRESCRIPTION\nFerrous sulfate 100 mg\nOral · once daily\nStatus: Active\nStart: 20 Jan 2026" } },
  { id: uuid(3), name: "03_Consultation_Feb.pdf", type: "CONSULTATION", date: "2026-02-03", pages: 2, uploadStatus: "DEMO", processingStatus: "PROCESSED", pageText: { 1: "CONSULTATION NOTE\nPrior CBC reviewed: Hb 9.2 g/dL, MCV 68 fL, platelets 390 x10^3/µL.\nMicrocytic indices documented.", 2: "ASSESSMENT\nIron deficiency confirmed.\nContinue oral iron and obtain iron studies." } },
  { id: uuid(4), name: "04_CBC_Mar.pdf", type: "LAB_REPORT", date: "2026-03-15", pages: 2, uploadStatus: "DEMO", processingStatus: "PROCESSED", pageText: { 1: "COMPLETE BLOOD COUNT\nHemoglobin: 10.4 g/dL\nRBC: 3.6 x10^6/µL\nHematocrit: 29.4 %\nMCV: 72 fL\nMCH: 23 pg\nMCHC: 30.9 g/dL\nRDW: 17.2 %\nWBC: 6.3 x10^3/µL\nPlatelets: 410 x10^3/µL", 2: "Report generated 15 Mar 2026. Synthetic demonstration record." } },
  { id: uuid(5), name: "05_Prescription_Mar.pdf", type: "PRESCRIPTION", date: "2026-03-18", pages: 1, uploadStatus: "DEMO", processingStatus: "PROCESSED", pageText: { 1: "PRESCRIPTION\nFerrous sulfate 100 mg\nOral · once daily\nStatus: Active\nContinue for 12 weeks." } },
  { id: uuid(6), name: "06_Ferritin_Report_Apr.pdf", type: "LAB_REPORT", date: "2026-04-12", pages: 1, uploadStatus: "DEMO", processingStatus: "REQUIRES_REVIEW", processingNote: "Unable to identify structured observations in the supplied scan.", pageText: { 1: "SCANNED LABORATORY REPORT\nImage quality insufficient for structured extraction.\nStatus: Requires review." } },
  { id: uuid(7), name: "07_CBC_Jun.pdf", type: "LAB_REPORT", date: "2026-06-14", pages: 2, uploadStatus: "DEMO", processingStatus: "PROCESSED", pageText: { 1: "COMPLETE BLOOD COUNT\nHemoglobin: 8.7 g/dL\nRBC: 3.6 x10^6/µL\nHematocrit: 29.4 %\nMCV: 66 fL\nMCH: 20.5 pg\nMCHC: 30.9 g/dL\nRDW: 17.2 %\nWBC: 6.1 x10^3/µL\nPlatelets: 438 x10^3/µL", 2: "CHEMISTRY\nCreatinine: 0.9 mg/dL\nGlucose: 92 mg/dL" } },
  { id: uuid(8), name: "08_Discharge_Summary_Jun.pdf", type: "DISCHARGE_SUMMARY", date: "2026-06-15", pages: 3, uploadStatus: "DEMO", processingStatus: "PROCESSED", pageText: { 1: "DISCHARGE SUMMARY\nNo active bleeding documented.\nFerrous sulfate active at discharge.", 2: "Laboratory summary: WBC 11.8 x10^3/µL; platelets 210 x10^3/µL; creatinine 0.9 mg/dL; glucose 92 mg/dL.", 3: "Hemoglobin on 14 Jun: 12.1 g/dL.\nCT findings as described in CT report.\nSee CT report for findings." } },
  { id: uuid(9), name: "09_Medication_List_Jun.pdf", type: "MEDICATION_LIST", date: "2026-06-15", pages: 1, uploadStatus: "DEMO", processingStatus: "PROCESSED", pageText: { 1: "MEDICATION RECONCILIATION\nCurrent medication list reviewed.\nFerrous sulfate: Not listed.\nMedication reconciliation complete." } },
  { id: uuid(10), name: "10_Referral_Letter.pdf", type: "REFERRAL", date: "2026-06-22", pages: 2, uploadStatus: "DEMO", processingStatus: "PROCESSED", pageText: { 1: "REFERRAL LETTER\nRecent Hb 8.7 g/dL; MCV 66 fL.\nCreatinine 0.9 mg/dL.", 2: "Please repeat CBC in six weeks and review prior iron studies." } },
  { id: uuid(11), name: "11_Followup_Notes.pdf", type: "FOLLOWUP", date: "2026-06-28", pages: 1, uploadStatus: "DEMO", processingStatus: "PROCESSED", pageText: { 1: "FOLLOW-UP NOTE\nPrior glucose documented as 92 mg/dL.\nMedication history reviewed; status remains unreconciled." } },
  { id: uuid(12), name: "12_Laboratory_Summary.pdf", type: "OTHER", date: "2026-06-30", pages: 1, uploadStatus: "DEMO", processingStatus: "PROCESSED", pageText: { 1: "LABORATORY SUMMARY\n15 Mar 2026: Hemoglobin 10.4 g/dL.\nHb stable on prior testing." } },
];

const doc = (n: number) => demoDocuments[n - 1];
let factSequence = 0;
const fact = (documentNumber: number, concept: string, originalConcept: string, value: number, unit: string, date: string, page: number, sourceText: string, confidence = 0.97): Fact => {
  factSequence += 1;
  const resolved = resolveCoreConcept(originalConcept); if (!resolved.concept) throw new Error(`Terminology source unavailable for demo fact: ${originalConcept}`);
  return { id: uuid(100 + factSequence), displayId: `F-${String(factSequence).padStart(3, "0")}`, concept, originalConcept, value, unit, date, datePrecision: "day", sourceDocumentId: doc(documentNumber).id, sourceDocument: doc(documentNumber).name, sourcePage: page, sourceText, confidence, type: "OBSERVATION", terminology: { caretraceId: resolved.concept.caretraceId, sourceText: originalConcept, matchType: resolved.matchType as "EXACT" | "ALIAS" | "NORMALIZED", terminologySource: resolved.concept.sourceSystem, sourceCode: resolved.concept.sourceCode, sourceVersion: resolved.concept.sourceVersion, sourceUri: resolved.concept.sourceUri, checksumVerified: null }, temporal: { eventDate: date, dateType: "document", precision: "day", status: "EXPLICIT", sourcePage: page, sourceText, confidence: "explicit" } };
};

export const demoFacts: Fact[] = [
  fact(1, "hemoglobin", "Hemoglobin", 9.2, "g/dL", "2026-01-18", 1, "Hemoglobin: 9.2 g/dL"),
  fact(1, "rbc", "RBC", 3.6, "x10^6/µL", "2026-01-18", 1, "RBC: 3.6 x10^6/µL"),
  fact(1, "hematocrit", "Hematocrit", 29.4, "%", "2026-01-18", 1, "Hematocrit: 29.4 %"),
  fact(1, "mcv", "MCV", 68, "fL", "2026-01-18", 1, "MCV: 68 fL"),
  fact(1, "mch", "MCH", 21, "pg", "2026-01-18", 1, "MCH: 21 pg"),
  fact(1, "mchc", "MCHC", 30.9, "g/dL", "2026-01-18", 1, "MCHC: 30.9 g/dL"),
  fact(1, "rdw", "RDW", 18, "%", "2026-01-18", 1, "RDW: 18.0 %"),
  fact(1, "wbc", "WBC", 6.3, "x10^3/µL", "2026-01-18", 1, "WBC: 6.3 x10^3/µL"),
  fact(1, "platelets", "Platelets", 390, "x10^3/µL", "2026-01-18", 1, "Platelets: 390 x10^3/µL"),
  fact(3, "hemoglobin", "Hb", 9.2, "g/dL", "2026-01-18", 1, "Prior CBC reviewed: Hb 9.2 g/dL", 0.94),
  fact(3, "mcv", "MCV", 68, "fL", "2026-01-18", 1, "Prior CBC reviewed: MCV 68 fL", 0.94),
  fact(3, "platelets", "platelets", 390, "x10^3/µL", "2026-01-18", 1, "platelets 390 x10^3/µL", 0.94),
  fact(4, "hemoglobin", "Hemoglobin", 10.4, "g/dL", "2026-03-15", 1, "Hemoglobin: 10.4 g/dL"),
  fact(4, "rbc", "RBC", 3.6, "x10^6/µL", "2026-03-15", 1, "RBC: 3.6 x10^6/µL"),
  fact(4, "hematocrit", "Hematocrit", 29.4, "%", "2026-03-15", 1, "Hematocrit: 29.4 %"),
  fact(4, "mcv", "MCV", 72, "fL", "2026-03-15", 1, "MCV: 72 fL"),
  fact(4, "mch", "MCH", 23, "pg", "2026-03-15", 1, "MCH: 23 pg"),
  fact(4, "mchc", "MCHC", 30.9, "g/dL", "2026-03-15", 1, "MCHC: 30.9 g/dL"),
  fact(4, "rdw", "RDW", 17.2, "%", "2026-03-15", 1, "RDW: 17.2 %"),
  fact(4, "wbc", "WBC", 6.3, "x10^3/µL", "2026-03-15", 1, "WBC: 6.3 x10^3/µL"),
  fact(4, "platelets", "Platelets", 410, "x10^3/µL", "2026-03-15", 1, "Platelets: 410 x10^3/µL"),
  fact(7, "hemoglobin", "Hemoglobin", 8.7, "g/dL", "2026-06-14", 1, "Hemoglobin: 8.7 g/dL"),
  fact(7, "rbc", "RBC", 3.6, "x10^6/µL", "2026-06-14", 1, "RBC: 3.6 x10^6/µL"),
  fact(7, "hematocrit", "Hematocrit", 29.4, "%", "2026-06-14", 1, "Hematocrit: 29.4 %"),
  fact(7, "mcv", "MCV", 66, "fL", "2026-06-14", 1, "MCV: 66 fL"),
  fact(7, "mch", "MCH", 20.5, "pg", "2026-06-14", 1, "MCH: 20.5 pg"),
  fact(7, "mchc", "MCHC", 30.9, "g/dL", "2026-06-14", 1, "MCHC: 30.9 g/dL"),
  fact(7, "rdw", "RDW", 17.2, "%", "2026-06-14", 1, "RDW: 17.2 %"),
  fact(7, "wbc", "WBC", 6.1, "x10^3/µL", "2026-06-14", 1, "WBC: 6.1 x10^3/µL"),
  fact(7, "platelets", "Platelets", 438, "x10^3/µL", "2026-06-14", 1, "Platelets: 438 x10^3/µL"),
  fact(7, "creatinine", "Creatinine", 0.9, "mg/dL", "2026-06-14", 2, "Creatinine: 0.9 mg/dL"),
  fact(7, "glucose", "Glucose", 92, "mg/dL", "2026-06-14", 2, "Glucose: 92 mg/dL"),
  fact(8, "hemoglobin", "Hemoglobin", 12.1, "g/dL", "2026-06-14", 3, "Hemoglobin on 14 Jun: 12.1 g/dL", 0.96),
  fact(8, "wbc", "WBC", 11.8, "x10^3/µL", "2026-06-14", 2, "Laboratory summary: WBC 11.8 x10^3/µL", 0.96),
  fact(8, "platelets", "platelets", 210, "x10^3/µL", "2026-06-14", 2, "platelets 210 x10^3/µL", 0.96),
  fact(8, "creatinine", "creatinine", 0.9, "mg/dL", "2026-06-14", 2, "creatinine 0.9 mg/dL", 0.96),
  fact(8, "glucose", "glucose", 92, "mg/dL", "2026-06-14", 2, "glucose 92 mg/dL", 0.96),
  fact(10, "hemoglobin", "Hb", 8.7, "g/dL", "2026-06-14", 1, "Recent Hb 8.7 g/dL", 0.93),
  fact(10, "mcv", "MCV", 66, "fL", "2026-06-14", 1, "MCV 66 fL", 0.93),
  fact(10, "creatinine", "Creatinine", 0.9, "mg/dL", "2026-06-14", 1, "Creatinine 0.9 mg/dL", 0.93),
  fact(11, "glucose", "glucose", 92, "mg/dL", "2026-06-14", 1, "Prior glucose documented as 92 mg/dL", 0.91),
  fact(12, "hemoglobin", "Hemoglobin", 10.4, "g/dL", "2026-03-15", 1, "15 Mar 2026: Hemoglobin 10.4 g/dL", 0.92),
];

const med = (n: number, documentNumber: number, date: string, status: Medication["status"], sourceText: string): Medication => ({ id: uuid(300 + n), displayId: `M-${String(n).padStart(3, "0")}`, drugName: "Ferrous sulfate", normalizedDrug: "ferrous sulfate", ingredient:null,brand:null,strength:status === "NOT_LISTED" ? null : "100",strengthUnit:status === "NOT_LISTED" ? null : "mg",dose: status === "NOT_LISTED" ? null : "100 mg",doseAmount:null,doseUnit:null,doseForm:null,frequency: status === "NOT_LISTED" ? null : "once daily", route: status === "NOT_LISTED" ? null : "oral",duration:null,status, date,startDate:status==="ACTIVE"?date:null,stopDate:status==="INACTIVE"?date:null,prescriber:null, sourceDocumentId: doc(documentNumber).id, sourceDocument: doc(documentNumber).name, sourcePage: 1, sourceText, confidence: 0.97 });

export const demoMedications: Medication[] = [
  med(1, 2, "2026-01-20", "ACTIVE", "Ferrous sulfate 100 mg · Oral · once daily · Status: Active"),
  med(2, 5, "2026-03-18", "ACTIVE", "Ferrous sulfate 100 mg · Status: Active"),
  med(3, 8, "2026-06-15", "ACTIVE", "Ferrous sulfate active at discharge."),
  med(4, 9, "2026-06-15", "NOT_LISTED", "Ferrous sulfate: Not listed."),
];

const claim = (n: number, documentNumber: number, date: string, text: string, page: number, extra: Partial<Claim> = {}): Claim => ({ id: uuid(400 + n), displayId: `C-${String(n).padStart(3, "0")}`, claim: text, date, sourceDocumentId: doc(documentNumber).id, sourceDocument: doc(documentNumber).name, sourcePage: page, sourceText: text, confidence: 0.94, ...extra });

export const demoClaims: Claim[] = [
  claim(1, 3, "2026-02-03", "Microcytic indices documented", 1, { supportConcepts: ["mcv", "mch"] }),
  claim(2, 3, "2026-02-03", "Iron deficiency confirmed", 2, { supportConcepts: ["ferritin", "tsat"], gapRule: "MISSING_SUPPORT" }),
  claim(3, 5, "2026-03-18", "Continue oral iron for 12 weeks", 1),
  claim(4, 8, "2026-06-15", "See CT report for findings", 3, { gapRule: "MISSING_SOURCE", referencedDocument: "CT report" }),
  claim(5, 8, "2026-06-15", "No active bleeding documented", 1),
  claim(6, 8, "2026-06-15", "Ferrous sulfate active at discharge", 1),
  claim(7, 9, "2026-06-15", "Medication reconciliation complete", 1),
  claim(8, 10, "2026-06-22", "Repeat CBC in six weeks", 2, { gapRule: "MISSING_FOLLOWUP", expectedConcept: "hemoglobin" }),
  claim(9, 12, "2026-06-30", "Hb stable on prior testing", 1, { supportConcepts: ["hemoglobin"] }),
];
