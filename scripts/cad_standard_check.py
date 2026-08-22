# -*- coding: utf-8 -*-
"""CAD Metadata & Standard Compliance Auditor.

Inspects an assembly and its components against the engineering standard.
Follows a Zero-Write principle (does not mutate CAD files).

Usage:
    python cad_standard_check.py <assembly_file.SLDASM> [--report report.md] [--lookup path/to/lookup.csv]
"""
import os
import sys
import argparse
import cad_pipeline_lib as cad

ERROR, WARNING, INFO = "ERROR", "WARNING", "INFO"


def audit_component(record, lookup_table):
    """Audits a single component record and returns a list of (severity, code, message)."""
    findings = []
    code = record.get("code", "?")
    comp_type = record.get("type")

    if record.get("error"):
        return [(WARNING, "C00", record["error"])]

    part_type = (record.get("PartType") or "").strip()

    # 1. Identity & Naming
    if not cad.CODE_PATTERN.match(code):
        findings.append((ERROR, "K01", f"File name contains illegal characters (lowercase, whitespace or non-ASCII): {code!r}"))
    elif cad.parse_code(code) is None and part_type not in ("Purchased", "Reference"):
        # Standard catalog items (SPECIFICATION 1.1, rule 3) keep their manufacturer
        # part number and are exempt from the project numbering scheme.
        # If PartType is empty the exemption cannot be judged — downgrade to WARNING so
        # the user is told to classify the part (T04) instead of getting a hard ERROR.
        sev = ERROR if part_type else WARNING
        findings.append((sev, "K04", f"File name does not follow [PROJECT]_[TYPE][SEQ] scheme (e.g. PRJ101_P001): {code!r}"))
    if not record.get("Description"):
        findings.append((ERROR, "K02", "Description property is empty (TITLE block and BOM will be blank)"))
    if not record.get("Revision"):
        findings.append((ERROR, "K03", "Revision property is empty (REV field in title block will be blank)"))

    # 2. Material & Mass
    if comp_type == "part" and part_type == "Manufactured" and not record.get("Material"):
        findings.append((ERROR, "M01", "Material not assigned in CAD model (MATERIAL field and costing disabled)"))

    if part_type == "ModifiedStandard":
        if not record.get("RawDimensions"):
            findings.append((ERROR, "T06", "ModifiedStandard part missing RawDimensions (base catalog item undefined, e.g. DIN 933 M12x60)"))
        if not (record.get("Supplier") or record.get("SupplierPartNumber")):
            findings.append((WARNING, "T07", "ModifiedStandard part missing vendor/supplier data in model"))

    raw_weight_expr = record.get("Weight_raw", "")
    if not raw_weight_expr:
        findings.append((ERROR, "M02", "Weight custom property missing"))
    elif "SW-Mass@" not in raw_weight_expr:
        findings.append((ERROR, "M03", f"Weight expression invalid: {raw_weight_expr[:40]!r} (expected 'SW-Mass@<filename>')"))

    unit_sys, mass_unit, _ = record.get("units", (None, None, None))
    if unit_sys != cad.UNITSYS_CUSTOM or mass_unit != cad.MASS_KG:
        findings.append((ERROR, "B01", f"Non-standard unit system (sys={unit_sys}, mass_unit={mass_unit}) — must be metric kg"))

    prop_mass = cad.parse_numeric(record.get("Weight"))
    true_mass_kg = record.get("mass_kg")
    if prop_mass is not None and true_mass_kg:
        ratio = prop_mass / true_mass_kg if true_mass_kg else 0
        if 500 < ratio < 2000:
            findings.append((ERROR, "B02", f"Mass evaluated in GRAMS instead of KG ({prop_mass:.2f} vs true {true_mass_kg:.3f} kg)"))
        elif abs(ratio - 1) > 0.05:
            findings.append((WARNING, "B03", f"Outdated mass property ({prop_mass:.3f} recorded vs true {true_mass_kg:.3f} kg) — rebuild needed"))

    # 3. Procurement & Sourcing
    proc_group = record.get("ProcurementGroup") or ""
    if not proc_group:
        findings.append((WARNING, "T01", "ProcurementGroup is empty (cannot be routed in ERP/procurement)"))
    elif lookup_table["ProcurementGroup"] and proc_group not in lookup_table["ProcurementGroup"]:
        findings.append((WARNING, "T02", f"ProcurementGroup not in approved lookup table: {proc_group!r}"))

    surface_treat = record.get("SurfaceTreatment") or ""
    if surface_treat and lookup_table["SurfaceTreatment"] and surface_treat not in lookup_table["SurfaceTreatment"]:
        findings.append((WARNING, "T03", f"SurfaceTreatment not in approved lookup table: {surface_treat!r}"))

    if not part_type:
        findings.append((WARNING, "T04", "PartType is empty (must be Manufactured / Purchased / ModifiedStandard / Reference)"))
    elif part_type not in ("Manufactured", "Purchased", "ModifiedStandard", "Reference"):
        findings.append((WARNING, "T08", f"Unrecognized PartType: {part_type!r}"))

    if part_type == "Purchased" and not (record.get("Supplier") or record.get("SupplierPartNumber")):
        findings.append((WARNING, "T05", "Purchased component missing Supplier or SupplierPartNumber"))

    # 4. Signatures & Governance
    missing_signatures = [field for field in ("DrawnBy", "CheckedBy", "ApprovedBy") if not record.get(field)]
    if missing_signatures:
        findings.append((WARNING, "I01", f"Signature metadata missing: {', '.join(missing_signatures)}"))

    return findings


def generate_markdown_report(asm_path, records, all_findings):
    """Builds a formatted Markdown compliance report."""
    total_components = len(records)
    total_errors = sum(1 for _, findings in all_findings for sev, _, _ in findings if sev == ERROR)
    total_warnings = sum(1 for _, findings in all_findings for sev, _, _ in findings if sev == WARNING)

    report_lines = [
        f"# CAD Metadata Audit Report",
        f"",
        f"- **Target Assembly:** `{os.path.basename(asm_path)}`",
        f"- **Total Unique Components:** {total_components}",
        f"- **Errors:** {total_errors} | **Warnings:** {total_warnings}",
        f"- **Status:** {'❌ NON-COMPLIANT' if total_errors > 0 else ('⚠️ COMPLIANT WITH WARNINGS' if total_warnings > 0 else '✅ FULLY COMPLIANT')}",
        f"",
        f"---",
        f"",
        f"## Detailed Component Audit",
        f"",
        f"| Component Code | Class | Qty | Status | Findings |",
        f"|---|---|---|---|---|",
    ]

    for rec, findings in all_findings:
        code = rec.get("code", "Unknown")
        qty = rec.get("qty", 1)
        parsed = cad.parse_code(code)
        class_str = cad.TYPE_CODES.get(parsed[1], "Unclassified") if parsed else "Unclassified"
        if not findings:
            status_str = "✅ OK"
            finding_str = "All checks passed"
        else:
            has_err = any(sev == ERROR for sev, _, _ in findings)
            status_str = "❌ ERROR" if has_err else "⚠️ WARN"
            finding_str = "<br>".join([f"`[{c}]` {m}" for _, c, m in findings])

        report_lines.append(f"| `{code}` | {class_str} | {qty} | {status_str} | {finding_str} |")

    return "\n".join(report_lines)


def main():
    parser = argparse.ArgumentParser(description="Audit CAD Assembly for standard metadata compliance.")
    parser.add_argument("assembly", help="Path to .SLDASM file")
    parser.add_argument("--report", help="Output path for Markdown report", default=None)
    parser.add_argument("--lookup", help="Path to custom lookup table CSV", default=None)
    args = parser.parse_args()

    if not os.path.exists(args.assembly):
        print(f"Error: Assembly file not found: {args.assembly}")
        sys.exit(1)

    print(f"Connecting to CAD session and inspecting: {args.assembly}...")
    sw = cad.connect()
    lookup = cad.load_lookup_table(args.lookup)

    doc, records = cad.extract_assembly_components(sw, args.assembly)
    all_findings = []
    for rec in records:
        findings = audit_component(rec, lookup)
        all_findings.append((rec, findings))

    report = generate_markdown_report(args.assembly, records, all_findings)

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Audit report saved to: {args.report}")
    else:
        print("\n" + report)


if __name__ == "__main__":
    main()
