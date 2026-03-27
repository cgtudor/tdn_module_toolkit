"""Tests for ModFileBackend."""

import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.mod_file_backend import ModFileBackend, ModFileError
from services.erf_parser import ErfFile, restype_from_extension
from services.gff_parser import read_gff

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


def make_test_mod(tmp_dir):
    """Create a small test .mod file from the real module."""
    src = MOD_FILE
    dst = os.path.join(tmp_dir, "test.mod")
    # Copy a subset of resources into a new .mod for testing
    from services.erf_parser import write_erf
    resources = {}
    with ErfFile(src) as erf:
        # Grab a few UTI, UTC resources
        for resref in ["apple", "armortest", "arrow"]:
            data = erf.read_resource(resref, 2025)  # uti
            if data:
                resources[(resref, 2025)] = data
        for resref in ["banker"]:
            data = erf.read_resource(resref, 2027)  # utc
            if data:
                resources[(resref, 2027)] = data
    write_erf(dst, resources, "MOD ")
    return dst


def test_lifecycle():
    print("\n=== Lifecycle Tests ===")

    backend = ModFileBackend(MOD_FILE)
    test("not loaded initially", not backend.is_loaded)
    test("get_mode", backend.get_mode() == "mod_file")

    backend.load()
    test("loaded after load()", backend.is_loaded)
    test("no unsaved changes", not backend.has_unsaved_changes)
    test("dirty_count is 0", backend.dirty_count == 0)

    backend.close()
    test("not loaded after close()", not backend.is_loaded)


def test_list_resources():
    print("\n=== list_resources Tests ===")

    backend = ModFileBackend(MOD_FILE)
    backend.load()

    utis = backend.list_resources("uti")
    test("list UTIs returns list", isinstance(utis, list))
    test("list UTIs non-empty", len(utis) > 0, f"got {len(utis)}")
    test("apple in UTIs", "apple" in utis)

    utcs = backend.list_resources("utc")
    test("list UTCs non-empty", len(utcs) > 0)
    test("banker in UTCs", "banker" in utcs)

    # Unknown type
    unknowns = backend.list_resources("xyz")
    test("unknown type returns empty", len(unknowns) == 0)

    backend.close()


def test_read_resource():
    print("\n=== read_resource Tests ===")

    backend = ModFileBackend(MOD_FILE)
    backend.load()

    data = backend.read_resource("apple", "uti")
    test("read apple returns dict", isinstance(data, dict))
    test("apple has __data_type", "__data_type" in data)
    test("apple Tag", data.get("Tag", {}).get("value") == "Apple")

    # Compare against JSON file
    json_path = os.path.join(JSON_DIR, "uti", "apple.uti.json")
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            expected = json.load(f)
        test("apple matches JSON",
             data.get("Tag") == expected.get("Tag") and
             data.get("Cost") == expected.get("Cost"))

    # Read nonexistent
    none_data = backend.read_resource("nonexistent_xyz", "uti")
    test("nonexistent returns None", none_data is None)

    # Read with bad type
    bad_type = backend.read_resource("apple", "xyz")
    test("bad type returns None", bad_type is None)

    backend.close()


def test_resource_exists():
    print("\n=== resource_exists Tests ===")

    backend = ModFileBackend(MOD_FILE)
    backend.load()

    test("apple.uti exists", backend.resource_exists("apple", "uti"))
    test("banker.utc exists", backend.resource_exists("banker", "utc"))
    test("nonexistent doesn't exist",
         not backend.resource_exists("nonexistent_xyz", "uti"))

    backend.close()


def test_write_and_dirty_tracking():
    print("\n=== write_resource & Dirty Tracking Tests ===")

    tmp_dir = tempfile.mkdtemp()
    try:
        mod_path = make_test_mod(tmp_dir)
        backend = ModFileBackend(mod_path)
        backend.load()

        test("no unsaved changes initially", not backend.has_unsaved_changes)

        # Read, modify, write back
        data = backend.read_resource("apple", "uti")
        test("read apple", data is not None)

        data["Tag"]["value"] = "ModifiedApple"
        result = backend.write_resource("apple", "uti", data)
        test("write returns True", result)
        test("has unsaved changes", backend.has_unsaved_changes)
        test("dirty_count is 1", backend.dirty_count == 1)

        # Read back modified data
        modified = backend.read_resource("apple", "uti")
        test("read returns modified data",
             modified["Tag"]["value"] == "ModifiedApple")

        # Version counter bumped
        ver = backend.get_resource_modified("apple", "uti")
        test("version counter bumped", ver == "1")

        backend.close()
    finally:
        shutil.rmtree(tmp_dir)


def test_delete_resource():
    print("\n=== delete_resource Tests ===")

    tmp_dir = tempfile.mkdtemp()
    try:
        mod_path = make_test_mod(tmp_dir)
        backend = ModFileBackend(mod_path)
        backend.load()

        test("apple exists before delete", backend.resource_exists("apple", "uti"))

        result = backend.delete_resource("apple", "uti")
        test("delete returns True", result)
        test("apple gone after delete", not backend.resource_exists("apple", "uti"))
        test("read deleted returns None",
             backend.read_resource("apple", "uti") is None)

        # apple should not appear in list
        utis = backend.list_resources("uti")
        test("apple not in list", "apple" not in utis)

        test("has unsaved changes", backend.has_unsaved_changes)

        # Delete nonexistent
        result2 = backend.delete_resource("nonexistent_xyz", "uti")
        test("delete nonexistent returns False", not result2)

        backend.close()
    finally:
        shutil.rmtree(tmp_dir)


def test_add_new_resource():
    print("\n=== Add New Resource Tests ===")

    tmp_dir = tempfile.mkdtemp()
    try:
        mod_path = make_test_mod(tmp_dir)
        backend = ModFileBackend(mod_path)
        backend.load()

        # Add a brand new resource
        new_item = {
            "__data_type": "UTI ",
            "Tag": {"type": "cexostring", "value": "NewItem"},
            "TemplateResRef": {"type": "resref", "value": "newitem"},
            "BaseItem": {"type": "int", "value": 0},
        }

        test("newitem doesn't exist", not backend.resource_exists("newitem", "uti"))

        result = backend.write_resource("newitem", "uti", new_item)
        test("write new returns True", result)
        test("newitem exists after add", backend.resource_exists("newitem", "uti"))
        test("newitem in list", "newitem" in backend.list_resources("uti"))

        # Read it back
        read_back = backend.read_resource("newitem", "uti")
        test("read back new item", read_back["Tag"]["value"] == "NewItem")

        # Delete the added item (should just remove from _added)
        result2 = backend.delete_resource("newitem", "uti")
        test("delete added returns True", result2)
        test("newitem gone", not backend.resource_exists("newitem", "uti"))

        backend.close()
    finally:
        shutil.rmtree(tmp_dir)


def test_rename_resource():
    print("\n=== rename_resource Tests ===")

    tmp_dir = tempfile.mkdtemp()
    try:
        mod_path = make_test_mod(tmp_dir)
        backend = ModFileBackend(mod_path)
        backend.load()

        test("apple exists", backend.resource_exists("apple", "uti"))
        test("apple2 doesn't exist", not backend.resource_exists("apple2", "uti"))

        result = backend.rename_resource("apple", "apple2", "uti")
        test("rename returns True", result)
        test("apple gone", not backend.resource_exists("apple", "uti"))
        test("apple2 exists", backend.resource_exists("apple2", "uti"))

        # Read renamed
        data = backend.read_resource("apple2", "uti")
        test("renamed data readable", data is not None)
        test("renamed data has Tag", data["Tag"]["value"] == "Apple")

        # Rename to existing should fail
        result2 = backend.rename_resource("armortest", "apple2", "uti")
        test("rename to existing fails", not result2)

        backend.close()
    finally:
        shutil.rmtree(tmp_dir)


def test_save_and_reload():
    print("\n=== save() and Reload Tests ===")

    tmp_dir = tempfile.mkdtemp()
    try:
        mod_path = make_test_mod(tmp_dir)
        backend = ModFileBackend(mod_path)
        backend.load()

        original_utis = set(backend.list_resources("uti"))
        test("original has apple", "apple" in original_utis)

        # Modify apple
        data = backend.read_resource("apple", "uti")
        data["Tag"]["value"] = "SavedApple"
        backend.write_resource("apple", "uti", data)

        # Add a new item
        new_item = {
            "__data_type": "UTI ",
            "Tag": {"type": "cexostring", "value": "BrandNew"},
            "TemplateResRef": {"type": "resref", "value": "brandnew"},
            "BaseItem": {"type": "int", "value": 0},
        }
        backend.write_resource("brandnew", "uti", new_item)

        # Delete arrow
        backend.delete_resource("arrow", "uti")

        test("dirty count is 3", backend.dirty_count == 3,
             f"got {backend.dirty_count}")

        # Save
        backend.save()
        test("no unsaved changes after save", not backend.has_unsaved_changes)
        test("dirty count 0 after save", backend.dirty_count == 0)

        # Verify changes persisted
        saved_apple = backend.read_resource("apple", "uti")
        test("modified apple persisted",
             saved_apple["Tag"]["value"] == "SavedApple")

        saved_new = backend.read_resource("brandnew", "uti")
        test("new item persisted",
             saved_new is not None and saved_new["Tag"]["value"] == "BrandNew")

        test("arrow deleted", not backend.resource_exists("arrow", "uti"))

        # Close and reopen to verify from fresh state
        backend.close()
        backend2 = ModFileBackend(mod_path)
        backend2.load()

        reopened_apple = backend2.read_resource("apple", "uti")
        test("reopened: apple modified",
             reopened_apple["Tag"]["value"] == "SavedApple")

        reopened_new = backend2.read_resource("brandnew", "uti")
        test("reopened: brandnew exists",
             reopened_new is not None and
             reopened_new["Tag"]["value"] == "BrandNew")

        test("reopened: arrow gone",
             not backend2.resource_exists("arrow", "uti"))

        backend2.close()
    finally:
        shutil.rmtree(tmp_dir)


def test_external_modification_detection():
    print("\n=== External Modification Detection Tests ===")

    tmp_dir = tempfile.mkdtemp()
    try:
        mod_path = make_test_mod(tmp_dir)
        backend = ModFileBackend(mod_path)
        backend.load()

        # Modify a resource
        data = backend.read_resource("apple", "uti")
        data["Tag"]["value"] = "Modified"
        backend.write_resource("apple", "uti", data)

        # Simulate external modification by touching the file
        import time
        time.sleep(0.1)
        with open(mod_path, "ab") as f:
            pass  # Just update mtime
        os.utime(mod_path, (time.time() + 1, time.time() + 1))

        # Save should fail
        try:
            backend.save()
            test("save raises on external modification", False)
        except ModFileError as e:
            test("save raises ModFileError",
                 "modified externally" in str(e).lower(),
                 str(e))

        backend.close()
    finally:
        shutil.rmtree(tmp_dir)


def test_get_resource_modified():
    print("\n=== get_resource_modified Tests ===")

    backend = ModFileBackend(MOD_FILE)
    backend.load()

    # Unmodified resource
    ver = backend.get_resource_modified("apple", "uti")
    test("unmodified version is '0'", ver == "0")

    # Nonexistent
    ver2 = backend.get_resource_modified("nonexistent_xyz", "uti")
    test("nonexistent version is ''", ver2 == "")

    backend.close()


def test_cache_behavior():
    print("\n=== Cache Behavior Tests ===")

    backend = ModFileBackend(MOD_FILE, cache_size=2)
    backend.load()

    # Read 3 resources with cache_size=2, first should be evicted
    backend.read_resource("apple", "uti")
    backend.read_resource("armortest", "uti")
    test("cache has 2 entries", len(backend._cache) == 2)

    backend.read_resource("arrow", "uti")
    test("cache still has 2 (evicted oldest)", len(backend._cache) == 2)

    # apple should have been evicted
    apple_key = ("apple", 2025)
    test("apple evicted from cache", apple_key not in backend._cache)

    backend.close()


if __name__ == "__main__":
    if not os.path.exists(MOD_FILE):
        print(f"SKIP: Module file not found: {MOD_FILE}")
        sys.exit(0)

    print("=" * 60)
    print("ModFileBackend Test Suite")
    print("=" * 60)

    test_lifecycle()
    test_list_resources()
    test_read_resource()
    test_resource_exists()
    test_write_and_dirty_tracking()
    test_delete_resource()
    test_add_new_resource()
    test_rename_resource()
    test_save_and_reload()
    test_external_modification_detection()
    test_get_resource_modified()
    test_cache_behavior()

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    sys.exit(1 if failed > 0 else 0)
