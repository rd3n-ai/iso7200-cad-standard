---
type: standard
description: Machine-readable rulebook and AI agent entry point for CAD metadata verification, ISO 7200 title block mapping, and downstream pipeline extraction.
---

# CAD Standards & Automation Rulebook — AI_GUIDELINES.md

> **AI Agent Context:** This document serves as the formal machine-readable specification and evaluation criteria for AI agents operating on or inspecting mechanical CAD models, metadata dictionaries, and technical drawing standards.

---

## 1. System Invariants & Core Rules

Any CAD dataset, automated script, or inspection tool interacting with this standard MUST satisfy these non-negotiable rules:

1. **Deterministic Naming:** Two layers are enforced.
   * *Character layer* (all components): `^[A-Z0-9][A-Z0-9_-]*$`. Prohibited: localized characters, spaces, punctuation (`Ø, #, &, @`). `-` and `_` are allowed.
   * *Structural layer* (project components only): `^[A-Z0-9][A-Z0-9-]*_(MK|PS|M|P)\d+$` — the project code admits `-` but **no `_`** (the underscore is the type separator). Standard catalog items (`PartType` = `Purchased` or `Reference`) keep their manufacturer part number and are exempt.
2. **Model = Single Source of Truth (SSOT):**
   * Technical drawings do NOT store independent copies of part numbers, descriptions, materials, weights, or revisions.
   * Drawing title blocks bind to 3D model properties using `$PRPSHEET:"<Property>"`.
   * Only drawing-level manufacturing notes (`GeneralTolerance`, `SurfaceRoughness`, `EdgeTreatment`) use `$PRP:"<Property>"`.
3. **English Neutrality:** All evaluated property values printed to drawings or BOMs must be in standard English.
4. **Mass Consistency:** All part and assembly templates enforce SI Unit custom preferences: Length in `mm`, Mass in `kg` (3 decimal places).
5. **Projection Method:** First Angle Projection (ISO-E) is standard across all drawing sheets and title block symbols.

---

## 2. Machine-Readable Property Dictionary

```yaml
model_properties:
  PartNumber:
    source: "SW-File Name"
    type: "automatic"
    bom_column: "PART NUMBER"
    title_block: "PART / DWG NO"
  Description:
    source: "manual"
    type: "string"
    bom_column: "DESCRIPTION"
    title_block: "TITLE"
  Revision:
    source: "manual"
    type: "string"
    default: "00"
    title_block: "REV"
  RevisionDate:
    source: "manual"
    type: "date_iso8601"
    title_block: null
  ECN_Note:
    source: "manual"
    type: "string"
    title_block: null
  Material:
    source: "SW-Material"
    type: "automatic"
    bom_column: "MATERIAL"
    title_block: "MATERIAL"
  Weight:
    source: "SW-Mass"
    type: "automatic_kg"
    bom_column: "MASS"
    title_block: "MASS"
  RawDimensions:
    source: "manual"
    type: "string"
    bom_column: "RAW SIZE"
    title_block: "RAW SIZE"
    note: "For ModifiedStandard (PS) parts, indicates base standard hardware (e.g. DIN 933 M12x60)"
  SurfaceTreatment:
    source: "lookup_table"
    type: "enum"
    bom_column: "SURFACE TREATMENT"
    title_block: "SURFACE TREATMENT"
  PartType:
    source: "enum"
    type: "enum"
    values: ["Manufactured", "Purchased", "ModifiedStandard", "Reference"]
    title_block: null
  ProcurementGroup:
    source: "lookup_table"
    type: "enum"
    bom_column: "PROCUREMENT"
    title_block: "PROCUREMENT"
  Supplier:
    source: "lookup_table"
    type: "string"
    bom_column: null
    title_block: null
  SupplierPartNumber:
    source: "manual"
    type: "string"
    bom_column: null
    title_block: null
  DrawnBy:
    source: "manual"
    type: "string"
    title_block: "DRAWN BY"
  CheckedBy:
    source: "manual"
    type: "string"
    title_block: "CHECKED"
  ApprovedBy:
    source: "manual"
    type: "string"
    title_block: "APPROVED"
  DrawnDate:
    source: "manual"
    type: "date_iso8601"
    title_block: "DATE"

drawing_properties:
  GeneralTolerance:
    default: "ISO 2768-m"
    title_block: "GENERAL TOL."
  SurfaceRoughness:
    default: "Ra 3.2"
    title_block: "SURFACE FINISH"
  EdgeTreatment:
    default: "Break sharp edges 0.5x45°, remove burrs"
    title_block: "EDGES"
```

---

## 3. Automated Error Taxonomy & Diagnostic Codes

AI agents auditing CAD models via `cad_standard_check.py` should categorize findings using the following diagnostic codes:

| Code | Severity | Category | Trigger Condition / Description |
|---|---|---|---|
| `K01` | ERROR | Identity | File name violates naming pattern (lowercase, space, or non-ASCII characters). |
| `K02` | ERROR | Identity | `Description` property is empty (leaves Title block and BOM blank). |
| `K03` | ERROR | Identity | `Revision` property is empty. |
| `K04` | ERROR | Identity | File name is ASCII-clean but does not follow the `[PROJECT]_[TYPE][SEQ]` structural scheme. Not raised for `Purchased` / `Reference` parts. |
| `M01` | ERROR | Material | `PartType=Manufactured` but no CAD material assigned. |
| `M02` | ERROR | Mass | `Weight` custom property missing from model. |
| `M03` | ERROR | Mass | `Weight` expression does not follow `SW-Mass@<filename>`. |
| `B01` | ERROR | Units | Document unit setting is not metric SI (`mm`, `kg`). |
| `B02` | ERROR | Units | Evaluated mass suggests Gram scaling error (factor of 1000 mismatch against SI model mass). |
| `B03` | WARNING | Units | Evaluated `Weight` property differs >5% from live calculated physics mass (rebuild required). |
| `T01` | WARNING | Sourcing | `ProcurementGroup` property is empty. |
| `T02` | WARNING | Sourcing | `ProcurementGroup` value not found in approved lookup table. |
| `T03` | WARNING | Sourcing | `SurfaceTreatment` value not found in approved lookup table. |
| `T04` | WARNING | Sourcing | `PartType` property is empty. |
| `T05` | WARNING | Sourcing | `PartType=Purchased` but `Supplier` or `SupplierPartNumber` is missing. |
| `T06` | ERROR | Sourcing | `PartType=ModifiedStandard` but `RawDimensions` (base hardware) is empty. |
| `T07` | WARNING | Sourcing | `PartType=ModifiedStandard` but `Supplier` and `SupplierPartNumber` are both empty. |
| `T08` | WARNING | Sourcing | `PartType` value is outside the approved enum (`Manufactured`, `Purchased`, `ModifiedStandard`, `Reference`). |
| `I01` | WARNING | Governance | Signature field (`DrawnBy`, `CheckedBy`, `ApprovedBy`) is empty. |
| `C00` | WARNING | Access | Component model could not be inspected (loaded in lightweight/suppressed state). All other checks skipped for this component. |
