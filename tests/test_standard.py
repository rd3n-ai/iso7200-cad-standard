# -*- coding: utf-8 -*-
"""Unit tests for the pure (SolidWorks-independent) functions of the ISO 7200
metadata standard reference implementation.

These tests run on any platform — they never touch a CAD session. They cover
the naming regexes, the part-code parser and the compliance audit logic.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import cad_pipeline_lib as cad  # noqa: E402
from cad_standard_check import audit_component  # noqa: E402

LOOKUP = {
    "SurfaceTreatment": {"Zinc Plating (ISO 2081 Fe/Zn 8/A)"},
    "ProcurementGroup": {"Laser_Cutting"},
    "Supplier": {"Vendor_LaserCut"},
    "StandardMaterial": {"AISI 304 (1.4301)"},
}

def record(**kw):
    base = {
        "code": "PRJ101_P001", "type": "part", "qty": 1,
        "Description": "Base plate", "Revision": "00",
        "PartType": "Manufactured", "Material": "AISI 304 (1.4301)",
        "Weight": "1.250", "Weight_raw": "SW-Mass@PRJ101_P001.sldprt",
        "mass_kg": 1.250, "units": (cad.UNITSYS_CUSTOM, cad.MASS_KG, 3),
        "ProcurementGroup": "Laser_Cutting", "SurfaceTreatment": "Zinc Plating (ISO 2081 Fe/Zn 8/A)",
    }
    base.update(kw)
    return base


class TestParseCode(unittest.TestCase):
    def test_valid_codes(self):
        self.assertEqual(cad.parse_code("PRJ101_P001.sldprt"), ("PRJ101", "P", 1))
        self.assertEqual(cad.parse_code("PRJ101_M00.sldasm"), ("PRJ101", "M", 0))
        self.assertEqual(cad.parse_code("MOD01_PS003.sldprt"), ("MOD01", "PS", 3))
        self.assertEqual(cad.parse_code("PRJ-101_P001.sldprt"), ("PRJ-101", "P", 1))  # hyphen in project

    def test_invalid_codes(self):
        self.assertIsNone(cad.parse_code("bearings.sldprt"))       # catalog part
        self.assertIsNone(cad.parse_code("prj101_p001.sldprt"))    # lowercase
        self.assertIsNone(cad.parse_code("ABC_01_P001.sldprt"))    # underscore inside project code

class TestCharacterLayer(unittest.TestCase):
    def test_character_layer_accepts(self):
        for name in ("PRJ101_P001", "PRJ-101_P001", "MOD01_PS003"):
            self.assertIsNotNone(cad.CODE_PATTERN.match(name), name)

    def test_character_layer_rejects(self):
        for name in ("prj101_p001", "P001_Ø", "PRJ 101_P001", "P#001"):
            self.assertIsNone(cad.CODE_PATTERN.match(name), name)


class TestAuditNaming(unittest.TestCase):
    def test_compliant_part_no_naming_findings(self):
        findings = audit_component(record(), LOOKUP)
        codes = [c for _, c, _ in findings]
        self.assertNotIn("K01", codes)
        self.assertNotIn("K04", codes)

    def test_manufactured_nonstandard_name_is_error(self):
        findings = audit_component(record(code="my_part", PartType="Manufactured"), LOOKUP)
        codes = [c for _, c, _ in findings]
        self.assertIn("K01", codes)  # lowercase -> character layer failure

    def test_nonstandard_name_with_unknown_parttype_is_warning(self):
        # K04 must not hard-fail a part that has not been classified yet.
        findings = audit_component(record(code="BEARING6004", PartType=""), LOOKUP)
        sev, code, _ = next(f for f in findings if f[1] == "K04")
        self.assertEqual(code, "K04")
        self.assertEqual(sev, "WARNING")

    def test_nonstandard_name_manufactured_is_error(self):
        findings = audit_component(record(code="BEARING6004", PartType="Manufactured"), LOOKUP)
        sev, code, _ = next(f for f in findings if f[1] == "K04")
        self.assertEqual(code, "K04")
        self.assertEqual(sev, "ERROR")

    def test_purchased_part_exempt_from_k04(self):
        findings = audit_component(record(code="SKF6204", PartType="Purchased",
                                          Supplier="SKF", SupplierPartNumber="6204"), LOOKUP)
        codes = [c for _, c, _ in findings]
        self.assertNotIn("K04", codes)


class TestAuditMaterialAndMass(unittest.TestCase):
    def test_manufactured_missing_material(self):
        findings = audit_component(record(Material=""), LOOKUP)
        self.assertIn("M01", [c for _, c, _ in findings])

    def test_purchased_missing_material_ok(self):
        findings = audit_component(record(PartType="Purchased", Material="",
                                          Supplier="SKF", SupplierPartNumber="6204"), LOOKUP)
        self.assertNotIn("M01", [c for _, c, _ in findings])

    def test_missing_weight(self):
        findings = audit_component(record(Weight="", Weight_raw=""), LOOKUP)
        self.assertIn("M02", [c for _, c, _ in findings])

    def test_invalid_weight_expression(self):
        findings = audit_component(record(Weight_raw="1.250"), LOOKUP)
        self.assertIn("M03", [c for _, c, _ in findings])

    def test_weight_in_grams_flagged_b02(self):
        findings = audit_component(record(Weight="1250.000", Weight_raw="SW-Mass@PRJ101_P001.sldprt"), LOOKUP)
        codes = [c for _, c, _ in findings]
        self.assertIn("B02", codes)

    def test_weight_drift_flagged_b03(self):
        findings = audit_component(record(Weight="1.320", Weight_raw="SW-Mass@PRJ101_P001.sldprt"), LOOKUP)
        codes = [c for _, c, _ in findings]
        self.assertIn("B03", codes)


class TestAuditSourcing(unittest.TestCase):
    def test_modified_standard_missing_raw_dimensions(self):
        findings = audit_component(record(code="PRJ101_PS001", PartType="ModifiedStandard",
                                          RawDimensions="", Supplier="DIN", SupplierPartNumber="933"), LOOKUP)
        self.assertIn("T06", [c for _, c, _ in findings])

    def test_purchased_missing_supplier(self):
        findings = audit_component(record(code="SKF6204.sldprt", PartType="Purchased"), LOOKUP)
        self.assertIn("T05", [c for _, c, _ in findings])

    def test_procurement_not_in_lookup(self):
        findings = audit_component(record(ProcurementGroup="Weird_Group"), LOOKUP)
        self.assertIn("T02", [c for _, c, _ in findings])


if __name__ == "__main__":
    unittest.main(verbosity=2)
