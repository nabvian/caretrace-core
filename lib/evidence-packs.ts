import type { DocumentType } from "./types";

export type QuantitativeRule = {
  key: string;
  label: string;
  domain: string;
  category: string;
  modality: string;
  units: string[];
  aliases: string[];
  materialAbs: number;
  materialRel: number;
  episodeWindowDays: number;
};

export type StatusValueRule = { key: string; label: string; phrases: string[]; positive: boolean };
export type StatusRule = {
  key: string;
  label: string;
  domain: string;
  modality: string;
  documentTypes: DocumentType[];
  episodeWindowDays: number;
  values: StatusValueRule[];
};

export type ClaimRule = {
  key: string;
  label: string;
  patterns: string[];
  requiresAny: string[];
  requiresLabels: string[];
  lookbackDays: number;
  modality: string;
};

const q = (key: string, label: string, domain: string, category: string, modality: string, units: string[], aliases: string[], materialAbs: number, materialRel: number, episodeWindowDays: number): QuantitativeRule => ({ key, label, domain, category, modality, units, aliases, materialAbs, materialRel, episodeWindowDays });
const value = (key: string, label: string, phrases: string[], positive = true): StatusValueRule => ({ key, label, phrases, positive });
const status = (key: string, label: string, domain: string, modality: string, documentTypes: DocumentType[], episodeWindowDays: number, values: StatusValueRule[]): StatusRule => ({ key, label, domain, modality, documentTypes, episodeWindowDays, values });

/**
 * Evidence packs configure extraction and comparison. The engine carries no
 * report-layout templates and never selects a clinically "correct" result;
 * everything it compares against is declared here as data.
 */
export const quantitativeRules: QuantitativeRule[] = [
  q("heart_rate", "Heart rate", "cardiology", "ecg", "CARDIOLOGY", ["/min"], ["Heart rate", "HR", "Ventricular rate", "Pulse rate"], 8, .12, 1),
  q("pr_interval", "PR interval", "cardiology", "ecg", "CARDIOLOGY", ["ms"], ["PR interval"], 20, .12, 2),
  q("qrs_duration", "QRS duration", "cardiology", "ecg", "CARDIOLOGY", ["ms"], ["QRS duration", "QRS width"], 15, .12, 2),
  q("qt_interval", "QT interval", "cardiology", "ecg", "CARDIOLOGY", ["ms"], ["QT interval"], 25, .10, 2),
  q("qtc_interval", "QTc interval", "cardiology", "ecg", "CARDIOLOGY", ["ms"], ["QTc", "Corrected QT", "QTcB", "QTcF"], 25, .10, 2),
  q("ejection_fraction", "Left ventricular ejection fraction", "cardiology", "echocardiography", "CARDIOLOGY", ["%"], ["Ejection fraction", "LVEF", "Left ventricular ejection fraction"], 5, .10, 30),
  q("lv_diameter", "LV end-diastolic diameter", "cardiology", "echocardiography", "CARDIOLOGY", ["mm"], ["LVEDD", "LV end diastolic diameter", "LV internal diameter"], 4, .10, 30),
  q("iv_septum", "Interventricular septal thickness", "cardiology", "echocardiography", "CARDIOLOGY", ["mm"], ["IVS", "Interventricular septum", "Septal thickness"], 2, .15, 30),
  q("lesion_size", "Lesion size", "imaging", "measurement", "IMAGING", ["mm"], ["Lesion size", "Mass size", "Nodule size", "Tumour size", "Tumor size"], 3, .15, 30),
  q("spleen_length", "Spleen length", "imaging", "measurement", "IMAGING", ["mm"], ["Spleen length", "Splenic length"], 5, .10, 30),
  q("liver_span", "Liver span", "imaging", "measurement", "IMAGING", ["mm"], ["Liver span", "Hepatic span"], 5, .10, 30),
  q("kidney_length", "Kidney length", "imaging", "measurement", "IMAGING", ["mm"], ["Kidney length", "Renal length"], 5, .10, 30),
  q("cortical_thickness", "Cortical thickness", "imaging", "measurement", "IMAGING", ["mm"], ["Cortical thickness", "Renal cortical thickness"], 2, .15, 30),
  q("calcium_score", "Coronary calcium score", "imaging", "measurement", "IMAGING", ["1"], ["Calcium score", "Agatston score", "Coronary calcium score"], 10, .15, 30),
  q("eeg_background_freq", "EEG background frequency", "neurophysiology", "eeg", "NEUROPHYSIOLOGY", ["Hz"], ["Background frequency", "Posterior dominant rhythm", "PDR", "Background rhythm", "Alpha frequency"], 1, .15, 7),
  q("nerve_conduction_velocity", "Nerve conduction velocity", "neurophysiology", "ncs", "NEUROPHYSIOLOGY", ["m/s"], ["Conduction velocity", "NCV", "Motor conduction velocity", "Sensory conduction velocity"], 5, .12, 30),
  q("distal_latency", "Distal motor latency", "neurophysiology", "ncs", "NEUROPHYSIOLOGY", ["ms"], ["Distal latency", "Distal motor latency", "Terminal latency"], .8, .15, 30),
  q("f_wave_latency", "F-wave latency", "neurophysiology", "ncs", "NEUROPHYSIOLOGY", ["ms"], ["F wave latency", "F-wave latency"], 2, .12, 30),
  q("cmap_amplitude", "CMAP amplitude", "neurophysiology", "ncs", "NEUROPHYSIOLOGY", ["mV"], ["CMAP", "CMAP amplitude", "Compound motor action potential"], 1, .20, 30),
  q("viral_load", "Viral load", "molecular", "assay", "MOLECULAR", ["/mL"], ["Viral load", "HBV DNA", "HCV RNA", "HIV RNA", "Quantitative PCR"], 0, .50, 30),
  q("ct_value", "PCR cycle threshold (Ct)", "molecular", "assay", "MOLECULAR", ["1"], ["Ct value", "Cycle threshold"], 3, .10, 30),
  q("variant_allele_fraction", "Variant allele fraction", "molecular", "genomics", "MOLECULAR", ["%"], ["Variant allele fraction", "VAF", "Allele fraction", "Allele frequency"], 5, .20, 90),
  q("tumor_mutational_burden", "Tumour mutational burden", "molecular", "genomics", "MOLECULAR", ["1"], ["Tumour mutational burden", "Tumor mutational burden", "TMB", "Mutational burden"], 2, .20, 180),
  q("microsatellite_score", "Microsatellite instability score", "molecular", "genomics", "MOLECULAR", ["%"], ["MSI score", "Microsatellite instability score"], 5, .20, 180),
  q("her2_ratio", "HER2/CEP17 ratio", "molecular", "assay", "MOLECULAR", ["1"], ["HER2/CEP17 ratio", "HER2 ratio", "HER2 CEP17"], .3, .15, 365),
];

const narrativeDocuments: DocumentType[] = ["IMAGING_REPORT", "CARDIOLOGY_REPORT", "NEUROPHYSIOLOGY_REPORT", "MOLECULAR_REPORT", "PATHOLOGY_REPORT", "CONSULTATION", "DISCHARGE_SUMMARY", "REFERRAL", "FOLLOWUP", "OTHER"];
export const statusRules: StatusRule[] = [
  status("acute_infarct", "Acute infarct", "imaging", "IMAGING", narrativeDocuments, 7, [value("ABSENT", "No acute infarct", ["no acute infarct", "no infarct", "negative for acute infarct"], false), value("PRESENT", "Acute infarct present", ["acute infarct", "acute cerebral infarct"])]),
  status("hemorrhage", "Haemorrhage", "imaging", "IMAGING", narrativeDocuments, 7, [value("ABSENT", "No haemorrhage", ["no acute hemorrhage", "no acute haemorrhage", "no intracranial hemorrhage", "no intracranial haemorrhage"], false), value("PRESENT", "Haemorrhage present", ["acute hemorrhage", "acute haemorrhage", "intracranial hemorrhage", "intracranial haemorrhage"])]),
  status("consolidation", "Pulmonary consolidation", "imaging", "IMAGING", narrativeDocuments, 7, [value("ABSENT", "No consolidation", ["no focal consolidation", "no consolidation"], false), value("PRESENT", "Consolidation present", ["focal consolidation", "airspace consolidation"])]),
  status("pleural_effusion", "Pleural effusion", "imaging", "IMAGING", narrativeDocuments, 7, [value("ABSENT", "No pleural effusion", ["no pleural effusion", "no effusion"], false), value("PRESENT", "Pleural effusion present", ["pleural effusion"])]),
  status("metastasis", "Metastatic disease", "imaging", "IMAGING", narrativeDocuments, 30, [value("ABSENT", "No metastasis", ["no metastasis", "no metastatic disease", "no evidence of metastasis"], false), value("PRESENT", "Metastatic disease present", ["metastatic disease", "metastasis present", "metastases"])]),
  status("fracture", "Fracture", "imaging", "IMAGING", narrativeDocuments, 7, [value("ABSENT", "No fracture", ["no acute fracture", "no fracture"], false), value("PRESENT", "Fracture present", ["acute fracture", "fracture identified"])]),
  status("rhythm", "Cardiac rhythm", "cardiology", "CARDIOLOGY", narrativeDocuments, 2, [value("SINUS", "Sinus rhythm", ["normal sinus rhythm", "sinus rhythm"], false), value("AF", "Atrial fibrillation", ["atrial fibrillation", "af with"]), value("FLUTTER", "Atrial flutter", ["atrial flutter"]), value("SINUS_TACHY", "Sinus tachycardia", ["sinus tachycardia"]), value("SINUS_BRADY", "Sinus bradycardia", ["sinus bradycardia"]), value("PACED", "Paced rhythm", ["paced rhythm", "pacemaker rhythm"])]),
  status("st_changes", "ST segment changes", "cardiology", "CARDIOLOGY", narrativeDocuments, 2, [value("ABSENT", "No ST changes", ["no acute st-t changes", "no st-t changes", "no st changes", "no ischaemic st changes"], false), value("DEPRESSION", "ST depression", ["st depression"]), value("ELEVATION", "ST elevation", ["st elevation"]), value("NONSPECIFIC", "Nonspecific ST changes", ["nonspecific st changes"])]),
  status("t_wave", "T wave morphology", "cardiology", "CARDIOLOGY", narrativeDocuments, 2, [value("NORMAL", "No T wave inversion", ["no t wave inversion"], false), value("INVERSION", "T wave inversion", ["t wave inversion", "inverted t waves"]), value("FLATTENED", "Flattened T waves", ["flattened t waves"])]),
  status("conduction_block", "Conduction block", "cardiology", "CARDIOLOGY", narrativeDocuments, 2, [value("ABSENT", "No conduction block", ["no bundle branch block", "no conduction block"], false), value("RBBB", "Right bundle branch block", ["right bundle branch block", "incomplete rbbb", "rbbb"]), value("LBBB", "Left bundle branch block", ["left bundle branch block", "lbbb"]), value("AVB1", "First degree AV block", ["first degree av block"])]),
  status("valve_status", "Valvular findings", "cardiology", "CARDIOLOGY", narrativeDocuments, 30, [value("NORMAL", "No valvular abnormality", ["no valvular abnormality", "valves are normal"], false), value("MR", "Mitral regurgitation", ["trivial mitral regurgitation", "mitral regurgitation"]), value("AS", "Aortic stenosis", ["aortic stenosis"])]),
  status("epileptiform_activity", "Epileptiform activity", "neurophysiology", "NEUROPHYSIOLOGY", narrativeDocuments, 7, [value("ABSENT", "No epileptiform activity", ["no epileptiform discharges", "no epileptiform activity", "no epileptiform abnormality"], false), value("PRESENT", "Epileptiform discharges present", ["epileptiform discharges", "spike and wave", "sharp waves", "epileptiform activity"])]),
  status("seizure_activity", "Electrographic seizure activity", "neurophysiology", "NEUROPHYSIOLOGY", narrativeDocuments, 7, [value("ABSENT", "No seizure activity", ["no electrographic seizures", "no seizure activity"], false), value("PRESENT", "Electrographic seizure recorded", ["electrographic seizure"])]),
  status("eeg_asymmetry", "EEG focality", "neurophysiology", "NEUROPHYSIOLOGY", narrativeDocuments, 7, [value("NORMAL", "No focal abnormality", ["no focal abnormality", "no asymmetry"], false), value("FOCAL", "Focal slowing", ["focal slowing"]), value("GENERALISED", "Generalised slowing", ["generalised slowing", "generalized slowing"])]),
  status("demyelination", "Nerve conduction pattern", "neurophysiology", "NEUROPHYSIOLOGY", narrativeDocuments, 30, [value("ABSENT", "No demyelinating features", ["no demyelinating features", "no features of demyelination"], false), value("DEMYELINATING", "Demyelinating pattern", ["demyelinating pattern", "features of demyelination"]), value("AXONAL", "Axonal pattern", ["axonal pattern"])]),
  status("variant_call", "Variant call", "molecular", "MOLECULAR", narrativeDocuments, 365, [value("NONE", "No variant detected", ["no pathogenic variant identified", "no pathogenic variant detected", "no variant detected"], false), value("PATHOGENIC", "Pathogenic variant detected", ["pathogenic variant detected", "likely pathogenic"]), value("VUS", "Variant of uncertain significance", ["variant of uncertain significance", "vus"]), value("BENIGN", "Benign variant", ["benign variant"], false)]),
  status("pcr_result", "Assay result", "molecular", "MOLECULAR", ["MOLECULAR_REPORT", "PATHOLOGY_REPORT"], 30, [value("NEGATIVE", "Not detected / negative", ["not detected", "negative"], false), value("POSITIVE", "Detected / positive", ["detected", "positive"]), value("INDETERMINATE", "Indeterminate", ["indeterminate", "inconclusive"], false)]),
  status("mutation_status", "Mutation status", "molecular", "MOLECULAR", narrativeDocuments, 365, [value("WILD_TYPE", "Wild type", ["mutation not detected", "no egfr mutation", "no kras mutation", "wild-type", "wild type"], false), value("EGFR", "EGFR mutation detected", ["egfr mutation detected"]), value("KRAS", "KRAS mutation detected", ["kras mutation detected"]), value("BRAF", "BRAF V600E detected", ["braf v600e detected"])]),
  status("receptor_status", "Receptor status", "molecular", "MOLECULAR", narrativeDocuments, 365, [value("ER_POS", "ER positive", ["er positive"]), value("ER_NEG", "ER negative", ["er negative"], false), value("PR_POS", "PR positive", ["pr positive"]), value("PR_NEG", "PR negative", ["pr negative"], false), value("HER2_POS", "HER2 positive", ["her2 positive"]), value("HER2_NEG", "HER2 negative", ["her2 negative"], false), value("TRIPLE_NEG", "Triple negative", ["triple negative"], false)]),
  status("msi_status", "Microsatellite status", "molecular", "MOLECULAR", narrativeDocuments, 365, [value("MSI_HIGH", "MSI-high", ["msi-high", "mmr deficient"]), value("MSI_LOW", "MSI-low", ["msi-low"], false), value("STABLE", "Microsatellite stable", ["microsatellite stable", "mmr proficient"], false)]),
];

export const claimRules: ClaimRule[] = [
  { key: "ECG_NORMAL", label: "ECG reported normal", patterns: ["ecg is normal", "normal ecg", "ecg within normal limits", "electrocardiogram normal"], requiresAny: ["rhythm", "heart_rate", "qrs_duration"], requiresLabels: ["An ECG report stating rhythm and intervals"], lookbackDays: 90, modality: "CARDIOLOGY" },
  { key: "LV_FUNCTION_NORMAL", label: "LV function reported normal", patterns: ["lv function normal", "normal lv function", "normal left ventricular function", "preserved ejection fraction"], requiresAny: ["ejection_fraction"], requiresLabels: ["Ejection fraction on echocardiography"], lookbackDays: 180, modality: "CARDIOLOGY" },
  { key: "EEG_NORMAL", label: "EEG reported normal", patterns: ["eeg is normal", "normal eeg", "eeg within normal limits", "electroencephalogram normal"], requiresAny: ["eeg_background_freq", "epileptiform_activity"], requiresLabels: ["An EEG report stating background and epileptiform activity"], lookbackDays: 180, modality: "NEUROPHYSIOLOGY" },
  { key: "MOLECULAR_TARGET_ABSENT", label: "Molecular target reported absent", patterns: ["no targetable mutation", "no actionable mutation", "wild type", "wild-type", "mutation not detected"], requiresAny: ["variant_call", "mutation_status"], requiresLabels: ["A molecular or genetic report stating the call"], lookbackDays: 365, modality: "MOLECULAR" },
  { key: "VIRAL_SUPPRESSION", label: "Viral suppression documented", patterns: ["virally suppressed", "viral suppression", "undetectable viral load", "viral load undetectable"], requiresAny: ["viral_load", "pcr_result"], requiresLabels: ["A quantitative viral load or molecular assay result"], lookbackDays: 90, modality: "MOLECULAR" },
  { key: "NO_ACUTE_INTRACRANIAL_FINDING", label: "No acute intracranial finding documented", patterns: ["no acute intracranial abnormality", "no acute intracranial finding"], requiresAny: ["acute_infarct", "hemorrhage"], requiresLabels: ["An imaging report addressing acute infarct or haemorrhage"], lookbackDays: 30, modality: "IMAGING" },
];

const quantByKey = new Map(quantitativeRules.map((rule) => [rule.key, rule]));
const statusByKey = new Map(statusRules.map((rule) => [rule.key, rule]));
export function quantitativeRuleFor(concept: string) { return quantByKey.get(concept); }
export function statusRuleFor(concept: string) { return statusByKey.get(concept); }
export function episodeWindowDays(concept: string) { return quantByKey.get(concept)?.episodeWindowDays ?? statusByKey.get(concept)?.episodeWindowDays ?? 0; }
export function isMaterialDifference(concept: string, left: number, right: number) {
  const rule = quantByKey.get(concept);
  if (!rule) return left !== right;
  const delta = Math.abs(left - right);
  const relative = Math.max(Math.abs(left), Math.abs(right)) ? delta / Math.max(Math.abs(left), Math.abs(right)) : 0;
  return delta >= rule.materialAbs || relative >= rule.materialRel;
}
export function statusValueFor(concept: string, documentedValue: string) {
  const rule = statusByKey.get(concept);
  if (!rule) return null;
  const normalized = documentedValue.trim().toLowerCase();
  return rule.values.find((candidate) => candidate.key.toLowerCase() === normalized || candidate.label.toLowerCase() === normalized || candidate.phrases.some((phrase) => phrase.toLowerCase() === normalized)) ?? null;
}
export function claimRuleForText(text: string) {
  const normalized = text.toLowerCase();
  return claimRules.find((rule) => rule.patterns.some((pattern) => normalized.includes(pattern))) ?? null;
}
export const activeEvidencePacks = [
  { key: "laboratory", label: "Laboratory", modality: "LABORATORY" },
  { key: "imaging", label: "Imaging", modality: "IMAGING" },
  { key: "cardiology", label: "Cardiology", modality: "CARDIOLOGY" },
  { key: "neurophysiology", label: "Neurophysiology", modality: "NEUROPHYSIOLOGY" },
  { key: "molecular", label: "Molecular", modality: "MOLECULAR" },
];
