"""Generate a large synthetic corpus for measuring bulk ingestion.

Entirely fictional. Names, record numbers and institutions are generated from
a fixed seed and correspond to no real person. The point of this corpus is not
clinical realism but *structural* realism at scale: many patients, many
modalities, repeated values, deliberate duplicates, and files that cannot be
parsed -- because those are the properties that determine whether an ingester
holds up on ten thousand files.

Text is written as .txt rather than rendered PDFs on purpose, and the benchmark
reports both: PDF parsing cost is measured separately on the real demo PDFs, so
the throughput figure is not silently a measure of one PDF library.
"""
from __future__ import annotations

import random
from pathlib import Path

FIRST = ["Arjun", "Meera", "Rohan", "Priya", "Kabir", "Ananya", "Vikram",
         "Divya", "Nikhil", "Saanvi", "Aditya", "Ishita", "Farhan", "Leela"]
LAST = ["Mehta", "Iyer", "Kapoor", "Nair", "Bose", "Rao", "Sethi", "Verma",
        "Chatterjee", "Menon", "Gill", "Fernandes"]
INSTITUTIONS = [
    "MERIDIAN DIAGNOSTIC LABORATORY (SYNTHETIC)",
    "NORTHFIELD GENERAL HOSPITAL (SYNTHETIC)",
    "RIVERSIDE INTERNAL MEDICINE CLINIC (SYNTHETIC)",
    "LAKESIDE IMAGING CENTRE (SYNTHETIC)",
    "CEDAR PATHOLOGY SERVICES (SYNTHETIC)",
]
CLINICIANS = ["Dr. R. Nair", "Dr. A. Sharma", "Dr. P. Menon", "Dr. S. Gill",
              "Dr. T. Bose"]

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _header(rng: random.Random, inst: str, name: str, dob: str, sex: str,
            mrn: str, date: str, title: str) -> str:
    return (f"{inst}\n"
            f"{'=' * len(inst)}\n\n"
            f"{title}\n\n"
            f"Patient: {name}    Sex: {sex}    DOB: {dob}\n"
            f"MRN: {mrn}\n"
            f"Report date: {date}\n\n")


def _lab(rng: random.Random) -> str:
    return ("HAEMATOLOGY -- COMPLETE BLOOD COUNT\n"
            f"Hemoglobin: {rng.uniform(7.5, 15.0):.1f} g/dL\n"
            f"MCV: {rng.uniform(62, 96):.0f} fL\n"
            f"MCH: {rng.uniform(19, 32):.0f} pg\n"
            f"Platelets: {rng.randint(120, 420)} x10^9/L\n"
            f"WBC: {rng.uniform(3.5, 12.0):.1f} x10^9/L\n"
            f"Ferritin: {rng.randint(6, 210)} ng/mL\n")


def _imaging(rng: random.Random) -> str:
    return ("IMAGING REPORT -- ULTRASOUND ABDOMEN\n"
            "Technique: Transabdominal greyscale imaging.\n"
            f"Findings: Liver measures {rng.uniform(12.0, 17.0):.1f} cm in "
            "craniocaudal span. No focal lesion described.\n"
            "Impression: As described above. Correlate clinically.\n")


def _pathology(rng: random.Random) -> str:
    return ("HISTOPATHOLOGY REPORT\n"
            "Specimen: Duodenal biopsy.\n"
            "Microscopy: Villous architecture described as preserved.\n"
            f"Ki-67 index: {rng.randint(2, 24)} percent.\n"
            "Impression: No malignancy identified in this specimen.\n")


def _ecg(rng: random.Random) -> str:
    return ("ELECTROCARDIOGRAM REPORT\n"
            f"Rate: {rng.randint(52, 118)} bpm\n"
            f"QTc: {rng.randint(360, 470)} ms\n"
            "Rhythm: Sinus rhythm reported.\n")


def _prescription(rng: random.Random) -> str:
    drug = rng.choice(["Ferrous sulfate", "Metformin", "Amoxicillin",
                       "Levothyroxine", "Atorvastatin"])
    return ("PRESCRIPTION\n"
            f"{drug} {rng.choice([50, 100, 250, 500])} mg -- "
            f"{rng.choice(['once daily', 'twice daily'])}, oral\n"
            "Status: active\n")


def _consult(rng: random.Random) -> str:
    return ("CONSULTATION NOTE\n"
            f"Assessment: {rng.choice(['Anaemia under evaluation', 'Iron deficiency suspected', 'Fatigue under evaluation'])}.\n"
            "Plan: Repeat laboratory studies as documented.\n")


MODALITIES = [
    ("LAB_REPORT", "LABORATORY REPORT", _lab, 0.42),
    ("PRESCRIPTION", "PRESCRIPTION", _prescription, 0.14),
    ("CONSULTATION", "CONSULTATION NOTE", _consult, 0.16),
    ("IMAGING_REPORT", "IMAGING REPORT", _imaging, 0.12),
    ("PATHOLOGY_REPORT", "PATHOLOGY REPORT", _pathology, 0.10),
    ("ECG_REPORT", "ELECTROCARDIOGRAM REPORT", _ecg, 0.06),
]


def generate(out_dir: Path, count: int = 10_000, patients: int = 400,
             seed: int = 20260825, duplicate_rate: float = 0.02,
             corrupt_rate: float = 0.005) -> dict:
    """Write `count` synthetic report files. Returns what was written.

    `duplicate_rate` and `corrupt_rate` are deliberate: an ingester that has
    never met a byte-identical resubmission or an unparseable file has not been
    measured on anything resembling a real corpus.
    """
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    roster = []
    for i in range(patients):
        first, last = rng.choice(FIRST), rng.choice(LAST)
        roster.append({
            "name": f"{first} {last}",
            "dob": f"{rng.randint(1, 28)} {rng.choice(MONTHS)} "
                   f"{rng.randint(1945, 2005)}",
            "sex": rng.choice(["M", "F"]),
            "mrn": f"SYN-{100000 + i}",
        })

    weights = [m[3] for m in MODALITIES]
    written, dupes, corrupt = 0, 0, 0
    last_text: str | None = None
    manifest: dict[str, int] = {}

    for n in range(count):
        pat = rng.choice(roster)
        kind, title, body, _w = rng.choices(MODALITIES, weights=weights, k=1)[0]
        inst = rng.choice(INSTITUTIONS)
        date = (f"{rng.randint(1, 28)} {rng.choice(MONTHS)} "
                f"{rng.choice([2024, 2025, 2026])}")
        text = (_header(rng, inst, pat["name"], pat["dob"], pat["sex"],
                        pat["mrn"], date, title)
                + body(rng)
                + f"\nReported by: {rng.choice(CLINICIANS)}\n"
                  f"Ordered by: {rng.choice(CLINICIANS)}\n")

        name = f"{n:05d}_{kind}.txt"
        if last_text is not None and rng.random() < duplicate_rate:
            # A byte-identical resubmission, which the ingester must report as
            # a duplicate rather than a second document.
            (out_dir / f"{n:05d}_RESUBMITTED.txt").write_text(last_text)
            dupes += 1
            manifest["DUPLICATE"] = manifest.get("DUPLICATE", 0) + 1
            written += 1
            continue

        if rng.random() < corrupt_rate:
            # A file that claims to be a PDF and is not. Real corpora contain
            # these, and one of them must not fail the batch.
            (out_dir / f"{n:05d}_UNREADABLE.pdf").write_bytes(
                b"%PDF-1.4\n" + rng.randbytes(200))
            corrupt += 1
            manifest["CORRUPT"] = manifest.get("CORRUPT", 0) + 1
            written += 1
            continue

        (out_dir / name).write_text(text)
        manifest[kind] = manifest.get(kind, 0) + 1
        last_text = text
        written += 1

    return {"written": written, "patients": patients,
            "duplicates": dupes, "corrupt": corrupt,
            "by_modality": manifest, "dir": str(out_dir)}


if __name__ == "__main__":     # pragma: no cover - operator utility
    import argparse, json
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--count", type=int, default=10_000)
    ap.add_argument("--patients", type=int, default=400)
    a = ap.parse_args()
    print(json.dumps(generate(Path(a.out), a.count, a.patients), indent=2))
