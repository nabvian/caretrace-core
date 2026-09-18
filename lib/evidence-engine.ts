import { demoCase, demoClaims, demoDocuments, demoFacts, demoMedications } from "./demo-data";
import { episodeWindowDays, isMaterialDifference, quantitativeRuleFor, statusRuleFor, statusValueFor } from "./evidence-packs";
import type { AuditResult, ChangeEvent, Claim, Conflict, DocumentReference, EvidenceGap, Fact, MedicalDocument, Medication, Relationship, TimelineEvent } from "./types";
import { resolveCoreConcept } from "./terminology/search-index";

const relId = (n: number) => `20000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const findingId = (n: number) => `30000000-0000-4000-8000-${String(n).padStart(12, "0")}`;

export function normalizeConcept(input: string) {
  const result = resolveCoreConcept(input);
  if (!result.concept || result.reviewRequired) throw new Error(`TERMINOLOGY SOURCE UNAVAILABLE: no validated deterministic mapping for “${input}”.`);
  return result.concept.caretraceId.split(":").at(-1)!;
}

function groupBy<T>(items: T[], key: (item: T) => string) {
  const groups = new Map<string, T[]>();
  for (const item of items) groups.set(key(item), [...(groups.get(key(item)) ?? []), item]);
  return groups;
}
function dateValue(value: string | null) { const time=value&&/^\d{4}-\d{2}-\d{2}$/.test(value)?Date.parse(`${value}T00:00:00Z`):Number.NaN;return Number.isFinite(time)?time:null; }
function dayDistance(left:string|null,right:string|null){const a=dateValue(left),b=dateValue(right);return a===null||b===null?Number.POSITIVE_INFINITY:Math.abs(b-a)/86_400_000;}
function episodes<T extends {date:string|null}>(items:T[],windowDays:number){
  const clusters:T[][]=[];
  for(const item of [...items].sort((a,b)=>(a.date??"").localeCompare(b.date??""))){if(!item.date)continue;const current=clusters.at(-1),previous=current?.at(-1);if(previous&&dayDistance(previous.date,item.date)<=windowDays)current!.push(item);else clusters.push([item]);}
  return clusters;
}

export function detectNumericConflicts(facts: Fact[]): Conflict[] {
  const conflicts:Conflict[]=[];
  const byConcept=groupBy(facts.filter((item)=>typeof item.value==="number"&&item.datePrecision==="day"&&item.date),item=>item.concept);
  for(const [concept,conceptFacts] of byConcept){
    for(const episode of episodes(conceptFacts,episodeWindowDays(concept))){
      const valueGroups:Fact[][]=[];
      for(const fact of episode){const group=valueGroups.find((items)=>!isMaterialDifference(concept,Number(items[0].value),Number(fact.value))&&items[0].unit===fact.unit);if(group)group.push(fact);else valueGroups.push([fact]);}
      if(valueGroups.length<2)continue;
      for(let leftIndex=0;leftIndex<valueGroups.length;leftIndex+=1)for(let rightIndex=leftIndex+1;rightIndex<valueGroups.length;rightIndex+=1){
        const left=valueGroups[leftIndex],right=valueGroups[rightIndex],documents=new Set([...left,...right].map((fact)=>fact.sourceDocumentId));if(documents.size<2)continue;
        const evidenceA=left[0],evidenceB=right[0],rule=quantitativeRuleFor(concept),window=episodeWindowDays(concept),episodeDates=[...left,...right].map((item)=>item.date!).sort();
        conflicts.push({id:findingId(100+conflicts.length+1),displayId:`CONFLICT #${String(conflicts.length+1).padStart(2,"0")}`,kind:"NUMERIC",concept,date:episodeDates[0],status:"UNRESOLVED",evidenceA,evidenceB,evidenceAMembers:left,evidenceBMembers:right,episodeStart:episodeDates[0],episodeEnd:episodeDates.at(-1),materialityBasis:rule?`${rule.materialAbs} ${rule.units[0]??""} absolute or ${rule.materialRel*100}% relative`:"Any documented difference",explanation:`Source documents record materially different ${evidenceA.concept} values within the same ${window}-day clinical episode. All restatements remain linked; CARETRACE does not select a winning value.`});
      }
    }
  }
  return conflicts.sort((a,b)=>a.concept.localeCompare(b.concept)||a.date.localeCompare(b.date));
}

export function detectStatusConflicts(facts:Fact[]):Conflict[]{
  const conflicts:Conflict[]=[],byConcept=groupBy(facts.filter((item)=>typeof item.value==="string"&&item.datePrecision==="day"&&item.date&&statusRuleFor(item.concept)),item=>item.concept);
  for(const [concept,conceptFacts] of byConcept)for(const episode of episodes(conceptFacts,episodeWindowDays(concept))){
    const byValue=groupBy(episode,(fact)=>fact.valueKey??statusValueFor(concept,String(fact.value))?.key??String(fact.value).toLowerCase());if(byValue.size<2)continue;const groups=[...byValue.values()];
    for(let leftIndex=0;leftIndex<groups.length;leftIndex+=1)for(let rightIndex=leftIndex+1;rightIndex<groups.length;rightIndex+=1){const left=groups[leftIndex],right=groups[rightIndex],documents=new Set([...left,...right].map((fact)=>fact.sourceDocumentId));if(documents.size<2)continue;const evidenceA=left[0],evidenceB=right[0],dates=[...left,...right].map((item)=>item.date!).sort();conflicts.push({id:findingId(150+conflicts.length+1),displayId:`CONFLICT #${String(conflicts.length+1).padStart(2,"0")}`,kind:"STATUS",concept,date:dates[0],status:"UNRESOLVED",evidenceA,evidenceB,evidenceAMembers:left,evidenceBMembers:right,episodeStart:dates[0],episodeEnd:dates.at(-1),materialityBasis:"Mutually exclusive declared evidence-pack value classes",explanation:`Source documents state mutually exclusive ${statusRuleFor(concept)?.label??concept} findings within the same ${episodeWindowDays(concept)}-day episode. Neither statement is preferred.`});}
  }
  return conflicts;
}

export function detectMedicationConflicts(medications: Medication[]): Conflict[] {
  const conflicts:Conflict[]=[],groups=groupBy(medications.filter((item)=>Boolean(item.date)),item=>`${item.normalizedDrug}:${item.date}`);
  for(const [key,candidates] of groups){const active=candidates.find((item)=>item.status==="ACTIVE"),absent=candidates.find((item)=>item.status==="NOT_LISTED"||item.status==="INACTIVE");if(!active||!absent)continue;conflicts.push({id:findingId(200+conflicts.length+1),displayId:"",kind:"MEDICATION",concept:key.split(":")[0],date:active.date!,status:"UNRESOLVED",evidenceA:active,evidenceB:absent,evidenceAMembers:[active],evidenceBMembers:[absent],episodeStart:active.date!,episodeEnd:active.date!,materialityBasis:"Active versus inactive/not-listed documentation in contemporaneous sources",explanation:"Medication status is documented inconsistently across contemporaneous sources. Absence from a list is not interpreted as discontinuation."});}
  return conflicts;
}

export function detectChanges(facts: Fact[]): ChangeEvent[] {
  const changes:ChangeEvent[]=[],dated=facts.filter((item):item is Fact&{date:string}=>typeof item.value==="number"&&item.date!==null&&item.temporal.status==="EXPLICIT");
  for(const [concept,conceptFacts] of groupBy(dated,(item)=>item.concept)){
    const dateGroups=groupBy(conceptFacts,(item)=>item.date),unambiguous=[...dateGroups.values()].filter((items)=>new Set(items.map((item)=>`${item.value}:${item.unit}`)).size===1).map((items)=>items.sort((a,b)=>b.confidence-a.confidence)[0]).sort((a,b)=>a.date.localeCompare(b.date));
    for(let index=1;index<unambiguous.length;index+=1){const from=unambiguous[index-1],to=unambiguous[index];if(from.value===to.value||from.unit!==to.unit||dayDistance(from.date,to.date)<=episodeWindowDays(concept))continue;changes.push({id:findingId(300+changes.length+1),concept,from,to,label:"Documented change"});}
  }
  return changes.sort((a,b)=>a.to.date!.localeCompare(b.to.date!)||a.concept.localeCompare(b.concept));
}

function claimEvidence(claim:Claim,facts:Fact[]){
  if(!claim.supportConcepts?.length||!claim.date)return{located:[] as string[],later:[] as string[]};const claimTime=dateValue(claim.date),lookback=claim.evidenceLookbackDays??Number.POSITIVE_INFINITY;
  const located=claim.supportConcepts.filter((concept)=>facts.some((fact)=>fact.concept===concept&&fact.date&&claimTime!==null&&dateValue(fact.date)!<=claimTime&&dayDistance(fact.date,claim.date)<=lookback));
  const later=claim.supportConcepts.filter((concept)=>facts.some((fact)=>fact.concept===concept&&fact.date&&claimTime!==null&&dateValue(fact.date)!>claimTime));return{located,later};
}

export function resolveDocumentReferences(references:DocumentReference[],documents:MedicalDocument[]){return references.map((reference)=>{const candidates=documents.filter((document)=>document.id!==reference.sourceDocumentId&&(!reference.targetDocumentType||document.type===reference.targetDocumentType)&&(!reference.referencedDate||document.date===reference.referencedDate||document.clinicalDates?.some((date)=>date.value===reference.referencedDate)));if(candidates.length===1)return{...reference,resolvedDocumentId:candidates[0].id,status:"RESOLVED" as const};if(!candidates.length)return{...reference,resolvedDocumentId:null,status:"NOT_PRESENT" as const};return{...reference,resolvedDocumentId:null,status:"REVIEW_REQUIRED" as const};});}
function referenceClaim(reference:DocumentReference):Claim{return{id:reference.id,displayId:reference.displayId,claim:`Reference to ${reference.label}`,date:reference.referencedDate,sourceDocumentId:reference.sourceDocumentId,sourceDocument:reference.sourceDocument,sourcePage:reference.sourcePage,sourceText:reference.sourceText,confidence:reference.confidence,category:"FINDING",reviewStatus:reference.reviewStatus,sourceProvenance:reference.sourceProvenance,sourceSpans:reference.sourceSpans};}

export function detectEvidenceGaps(claims:Claim[],facts:Fact[],documents:MedicalDocument[],documentReferences:DocumentReference[]=[]):EvidenceGap[]{
  const gaps:EvidenceGap[]=[];
  for(const claim of claims){
    if(claim.gapRule==="MISSING_SUPPORT"){const {located,later}=claimEvidence(claim,facts),missing=(claim.supportConcepts??[]).filter((concept)=>!located.includes(concept));if(missing.length)gaps.push({id:findingId(401+gaps.length),displayId:`EVIDENCE GAP #${String(gaps.length+1).padStart(2,"0")}`,kind:"MISSING_SUPPORTING_TEST",title:"Supporting evidence not located",claim,evidenceLocated:located,evidenceNotLocated:claim.evidenceLabels?.length?claim.evidenceLabels:missing,laterEvidence:later,basis:`No qualifying source-linked evidence was located on or before the claim within its ${claim.evidenceLookbackDays??"configured"}-day lookback window. Later evidence is not treated as support.`,status:"SUPPORTING_EVIDENCE_NOT_FOUND"});}
    if(claim.gapRule==="MISSING_SOURCE"&&claim.referencedDocument){const found=documents.some((document)=>document.type==="IMAGING_REPORT"||document.name.toLowerCase().includes(claim.referencedDocument!.toLowerCase()));if(!found)gaps.push({id:findingId(401+gaps.length),displayId:`EVIDENCE GAP #${String(gaps.length+1).padStart(2,"0")}`,kind:"MISSING_REFERENCED_DOCUMENT",title:"Referenced document not present",claim,evidenceLocated:["Document reference"],evidenceNotLocated:[claim.referencedDocument],basis:"The source explicitly references a document that is not present in this patient case.",status:"NOT_PRESENT_IN_RECORDS"});}
    if(claim.gapRule==="MISSING_FOLLOWUP"&&claim.expectedConcept&&claim.date){const found=facts.some((fact)=>fact.concept===claim.expectedConcept&&fact.date&&fact.date>claim.date!);if(!found)gaps.push({id:findingId(401+gaps.length),displayId:`EVIDENCE GAP #${String(gaps.length+1).padStart(2,"0")}`,kind:"MISSING_FOLLOWUP",title:"Expected follow-up not located",claim,evidenceLocated:["Referral request"],evidenceNotLocated:[`Follow-up ${claim.expectedConcept} observation after ${claim.date}`],basis:"An explicit follow-up expectation was documented, but no later matching evidence atom is present.",status:"FOLLOWUP_NOT_LOCATED"});}
  }
  for(const reference of documentReferences.filter((item)=>item.status==="NOT_PRESENT")){const claim=referenceClaim(reference);gaps.push({id:`gap:${reference.id}`,displayId:`EVIDENCE GAP #${String(gaps.length+1).padStart(2,"0")}`,kind:"MISSING_REFERENCED_DOCUMENT",title:"Referenced document not present",claim,reference,evidenceLocated:[`${reference.label} reference in ${reference.sourceDocument}`],evidenceNotLocated:[reference.referencedDate?`${reference.label} dated ${reference.referencedDate}`:reference.label],basis:"The explicit document reference could not be resolved inside this patient boundary.",status:"NOT_PRESENT_IN_RECORDS"});}
  return gaps;
}

export function buildRelationships(facts:Fact[],claims:Claim[],changes:ChangeEvent[],conflicts:Conflict[],gaps:EvidenceGap[]):Relationship[]{
  const relationships:Relationship[]=[],add=(fromId:string,toId:string,type:Relationship["type"],rationale:string)=>relationships.push({id:relId(relationships.length+1),fromId,toId,type,rationale});
  for(const items of groupBy(facts,(item)=>`${item.concept}:${item.date}:${item.value}:${item.unit}`).values())if(items.length>1)for(let index=1;index<items.length;index+=1)add(items[0].id,items[index].id,"DUPLICATES","Same normalized concept, documented date, value class/value, and unit.");
  for(const change of changes)add(change.from.id,change.to.id,"CHANGED_TO","Distinct material values for the same normalized concept in different clinical episodes.");
  for(const conflict of conflicts)for(const left of conflict.evidenceAMembers??[conflict.evidenceA])for(const right of conflict.evidenceBMembers??[conflict.evidenceB])if(left.sourceDocumentId!==right.sourceDocumentId)add(left.id,right.id,"CONTRADICTS",conflict.explanation);
  for(const claim of claims){const evidence=claimEvidence(claim,facts);for(const concept of evidence.located){const support=facts.find((fact)=>fact.concept===concept&&fact.date&&claim.date&&fact.date<=claim.date&&dayDistance(fact.date,claim.date)<= (claim.evidenceLookbackDays??Number.POSITIVE_INFINITY));if(support)add(support.id,claim.id,"SUPPORTS",`Located ${concept} evidence inside the configured pre-claim lookback window.`);}}
  for(const gap of gaps)add(gap.reference?.id??gap.claim.id,gap.id,"MISSING_SUPPORT",gap.basis??gap.title);return relationships;
}

export function buildTimeline(documents:MedicalDocument[],facts:Fact[],claims:Claim[],conflicts:Conflict[]):TimelineEvent[]{return documents.map((document)=>{const documentFacts=facts.filter((fact)=>fact.sourceDocumentId===document.id),documentClaims=claims.filter((claim)=>claim.sourceDocumentId===document.id),flags=conflicts.filter((conflict)=>(conflict.evidenceAMembers??[conflict.evidenceA]).some((item)=>item.sourceDocumentId===document.id)||(conflict.evidenceBMembers??[conflict.evidenceB]).some((item)=>item.sourceDocumentId===document.id)).map((conflict)=>conflict.kind==="MEDICATION"?"Medication documentation conflict":`${conflict.concept} conflict`),detail=documentFacts.length?documentFacts.slice(0,3).map((fact)=>`${fact.originalConcept} ${fact.value}${fact.unit?` ${fact.unit}`:""}`).join(" · "):documentClaims.length?documentClaims[0].claim:document.processingNote??"Document ingested",clinicalDate=document.clinicalDates?.find((item)=>item.type==="specimen_collection")??document.clinicalDates?.find((item)=>item.type==="encounter")??document.clinicalDates?.find((item)=>item.type==="report")??document.clinicalDates?.[0];return{id:`timeline-${document.id}`,date:document.uploadStatus==="DEMO"?document.date:clinicalDate?.value??null,title:document.name.replace(/^\d+_|\.pdf$/g,"").replaceAll("_"," "),document,detail,factIds:documentFacts.map((fact)=>fact.id),flags};}).sort((a,b)=>(a.date??"9999").localeCompare(b.date??"9999"));}

export function runEvidenceAudit():AuditResult{
  const conflicts=[...detectNumericConflicts(demoFacts),...detectStatusConflicts(demoFacts),...detectMedicationConflicts(demoMedications)].map((conflict,index)=>({...conflict,displayId:`CONFLICT #${String(index+1).padStart(2,"0")}`})),changes=detectChanges(demoFacts),gaps=detectEvidenceGaps(demoClaims,demoFacts,demoDocuments,[]),relationships=buildRelationships(demoFacts,demoClaims,changes,conflicts,gaps),traceable=[...demoFacts,...demoClaims,...demoMedications].filter((item)=>item.sourceDocumentId&&item.sourcePage&&item.sourceText).length,total=demoFacts.length+demoClaims.length+demoMedications.length;
  return{caseRecord:demoCase,documents:demoDocuments,facts:demoFacts,claims:demoClaims,medications:demoMedications,events:[],documentReferences:[],changes,conflicts,gaps,relationships,timeline:buildTimeline(demoDocuments,demoFacts,demoClaims,conflicts),metrics:{documents:demoDocuments.length,facts:demoFacts.length,claims:demoClaims.length,medications:demoMedications.length,events:0,references:0,changes:changes.length,conflicts:conflicts.length,gaps:gaps.length,unresolved:conflicts.length+gaps.length,traceability:Math.round(traceable/total*100)}};
}
export const demoAudit=runEvidenceAudit();
const expected={documents:12,facts:42,claims:9,changes:7,conflicts:4,gaps:3};for(const [key,value] of Object.entries(expected))if(demoAudit.metrics[key as keyof typeof expected]!==value)throw new Error(`Synthetic audit invariant failed: ${key} must equal ${value}.`);
