# CAD Metadata & Engineering Standards Specification

**Specification Version:** 1.0 (Global AI-Ready Standard)  
**Standard Compliance:** ISO 7200 (Title Blocks), ISO 128 (Technical Drawings), ISO 2768-m (General Tolerances), ISO-E (First-Angle Projection)
**License:** CC BY 4.0 — see [LICENSE-SPEC](LICENSE-SPEC)

> **Portability note.** The property schema, the numbering scheme and the BOM contract are
> CAD-neutral: any system with user-defined custom properties can implement them. The dynamic
> link syntax quoted in section 3 (`$PRPSHEET` / `$PRP`) is SolidWorks notation. Substitute the
> equivalent mechanism in your own CAD system — the binding rule is what matters, not the syntax.

---

## 1. Smart Part Numbering Architecture

File names serve as the unique, immutable identity of every component in the product lifecycle. Descriptive texts, materials, or dimensional values must **never** be placed inside file names.

### 1.1 Format Schema
```
[PROJECT_CODE]_[TYPE_CODE][SEQUENCE_NUMBER]
```

Two layers are enforced — a **character layer** valid for every file name, and a **structural layer** that parses only project components.

* **Character layer (all file names):** `^[A-Z0-9][A-Z0-9_-]*$` — only uppercase alphanumerics plus `-` and `_`. Applied first; any violation is `K01`.
* **Structural layer (project components only):** `^[A-Z0-9][A-Z0-9-]*_(MK|PS|M|P)\d+$` — the project code itself admits `-` but **no `_`** (the underscore is the type separator); the type code is one of `MK | PS | M | P`. Applied only when the character layer passes; violations are `K04`.
* **`PROJECT_CODE`**: Alphanumeric project or customer identifier (e.g., `PRJ101`, `MOD02`), optional hyphens.
* **`TYPE_CODE`**: Explicit design classification:
  * `M` : Main Assembly or Sub-Assembly (e.g., `PRJ101_M00` for top-level, `PRJ101_M01` for sub-assembly).
  * `MK` : Welded Assembly / Structural Frame (Weldment).
  * `P` : Custom manufactured component machined/formed from raw stock.
  * `PS` : **Modified Standard Component** — Standard catalog hardware subjected to secondary machining (e.g., a standard fastener with turned tip or shortened thread). The starting catalog item is recorded under `RawDimensions` (e.g., `DIN 933 M12x60`).
* **`SEQUENCE_NUMBER`**: 2-digit (`00`–`99`) or 3-digit (`001`–`999`) numerical index.

> **Validation Rules:**
> 1. No localized non-ASCII characters (`ç, ğ, ı, ö, ş, ü, etc.`).
> 2. No whitespace or special punctuation (`Ø, #, &, @, /`).
> 3. Standard off-the-shelf catalog items (e.g., bearings, unmachined fasteners) retain standard manufacturer/catalog part numbers and reside in a central standard parts library without receiving custom project codes.

---

## 2. Standard Metadata Property Schema (SSOT Dictionary)

All 3D CAD models (Parts and Assemblies) must define the following standardized English custom property keys:

| Property Key | Description | Source / Type | Title Block Field | Downstream Target |
|---|---|---|---|---|
| `PartNumber` | Part / Assembly Unique Code | Evaluated from File Name | `PART / DWG NO` | BOM / ERP Key |
| `Description` | Functional English component title | Free Text | `TITLE` | BOM Title |
| `Revision` | Engineering revision code (`00`, `01`, `A`) | Text (Default: `00`) | `REV` | Revision Tracking |
| `RevisionDate` | Date of last revision change (`YYYY-MM-DD`)| Date | *(Internal)* | Change Log |
| `ECN_Note` | Engineering Change Notice reason | Free Text | *(Internal)* | ECN Audit |
| `Material` | Material grade and specification | CAD Material Link | `MATERIAL` | Procurement / FEA |
| `Weight` | Component mass | CAD Mass Link (kg) | `MASS` | Logistics / Sizing |
| `RawDimensions` | Stock billet / bar / sheet blank size | Free Text | `RAW SIZE` | Raw Stock Cutlist |
| `SurfaceTreatment`| Finishing, plating, or coating | Controlled Lookup | `SURFACE TREATMENT`| Manufacturing Routing |
| `PartType` | Classification (`Manufactured`, `Purchased`, `ModifiedStandard`, `Reference`)| Radio / Enum | *(Internal)* | Supply Chain Routing |
| `ProcurementGroup`| Sourcing channel (e.g., `Laser_Cutting`, `Turning`, `Hardware`)| Controlled Lookup | `PROCUREMENT` | ERP Category |
| `Supplier` | Catalog manufacturer / vendor name | Controlled Lookup | *(Internal)* | Purchasing Order |
| `SupplierPartNumber`| Manufacturer order code | Free Text | *(Internal)* | Purchasing Order |
| `DrawnBy` | Author / Design Engineer | Text | `DRAWN BY` | Sign-off / PDM |
| `CheckedBy` | Verification Engineer | Text | `CHECKED` | Sign-off / PDM |
| `ApprovedBy` | Approval Authority | Text | `APPROVED` | Sign-off / PDM |
| `DrawnDate` | Initial creation date (`YYYY-MM-DD`) | Date | `DATE` | Sign-off / PDM |

---

## 3. ISO 7200 Technical Drawing Mapping

Drawing sheets must dynamically resolve all part information from the referenced 3D model.

### 3.1 Dynamic Expression Links
* **Model-Derived Properties (`$PRPSHEET`):** Read directly from the primary referenced model view.
* **Drawing-Specific Properties (`$PRP`):** Local sheet scale, sheet index, and drawing-specific manufacturing notes.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ ISO 7200 TITLE BLOCK SPECIFICATION                                         │
├──────────────────────┬──────────────────────┬───────────────────────────────┤
│ PART / DWG NO        │ TITLE                │ REV                           │
│ $PRPSHEET:"SW-File Name"│ $PRPSHEET:"Description"│ $PRPSHEET:"Revision"       │
├──────────────────────┼──────────────────────┼───────────────────────────────┤
│ MATERIAL             │ MASS (kg)            │ RAW SIZE                      │
│ $PRPSHEET:"Material" │ $PRPSHEET:"Weight"   │ $PRPSHEET:"RawDimensions"     │
├──────────────────────┼──────────────────────┼───────────────────────────────┤
│ SURFACE TREATMENT    │ PROCUREMENT          │ CONFIGURATION                 │
│ $PRPSHEET:"SurfaceTreatment"│ $PRPSHEET:"ProcurementGroup"│ $PRPSHEET:"SW-Configuration Name" │
├──────────────────────┼──────────────────────┼───────────────────────────────┤
│ DRAWN BY / DATE      │ CHECKED / APPROVED   │ SCALE / SHEET                 │
│ $PRPSHEET:"DrawnBy"  │ $PRPSHEET:"CheckedBy"│ $PRP:"SW-Sheet Scale"         │
│ $PRPSHEET:"DrawnDate"│ $PRPSHEET:"ApprovedBy"│ $PRP:"SW-Current Sheet"/Total │
├──────────────────────┴──────────────────────┴───────────────────────────────┤
│ GENERAL TOLERANCES: $PRP:"GeneralTolerance" (Default: ISO 2768-m)            │
│ SURFACE FINISH:     $PRP:"SurfaceRoughness" (Default: Ra 3.2)               │
│ EDGES:              $PRP:"EdgeTreatment"   (Default: Break sharp edges)     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Bill of Materials (BOM) & ERP Alignment

BOM templates adhere to the exact same dictionary:
1. **Item No:** Sequential item index in assembly hierarchy.
2. **Part Number:** Evaluated from component file name.
3. **Description:** Evaluated from `Description`.
4. **Qty:** Dynamic instance count in configuration.
5. **Material:** Evaluated from `Material`.
6. **Mass (kg):** Single component mass in kg.
7. **Total Mass (kg):** Calculated equation column (`Qty * Mass`).
8. **Surface Treatment:** Evaluated from `SurfaceTreatment`.
9. **Raw Dimensions / Base Part:** Evaluated from `RawDimensions`.
10. **Procurement Group:** Evaluated from `ProcurementGroup`.
