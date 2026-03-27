"""Test script for gff_parser.py and erf_parser.py.

Tests against real module data:
- Opens the actual .mod file with ErfFile
- Reads GFF resources and parses them with read_gff
- Compares output against existing nwn_gff JSON files
- Tests write_gff round-trip
"""

import json
import sys
import os
import math

# Add parent to path so we can import the modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gff_parser import read_gff, write_gff, GffParseError
from erf_parser import (
    ErfFile, ErfError, write_erf,
    restype_from_extension, extension_from_restype,
    restype_registered, extension_registered,
)

MOD_FILE = r"D:\tdn\workspace\tdn_gff\tdn_build.mod"
JSON_DIR = r"D:\tdn\workspace\tdn_gff\module"

passed = 0
failed = 0


def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name} {detail}")


def compare_values(a, b, path=""):
    """Deep compare two values, returning list of differences."""
    diffs = []
    if isinstance(a, dict) and isinstance(b, dict):
        all_keys = set(a.keys()) | set(b.keys())
        for k in sorted(all_keys):
            if k not in a:
                diffs.append(f"{path}.{k}: missing in actual")
            elif k not in b:
                diffs.append(f"{path}.{k}: missing in expected")
            else:
                diffs.extend(compare_values(a[k], b[k], f"{path}.{k}"))
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            diffs.append(f"{path}: list length {len(a)} vs {len(b)}")
        for i in range(min(len(a), len(b))):
            diffs.extend(compare_values(a[i], b[i], f"{path}[{i}]"))
    elif isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            pass
        elif a != b:
            # Check if they're close enough (float precision)
            if abs(a - b) > 1e-6 * max(abs(a), abs(b), 1):
                diffs.append(f"{path}: {a!r} vs {b!r}")
    elif isinstance(a, float) and isinstance(b, int):
        if a != float(b):
            diffs.append(f"{path}: {a!r} (float) vs {b!r} (int)")
    elif isinstance(a, int) and isinstance(b, float):
        if float(a) != b:
            diffs.append(f"{path}: {a!r} (int) vs {b!r} (float)")
    elif a != b:
        diffs.append(f"{path}: {a!r} vs {b!r}")
    return diffs


def test_restype_registry():
    print("\n=== ResType Registry Tests ===")
    test("uti -> 2025", restype_from_extension("uti") == 2025)
    test("utc -> 2027", restype_from_extension("utc") == 2027)
    test("are -> 2012", restype_from_extension("are") == 2012)
    test("git -> 2023", restype_from_extension("git") == 2023)
    test("ifo -> 2014", restype_from_extension("ifo") == 2014)
    test("dlg -> 2029", restype_from_extension("dlg") == 2029)
    test("2025 -> uti", extension_from_restype(2025) == "uti")
    test("2027 -> utc", extension_from_restype(2027) == "utc")
    test("case insensitive", restype_from_extension("UTI") == 2025)
    test("registered check", restype_registered(2025))
    test("unregistered check", not restype_registered(99999))
    test("ext registered", extension_registered("uti"))
    test("ext unregistered", not extension_registered("xyz"))


def test_erf_reader():
    print("\n=== ERF Reader Tests ===")

    if not os.path.exists(MOD_FILE):
        print(f"  SKIP: Module file not found: {MOD_FILE}")
        return

    with ErfFile(MOD_FILE) as erf:
        test("file opened", erf._file is not None)
        test("file type is MOD", erf.file_type.strip() in ("MOD", "MOD "),
             f"got {erf.file_type!r}")
        test("has resources", erf.resource_count > 0,
             f"got {erf.resource_count}")

        # List all resources
        all_res = erf.list_resources()
        test("list_resources returns list", isinstance(all_res, list))
        test("list_resources non-empty", len(all_res) > 0,
             f"got {len(all_res)}")

        # Filter by UTI type
        uti_res = erf.list_resources(type_filter=2025)
        test("UTI filter works", len(uti_res) > 0,
             f"got {len(uti_res)} UTIs")

        # Check resource_exists
        if uti_res:
            first_uti = uti_res[0]
            test("resource_exists positive",
                 erf.resource_exists(first_uti[0], first_uti[1]))
        test("resource_exists negative",
             not erf.resource_exists("nonexistent_xyz", 2025))

        # Read a specific resource
        if uti_res:
            data = erf.read_resource(first_uti[0], first_uti[1])
            test("read_resource returns bytes",
                 data is not None and isinstance(data, bytes))
            test("read_resource non-empty",
                 data is not None and len(data) > 0)

        # Read nonexistent resource
        data = erf.read_resource("nonexistent_xyz", 2025)
        test("read nonexistent returns None", data is None)

    # Test context manager closes file
    test("file closed after context", erf._file is None)


def test_gff_parser_basic():
    print("\n=== GFF Parser Basic Tests ===")

    if not os.path.exists(MOD_FILE):
        print(f"  SKIP: Module file not found: {MOD_FILE}")
        return

    with ErfFile(MOD_FILE) as erf:
        # Find 'apple' UTI if it exists
        uti_type = 2025
        apple_data = erf.read_resource("apple", uti_type)

        if apple_data is None:
            # Try any UTI
            uti_list = erf.list_resources(type_filter=uti_type)
            if uti_list:
                resref = uti_list[0][0]
                apple_data = erf.read_resource(resref, uti_type)
                print(f"  (using {resref} instead of apple)")
            else:
                print("  SKIP: No UTI resources found")
                return

        # Parse GFF binary
        result = read_gff(apple_data)
        test("result is dict", isinstance(result, dict))
        test("has __data_type", "__data_type" in result)
        test("__data_type is UTI",
             result.get("__data_type", "").strip() == "UTI",
             f"got {result.get('__data_type')!r}")
        test("no __struct_id on root", "__struct_id" not in result)

        # Check typed field structure
        if "Tag" in result:
            test("Tag has type key", "type" in result["Tag"])
            test("Tag type is cexostring",
                 result["Tag"]["type"] == "cexostring")
            test("Tag has value key", "value" in result["Tag"])

        if "BaseItem" in result:
            test("BaseItem type is int",
                 result["BaseItem"]["type"] == "int")

        if "Cost" in result:
            test("Cost type is dword",
                 result["Cost"]["type"] == "dword")
            test("Cost value is int",
                 isinstance(result["Cost"]["value"], int))


def test_gff_vs_json():
    """Compare GFF parser output against known nwn_gff JSON files."""
    print("\n=== GFF Parser vs nwn_gff JSON Comparison ===")

    if not os.path.exists(MOD_FILE):
        print(f"  SKIP: Module file not found: {MOD_FILE}")
        return

    json_uti_dir = os.path.join(JSON_DIR, "uti")
    if not os.path.exists(json_uti_dir):
        print(f"  SKIP: JSON UTI directory not found: {json_uti_dir}")
        return

    # Test a few UTI files
    test_resrefs = ["apple", "armortest", "arrow", "bolt", "book"]
    tested = 0

    with ErfFile(MOD_FILE) as erf:
        for resref in test_resrefs:
            json_path = os.path.join(json_uti_dir, f"{resref}.uti.json")
            if not os.path.exists(json_path):
                continue

            binary = erf.read_resource(resref, 2025)
            if binary is None:
                continue

            with open(json_path, "r", encoding="utf-8") as f:
                expected = json.load(f)

            actual = read_gff(binary)
            diffs = compare_values(actual, expected)
            test(f"{resref}.uti matches JSON",
                 len(diffs) == 0,
                 f"\n    " + "\n    ".join(diffs[:10]) if diffs else "")
            tested += 1

    if tested == 0:
        print("  SKIP: No matching UTI files found for comparison")

    # Also test UTC files
    json_utc_dir = os.path.join(JSON_DIR, "utc")
    if os.path.exists(json_utc_dir):
        test_utc = ["banker"]
        with ErfFile(MOD_FILE) as erf:
            for resref in test_utc:
                json_path = os.path.join(json_utc_dir, f"{resref}.utc.json")
                if not os.path.exists(json_path):
                    continue

                binary = erf.read_resource(resref, 2027)
                if binary is None:
                    continue

                with open(json_path, "r", encoding="utf-8") as f:
                    expected = json.load(f)

                actual = read_gff(binary)
                diffs = compare_values(actual, expected)
                test(f"{resref}.utc matches JSON",
                     len(diffs) == 0,
                     f"\n    " + "\n    ".join(diffs[:10]) if diffs else "")


def test_gff_roundtrip():
    """Test binary -> dict -> binary -> dict roundtrip."""
    print("\n=== GFF Round-trip Tests ===")

    if not os.path.exists(MOD_FILE):
        print(f"  SKIP: Module file not found: {MOD_FILE}")
        return

    with ErfFile(MOD_FILE) as erf:
        # Test with a few different resource types
        test_items = []
        for resref in ["apple", "armortest"]:
            data = erf.read_resource(resref, 2025)
            if data:
                test_items.append((resref, "uti", data))

        for resref in ["banker"]:
            data = erf.read_resource(resref, 2027)
            if data:
                test_items.append((resref, "utc", data))

        for resref, ext, original_binary in test_items:
            # Parse binary to dict
            dict1 = read_gff(original_binary)

            # Write dict back to binary
            new_binary = write_gff(dict1)

            # Parse the new binary
            dict2 = read_gff(new_binary)

            # Compare dicts (should be identical)
            diffs = compare_values(dict1, dict2)
            test(f"{resref}.{ext} roundtrip dict match",
                 len(diffs) == 0,
                 f"\n    " + "\n    ".join(diffs[:10]) if diffs else "")


def test_erf_roundtrip():
    """Test ERF write -> read roundtrip."""
    print("\n=== ERF Round-trip Tests ===")

    if not os.path.exists(MOD_FILE):
        print(f"  SKIP: Module file not found: {MOD_FILE}")
        return

    import tempfile

    with ErfFile(MOD_FILE) as erf:
        # Read a subset of resources
        resources = {}
        uti_list = erf.list_resources(type_filter=2025)[:5]
        for resref, restype in uti_list:
            data = erf.read_resource(resref, restype)
            if data:
                resources[(resref, restype)] = data

    if not resources:
        print("  SKIP: No resources to test")
        return

    test("collected resources", len(resources) > 0,
         f"got {len(resources)}")

    # Write to temp file
    tmp_path = os.path.join(tempfile.gettempdir(), "test_erf_roundtrip.mod")
    try:
        write_erf(tmp_path, resources, "MOD ")

        test("ERF file created", os.path.exists(tmp_path))
        test("ERF file non-empty", os.path.getsize(tmp_path) > 0)

        # Read back
        with ErfFile(tmp_path) as erf2:
            test("re-opened ERF", erf2.resource_count == len(resources),
                 f"expected {len(resources)}, got {erf2.resource_count}")

            for (resref, restype), original_data in resources.items():
                read_data = erf2.read_resource(resref, restype)
                test(f"roundtrip {resref}",
                     read_data == original_data,
                     f"size {len(read_data) if read_data else 0} vs {len(original_data)}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        bak = tmp_path + ".bak"
        if os.path.exists(bak):
            os.remove(bak)


def test_gff_error_handling():
    """Test error handling for malformed data."""
    print("\n=== GFF Error Handling Tests ===")

    # Too short
    try:
        read_gff(b"")
        test("empty data raises", False)
    except GffParseError:
        test("empty data raises GffParseError", True)

    # Wrong version
    try:
        bad = b"GFF V9.9" + b"\x00" * 48
        read_gff(bad)
        test("bad version raises", False)
    except GffParseError:
        test("bad version raises GffParseError", True)

    # write_gff with bad data_type
    try:
        write_gff({"__data_type": "XX"})
        test("bad data_type raises", False)
    except GffParseError:
        test("bad data_type raises GffParseError", True)


if __name__ == "__main__":
    print("=" * 60)
    print("GFF/ERF Parser Test Suite")
    print("=" * 60)

    test_restype_registry()
    test_erf_reader()
    test_gff_parser_basic()
    test_gff_vs_json()
    test_gff_roundtrip()
    test_erf_roundtrip()
    test_gff_error_handling()

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    sys.exit(1 if failed > 0 else 0)
