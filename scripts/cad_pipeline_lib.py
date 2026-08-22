# -*- coding: utf-8 -*-
"""Core library — read-only metadata extraction from a running SolidWorks session.

Attaches to an already-running SolidWorks instance over the COM API and extracts
structured metadata, mass properties and BOM components. This is NOT headless:
SolidWorks must be installed, licensed and running on the same Windows machine.

Zero-Write Principle:
This module NEVER modifies or saves any CAD document. It opens files in silent,
read-only mode and closes only the sessions it initiated.
"""
import os
import re
import csv
import pythoncom
import win32com.client
from win32com.client import gencache

# SolidWorks Type Library GUID
SW_TLB = "{83A33D31-27C5-11CE-BFD4-00400513BB57}"
try:
    MOD = gencache.GetModuleForTypelib(SW_TLB, 0, 34, 0)
except Exception:
    MOD = None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_LOOKUP_CSV = os.path.join(BASE_DIR, "examples", "lookup_table.csv")

DOC_PART, DOC_ASM, DOC_DRW = 1, 2, 3
OPEN_RO_SILENT = 1 + 2  # swOpenDocOptions_Silent | _ReadOnly
P_UNITSYS, P_MASS, P_MASSDEC = 263, 259, 261
UNITSYS_CUSTOM, MASS_KG = 4, 3

# Smart part numbering regex: PROJECT_TYPEINDEX (e.g. PRJ101_P001, MOD01_PS003)
CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]*$")
CODE_PARSE = re.compile(r"^(?P<project>[A-Z0-9][A-Z0-9-]*)_(?P<type>MK|PS|M|P)(?P<no>\d+)$", re.I)

TYPE_CODES = {
    "M": "Assembly / Sub-Assembly",
    "MK": "Welded Assembly / Structural Frame",
    "P": "Manufactured Part (from raw stock)",
    "PS": "Modified Standard Part (from catalog hardware)",
}


def parse_code(file_name):
    """Parses 'PRJ101_P001' into ('PRJ101', 'P', 1). Returns None if non-compliant."""
    m = CODE_PARSE.match(os.path.splitext(os.path.basename(file_name))[0].strip())
    return (m.group("project").upper(), m.group("type").upper(), int(m.group("no"))) if m else None


def cast(obj, iface):
    """Safe QueryInterface cast for COM objects."""
    if obj is None or MOD is None:
        return obj
    cls = getattr(MOD, iface, None)
    if cls is None:
        return obj
    ole = getattr(obj, "_oleobj_", obj)
    return cls(ole.QueryInterface(cls.CLSID, pythoncom.IID_IDispatch))


def connect():
    """Attaches to an active CAD session without spawning a new UI instance."""
    o = win32com.client.GetActiveObject("SldWorks.Application")
    return cast(o, "ISldWorks") if MOD else o


def open_docs(sw):
    """Iterates through open documents in the active CAD session."""
    d = sw.GetFirstDocument()
    while d is not None:
        md = cast(d, "IModelDoc2")
        yield md
        d = md.GetNext()


def open_readonly(sw, path):
    """Opens a document in read-only mode if not already loaded.
    Returns (model_doc, opened_by_script).
    """
    target = os.path.normcase(os.path.abspath(path))
    for md in open_docs(sw):
        if os.path.normcase(md.GetPathName() or "") == target:
            return md, False
    ext = os.path.splitext(path)[1].lower()
    doc_type = {".sldprt": DOC_PART, ".sldasm": DOC_ASM, ".slddrw": DOC_DRW}.get(ext, DOC_PART)
    res = sw.OpenDoc6(path, doc_type, OPEN_RO_SILENT, "", 0, 0)
    doc = res[0] if isinstance(res, tuple) else res
    return (cast(doc, "IModelDoc2") if doc else None), True


def get_property(md, config, prop_name):
    """Retrieves resolved custom property value (config-level first, then document-level)."""
    for cfg in (config, ""):
        try:
            r = md.Extension.CustomPropertyManager(cfg or "").Get6(prop_name, False, "", "", False, False)
        except Exception:
            continue
        if isinstance(r, tuple) and len(r) > 2:
            resolved, raw = (r[2] or "").strip(), (r[1] or "").strip()
            if resolved:
                return resolved, raw
            if raw:
                return raw, raw
    return "", ""


def get_mass_si(md):
    """Calculates true physical mass in kg (SI) directly from solid geometry."""
    for method_name in ("CreateMassProperty2", "CreateMassProperty"):
        try:
            mp = getattr(md.Extension, method_name)()
            if mp is not None:
                return float(cast(mp, "IMassProperty").Mass)
        except Exception:
            continue
    return None


def get_unit_settings(md):
    """Returns (unit_system, mass_unit, mass_decimals)."""
    ext = md.Extension
    return (
        ext.GetUserPreferenceInteger(P_UNITSYS, 0),
        ext.GetUserPreferenceInteger(P_MASS, 0),
        ext.GetUserPreferenceInteger(P_MASSDEC, 0),
    )


def load_lookup_table(lookup_csv_path=None):
    """Loads approved enum values from CSV lookup table."""
    csv_file = lookup_csv_path or DEFAULT_LOOKUP_CSV
    out = {
        "SurfaceTreatment": set(),
        "ProcurementGroup": set(),
        "Supplier": set(),
        "StandardMaterial": set(),
    }
    if not os.path.exists(csv_file):
        return out
    with open(csv_file, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            for csv_col, key in (
                ("SurfaceTreatment", "SurfaceTreatment"),
                ("ProcurementGroup", "ProcurementGroup"),
                ("DefaultSupplier", "Supplier"),
                ("StandardMaterial", "StandardMaterial"),
            ):
                val = (row.get(csv_col) or "").strip()
                if val:
                    out[key].add(val)
    return out


def extract_assembly_components(sw, asm_path):
    """Extracts aggregated components with quantities and properties from an assembly."""
    doc, is_temporary = open_readonly(sw, asm_path)
    if doc is None:
        raise RuntimeError(f"Could not open assembly file: {asm_path}")
    try:
        asm = cast(doc, "IAssemblyDoc")
        raw_components = asm.GetComponents(False) or []
        counts, first_instances = {}, {}
        for c in raw_components:
            comp = cast(c, "IComponent2")
            path = comp.GetPathName() or ""
            # swComponentSuppressionState_e: 0 = SuppressedIdMismatch, 1 = Suppressed
            if not path or comp.GetSuppression() in (0, 1) or getattr(comp, "ExcludeFromBOM", False):
                continue
            cfg = comp.ReferencedConfiguration or ""
            key = (os.path.normcase(path), cfg)
            counts[key] = counts.get(key, 0) + 1
            first_instances.setdefault(key, comp)

        records = []
        for (norm_path, cfg), qty in counts.items():
            comp = first_instances[(norm_path, cfg)]
            md = cast(comp.GetModelDoc2(), "IModelDoc2")
            file_path = comp.GetPathName()
            code = os.path.splitext(os.path.basename(file_path))[0]
            record = {
                "code": code,
                "configuration": cfg,
                "qty": qty,
                "path": file_path,
                "type": "assembly" if file_path.lower().endswith(".sldasm") else "part",
            }
            if md is None:
                record["error"] = "Model not loaded (lightweight state)"
                records.append(record)
                continue

            for field in (
                "Description", "Revision", "Material", "Weight", "RawDimensions",
                "SurfaceTreatment", "PartType", "ProcurementGroup", "Supplier",
                "SupplierPartNumber", "ProjectCode", "DrawnBy", "CheckedBy",
                "ApprovedBy", "DrawnDate",
            ):
                resolved, raw_val = get_property(md, cfg, field)
                record[field] = resolved
                if field == "Weight":
                    record["Weight_raw"] = raw_val

            record["mass_kg"] = get_mass_si(md)
            record["units"] = get_unit_settings(md)
            records.append(record)

        records.sort(key=lambda x: x["code"])
        return doc, records
    finally:
        if is_temporary:
            sw.CloseDoc(doc.GetTitle())


def parse_numeric(val):
    """Parses '0.395' / '0,395' into float."""
    try:
        return float(str(val).replace(",", ".").split()[0])
    except Exception:
        return None
