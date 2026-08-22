# -*- coding: utf-8 -*-
"""CAD Bill of Materials & Procurement Data Extractor.

Extracts structured datasets (Manufacturing Cutlist, Hardware Procurement,
Vendor Orders, Cost Summaries) from an active CAD assembly.

Zero-Write Principle:
Operates in strictly read-only mode and leaves CAD files untouched.

Usage:
    python cad_bom_extract.py <assembly_file.SLDASM> [--outdir ./output]
"""
import os
import sys
import csv
import argparse
import cad_pipeline_lib as cad


def extract_bom(asm_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    asm_name = os.path.splitext(os.path.basename(asm_path))[0]

    sw = cad.connect()
    _, records = cad.extract_assembly_components(sw, asm_path)

    # Output CSV 1: Complete Engineering BOM
    bom_file = os.path.join(out_dir, f"{asm_name}_BOM.csv")
    fieldnames = [
        "PartNumber", "Description", "Qty", "Type", "PartType",
        "Material", "Mass_kg", "TotalMass_kg", "RawDimensions",
        "SurfaceTreatment", "ProcurementGroup", "Supplier", "SupplierPartNumber", "Revision"
    ]

    total_mass_all = 0.0
    with open(bom_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            qty = r.get("qty", 1)
            mass = r.get("mass_kg") or cad.parse_numeric(r.get("Weight")) or 0.0
            tot_mass = mass * qty
            total_mass_all += tot_mass

            writer.writerow({
                "PartNumber": r.get("code", ""),
                "Description": r.get("Description", ""),
                "Qty": qty,
                "Type": r.get("type", ""),
                "PartType": r.get("PartType", ""),
                "Material": r.get("Material", ""),
                "Mass_kg": f"{mass:.3f}",
                "TotalMass_kg": f"{tot_mass:.3f}",
                "RawDimensions": r.get("RawDimensions", ""),
                "SurfaceTreatment": r.get("SurfaceTreatment", ""),
                "ProcurementGroup": r.get("ProcurementGroup", ""),
                "Supplier": r.get("Supplier", ""),
                "SupplierPartNumber": r.get("SupplierPartNumber", ""),
                "Revision": r.get("Revision", ""),
            })

    # Output CSV 2: Sourcing / Procurement Routing
    proc_file = os.path.join(out_dir, f"{asm_name}_Procurement.csv")
    with open(proc_file, "w", encoding="utf-8-sig", newline="") as f:
        p_writer = csv.DictWriter(f, fieldnames=["ProcurementGroup", "PartNumber", "Description", "Qty", "Material/Catalog", "Finish", "Supplier"])
        p_writer.writeheader()
        for r in records:
            p_writer.writerow({
                "ProcurementGroup": r.get("ProcurementGroup", "Unassigned"),
                "PartNumber": r.get("code", ""),
                "Description": r.get("Description", ""),
                "Qty": r.get("qty", 1),
                "Material/Catalog": r.get("Material") or r.get("SupplierPartNumber") or r.get("RawDimensions") or "",
                "Finish": r.get("SurfaceTreatment", "None"),
                "Supplier": r.get("Supplier", ""),
            })

    print(f"Extraction completed successfully.")
    print(f"- Total Unique Components: {len(records)}")
    print(f"- Total Calculated Assembly Mass: {total_mass_all:.3f} kg")
    print(f"- Generated: {bom_file}")
    print(f"- Generated: {proc_file}")


def main():
    parser = argparse.ArgumentParser(description="Extract structured BOM and procurement data from CAD assembly.")
    parser.add_argument("assembly", help="Path to .SLDASM file")
    parser.add_argument("--outdir", help="Output directory", default="./output")
    args = parser.parse_args()

    if not os.path.exists(args.assembly):
        print(f"Error: Assembly file not found: {args.assembly}")
        sys.exit(1)

    extract_bom(args.assembly, args.outdir)


if __name__ == "__main__":
    main()
