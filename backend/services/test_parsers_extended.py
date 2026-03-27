"""Extended tests for gff_parser.py and erf_parser.py.

Tests more complex GFF structures: DLGs, GITs, ITPs, and all resource types.
Also validates that EVERY resource in the module can be parsed without errors.
"""

import json
import sys
import os
import math
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gff_parser import read_gff, write_gff, GffParseError, FIELD_TYPE_NAMES
from erf_parser import (
    ErfFile, restype_from_extension, extension_from_restype,
    restype_registered,
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


def collect_field_types(d, types_seen=None):
    """Recursively collect all GFF field types present in a dict."""
    if types_seen is None:
        types_seen = set()
    if not isinstance(d, dict):
        return types_seen
    for key, val in d.items():
        if key.startswith("__"):
            continue
        if isinstance(val, dict) and "type" in val:
            types_seen.add(val["type"])
            if val["type"] == "struct" and "value" in val:
                collect_field_types(val["value"], types_seen)
            elif val["type"] == "list" and "value" in val:
                for item in val["value"]:
                    collect_field_types(item, types_seen)
    return types_seen


def test_all_gff_resources():
    """Parse every GFF resource in the module to check for parse errors."""
    print("\n=== Parse ALL GFF Resources ===")

    if not os.path.exists(MOD_FILE):
        print(f"  SKIP: Module file not found: {MOD_FILE}")
        return

    # GFF resource types (all the types that use GFF format)
    gff_restypes = [
        2012,  # are
        2023,  # git
        2025,  # uti
        2027,  # utc
        2029,  # dlg
        2030,  # itp
        2032,  # utt
        2035,  # uts
        2037,  # gff
        2038,  # fac
        2040,  # ute
        2042,  # utd
        2044,  # utp
        2046,  # gic
        2047,  # gui
        2051,  # utm
        2055,  # utg
        2056,  # jrl
        2058,  # utw
        2014,  # ifo
    ]

    total = 0
    errors = 0
    types_seen = set()

    with ErfFile(MOD_FILE) as erf:
        all_res = erf.list_resources()
        for resref, restype in all_res:
            if restype not in gff_restypes:
                continue

            total += 1
            data = erf.read_resource(resref, restype)
            if data is None:
                continue

            try:
                result = read_gff(data)
                collect_field_types(result, types_seen)
            except Exception as e:
                errors += 1
                ext = extension_from_restype(restype) if restype_registered(restype) else str(restype)
                if errors <= 5:
                    print(f"  ERROR: {resref}.{ext}: {e}")

    test(f"parsed {total} GFF resources", errors == 0,
         f"{errors} errors out of {total}")
    print(f"  Field types seen across all resources: {sorted(types_seen)}")


def test_complex_json_comparison():
    """Compare complex GFF types (DLG, GIT, ITP) against JSON files."""
    print("\n=== Complex GFF vs JSON Comparison ===")

    if not os.path.exists(MOD_FILE):
        print(f"  SKIP: Module file not found: {MOD_FILE}")
        return

    # Test various resource types
    test_cases = [
        ("dlg", 2029, 3),   # Dialogs (deeply nested structs)
        ("git", 2023, 2),   # Area instances (many lists)
        ("are", 2012, 2),   # Area metadata
        ("utp", 2044, 3),   # Placeables
        ("utd", 2042, 3),   # Doors
        ("ute", 2040, 3),   # Encounters
        ("utm", 2051, 3),   # Stores
        ("utt", 2032, 3),   # Triggers
        ("utw", 2058, 3),   # Waypoints
        ("itp", 2030, 2),   # Palettes
        ("fac", 2038, 1),   # Factions
        ("jrl", 2056, 2),   # Journals
    ]

    with ErfFile(MOD_FILE) as erf:
        for ext, restype, max_tests in test_cases:
            json_dir = os.path.join(JSON_DIR, ext)
            if not os.path.exists(json_dir):
                continue

            # Get list of resources of this type
            res_list = erf.list_resources(type_filter=restype)
            tested = 0

            for resref, _ in res_list:
                if tested >= max_tests:
                    break

                json_path = os.path.join(json_dir, f"{resref}.{ext}.json")
                if not os.path.exists(json_path):
                    continue

                binary = erf.read_resource(resref, restype)
                if binary is None:
                    continue

                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        expected = json.load(f)

                    actual = read_gff(binary)
                    diffs = compare_values(actual, expected)
                    test(f"{resref}.{ext} matches JSON",
                         len(diffs) == 0,
                         f"\n    " + "\n    ".join(diffs[:5]) if diffs else "")
                    tested += 1
                except Exception as e:
                    test(f"{resref}.{ext} parse", False, str(e))
                    tested += 1


def test_roundtrip_all_types():
    """Test write_gff roundtrip with various resource types."""
    print("\n=== Round-trip Various Types ===")

    if not os.path.exists(MOD_FILE):
        print(f"  SKIP: Module file not found: {MOD_FILE}")
        return

    gff_restypes = [2012, 2023, 2025, 2027, 2029, 2030, 2032,
                    2035, 2040, 2042, 2044, 2051, 2058]

    with ErfFile(MOD_FILE) as erf:
        for restype in gff_restypes:
            ext = extension_from_restype(restype) if restype_registered(restype) else str(restype)
            res_list = erf.list_resources(type_filter=restype)
            if not res_list:
                continue

            # Test first resource of each type
            resref = res_list[0][0]
            binary = erf.read_resource(resref, restype)
            if binary is None:
                continue

            try:
                dict1 = read_gff(binary)
                new_binary = write_gff(dict1)
                dict2 = read_gff(new_binary)
                diffs = compare_values(dict1, dict2)
                test(f"{resref}.{ext} roundtrip",
                     len(diffs) == 0,
                     f"\n    " + "\n    ".join(diffs[:5]) if diffs else "")
            except Exception as e:
                test(f"{resref}.{ext} roundtrip", False,
                     f"{e}\n    {traceback.format_exc()}")


if __name__ == "__main__":
    print("=" * 60)
    print("Extended GFF/ERF Parser Test Suite")
    print("=" * 60)

    test_all_gff_resources()
    test_complex_json_comparison()
    test_roundtrip_all_types()

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    sys.exit(1 if failed > 0 else 0)
