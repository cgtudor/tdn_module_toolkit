"""SQLite indexer for fast searching and caching."""
import sqlite3
import hashlib
import os
import sys
import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, TYPE_CHECKING
from contextlib import contextmanager

from services.gff_service import GFFService

if TYPE_CHECKING:
    from services.tlk_service import TLKService


# ---------------------------------------------------------------------------
# Module-level worker functions for ProcessPoolExecutor
# Must be at module level (not methods) so they're picklable on Windows.
# ---------------------------------------------------------------------------

def _worker_init(extra_paths):
    """Initializer for worker processes -- ensures imports resolve."""
    for p in extra_paths:
        if p not in sys.path:
            sys.path.insert(0, p)


def _parse_item_batch(args):
    """Parse a batch of raw item GFF bytes and extract index fields.

    Args:
        args: (batch, hash_map) where batch is [(resref, raw_bytes), ...] and
              hash_map maps resref -> precomputed MD5 hex digest.

    Returns:
        List of (resref, name, base_item, cost, stack_size, identified,
                 content_hash, loc_data_for_tlk) tuples.
        loc_data_for_tlk is the raw LocalizedName dict (for TLK resolution
        on the main thread) or None.
    """
    from services.gff_parser import read_gff

    batch, hash_map = args
    results = []
    for resref, raw_bytes in batch:
        try:
            data = read_gff(raw_bytes)
        except Exception:
            continue

        # Extract locstring inline (replicates GFFService.extract_locstring)
        name = ""
        loc_data = data.get("LocalizedName")
        if loc_data is not None:
            name = _extract_locstring(loc_data)

        # Extract simple values inline (replicates GFFService.extract_value)
        base_item = _extract_val(data, "BaseItem", 0)
        cost = _extract_val(data, "Cost", 0)
        stack_size = _extract_val(data, "StackSize", 1)
        identified = _extract_val(data, "Identified", 1)

        content_hash = hash_map.get(resref)
        results.append((resref, name, base_item, cost, stack_size, identified,
                         content_hash, loc_data))
    return results


def _parse_creature_batch(args):
    """Parse a batch of raw creature GFF bytes and extract index fields.

    Returns list of (resref, first_name, last_name, race, appearance,
    equipment_count, inventory_count, content_hash, item_refs) tuples.
    """
    from services.gff_parser import read_gff

    batch, hash_map = args
    results = []
    for resref, raw_bytes in batch:
        try:
            data = read_gff(raw_bytes)
        except Exception:
            continue

        first_name = _extract_locstring(data.get("FirstName"))
        last_name = _extract_locstring(data.get("LastName"))
        race = _extract_val(data, "Race", 0)
        appearance = _extract_val(data, "Appearance_Type", 0)

        equip_list = _extract_list(data, "Equip_ItemList")
        inv_list = _extract_list(data, "ItemList")

        # Collect item references inline
        item_refs = []
        for idx, inv_item in enumerate(inv_list):
            item_rr = _extract_val(inv_item, "TemplateResRef", "")
            if item_rr:
                item_refs.append((item_rr, "creature_inventory", resref,
                                  json.dumps({"index": idx})))

        for equip_item in equip_list:
            slot_id = equip_item.get("__struct_id", 0)
            item_rr = _extract_val(equip_item, "EquippedRes", "")
            if not item_rr:
                item_rr = _extract_val(equip_item, "TemplateResRef", "")
            if item_rr:
                item_refs.append((item_rr, "creature_equipment", resref,
                                  json.dumps({"slot_id": slot_id})))

        content_hash = hash_map.get(resref)
        results.append((resref, first_name, last_name, race, appearance,
                         len(equip_list), len(inv_list), content_hash,
                         item_refs))
    return results


def _parse_store_batch(args):
    """Parse a batch of raw store GFF bytes and extract index fields.

    Returns list of (resref, name, markup, markdown, max_buy, gold,
    item_count, content_hash, item_refs) tuples.
    """
    from services.gff_parser import read_gff

    batch, hash_map = args
    results = []
    for resref, raw_bytes in batch:
        try:
            data = read_gff(raw_bytes)
        except Exception:
            continue

        name = _extract_locstring(data.get("LocName"))
        markup = _extract_val(data, "MarkUp", 100)
        markdown = _extract_val(data, "MarkDown", 100)
        max_buy = _extract_val(data, "MaxBuyPrice", -1)
        gold = _extract_val(data, "StoreGold", -1)

        item_count = 0
        item_refs = []
        store_list = _extract_list(data, "StoreList")
        for cat_entry in store_list:
            cat_id = cat_entry.get("__struct_id", 0)
            item_list = _extract_list(cat_entry, "ItemList")
            item_count += len(item_list)
            for idx, store_item in enumerate(item_list):
                item_rr = _extract_val(store_item, "InventoryRes", "")
                if item_rr:
                    item_refs.append((item_rr, "store_template", resref,
                                      json.dumps({"category_id": cat_id,
                                                   "index": idx})))

        content_hash = hash_map.get(resref)
        results.append((resref, name, markup, markdown, max_buy, gold,
                         item_count, content_hash, item_refs))
    return results


def _parse_area_batch(args):
    """Parse a batch of raw area GIT GFF bytes and extract index fields.

    Args:
        args: (batch, hash_map, are_data_map) where batch is
              [(resref, raw_git_bytes), ...], hash_map maps resref -> hash,
              and are_data_map maps resref -> raw ARE bytes (may be empty).

    Returns list of (resref, name, store_count, creature_count, content_hash,
    item_refs) tuples.
    """
    from services.gff_parser import read_gff

    batch, hash_map, are_data_map = args
    results = []
    for resref, raw_git_bytes in batch:
        try:
            git_data = read_gff(raw_git_bytes)
        except Exception:
            continue

        # Parse ARE for name
        name = ""
        are_bytes = are_data_map.get(resref)
        if are_bytes:
            try:
                are_data = read_gff(are_bytes)
                name = _extract_locstring(are_data.get("Name"))
            except Exception:
                pass

        store_list = _extract_list(git_data, "StoreList")
        creature_list = _extract_list(git_data, "Creature List")

        # Collect item references from area store instances
        item_refs = []
        for store_idx, store_instance in enumerate(store_list):
            inner_store_list = _extract_list(store_instance, "StoreList")
            for cat_entry in inner_store_list:
                cat_id = cat_entry.get("__struct_id", 0)
                item_list = _extract_list(cat_entry, "ItemList")
                for item_idx, store_item in enumerate(item_list):
                    item_rr = _extract_val(store_item, "TemplateResRef", "")
                    if not item_rr:
                        item_rr = _extract_val(store_item, "InventoryRes", "")
                    if item_rr:
                        item_refs.append((item_rr, "area_store", resref,
                                          json.dumps({
                                              "store_index": store_idx,
                                              "category_id": cat_id,
                                              "item_index": item_idx,
                                          })))

        content_hash = hash_map.get(resref)
        results.append((resref, name, len(store_list), len(creature_list),
                         content_hash, item_refs))
    return results


# ---------------------------------------------------------------------------
# Inline GFF field helpers for worker processes (no GFFService dependency)
# ---------------------------------------------------------------------------

def _extract_locstring(loc_data) -> str:
    """Extract a localized string from GFF data (worker-safe)."""
    if loc_data is None:
        return ""
    if isinstance(loc_data, dict):
        if "value" in loc_data:
            value = loc_data["value"]
            if isinstance(value, dict):
                if "0" in value:
                    return value["0"]
                for k, v in value.items():
                    if k != "id" and isinstance(v, str):
                        return v
                return ""
            return str(value) if value else ""
        if "0" in loc_data:
            return loc_data["0"]
        for k, v in loc_data.items():
            if k != "id" and isinstance(v, str):
                return v
        return ""
    return str(loc_data) if loc_data else ""


def _extract_val(data: dict, key: str, default=None):
    """Extract a value from GFF data (worker-safe)."""
    if key not in data:
        return default
    val = data[key]
    if isinstance(val, dict) and "value" in val:
        return val["value"]
    return val


def _extract_list(data: dict, key: str) -> list:
    """Extract a list from GFF data (worker-safe)."""
    if key not in data:
        return []
    val = data[key]
    if isinstance(val, dict) and "value" in val:
        val = val["value"]
    if isinstance(val, list):
        return val
    return []


def get_base_path() -> Path:
    """Get base path for data files (works in dev and PyInstaller bundled mode)."""
    if getattr(sys, 'frozen', False):
        # Running as bundled executable (PyInstaller)
        # _MEIPASS is the temp folder where PyInstaller extracts files
        return Path(sys._MEIPASS)
    # Running in development
    return Path(__file__).parent.parent


class Indexer:
    """SQLite-based index for inventory data."""

    SCHEMA_VERSION = "1"

    def __init__(self, db_path: str, gff_service: GFFService,
                 tlk_service: Optional["TLKService"] = None):
        self.db_path = db_path
        self.gff = gff_service
        self.tlk = tlk_service
        self._init_db()

    def _init_db(self):
        """Initialize database schema and run migrations for existing DBs."""
        schema_path = get_base_path() / "db" / "schema.sql"
        print(f"Loading schema from: {schema_path}", flush=True)
        with open(schema_path, 'r') as f:
            schema = f.read()

        with self._get_connection() as conn:
            conn.executescript(schema)

            # --- Migrations for pre-existing databases ---
            # CREATE TABLE IF NOT EXISTS handles module_metadata automatically.
            # But content_hash columns need ALTER TABLE for existing tables.
            cursor = conn.execute("PRAGMA table_info(items)")
            columns = {row["name"] for row in cursor.fetchall()}
            if "content_hash" not in columns:
                print("Migrating schema: adding content_hash columns...", flush=True)
                for table in ("items", "creatures", "stores", "areas"):
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN content_hash TEXT")
                print("Schema migration complete.", flush=True)

    @contextmanager
    def _get_connection(self):
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Module metadata helpers
    # ------------------------------------------------------------------

    def _get_module_metadata(self) -> Dict[str, str]:
        """Read all key/value pairs from the module_metadata table."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT key, value FROM module_metadata")
            return {row["key"]: row["value"] for row in cursor.fetchall()}

    def _set_module_metadata(self, metadata: Dict[str, str]) -> None:
        """Write/update key/value pairs in the module_metadata table."""
        with self._get_connection() as conn:
            for key, value in metadata.items():
                conn.execute(
                    "INSERT OR REPLACE INTO module_metadata (key, value) VALUES (?, ?)",
                    (key, value),
                )

    def _check_module_fingerprint(self) -> bool:
        """Check if the current .mod file matches the stored fingerprint.

        Returns True if path, mtime, size, and schema version ALL match,
        meaning the module is unchanged and the index can be reused as-is.
        """
        backend = self.gff.backend
        if not (hasattr(backend, 'get_mode') and backend.get_mode() == "mod_file"):
            return False

        mod_path = backend._mod_path

        try:
            current_mtime = str(os.path.getmtime(mod_path))
            current_size = str(os.path.getsize(mod_path))
        except OSError:
            return False

        stored = self._get_module_metadata()
        return (
            stored.get("mod_file_path") == mod_path
            and stored.get("mod_file_mtime") == current_mtime
            and stored.get("mod_file_size") == current_size
            and stored.get("schema_version") == self.SCHEMA_VERSION
        )

    def _store_module_fingerprint(self) -> None:
        """Store the current .mod file fingerprint in module_metadata."""
        backend = self.gff.backend
        if not (hasattr(backend, 'get_mode') and backend.get_mode() == "mod_file"):
            return

        mod_path = backend._mod_path
        try:
            self._set_module_metadata({
                "mod_file_path": mod_path,
                "mod_file_mtime": str(os.path.getmtime(mod_path)),
                "mod_file_size": str(os.path.getsize(mod_path)),
                "schema_version": self.SCHEMA_VERSION,
            })
        except OSError:
            pass  # Best-effort; next load will just do a full reindex

    # ------------------------------------------------------------------
    # Reindex entry points
    # ------------------------------------------------------------------

    def reindex_all(self, progress_callback=None) -> dict:
        """Reindex all files (full rebuild). Returns counts.

        In MOD mode, uses parallel GFF parsing across multiple CPU cores
        for significantly faster first-time indexing.

        Item references are collected inline during creature/store/area
        indexing to avoid double-parsing the same GFF resources.
        """
        backend = self.gff.backend
        is_mod_mode = hasattr(backend, 'get_mode') and backend.get_mode() == "mod_file"

        if is_mod_mode:
            counts = self._parallel_reindex_all(progress_callback)
        else:
            item_count = self._reindex_items()
            creature_count, creature_refs = self._reindex_creatures(collect_item_refs=True)
            store_count, store_refs = self._reindex_stores(collect_item_refs=True)
            area_count, area_refs = self._reindex_areas(collect_item_refs=True)

            all_refs = creature_refs + store_refs + area_refs
            ref_count = self._batch_insert_item_references(all_refs)

            counts = {
                "items": item_count,
                "creatures": creature_count,
                "stores": store_count,
                "areas": area_count,
                "item_references": ref_count,
            }

        # Store fingerprint so subsequent opens can skip reindex
        self._store_module_fingerprint()

        return counts

    # ------------------------------------------------------------------
    # Parallel reindex for MOD mode (cold load)
    # ------------------------------------------------------------------

    @staticmethod
    def _make_batches(items: list, batch_size: int) -> list:
        """Split a list into batches of at most batch_size."""
        return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]

    def _parallel_reindex_all(self, progress_callback=None) -> dict:
        """Full reindex using parallel GFF parsing across CPU cores.

        1. Reads all raw GFF bytes from ERF (sequential I/O, main thread).
        2. Dispatches parsing+field extraction to worker processes.
        3. Collects results: TLK resolution + SQLite batch writes on main thread.
        4. Collects item references inline (no double-parse).

        Falls back to sequential reindex if the process pool fails to start.
        """
        backend = self.gff.backend
        erf = backend._erf
        if erf is None:
            print("  Warning: ERF not loaded, falling back to sequential reindex", flush=True)
            return self._sequential_reindex_all(progress_callback)

        from .erf_parser import restype_from_extension

        start = time.time()
        worker_count = min(os.cpu_count() or 1, 8)
        # Resources per batch -- balances pickling overhead vs. parallelism
        batch_size = 200

        def report(msg):
            print(f"  {msg}", flush=True)
            if progress_callback:
                progress_callback(msg)

        report(f"Parallel reindex: {worker_count} workers")

        # --- 1. Bulk-read raw bytes from ERF (sequential I/O) ---
        report("Reading raw resources from ERF...")
        uti_type = restype_from_extension("uti")
        utc_type = restype_from_extension("utc")
        utm_type = restype_from_extension("utm")
        git_type = restype_from_extension("git")
        are_type = restype_from_extension("are")

        raw_items = erf.bulk_read_by_type(uti_type)      # resref -> bytes
        raw_creatures = erf.bulk_read_by_type(utc_type)
        raw_stores = erf.bulk_read_by_type(utm_type)
        raw_gits = erf.bulk_read_by_type(git_type)
        raw_ares = erf.bulk_read_by_type(are_type)

        # Compute hashes from already-read bytes (avoids second disk pass)
        hash_items = {rr: hashlib.md5(data).hexdigest() for rr, data in raw_items.items()}
        hash_creatures = {rr: hashlib.md5(data).hexdigest() for rr, data in raw_creatures.items()}
        hash_stores = {rr: hashlib.md5(data).hexdigest() for rr, data in raw_stores.items()}
        hash_gits = {rr: hashlib.md5(data).hexdigest() for rr, data in raw_gits.items()}

        read_time = time.time() - start
        report(f"Read {len(raw_items)} items, {len(raw_creatures)} creatures, "
               f"{len(raw_stores)} stores, {len(raw_gits)} areas in {read_time:.2f}s")

        # --- 2. Dispatch parsing to process pool ---
        # Build (resref, raw_bytes) lists for batching
        item_pairs = list(raw_items.items())
        creature_pairs = list(raw_creatures.items())
        store_pairs = list(raw_stores.items())
        git_pairs = list(raw_gits.items())

        item_batches = self._make_batches(item_pairs, batch_size)
        creature_batches = self._make_batches(creature_pairs, batch_size)
        store_batches = self._make_batches(store_pairs, batch_size)
        area_batches = self._make_batches(git_pairs, batch_size)

        # Build per-batch ARE data maps for area workers
        area_batch_are_maps = []
        for batch in area_batches:
            are_map = {}
            for resref, _ in batch:
                if resref in raw_ares:
                    are_map[resref] = raw_ares[resref]
            area_batch_are_maps.append(are_map)

        # Determine sys.path for workers (use get_base_path for PyInstaller compat)
        backend_dir = str(get_base_path())
        extra_paths = [backend_dir] + [p for p in sys.path if p not in [backend_dir]]

        all_item_results = []
        all_creature_results = []
        all_store_results = []
        all_area_results = []

        parse_start = time.time()
        report("Parsing GFF resources in parallel...")

        try:
            with ProcessPoolExecutor(
                max_workers=worker_count,
                initializer=_worker_init,
                initargs=(extra_paths,),
            ) as pool:
                # Submit all batches
                item_futures = [
                    pool.submit(_parse_item_batch, (batch, hash_items))
                    for batch in item_batches
                ]
                creature_futures = [
                    pool.submit(_parse_creature_batch, (batch, hash_creatures))
                    for batch in creature_batches
                ]
                store_futures = [
                    pool.submit(_parse_store_batch, (batch, hash_stores))
                    for batch in store_batches
                ]
                area_futures = [
                    pool.submit(_parse_area_batch, (batch, hash_gits, are_map))
                    for batch, are_map in zip(area_batches, area_batch_are_maps)
                ]

                # Collect results
                for f in as_completed(item_futures):
                    all_item_results.extend(f.result())
                for f in as_completed(creature_futures):
                    all_creature_results.extend(f.result())
                for f in as_completed(store_futures):
                    all_store_results.extend(f.result())
                for f in as_completed(area_futures):
                    all_area_results.extend(f.result())

        except Exception as e:
            # Pool failed to start or worker crashed -- fall back gracefully
            print(f"  Warning: Parallel parsing failed ({type(e).__name__}: {e}), "
                  f"falling back to sequential", flush=True)
            return self._sequential_reindex_all(progress_callback)

        parse_time = time.time() - parse_start
        report(f"Parsed {len(all_item_results)} items, {len(all_creature_results)} creatures, "
               f"{len(all_store_results)} stores, {len(all_area_results)} areas in {parse_time:.2f}s")

        # --- 3. TLK resolution + batch SQLite writes (main thread) ---
        report("Writing index to database...")
        write_start = time.time()
        all_item_refs = []

        with self._get_connection() as conn:
            # Items
            conn.execute("DELETE FROM items")
            conn.execute("DELETE FROM items_fts")
            for row in all_item_results:
                resref, name, base_item, cost, stack_size, identified, content_hash, loc_data = row
                # TLK resolution on main thread
                if self.tlk and loc_data is not None:
                    tlk_name = self.tlk.resolve_localized_name(loc_data)
                    if tlk_name:
                        name = tlk_name
                conn.execute("""
                    INSERT OR REPLACE INTO items
                    (resref, name, base_item, cost, stack_size, identified, file_modified, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (resref, name, base_item, cost, stack_size, identified, "0", content_hash))
                conn.execute("INSERT INTO items_fts (resref, name) VALUES (?, ?)",
                             (resref, name))

            # Creatures
            conn.execute("DELETE FROM creatures")
            conn.execute("DELETE FROM creatures_fts")
            for row in all_creature_results:
                resref, first_name, last_name, race, appearance, eq_count, inv_count, content_hash, item_refs = row
                conn.execute("""
                    INSERT OR REPLACE INTO creatures
                    (resref, first_name, last_name, race, appearance,
                     equipment_count, inventory_count, file_modified, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (resref, first_name, last_name, race, appearance,
                      eq_count, inv_count, "0", content_hash))
                conn.execute("""
                    INSERT INTO creatures_fts (resref, first_name, last_name)
                    VALUES (?, ?, ?)
                """, (resref, first_name, last_name))
                all_item_refs.extend(item_refs)

            # Stores
            conn.execute("DELETE FROM stores")
            conn.execute("DELETE FROM stores_fts")
            for row in all_store_results:
                resref, name, markup, markdown, max_buy, gold, item_count, content_hash, item_refs = row
                conn.execute("""
                    INSERT OR REPLACE INTO stores
                    (resref, name, markup, markdown, max_buy_price,
                     store_gold, item_count, file_modified, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (resref, name, markup, markdown, max_buy,
                      gold, item_count, "0", content_hash))
                conn.execute("INSERT INTO stores_fts (resref, name) VALUES (?, ?)",
                             (resref, name))
                all_item_refs.extend(item_refs)

            # Areas
            conn.execute("DELETE FROM areas")
            conn.execute("DELETE FROM areas_fts")
            for row in all_area_results:
                resref, name, store_count, creature_count, content_hash, item_refs = row
                conn.execute("""
                    INSERT OR REPLACE INTO areas
                    (resref, name, store_count, creature_count, file_modified, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (resref, name, store_count, creature_count, "0", content_hash))
                conn.execute("INSERT INTO areas_fts (resref, name) VALUES (?, ?)",
                             (resref, name))
                all_item_refs.extend(item_refs)

            # Item references
            conn.execute("DELETE FROM item_references")
            if all_item_refs:
                conn.executemany("""
                    INSERT OR REPLACE INTO item_references
                    (item_resref, reference_type, source_resref, extra_data)
                    VALUES (?, ?, ?, ?)
                """, all_item_refs)

        write_time = time.time() - write_start
        total_time = time.time() - start
        report(f"DB write completed in {write_time:.2f}s (total: {total_time:.2f}s)")

        return {
            "items": len(all_item_results),
            "creatures": len(all_creature_results),
            "stores": len(all_store_results),
            "areas": len(all_area_results),
            "item_references": len(all_item_refs),
        }

    def _sequential_reindex_all(self, progress_callback=None) -> dict:
        """Sequential full reindex fallback (used when process pool unavailable)."""
        item_count = self._reindex_items()
        creature_count, creature_refs = self._reindex_creatures(collect_item_refs=True)
        store_count, store_refs = self._reindex_stores(collect_item_refs=True)
        area_count, area_refs = self._reindex_areas(collect_item_refs=True)

        all_refs = creature_refs + store_refs + area_refs
        ref_count = self._batch_insert_item_references(all_refs)

        return {
            "items": item_count,
            "creatures": creature_count,
            "stores": store_count,
            "areas": area_count,
            "item_references": ref_count,
        }

    def smart_reindex_all(self, progress_callback=None) -> dict:
        """Incrementally update index based on change detection.

        For JSON mode: uses file modification times.
        For MOD mode: uses module-level fingerprint + per-resource content
        hashes. If the .mod file is unchanged since the last index, skips
        reindexing entirely. Otherwise performs hash-based incremental
        reindex, only re-parsing resources whose content actually changed.

        Args:
            progress_callback: Optional function(message: str) to report progress.

        Returns counts of changes per type.
        """
        backend = self.gff.backend
        is_mod_mode = hasattr(backend, 'get_mode') and backend.get_mode() == "mod_file"

        if is_mod_mode:
            # --- Module fingerprint check ---
            if self._check_module_fingerprint():
                print("  MOD file unchanged (fingerprint match) -- skipping reindex", flush=True)
                if progress_callback:
                    progress_callback("Index up-to-date (unchanged module)")
                cached = self.get_counts()
                with self._get_connection() as conn:
                    cursor = conn.execute("SELECT COUNT(*) FROM item_references")
                    ref_count = cursor.fetchone()[0]
                return {
                    "items": {"added": 0, "updated": 0, "deleted": 0, "unchanged": cached.get("items", 0)},
                    "creatures": {"added": 0, "updated": 0, "deleted": 0, "unchanged": cached.get("creatures", 0)},
                    "stores": {"added": 0, "updated": 0, "deleted": 0, "unchanged": cached.get("stores", 0)},
                    "areas": {"added": 0, "updated": 0, "deleted": 0, "unchanged": cached.get("areas", 0)},
                    "item_references": ref_count,
                }

            # Check if this is a cold load (empty DB) -- use parallel full reindex
            cached = self.get_counts()
            is_cold_load = all(v == 0 for v in cached.values())

            if is_cold_load:
                print("  Cold load (empty index) -- full parallel reindex", flush=True)
                if progress_callback:
                    progress_callback("First-time indexing (parallel)...")
                return self.reindex_all(progress_callback)

            print("  MOD file changed -- hash-based incremental reindex", flush=True)
            if progress_callback:
                progress_callback("Hash-based incremental reindex...")

        def report(msg):
            print(msg, flush=True)
            if progress_callback:
                progress_callback(msg)

        report("  Indexing items...")
        items_result = self._smart_reindex_items(progress_callback)
        report("  Indexing creatures...")
        creatures_result = self._smart_reindex_creatures(progress_callback)
        report("  Indexing stores...")
        stores_result = self._smart_reindex_stores(progress_callback)
        report("  Indexing areas...")
        areas_result = self._smart_reindex_areas(progress_callback)

        counts = {
            "items": items_result,
            "creatures": creatures_result,
            "stores": stores_result,
            "areas": areas_result,
        }

        # Rebuild item references if any containers changed
        containers_changed = (
            counts["creatures"]["added"] + counts["creatures"]["updated"] + counts["creatures"]["deleted"] +
            counts["stores"]["added"] + counts["stores"]["updated"] + counts["stores"]["deleted"] +
            counts["areas"]["added"] + counts["areas"]["updated"] + counts["areas"]["deleted"]
        )

        if containers_changed > 0:
            counts["item_references"] = self._reindex_item_references()
        else:
            # Get existing count
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM item_references")
                counts["item_references"] = cursor.fetchone()[0]

        # Store fingerprint after successful reindex (MOD mode only)
        if is_mod_mode:
            self._store_module_fingerprint()

        return counts

    def _smart_reindex_items(self, progress_callback=None) -> dict:
        """Incrementally reindex items based on modification times or content hashes."""
        counts = {"added": 0, "updated": 0, "deleted": 0, "unchanged": 0}

        backend = self.gff.backend
        is_mod_mode = hasattr(backend, 'get_mode') and backend.get_mode() == "mod_file"

        # Get existing entries from DB
        existing = {}  # resref -> comparison value (file_modified or content_hash)
        with self._get_connection() as conn:
            if is_mod_mode:
                cursor = conn.execute("SELECT resref, content_hash FROM items")
                for row in cursor.fetchall():
                    existing[row["resref"]] = row["content_hash"]
            else:
                cursor = conn.execute("SELECT resref, file_modified FROM items")
                for row in cursor.fetchall():
                    existing[row["resref"]] = row["file_modified"]

        # In MOD mode, bulk-hash all items in one sequential I/O pass
        current_hashes = {}  # resref -> hash (MOD mode only)
        if is_mod_mode and hasattr(backend, '_erf') and backend._erf is not None:
            from .erf_parser import restype_from_extension
            restype = restype_from_extension("uti")
            current_hashes = backend._erf.bulk_hash_by_type(restype)

        # Scan resources
        current_files = set()
        resref_list = self.gff.list_item_resrefs()
        total_files = len(resref_list)
        print(f"    Found {total_files} item files to check", flush=True)
        if progress_callback:
            progress_callback(f"Scanning {total_files} items...")

        for idx, resref in enumerate(resref_list):
            if idx > 0 and idx % 500 == 0:
                msg = f"Items: {idx}/{total_files}"
                print(f"    Processed {msg}...", flush=True)
                if progress_callback:
                    progress_callback(msg)

            current_files.add(resref)

            if is_mod_mode:
                current_val = current_hashes.get(resref)
                # For dirty/added resources not in ERF, compute hash individually
                if current_val is None and hasattr(backend, 'get_resource_hash'):
                    current_val = backend.get_resource_hash(resref, "uti")
                stored_val = existing.get(resref)
                # NULL stored hash (old DB) always triggers re-parse
                if resref not in existing:
                    self._index_single_item(resref, content_hash=current_val)
                    counts["added"] += 1
                elif stored_val is None or stored_val != current_val:
                    self._index_single_item(resref, content_hash=current_val)
                    counts["updated"] += 1
                else:
                    counts["unchanged"] += 1
            else:
                current_mtime = self.gff.get_item_modified(resref)
                if resref not in existing:
                    self._index_single_item(resref)
                    counts["added"] += 1
                elif existing[resref] != current_mtime:
                    self.update_item_index(resref)
                    counts["updated"] += 1
                else:
                    counts["unchanged"] += 1

        # Remove deleted files from index
        deleted = set(existing.keys()) - current_files
        for resref in deleted:
            self._delete_item_from_index(resref)
            counts["deleted"] += 1

        print(f"    Items: {counts['added']} added, {counts['updated']} updated, {counts['deleted']} deleted, {counts['unchanged']} unchanged", flush=True)
        return counts

    def _smart_reindex_creatures(self, progress_callback=None,
                                  collect_item_refs: bool = False) -> tuple:
        """Incrementally reindex creatures based on modification times or content hashes.

        Args:
            progress_callback: Optional function(message: str) to report progress.
            collect_item_refs: If True, also collect item reference tuples
                from added/updated creatures.

        Returns:
            (counts_dict, item_refs) where item_refs is a list of tuples
            from added/updated creatures if collect_item_refs is True,
            otherwise an empty list.
        """
        counts = {"added": 0, "updated": 0, "deleted": 0, "unchanged": 0}
        item_refs = []

        backend = self.gff.backend
        is_mod_mode = hasattr(backend, 'get_mode') and backend.get_mode() == "mod_file"

        existing = {}
        with self._get_connection() as conn:
            if is_mod_mode:
                cursor = conn.execute("SELECT resref, content_hash FROM creatures")
                for row in cursor.fetchall():
                    existing[row["resref"]] = row["content_hash"]
            else:
                cursor = conn.execute("SELECT resref, file_modified FROM creatures")
                for row in cursor.fetchall():
                    existing[row["resref"]] = row["file_modified"]

        current_hashes = {}
        if is_mod_mode and hasattr(backend, '_erf') and backend._erf is not None:
            from .erf_parser import restype_from_extension
            restype = restype_from_extension("utc")
            current_hashes = backend._erf.bulk_hash_by_type(restype)

        current_files = set()
        resref_list = self.gff.list_creature_resrefs()
        total_files = len(resref_list)
        print(f"    Found {total_files} creature files to check", flush=True)
        if progress_callback:
            progress_callback(f"Scanning {total_files} creatures...")

        for idx, resref in enumerate(resref_list):
            if idx > 0 and idx % 500 == 0:
                msg = f"Creatures: {idx}/{total_files}"
                print(f"    Processed {msg}...", flush=True)
                if progress_callback:
                    progress_callback(msg)

            current_files.add(resref)

            if is_mod_mode:
                current_val = current_hashes.get(resref)
                if current_val is None and hasattr(backend, 'get_resource_hash'):
                    current_val = backend.get_resource_hash(resref, "utc")
                stored_val = existing.get(resref)
                if resref not in existing:
                    self._index_single_creature(resref, content_hash=current_val)
                    if collect_item_refs:
                        data = self.gff.get_creature(resref)
                        if data:
                            item_refs.extend(self._extract_creature_item_refs(resref, data))
                    counts["added"] += 1
                elif stored_val is None or stored_val != current_val:
                    self._index_single_creature(resref, content_hash=current_val)
                    if collect_item_refs:
                        data = self.gff.get_creature(resref)
                        if data:
                            item_refs.extend(self._extract_creature_item_refs(resref, data))
                    counts["updated"] += 1
                else:
                    counts["unchanged"] += 1
            else:
                current_mtime = self.gff.get_creature_modified(resref)
                if resref not in existing:
                    self._index_single_creature(resref)
                    if collect_item_refs:
                        data = self.gff.get_creature(resref)
                        if data:
                            item_refs.extend(self._extract_creature_item_refs(resref, data))
                    counts["added"] += 1
                elif existing[resref] != current_mtime:
                    self._index_single_creature(resref)
                    if collect_item_refs:
                        data = self.gff.get_creature(resref)
                        if data:
                            item_refs.extend(self._extract_creature_item_refs(resref, data))
                    counts["updated"] += 1
                else:
                    counts["unchanged"] += 1

        deleted = set(existing.keys()) - current_files
        for resref in deleted:
            self._delete_creature_from_index(resref)
            counts["deleted"] += 1

        print(f"    Creatures: {counts['added']} added, {counts['updated']} updated, {counts['deleted']} deleted, {counts['unchanged']} unchanged", flush=True)
        return (counts, item_refs) if collect_item_refs else counts

    def _smart_reindex_stores(self, progress_callback=None,
                               collect_item_refs: bool = False) -> tuple:
        """Incrementally reindex stores based on modification times or content hashes.

        Args:
            progress_callback: Optional function(message: str) to report progress.
            collect_item_refs: If True, also collect item reference tuples
                from added/updated stores.

        Returns:
            (counts_dict, item_refs) where item_refs is a list of tuples
            from added/updated stores if collect_item_refs is True,
            otherwise an empty list.
        """
        counts = {"added": 0, "updated": 0, "deleted": 0, "unchanged": 0}
        item_refs = []

        backend = self.gff.backend
        is_mod_mode = hasattr(backend, 'get_mode') and backend.get_mode() == "mod_file"

        existing = {}
        with self._get_connection() as conn:
            if is_mod_mode:
                cursor = conn.execute("SELECT resref, content_hash FROM stores")
                for row in cursor.fetchall():
                    existing[row["resref"]] = row["content_hash"]
            else:
                cursor = conn.execute("SELECT resref, file_modified FROM stores")
                for row in cursor.fetchall():
                    existing[row["resref"]] = row["file_modified"]

        current_hashes = {}
        if is_mod_mode and hasattr(backend, '_erf') and backend._erf is not None:
            from .erf_parser import restype_from_extension
            restype = restype_from_extension("utm")
            current_hashes = backend._erf.bulk_hash_by_type(restype)

        current_files = set()
        resref_list = self.gff.list_store_resrefs()
        total_files = len(resref_list)
        print(f"    Found {total_files} store files to check", flush=True)
        if progress_callback:
            progress_callback(f"Scanning {total_files} stores...")

        for idx, resref in enumerate(resref_list):
            if idx > 0 and idx % 100 == 0:
                msg = f"Stores: {idx}/{total_files}"
                print(f"    Processed {msg}...", flush=True)
                if progress_callback:
                    progress_callback(msg)

            current_files.add(resref)

            if is_mod_mode:
                current_val = current_hashes.get(resref)
                if current_val is None and hasattr(backend, 'get_resource_hash'):
                    current_val = backend.get_resource_hash(resref, "utm")
                stored_val = existing.get(resref)
                if resref not in existing:
                    self._index_single_store(resref, content_hash=current_val)
                    if collect_item_refs:
                        data = self.gff.get_store(resref)
                        if data:
                            item_refs.extend(self._extract_store_item_refs(resref, data))
                    counts["added"] += 1
                elif stored_val is None or stored_val != current_val:
                    self._index_single_store(resref, content_hash=current_val)
                    if collect_item_refs:
                        data = self.gff.get_store(resref)
                        if data:
                            item_refs.extend(self._extract_store_item_refs(resref, data))
                    counts["updated"] += 1
                else:
                    counts["unchanged"] += 1
            else:
                current_mtime = self.gff.get_store_modified(resref)
                if resref not in existing:
                    self._index_single_store(resref)
                    if collect_item_refs:
                        data = self.gff.get_store(resref)
                        if data:
                            item_refs.extend(self._extract_store_item_refs(resref, data))
                    counts["added"] += 1
                elif existing[resref] != current_mtime:
                    self._index_single_store(resref)
                    if collect_item_refs:
                        data = self.gff.get_store(resref)
                        if data:
                            item_refs.extend(self._extract_store_item_refs(resref, data))
                    counts["updated"] += 1
                else:
                    counts["unchanged"] += 1

        deleted = set(existing.keys()) - current_files
        for resref in deleted:
            self._delete_store_from_index(resref)
            counts["deleted"] += 1

        print(f"    Stores: {counts['added']} added, {counts['updated']} updated, {counts['deleted']} deleted, {counts['unchanged']} unchanged", flush=True)
        return (counts, item_refs) if collect_item_refs else counts

    def _smart_reindex_areas(self, progress_callback=None,
                              collect_item_refs: bool = False) -> tuple:
        """Incrementally reindex areas based on modification times or content hashes.

        Args:
            progress_callback: Optional function(message: str) to report progress.
            collect_item_refs: If True, also collect item reference tuples
                from added/updated area store instances.

        Returns:
            (counts_dict, item_refs) where item_refs is a list of tuples
            from added/updated areas if collect_item_refs is True,
            otherwise an empty list.
        """
        counts = {"added": 0, "updated": 0, "deleted": 0, "unchanged": 0}
        item_refs = []

        backend = self.gff.backend
        is_mod_mode = hasattr(backend, 'get_mode') and backend.get_mode() == "mod_file"

        existing = {}
        with self._get_connection() as conn:
            if is_mod_mode:
                cursor = conn.execute("SELECT resref, content_hash FROM areas")
                for row in cursor.fetchall():
                    existing[row["resref"]] = row["content_hash"]
            else:
                cursor = conn.execute("SELECT resref, file_modified FROM areas")
                for row in cursor.fetchall():
                    existing[row["resref"]] = row["file_modified"]

        current_hashes = {}
        if is_mod_mode and hasattr(backend, '_erf') and backend._erf is not None:
            from .erf_parser import restype_from_extension
            restype = restype_from_extension("git")
            current_hashes = backend._erf.bulk_hash_by_type(restype)

        current_files = set()
        resref_list = self.gff.list_area_git_resrefs()
        total_files = len(resref_list)
        print(f"    Found {total_files} area files to check", flush=True)
        if progress_callback:
            progress_callback(f"Scanning {total_files} areas...")

        for idx, resref in enumerate(resref_list):
            if idx > 0 and idx % 50 == 0:
                msg = f"Areas: {idx}/{total_files}"
                print(f"    Processed {msg}...", flush=True)
                if progress_callback:
                    progress_callback(msg)

            current_files.add(resref)

            if is_mod_mode:
                current_val = current_hashes.get(resref)
                if current_val is None and hasattr(backend, 'get_resource_hash'):
                    current_val = backend.get_resource_hash(resref, "git")
                stored_val = existing.get(resref)
                if resref not in existing:
                    self._index_single_area(resref, content_hash=current_val)
                    if collect_item_refs:
                        git_data = self.gff.get_area_git(resref)
                        if git_data:
                            item_refs.extend(self._extract_area_item_refs(resref, git_data))
                    counts["added"] += 1
                elif stored_val is None or stored_val != current_val:
                    self._index_single_area(resref, content_hash=current_val)
                    if collect_item_refs:
                        git_data = self.gff.get_area_git(resref)
                        if git_data:
                            item_refs.extend(self._extract_area_item_refs(resref, git_data))
                    counts["updated"] += 1
                else:
                    counts["unchanged"] += 1
            else:
                current_mtime = self.gff.get_area_modified(resref)
                if resref not in existing:
                    self._index_single_area(resref)
                    if collect_item_refs:
                        git_data = self.gff.get_area_git(resref)
                        if git_data:
                            item_refs.extend(self._extract_area_item_refs(resref, git_data))
                    counts["added"] += 1
                elif existing[resref] != current_mtime:
                    self._index_single_area(resref)
                    if collect_item_refs:
                        git_data = self.gff.get_area_git(resref)
                        if git_data:
                            item_refs.extend(self._extract_area_item_refs(resref, git_data))
                    counts["updated"] += 1
                else:
                    counts["unchanged"] += 1

        deleted = set(existing.keys()) - current_files
        for resref in deleted:
            self._delete_area_from_index(resref)
            counts["deleted"] += 1

        print(f"    Areas: {counts['added']} added, {counts['updated']} updated, {counts['deleted']} deleted, {counts['unchanged']} unchanged", flush=True)
        return (counts, item_refs) if collect_item_refs else counts

    def _index_single_item(self, resref: str, content_hash: Optional[str] = None):
        """Index a single item."""
        data = self.gff.get_item(resref)
        if not data:
            return

        name = ""
        if self.tlk:
            loc_data = data.get("LocalizedName")
            name = self.tlk.resolve_localized_name(loc_data)
        if not name:
            name = GFFService.extract_locstring(data, "LocalizedName")

        base_item = GFFService.extract_value(data, "BaseItem", 0)
        cost = GFFService.extract_value(data, "Cost", 0)
        stack_size = GFFService.extract_value(data, "StackSize", 1)
        identified = GFFService.extract_value(data, "Identified", 1)
        modified = self.gff.get_item_modified(resref)

        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO items
                (resref, name, base_item, cost, stack_size, identified, file_modified, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (resref, name, base_item, cost, stack_size, identified, modified, content_hash))

            conn.execute("DELETE FROM items_fts WHERE resref = ?", (resref,))
            conn.execute(
                "INSERT INTO items_fts (resref, name) VALUES (?, ?)",
                (resref, name)
            )

    def _index_single_creature(self, resref: str, content_hash: Optional[str] = None):
        """Index a single creature."""
        data = self.gff.get_creature(resref)
        if not data:
            return

        first_name = GFFService.extract_locstring(data, "FirstName")
        last_name = GFFService.extract_locstring(data, "LastName")
        race = GFFService.extract_value(data, "Race", 0)
        appearance = GFFService.extract_value(data, "Appearance_Type", 0)

        equip_list = GFFService.extract_list(data, "Equip_ItemList")
        inv_list = GFFService.extract_list(data, "ItemList")
        equipment_count = len(equip_list)
        inventory_count = len(inv_list)

        modified = self.gff.get_creature_modified(resref)

        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO creatures
                (resref, first_name, last_name, race, appearance,
                 equipment_count, inventory_count, file_modified, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (resref, first_name, last_name, race, appearance,
                  equipment_count, inventory_count, modified, content_hash))

            conn.execute("DELETE FROM creatures_fts WHERE resref = ?", (resref,))
            conn.execute("""
                INSERT INTO creatures_fts (resref, first_name, last_name)
                VALUES (?, ?, ?)
            """, (resref, first_name, last_name))

    def _index_single_store(self, resref: str, content_hash: Optional[str] = None):
        """Index a single store."""
        data = self.gff.get_store(resref)
        if not data:
            return

        name = GFFService.extract_locstring(data, "LocName")
        markup = GFFService.extract_value(data, "MarkUp", 100)
        markdown = GFFService.extract_value(data, "MarkDown", 100)
        max_buy = GFFService.extract_value(data, "MaxBuyPrice", -1)
        gold = GFFService.extract_value(data, "StoreGold", -1)

        item_count = 0
        store_list = GFFService.extract_list(data, "StoreList")
        for category_entry in store_list:
            item_list = GFFService.extract_list(category_entry, "ItemList")
            item_count += len(item_list)

        modified = self.gff.get_store_modified(resref)

        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO stores
                (resref, name, markup, markdown, max_buy_price,
                 store_gold, item_count, file_modified, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (resref, name, markup, markdown, max_buy,
                  gold, item_count, modified, content_hash))

            conn.execute("DELETE FROM stores_fts WHERE resref = ?", (resref,))
            conn.execute("""
                INSERT INTO stores_fts (resref, name) VALUES (?, ?)
            """, (resref, name))

    def _index_single_area(self, resref: str, content_hash: Optional[str] = None):
        """Index a single area."""
        git_data = self.gff.get_area_git(resref)
        are_data = self.gff.get_area_are(resref)

        if not git_data:
            return

        name = ""
        if are_data:
            name = GFFService.extract_locstring(are_data, "Name")

        store_list = GFFService.extract_list(git_data, "StoreList")
        creature_list = GFFService.extract_list(git_data, "Creature List")

        modified = self.gff.get_area_modified(resref)

        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO areas
                (resref, name, store_count, creature_count, file_modified, content_hash)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (resref, name, len(store_list), len(creature_list), modified, content_hash))

            conn.execute("DELETE FROM areas_fts WHERE resref = ?", (resref,))
            conn.execute("""
                INSERT INTO areas_fts (resref, name) VALUES (?, ?)
            """, (resref, name))

    def _delete_item_from_index(self, resref: str):
        """Remove an item from the index."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM items WHERE resref = ?", (resref,))
            conn.execute("DELETE FROM items_fts WHERE resref = ?", (resref,))

    def _delete_creature_from_index(self, resref: str):
        """Remove a creature from the index."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM creatures WHERE resref = ?", (resref,))
            conn.execute("DELETE FROM creatures_fts WHERE resref = ?", (resref,))

    def _delete_store_from_index(self, resref: str):
        """Remove a store from the index."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM stores WHERE resref = ?", (resref,))
            conn.execute("DELETE FROM stores_fts WHERE resref = ?", (resref,))

    def _delete_area_from_index(self, resref: str):
        """Remove an area from the index."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM areas WHERE resref = ?", (resref,))
            conn.execute("DELETE FROM areas_fts WHERE resref = ?", (resref,))

    def _reindex_items(self) -> int:
        """Reindex all items."""
        resrefs = self.gff.list_item_resrefs()
        count = 0

        # Pre-compute hashes in MOD mode for storage
        bulk_hashes = {}
        backend = self.gff.backend
        is_mod_mode = hasattr(backend, 'get_mode') and backend.get_mode() == "mod_file"
        if is_mod_mode and hasattr(backend, '_erf') and backend._erf is not None:
            from .erf_parser import restype_from_extension
            bulk_hashes = backend._erf.bulk_hash_by_type(restype_from_extension("uti"))

        with self._get_connection() as conn:
            # Clear existing
            conn.execute("DELETE FROM items")
            conn.execute("DELETE FROM items_fts")

            for resref in resrefs:
                data = self.gff.get_item(resref)
                if not data:
                    continue

                # Try TLK resolution first, then fall back to embedded text
                name = ""
                if self.tlk:
                    loc_data = data.get("LocalizedName")
                    name = self.tlk.resolve_localized_name(loc_data)
                if not name:
                    name = GFFService.extract_locstring(data, "LocalizedName")

                base_item = GFFService.extract_value(data, "BaseItem", 0)
                cost = GFFService.extract_value(data, "Cost", 0)
                stack_size = GFFService.extract_value(data, "StackSize", 1)
                identified = GFFService.extract_value(data, "Identified", 1)
                modified = self.gff.get_item_modified(resref)
                content_hash = bulk_hashes.get(resref) if is_mod_mode else None

                conn.execute("""
                    INSERT OR REPLACE INTO items
                    (resref, name, base_item, cost, stack_size, identified, file_modified, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (resref, name, base_item, cost, stack_size, identified, modified, content_hash))

                conn.execute("""
                    INSERT INTO items_fts (resref, name) VALUES (?, ?)
                """, (resref, name))

                count += 1

        return count

    def _reindex_creatures(self, collect_item_refs: bool = False) -> tuple:
        """Reindex all creatures.

        Args:
            collect_item_refs: If True, also extract item reference tuples
                from creature inventories and equipment.

        Returns:
            (count, item_refs) where item_refs is a list of tuples if
            collect_item_refs is True, otherwise an empty list.
        """
        resrefs = self.gff.list_creature_resrefs()
        count = 0
        item_refs = []

        bulk_hashes = {}
        backend = self.gff.backend
        is_mod_mode = hasattr(backend, 'get_mode') and backend.get_mode() == "mod_file"
        if is_mod_mode and hasattr(backend, '_erf') and backend._erf is not None:
            from .erf_parser import restype_from_extension
            bulk_hashes = backend._erf.bulk_hash_by_type(restype_from_extension("utc"))

        with self._get_connection() as conn:
            conn.execute("DELETE FROM creatures")
            conn.execute("DELETE FROM creatures_fts")

            for resref in resrefs:
                data = self.gff.get_creature(resref)
                if not data:
                    continue

                first_name = GFFService.extract_locstring(data, "FirstName")
                last_name = GFFService.extract_locstring(data, "LastName")
                race = GFFService.extract_value(data, "Race", 0)
                appearance = GFFService.extract_value(data, "Appearance_Type", 0)

                # Count equipment and inventory
                equip_list = GFFService.extract_list(data, "Equip_ItemList")
                inv_list = GFFService.extract_list(data, "ItemList")
                equipment_count = len(equip_list)
                inventory_count = len(inv_list)

                modified = self.gff.get_creature_modified(resref)
                content_hash = bulk_hashes.get(resref) if is_mod_mode else None

                conn.execute("""
                    INSERT OR REPLACE INTO creatures
                    (resref, first_name, last_name, race, appearance,
                     equipment_count, inventory_count, file_modified, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (resref, first_name, last_name, race, appearance,
                      equipment_count, inventory_count, modified, content_hash))

                conn.execute("""
                    INSERT INTO creatures_fts (resref, first_name, last_name)
                    VALUES (?, ?, ?)
                """, (resref, first_name, last_name))

                # Collect item references from this creature
                if collect_item_refs:
                    item_refs.extend(
                        self._extract_creature_item_refs(resref, data)
                    )

                count += 1

        return count, item_refs

    def _reindex_stores(self, collect_item_refs: bool = False) -> tuple:
        """Reindex all stores.

        Args:
            collect_item_refs: If True, also extract item reference tuples
                from store inventories.

        Returns:
            (count, item_refs) where item_refs is a list of tuples if
            collect_item_refs is True, otherwise an empty list.
        """
        resrefs = self.gff.list_store_resrefs()
        count = 0
        item_refs = []

        bulk_hashes = {}
        backend = self.gff.backend
        is_mod_mode = hasattr(backend, 'get_mode') and backend.get_mode() == "mod_file"
        if is_mod_mode and hasattr(backend, '_erf') and backend._erf is not None:
            from .erf_parser import restype_from_extension
            bulk_hashes = backend._erf.bulk_hash_by_type(restype_from_extension("utm"))

        with self._get_connection() as conn:
            conn.execute("DELETE FROM stores")
            conn.execute("DELETE FROM stores_fts")

            for resref in resrefs:
                data = self.gff.get_store(resref)
                if not data:
                    continue

                name = GFFService.extract_locstring(data, "LocName")
                markup = GFFService.extract_value(data, "MarkUp", 100)
                markdown = GFFService.extract_value(data, "MarkDown", 100)
                max_buy = GFFService.extract_value(data, "MaxBuyPrice", -1)
                gold = GFFService.extract_value(data, "StoreGold", -1)

                # Count items across all categories
                # StoreList contains category entries, each with ItemList
                item_count = 0
                store_list = GFFService.extract_list(data, "StoreList")
                for category_entry in store_list:
                    item_list = GFFService.extract_list(category_entry, "ItemList")
                    item_count += len(item_list)

                modified = self.gff.get_store_modified(resref)
                content_hash = bulk_hashes.get(resref) if is_mod_mode else None

                conn.execute("""
                    INSERT OR REPLACE INTO stores
                    (resref, name, markup, markdown, max_buy_price,
                     store_gold, item_count, file_modified, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (resref, name, markup, markdown, max_buy,
                      gold, item_count, modified, content_hash))

                # Use LocName for FTS as well
                conn.execute("""
                    INSERT INTO stores_fts (resref, name) VALUES (?, ?)
                """, (resref, name))

                # Collect item references from this store
                if collect_item_refs:
                    item_refs.extend(
                        self._extract_store_item_refs(resref, data)
                    )

                count += 1

        return count, item_refs

    def _reindex_areas(self, collect_item_refs: bool = False) -> tuple:
        """Reindex all areas.

        Args:
            collect_item_refs: If True, also extract item reference tuples
                from area store instances.

        Returns:
            (count, item_refs) where item_refs is a list of tuples if
            collect_item_refs is True, otherwise an empty list.
        """
        resrefs = self.gff.list_area_git_resrefs()
        count = 0
        item_refs = []

        bulk_hashes = {}
        backend = self.gff.backend
        is_mod_mode = hasattr(backend, 'get_mode') and backend.get_mode() == "mod_file"
        if is_mod_mode and hasattr(backend, '_erf') and backend._erf is not None:
            from .erf_parser import restype_from_extension
            bulk_hashes = backend._erf.bulk_hash_by_type(restype_from_extension("git"))

        with self._get_connection() as conn:
            conn.execute("DELETE FROM areas")
            conn.execute("DELETE FROM areas_fts")

            for resref in resrefs:
                git_data = self.gff.get_area_git(resref)
                are_data = self.gff.get_area_are(resref)

                if not git_data:
                    continue

                # Get name from ARE file if available
                name = ""
                if are_data:
                    name = GFFService.extract_locstring(are_data, "Name")

                # Count instances
                store_list = GFFService.extract_list(git_data, "StoreList")
                creature_list = GFFService.extract_list(git_data, "Creature List")

                modified = self.gff.get_area_modified(resref)
                content_hash = bulk_hashes.get(resref) if is_mod_mode else None

                conn.execute("""
                    INSERT OR REPLACE INTO areas
                    (resref, name, store_count, creature_count, file_modified, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (resref, name, len(store_list), len(creature_list), modified, content_hash))

                conn.execute("""
                    INSERT INTO areas_fts (resref, name) VALUES (?, ?)
                """, (resref, name))

                # Collect item references from area store instances
                if collect_item_refs:
                    item_refs.extend(
                        self._extract_area_item_refs(resref, git_data)
                    )

                count += 1

        return count, item_refs

    # ===== Item Reference Extraction Helpers =====

    @staticmethod
    def _extract_creature_item_refs(creature_resref: str, data: dict) -> list:
        """Extract item reference tuples from a creature's inventory and equipment.

        Args:
            creature_resref: The creature's resref.
            data: The parsed creature GFF data.

        Returns:
            List of (item_resref, reference_type, source_resref, extra_data) tuples.
        """
        refs = []

        # Inventory items
        inv_list = GFFService.extract_list(data, "ItemList")
        for idx, inv_item in enumerate(inv_list):
            item_resref = GFFService.extract_value(inv_item, "TemplateResRef", "")
            if item_resref:
                extra_data = json.dumps({"index": idx})
                refs.append((item_resref, "creature_inventory", creature_resref, extra_data))

        # Equipment items
        equip_list = GFFService.extract_list(data, "Equip_ItemList")
        for equip_item in equip_list:
            slot_id = equip_item.get("__struct_id", 0)
            item_resref = GFFService.extract_value(equip_item, "EquippedRes", "")
            if not item_resref:
                item_resref = GFFService.extract_value(equip_item, "TemplateResRef", "")
            if item_resref:
                extra_data = json.dumps({"slot_id": slot_id})
                refs.append((item_resref, "creature_equipment", creature_resref, extra_data))

        return refs

    @staticmethod
    def _extract_store_item_refs(store_resref: str, data: dict) -> list:
        """Extract item reference tuples from a store's inventory.

        Args:
            store_resref: The store's resref.
            data: The parsed store GFF data.

        Returns:
            List of (item_resref, reference_type, source_resref, extra_data) tuples.
        """
        refs = []
        store_list = GFFService.extract_list(data, "StoreList")
        for cat_entry in store_list:
            cat_id = cat_entry.get("__struct_id", 0)
            item_list = GFFService.extract_list(cat_entry, "ItemList")
            for idx, store_item in enumerate(item_list):
                item_resref = GFFService.extract_value(store_item, "InventoryRes", "")
                if item_resref:
                    extra_data = json.dumps({"category_id": cat_id, "index": idx})
                    refs.append((item_resref, "store_template", store_resref, extra_data))
        return refs

    @staticmethod
    def _extract_area_item_refs(area_resref: str, git_data: dict) -> list:
        """Extract item reference tuples from area store instances.

        Args:
            area_resref: The area's resref.
            git_data: The parsed area GIT data.

        Returns:
            List of (item_resref, reference_type, source_resref, extra_data) tuples.
        """
        refs = []
        area_store_list = GFFService.extract_list(git_data, "StoreList")
        for store_idx, store_instance in enumerate(area_store_list):
            inner_store_list = GFFService.extract_list(store_instance, "StoreList")
            for cat_entry in inner_store_list:
                cat_id = cat_entry.get("__struct_id", 0)
                item_list = GFFService.extract_list(cat_entry, "ItemList")
                for item_idx, store_item in enumerate(item_list):
                    item_resref = GFFService.extract_value(store_item, "TemplateResRef", "")
                    if not item_resref:
                        item_resref = GFFService.extract_value(store_item, "InventoryRes", "")
                    if item_resref:
                        extra_data = json.dumps({
                            "store_index": store_idx,
                            "category_id": cat_id,
                            "item_index": item_idx
                        })
                        refs.append((item_resref, "area_store", area_resref, extra_data))
        return refs

    def _batch_insert_item_references(self, item_refs: list) -> int:
        """Batch insert item references into the database.

        Clears existing references and inserts all provided tuples using
        executemany() for efficiency.

        Args:
            item_refs: List of (item_resref, reference_type, source_resref, extra_data) tuples.

        Returns:
            Number of references inserted.
        """
        with self._get_connection() as conn:
            conn.execute("DELETE FROM item_references")
            if item_refs:
                conn.executemany("""
                    INSERT OR REPLACE INTO item_references
                    (item_resref, reference_type, source_resref, extra_data)
                    VALUES (?, ?, ?, ?)
                """, item_refs)
        return len(item_refs)

    def _reindex_item_references(self) -> int:
        """Reindex all item references across the module.

        Scans all creatures, stores, and areas to build an index of where
        each item is used. This is a standalone fallback for cases where only
        item references need rebuilding (e.g., from smart_reindex_all when
        containers changed). For full reindex, item references are collected
        inline during _reindex_creatures/stores/areas to avoid double-parsing.
        """
        all_refs = []

        # Collect creature inventory and equipment refs
        for creature_resref in self.gff.list_creature_resrefs():
            creature_data = self.gff.get_creature(creature_resref)
            if not creature_data:
                continue
            all_refs.extend(
                self._extract_creature_item_refs(creature_resref, creature_data)
            )

        # Collect store template item refs
        for store_resref in self.gff.list_store_resrefs():
            store_data = self.gff.get_store(store_resref)
            if not store_data:
                continue
            all_refs.extend(
                self._extract_store_item_refs(store_resref, store_data)
            )

        # Collect area store instance item refs
        for area_resref in self.gff.list_area_git_resrefs():
            git_data = self.gff.get_area_git(area_resref)
            if not git_data:
                continue
            all_refs.extend(
                self._extract_area_item_refs(area_resref, git_data)
            )

        return self._batch_insert_item_references(all_refs)

    def get_item_references(self, item_resref: str) -> Dict[str, List[dict]]:
        """Get all references to an item from the index.

        Args:
            item_resref: The item resref to look up

        Returns:
            Dict with reference lists by type
        """
        references = {
            "creature_inventory": [],
            "creature_equipment": [],
            "store_templates": [],
            "area_stores": [],
            "total_count": 0
        }

        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT reference_type, source_resref, extra_data
                FROM item_references
                WHERE item_resref = ?
            """, (item_resref,))

            for row in cursor.fetchall():
                ref_type = row["reference_type"]
                source = row["source_resref"]
                extra = json.loads(row["extra_data"]) if row["extra_data"] else {}

                if ref_type == "creature_inventory":
                    references["creature_inventory"].append({
                        "creature_resref": source,
                        "index": extra.get("index", 0)
                    })
                elif ref_type == "creature_equipment":
                    references["creature_equipment"].append({
                        "creature_resref": source,
                        "slot_id": extra.get("slot_id", 0)
                    })
                elif ref_type == "store_template":
                    references["store_templates"].append({
                        "store_resref": source,
                        "category_id": extra.get("category_id", 0),
                        "index": extra.get("index", 0)
                    })
                elif ref_type == "area_store":
                    references["area_stores"].append({
                        "area_resref": source,
                        "store_index": extra.get("store_index", 0),
                        "category_id": extra.get("category_id", 0),
                        "item_index": extra.get("item_index", 0)
                    })

                references["total_count"] += 1

        return references

    # ===== Query Methods =====

    def search_items(self, query: str, limit: int = 50) -> List[dict]:
        """Full-text search items."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT i.* FROM items i
                JOIN items_fts fts ON i.resref = fts.resref
                WHERE items_fts MATCH ?
                LIMIT ?
            """, (query, limit))
            return [dict(row) for row in cursor.fetchall()]

    def search_creatures(self, query: str, limit: int = 50) -> List[dict]:
        """Full-text search creatures."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT c.* FROM creatures c
                JOIN creatures_fts fts ON c.resref = fts.resref
                WHERE creatures_fts MATCH ?
                LIMIT ?
            """, (query, limit))
            return [dict(row) for row in cursor.fetchall()]

    def search_stores(self, query: str, limit: int = 50) -> List[dict]:
        """Full-text search stores."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT s.* FROM stores s
                JOIN stores_fts fts ON s.resref = fts.resref
                WHERE stores_fts MATCH ?
                LIMIT ?
            """, (query, limit))
            return [dict(row) for row in cursor.fetchall()]

    def search_areas(self, query: str, limit: int = 50) -> List[dict]:
        """Full-text search areas."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT a.* FROM areas a
                JOIN areas_fts fts ON a.resref = fts.resref
                WHERE areas_fts MATCH ?
                LIMIT ?
            """, (query, limit))
            return [dict(row) for row in cursor.fetchall()]

    def list_items(self, offset: int = 0, limit: int = 50,
                   base_item: Optional[int] = None,
                   min_cost: Optional[int] = None,
                   max_cost: Optional[int] = None) -> Tuple[List[dict], int]:
        """List items with pagination and filters."""
        with self._get_connection() as conn:
            # Build query with filters
            where_clauses = []
            params = []

            if base_item is not None:
                where_clauses.append("base_item = ?")
                params.append(base_item)
            if min_cost is not None:
                where_clauses.append("cost >= ?")
                params.append(min_cost)
            if max_cost is not None:
                where_clauses.append("cost <= ?")
                params.append(max_cost)

            where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

            # Get total count
            count_cursor = conn.execute(
                f"SELECT COUNT(*) FROM items{where_sql}", params
            )
            total = count_cursor.fetchone()[0]

            # Get page
            cursor = conn.execute(
                f"SELECT * FROM items{where_sql} ORDER BY name LIMIT ? OFFSET ?",
                params + [limit, offset]
            )
            items = [dict(row) for row in cursor.fetchall()]

            return items, total

    def list_creatures(self, offset: int = 0, limit: int = 50) -> Tuple[List[dict], int]:
        """List creatures with pagination."""
        with self._get_connection() as conn:
            count_cursor = conn.execute("SELECT COUNT(*) FROM creatures")
            total = count_cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT * FROM creatures ORDER BY first_name, last_name LIMIT ? OFFSET ?",
                (limit, offset)
            )
            creatures = [dict(row) for row in cursor.fetchall()]

            return creatures, total

    def list_stores(self, offset: int = 0, limit: int = 50) -> Tuple[List[dict], int]:
        """List stores with pagination."""
        with self._get_connection() as conn:
            count_cursor = conn.execute("SELECT COUNT(*) FROM stores")
            total = count_cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT * FROM stores ORDER BY name LIMIT ? OFFSET ?",
                (limit, offset)
            )
            stores = [dict(row) for row in cursor.fetchall()]

            return stores, total

    def list_areas(self, offset: int = 0, limit: int = 50) -> Tuple[List[dict], int]:
        """List areas with pagination."""
        with self._get_connection() as conn:
            count_cursor = conn.execute("SELECT COUNT(*) FROM areas")
            total = count_cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT * FROM areas ORDER BY name LIMIT ? OFFSET ?",
                (limit, offset)
            )
            areas = [dict(row) for row in cursor.fetchall()]

            return areas, total

    def get_item_by_resref(self, resref: str) -> Optional[dict]:
        """Get a single item from index."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM items WHERE resref = ?", (resref,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_counts(self) -> dict:
        """Get count of all indexed items."""
        with self._get_connection() as conn:
            counts = {}
            for table in ["items", "creatures", "stores", "areas"]:
                cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cursor.fetchone()[0]
            return counts

    def delete_item_index(self, resref: str):
        """Delete an item from the index by resref."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM items WHERE resref = ?", (resref,))
            conn.execute("DELETE FROM items_fts WHERE resref = ?", (resref,))

    def update_item_index(self, resref: str, content_hash: Optional[str] = None):
        """Update index for a single item.

        Only deletes from index if the file truly doesn't exist on disk.
        If the file exists but can't be read (e.g., in use), skips the update.
        """
        data = self.gff.get_item(resref)
        if not data:
            # Check if file truly doesn't exist vs. temporarily unreadable
            if not self.gff.item_exists(resref):
                # File is gone, remove from index
                self.delete_item_index(resref)
            else:
                # File exists but couldn't be read (in use, parse error, etc.)
                # Skip this update - don't delete from index
                print(f"Skipping index update for {resref}: file exists but couldn't be read")
            return

        # Try TLK resolution first, then fall back to embedded text
        name = ""
        if self.tlk:
            loc_data = data.get("LocalizedName")
            name = self.tlk.resolve_localized_name(loc_data)
        if not name:
            name = GFFService.extract_locstring(data, "LocalizedName")

        base_item = GFFService.extract_value(data, "BaseItem", 0)
        cost = GFFService.extract_value(data, "Cost", 0)
        stack_size = GFFService.extract_value(data, "StackSize", 1)
        identified = GFFService.extract_value(data, "Identified", 1)
        modified = self.gff.get_item_modified(resref)

        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO items
                (resref, name, base_item, cost, stack_size, identified, file_modified, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (resref, name, base_item, cost, stack_size, identified, modified, content_hash))

            conn.execute("DELETE FROM items_fts WHERE resref = ?", (resref,))
            conn.execute(
                "INSERT INTO items_fts (resref, name) VALUES (?, ?)",
                (resref, name)
            )

    def update_store_index(self, resref: str, content_hash: Optional[str] = None):
        """Update index for a single store.

        Only deletes from index if the store truly doesn't exist on disk.
        If the store exists but can't be read (e.g., in use), skips the update.
        """
        data = self.gff.get_store(resref)
        if not data:
            if not self.gff.store_exists(resref):
                self._delete_store_from_index(resref)
            else:
                print(f"Skipping store index update for {resref}: file exists but couldn't be read")
            return

        self._index_single_store(resref, content_hash)

    def update_creature_index(self, resref: str, content_hash: Optional[str] = None):
        """Update index for a single creature.

        Only deletes from index if the creature truly doesn't exist on disk.
        If the creature exists but can't be read (e.g., in use), skips the update.
        """
        data = self.gff.get_creature(resref)
        if not data:
            if not self.gff.creature_exists(resref):
                self._delete_creature_from_index(resref)
            else:
                print(f"Skipping creature index update for {resref}: file exists but couldn't be read")
            return

        self._index_single_creature(resref, content_hash)

    def update_area_index(self, resref: str, content_hash: Optional[str] = None):
        """Update index for a single area.

        Only deletes from index if the area truly doesn't exist on disk.
        """
        git_data = self.gff.get_area_git(resref)
        if not git_data:
            self._delete_area_from_index(resref)
            return

        self._index_single_area(resref, content_hash)
