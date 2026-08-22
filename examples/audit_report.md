# CAD Metadata Audit Report

- **Target Assembly:** `PRJ101_MAIN.SLDASM`
- **Total Unique Components:** 9
- **Errors:** 0 | **Warnings:** 2
- **Status:** ⚠️ COMPLIANT WITH WARNINGS

> Illustrative sample output — run `cad_standard_check.py` against a real assembly
> to audit your own dataset.

## Detailed Component Audit

| Component Code | Class | Qty | Status | Findings |
|---|---|---|---|---|
| `PRJ101_M00` | Assembly / Sub-Assembly | 1 | ✅ OK | All checks passed |
| `PRJ101_P001` | Manufactured Part (from raw stock) | 4 | ✅ OK | All checks passed |
| `PRJ101_P002` | Manufactured Part (from raw stock) | 2 | ⚠️ WARN | `[I01]` Signature metadata missing: ApprovedBy |
| `PRJ101_MK01` | Welded Assembly / Structural Frame | 1 | ✅ OK | All checks passed |
| `PRJ101_PS003` | Modified Standard Part (from catalog hardware) | 6 | ✅ OK | All checks passed |
| `DIN 933 M12x60` | Standard catalog item (exempt) | 12 | ⚠️ WARN | `[C00]` Component model could not be inspected (loaded in lightweight state) |
| `SKF 6204-2RS` | Standard catalog item (exempt) | 2 | ✅ OK | All checks passed |
| `PRJ101_P004` | Manufactured Part (from raw stock) | 1 | ✅ OK | All checks passed |
| `PRJ101_M02` | Assembly / Sub-Assembly | 1 | ✅ OK | All checks passed |
