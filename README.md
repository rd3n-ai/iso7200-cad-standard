# ISO 7200 CAD Metadata Standard

> An open engineering-metadata standard for mechanical design offices: a single source of truth
> across 3D model properties, ISO 7200 title blocks and BOM/ERP exports — plus a machine-readable
> rulebook (`AI_GUIDELINES.md`) so automated agents can audit a dataset against it.
> Ships with a SolidWorks reference implementation.

[![Code: Apache 2.0](https://img.shields.io/badge/Code-Apache%202.0-blue.svg)](LICENSE)
[![Spec: CC BY 4.0](https://img.shields.io/badge/Spec-CC%20BY%204.0-lightgrey.svg)](LICENSE-SPEC)
[![Standard: ISO 7200](https://img.shields.io/badge/Standard-ISO%207200-success.svg)](SPECIFICATION.md)
[![Architecture: SSOT](https://img.shields.io/badge/Architecture-SSOT%20Model--Driven-orange.svg)](SPECIFICATION.md)
[![AI Rulebook](https://img.shields.io/badge/AI%20Rulebook-AI__GUIDELINES.md-purple.svg)](AI_GUIDELINES.md)

---

## Scope — please read first

**What this repository is:**
* A written engineering standard (`SPECIFICATION.md`) — property dictionary, part-numbering scheme,
  ISO 7200 title block mapping, BOM column contract.
* A machine-readable rulebook (`AI_GUIDELINES.md`) — the same standard expressed as YAML plus a
  20-code diagnostic taxonomy, so an LLM or CI job can audit a CAD dataset and report violations in
  a stable vocabulary.
* A **reference implementation** under `scripts/` showing how the audit and the BOM extraction are
  mechanised against one CAD system.

**What this repository is not:**
* Not a product, not a supported tool, and **not headless** — the scripts attach over COM to a
  SolidWorks instance that is already installed, licensed and running on the same Windows machine.
* Not CAD-neutral in its code. The *standard* is portable to any CAD system that supports custom
  properties; the *scripts* are SolidWorks-specific.
* Not cost or ERP software. It extracts the data an ERP needs; it does not price anything.

The standard is the deliverable. The scripts illustrate it, and are published as-is.

---

## 1. The problem

In most mechanical design offices engineering metadata is fractured across spreadsheets, drawing
title blocks and CAD files. The consequences are familiar: BOM exports that break, drawings whose
material and mass disagree with the model they depict, and mass audits done by eye.

The fix is not another tool. It is a rule that a fact is only allowed to live in one place.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   SINGLE SOURCE OF TRUTH (3D MODEL)                    │
│   Part Number (File Name) │ Description │ Material │ Weight (kg, SI)   │
│   Procurement Group       │ Surface Treatment │ Revision │ Signatures  │
└──────────────────┬─────────────────────────────────┬───────────────────┘
                   │ $PRPSHEET Dynamic Link          │ Read-Only Inspection
                   ▼                                 ▼
┌──────────────────────────────────────┐  ┌──────────────────────────────┐
│     ISO 7200 TECHNICAL DRAWING       │  │    DOWNSTREAM DATA PIPELINE  │
│  • Auto-resolved Title Block Fields  │  │  • Automated Standard Audits │
│  • Drawing-Specific Notes ($PRP)     │  │  • BOM & Procurement Tables  │
│  • First-Angle Projection (ISO-E)    │  │  • Mass Rollup (CSV)         │
└──────────────────────────────────────┘  └──────────────────────────────┘
```

---

## 2. Core principles

### Principle 1 — The model is the single source of truth
A drawing never keeps its own copy of part metadata. Every title block field (`TITLE`, `REV`,
`MATERIAL`, `MASS`, `RAW SIZE`, `SURFACE TREATMENT`, `PROCUREMENT`) resolves dynamically from the
referenced 3D model via `$PRPSHEET`. The sheet owns only what is genuinely drawing-local: geometric
tolerances, surface finish and general notes (`$PRP`).

### Principle 2 — Deterministic part numbering
Identity lives in the file name and nowhere else. Two layers are enforced:

```
[PROJECT_CODE]_[TYPE_CODE][SEQUENCE]
PRJ101_M00 · PRJ101_MK01 · PRJ101_P001 · MOD01_PS003
```

| Code | Meaning |
|---|---|
| `M`  | Main assembly or sub-assembly |
| `MK` | Welded assembly / structural frame |
| `P`  | Manufactured part, made from raw stock |
| `PS` | Modified standard part — catalog hardware with secondary machining |

No localized characters, whitespace or symbols (`#`, `&`, `Ø`). Descriptions, materials and
dimensions never appear in a file name. Unmodified catalog items (bearings, plain fasteners) keep
their manufacturer part number and stay out of the project numbering scheme entirely.

### Principle 3 — Inspection must never mutate
Any tool built on this standard reads. It opens documents read-only, closes only the sessions it
opened itself, and writes its findings to a report — never back into the CAD file.

### Principle 4 — The rulebook is machine-readable
`AI_GUIDELINES.md` carries the property dictionary as YAML and every failure mode as a stable
diagnostic code (`K01`, `M02`, `B02`, …). This gives an agent, a CI job or a human reviewer one
shared vocabulary for "what is wrong with this dataset", instead of prose that has to be
re-interpreted every time.

---

## 3. Repository layout

```
.
├── SPECIFICATION.md        # The standard: property schema, numbering, ISO 7200 mapping, BOM contract
├── AI_GUIDELINES.md        # Same standard, machine-readable: YAML dictionary + diagnostic taxonomy
├── examples/
│   └── lookup_table.csv    # Controlled vocabulary: surface treatments, procurement groups, materials
├── scripts/                # SolidWorks reference implementation (see Scope above)
│   ├── cad_pipeline_lib.py   # Read-only COM extraction core
│   ├── cad_standard_check.py # Rulebook auditor, emits a Markdown report
│   └── cad_bom_extract.py    # BOM and procurement routing, emits CSV
├── LICENSE                 # Apache-2.0 (code)
├── LICENSE-SPEC            # CC BY 4.0 (specification)
└── NOTICE
```

---

## 4. Reference implementation

**Requirements:** Windows · Python 3.8+ · `pip install -r requirements.txt` (pywin32) · a running,
licensed SolidWorks session with the target assembly resolved.

```bash
python scripts/cad_standard_check.py path/to/ASSEMBLY.SLDASM --report audit_report.md
```

Walks every unique component in the assembly and checks: file-name compliance on both layers,
required properties, material assignment on manufactured parts, SI unit configuration, the
gram-versus-kilogram scaling error, mass drift between the stored property and live geometry,
controlled-vocabulary conformance, and signature completeness. Report shape:

```markdown
# CAD Metadata Audit Report

- **Target Assembly:** `ASSEMBLY.SLDASM`
- **Total Unique Components:** <n>
- **Errors:** <n> | **Warnings:** <n>
- **Status:** NON-COMPLIANT | COMPLIANT WITH WARNINGS | FULLY COMPLIANT

| Component Code | Class | Qty | Status | Findings |
|---|---|---|---|---|
| `PRJ101_P001` | Manufactured Part (from raw stock) | 4 | ERROR | `[M01]` Material not assigned … |
```

```bash
python scripts/cad_bom_extract.py path/to/ASSEMBLY.SLDASM --outdir ./output
```

Emits two CSVs — a full engineering BOM (part number, description, qty, material, per-unit and
rolled-up mass in kg, raw size, finish, revision) and a procurement routing sheet grouped by
sourcing channel.

---

## 5. Adopting the standard without the scripts

The standard carries on its own. To apply it in any CAD system that supports custom properties:

1. Add the property keys from `SPECIFICATION.md` §2 to your part and assembly templates.
2. Bind your title block to those properties instead of typing values into the sheet.
3. Replace the vocabulary in `examples/lookup_table.csv` with your own suppliers, finishes and
   material grades.
4. Point your BOM template at the same keys, so the drawing and the BOM cannot disagree.

The diagnostic codes in `AI_GUIDELINES.md` §3 stay valid as a review checklist even when the
checking is done by a person rather than a script.

---

## 6. Contributing & scope

Issues and pull requests on the **specification** — the property dictionary, the numbering scheme,
the title block mapping, the diagnostic taxonomy — are genuinely welcome. That is where the value
is, and where the discussion is useful.

The `scripts/` directory is published as a reference implementation and is provided **as-is**,
without support or a compatibility guarantee across SolidWorks versions.

---

## 7. License & attribution

* **Code** (`scripts/`) — [Apache License 2.0](LICENSE)
* **Specification** (`SPECIFICATION.md`, `AI_GUIDELINES.md`, `examples/`) — [CC BY 4.0](LICENSE-SPEC)

Copyright 2026 Nizam Yuksel ([RD3N](https://rd3n.com)) — mechanical design and engineering
automation. For CAD/PLM standardisation or ERP data-pipeline work, open an issue.

SolidWorks is a registered trademark of Dassault Systèmes SolidWorks Corporation. This project is
independent and is not affiliated with, endorsed by or sponsored by Dassault Systèmes; the name is
used only to identify the CAD system the reference implementation targets.
