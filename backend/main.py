"""FastAPI application entry point for Module Toolkit."""
import multiprocessing
import sys
import os
import logging
from pathlib import Path
from datetime import datetime

# CRITICAL: Must be called at the very start for PyInstaller on Windows
# This prevents infinite subprocess spawning in bundled executables
if __name__ == "__main__":
    multiprocessing.freeze_support()


def setup_logging():
    """Set up file logging for production mode diagnostics."""
    if getattr(sys, 'frozen', False):
        # In bundled mode, log to user's app data directory
        app_data = os.environ.get('APPDATA') or os.path.expanduser('~')
        log_dir = Path(app_data) / 'TDN Module Toolkit' / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        log_file = log_dir / f'backend-{timestamp}.log'
        
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        logging.info(f"=== Backend starting (frozen mode) ===")
        logging.info(f"Log file: {log_file}")
        logging.info(f"Executable: {sys.executable}")
        logging.info(f"Working directory: {os.getcwd()}")
    else:
        # Development mode - just use stdout
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )


# Set up logging before any other imports that might fail
setup_logging()
logger = logging.getLogger(__name__)

try:
    import asyncio
    from contextlib import asynccontextmanager
    from typing import AsyncGenerator

    from fastapi import FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse, JSONResponse
    from sse_starlette.sse import EventSourceResponse

    from services.gff_service import GFFService
    from services.json_directory_backend import JsonDirectoryBackend
    from services.mod_file_backend import ModFileBackend
    from services.indexer import Indexer
    from services.watcher import FileWatcher
    from services.inventory_ops import InventoryOperations
    from services.config_service import ConfigService
    from services.tlk_service import TLKService
    from services.tda_service import TDAService
    from services.palette_service import PaletteService

    from api import items as items_api
    from api import creatures as creatures_api
    from api import stores as stores_api
    from api import instances as instances_api
    from api import search as search_api
    from api import config as config_api
    
    logger.info("All imports successful")
except Exception as e:
    logger.exception(f"Failed to import modules: {e}")
    raise


def get_base_path() -> Path:
    """Get base path for resources (works in dev and PyInstaller bundled mode)."""
    if getattr(sys, 'frozen', False):
        # Running as bundled executable (PyInstaller)
        return Path(sys.executable).parent
    # Running in development
    return Path(__file__).parent


def get_app_data_path() -> Path:
    """Get the application data path for storing persistent files (config, database)."""
    if getattr(sys, 'frozen', False):
        # In bundled mode, use user's app data directory
        app_data = os.environ.get('APPDATA') or os.path.expanduser('~')
        app_path = Path(app_data) / 'TDN Module Toolkit'
        app_path.mkdir(parents=True, exist_ok=True)
        return app_path
    # In development, use the backend directory
    return get_base_path()


BASE_PATH = get_base_path()
logger.info(f"BASE_PATH: {BASE_PATH}")

# Path to pre-built frontend
if getattr(sys, 'frozen', False):
    # In bundled mode, frontend is alongside the executable
    FRONTEND_DIST = BASE_PATH.parent / "frontend" / "dist"
else:
    # In development
    FRONTEND_DIST = BASE_PATH.parent / "frontend" / "dist"
logger.info(f"FRONTEND_DIST: {FRONTEND_DIST}")

# Initialize config service first
logger.info("Initializing ConfigService...")
config_service = ConfigService()
logger.info(f"ConfigService initialized, configured={config_service.is_configured()}")

# Configuration - use config service if available, otherwise defaults
def get_module_path():
    config = config_service.get_config()
    if config.configured and config.module_path:
        return config.module_path
    return os.environ.get(
        "TDN_MODULE_PATH",
        r"D:\tdn\workspace\tdn_gff\module"
    )

DB_PATH = os.environ.get(
    "TDN_DB_PATH",
    str(get_app_data_path() / "inventory_index.db")
)

# Global services
gff_service: GFFService = None
current_backend = None  # GFFStorageBackend (JsonDirectoryBackend or ModFileBackend)
indexer: Indexer = None
file_watcher: FileWatcher = None
inventory_ops: InventoryOperations = None
tlk_service: TLKService = None
tda_service: TDAService = None
palette_service: PaletteService = None

# Event queue for SSE
event_queue: asyncio.Queue = None

# Application state: needs_configuration | initializing | indexing | ready | error
app_state: str = "needs_configuration"
app_error_message: str = None

# Indexing status (kept for backward compat)
is_indexing: bool = False
indexing_message: str = ""

# Flag to prevent concurrent reinitialize calls (atomic in single-threaded asyncio)
_reinitializing: bool = False


def on_file_change(event_type: str, file_type: str, resref: str):
    """Handle file change notifications."""
    print(f"File change: {event_type} {file_type} {resref}")

    # Update index for the changed resource type
    if file_type == "item":
        indexer.update_item_index(resref)
    elif file_type == "store":
        indexer.update_store_index(resref)
    elif file_type == "creature":
        indexer.update_creature_index(resref)
    elif file_type in ("area", "area_meta"):
        indexer.update_area_index(resref)

    # Queue event for SSE
    if event_queue:
        try:
            event_queue.put_nowait({
                "event": "file_change",
                "data": {
                    "type": event_type,
                    "file_type": file_type,
                    "resref": resref
                }
            })
        except asyncio.QueueFull:
            pass  # Drop event if queue is full


def _initialize_services():
    """Initialize all services from current config. Called during startup and reinitialize.

    Builds all services into local variables first, then assigns to globals
    atomically on success. This preserves old globals if init fails mid-way.

    Note: event_queue and file_watcher are NOT created here because
    asyncio.Queue must be created in the async context (not in a thread pool).
    The caller is responsible for creating those after this function returns.
    """
    global gff_service, current_backend, indexer, inventory_ops, tlk_service, tda_service, palette_service
    global is_indexing, indexing_message, app_state, app_error_message

    app_state = "initializing"
    is_indexing = True
    indexing_message = "Initializing services..."

    module_path = get_module_path()

    print(f"Module path: {module_path}", flush=True)
    print(f"Database path: {DB_PATH}", flush=True)

    # Initialize TLK service
    indexing_message = "Loading TLK files..."
    print("Loading TLK files...", flush=True)
    base_tlk_path = config_service.get_base_tlk_json_path()
    custom_tlk_path = config_service.get_custom_tlk_json_path()
    new_tlk_service = TLKService(base_tlk_path, custom_tlk_path)
    if base_tlk_path or custom_tlk_path:
        new_tlk_service.load_tlk_files()
        print(f"TLK service loaded: {new_tlk_service.get_entry_count()} entries", flush=True)

    # Initialize 2DA service
    indexing_message = "Loading 2DA files..."
    print("Loading 2DA files...", flush=True)
    baseitems_path = config_service.get_baseitems_2da_path()
    itemprops_path = config_service.get_itemprops_2da_path()
    racialtypes_path = config_service.get_racialtypes_2da_path()
    appearance_path = config_service.get_appearance_2da_path()
    tda_folder_path = config_service.get_tda_folder_path()

    new_tda_service = TDAService(
        baseitems_path=baseitems_path,
        itemprops_path=itemprops_path,
        racialtypes_path=racialtypes_path,
        appearance_path=appearance_path,
        tda_folder_path=tda_folder_path
    )

    load_results = new_tda_service.load_all()
    print(f"2DA service loaded: baseitems={load_results['baseitems']}, "
          f"itemprops={load_results['itemprops']}, racialtypes={load_results['racialtypes']}, "
          f"appearances={load_results['appearances']}, itempropdef={load_results['itempropdef']}", flush=True)

    # Initialize core services
    indexing_message = "Initializing core services..."
    print("Initializing core services...", flush=True)

    config = config_service.get_config()
    source_mode = config.source_mode

    if source_mode == "mod_file":
        print(f"Mode: mod_file ({config.mod_file_path})", flush=True)
        new_backend = ModFileBackend(config.mod_file_path)
        new_backend.load()
    else:
        print(f"Mode: json_directory ({module_path})", flush=True)
        new_backend = JsonDirectoryBackend(module_path)

    new_gff_service = GFFService(new_backend)
    new_indexer = Indexer(DB_PATH, new_gff_service, new_tlk_service)
    new_inventory_ops = InventoryOperations(new_gff_service, new_tda_service)
    new_palette_service = PaletteService(new_backend)
    print("Core services initialized", flush=True)

    # Initialize API modules
    print("Initializing API modules...", flush=True)
    items_api.init(new_gff_service, new_indexer, new_inventory_ops, new_tda_service, new_palette_service)
    creatures_api.init(new_gff_service, new_indexer, new_inventory_ops, new_tda_service)
    stores_api.init(new_gff_service, new_indexer, new_inventory_ops, new_tda_service)
    instances_api.init(new_gff_service, new_indexer, new_inventory_ops, new_tda_service, new_tlk_service)
    search_api.init(new_indexer)
    print("API modules initialized", flush=True)

    # Progress callback to update indexing_message for API status
    def update_indexing_progress(message: str):
        global indexing_message
        indexing_message = message

    # Index
    app_state = "indexing"
    indexing_message = "Syncing index..."
    print("Syncing index (incremental)...", flush=True)
    counts = new_indexer.smart_reindex_all(progress_callback=update_indexing_progress)
    print("Index sync complete:", flush=True)
    for entity_type, result in counts.items():
        if isinstance(result, dict):
            print(f"  {entity_type}: +{result['added']} added, ~{result['updated']} updated, -{result['deleted']} deleted, ={result['unchanged']} unchanged", flush=True)
        else:
            print(f"  {entity_type}: {result} references", flush=True)

    # Mark indexing as complete
    is_indexing = False
    indexing_message = ""

    # Atomic swap: only assign to globals after everything succeeds
    gff_service = new_gff_service
    current_backend = new_backend
    indexer = new_indexer
    inventory_ops = new_inventory_ops
    tlk_service = new_tlk_service
    tda_service = new_tda_service
    palette_service = new_palette_service

    app_state = "ready"
    app_error_message = None
    print("Services ready.", flush=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global app_state, app_error_message
    global is_indexing, indexing_message
    global event_queue, file_watcher

    logger.info("Lifespan handler starting...")

    # Flush output immediately for Electron to see progress
    # Note: reconfigure may fail in frozen mode, so wrap in try/except
    try:
        import sys
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)
    except Exception as e:
        logger.warning(f"Could not reconfigure stdout/stderr: {e}")

    logger.info(f"Starting TDN Module Toolkit...")
    logger.info(f"Configured: {config_service.is_configured()}")
    print(f"Starting TDN Module Toolkit...", flush=True)
    print(f"Configured: {config_service.is_configured()}", flush=True)

    # Always init the config API so config endpoints work
    logger.info("Initializing config API...")
    config_api.init(config_service)

    if config_service.is_configured():
        # Full startup with service initialization
        try:
            _initialize_services()
            # Create event queue and start file watcher in async context
            event_queue = asyncio.Queue(maxsize=100)
            config = config_service.get_config()
            if config.source_mode != "mod_file":
                file_watcher = FileWatcher(get_module_path(), on_file_change)
                file_watcher.start()
        except Exception as e:
            app_state = "error"
            app_error_message = str(e)
            is_indexing = False
            indexing_message = ""
            print(f"ERROR during initialization: {e}", flush=True)
    else:
        # Not configured yet - skip heavy initialization, start fast
        app_state = "needs_configuration"
        is_indexing = False
        indexing_message = ""
        print("Skipping service initialization (not configured).", flush=True)

    yield

    # Cleanup
    logger.info("Shutting down...")
    print("Shutting down...")
    if file_watcher:
        file_watcher.stop()
    if current_backend and hasattr(current_backend, 'close'):
        try:
            current_backend.close()
        except Exception as e:
            logger.warning(f"Error closing backend: {e}")


# Create FastAPI app
logger.info("Creating FastAPI app...")
app = FastAPI(
    title="TDN Module Toolkit",
    description="Inventory management tool for The Dragon's Neck module",
    version="1.0.0",
    lifespan=lifespan
)
logger.info("FastAPI app created")

# CORS middleware
logger.info("Adding CORS middleware...")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:8000", "http://127.0.0.1:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info("CORS middleware added")

@app.middleware("http")
async def service_guard_middleware(request: Request, call_next):
    """Return 503 for API endpoints that need services when they are not initialized."""
    path = request.url.path

    # Let non-API paths through (frontend, assets, docs)
    if not path.startswith("/api/"):
        return await call_next(request)

    # Exempt paths that work without services
    if path.startswith("/api/config") or path in ("/api/system/status", "/api/system/save", "/api/system/dirty"):
        return await call_next(request)

    # If services are not ready, return 503
    if gff_service is None or indexer is None:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Services not initialized. Please configure the application first.",
                "state": app_state
            }
        )

    return await call_next(request)


# Include routers
app.include_router(config_api.router)
app.include_router(items_api.router)
app.include_router(creatures_api.router)
app.include_router(stores_api.router)
app.include_router(instances_api.router)
app.include_router(search_api.router)

# Serve static assets (JS, CSS, images) from pre-built frontend
if FRONTEND_DIST.exists() and (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="static")


@app.get("/api/system/status")
async def get_status():
    """Get system status and index counts."""
    counts = indexer.get_counts() if indexer else {}
    config = config_service.get_config()
    mode = config.source_mode if config else "json_directory"
    dirty_count = 0
    if current_backend and hasattr(current_backend, 'dirty_count'):
        dirty_count = current_backend.dirty_count
    return {
        "status": "running",
        "state": app_state,
        "mode": mode,
        "module_path": get_module_path(),
        "file_watcher": file_watcher.is_running if file_watcher else False,
        "counts": counts,
        "configured": config_service.is_configured(),
        "indexing": is_indexing,
        "indexing_message": indexing_message,
        "error_message": app_error_message,
        "dirty_count": dirty_count
    }


@app.post("/api/config/reinitialize")
async def reinitialize():
    """Reinitialize all services after configuration change.

    Stops the file watcher, re-reads config, recreates all services,
    reindexes, and restarts the file watcher. Returns immediately while
    heavy work runs in the background.
    """
    global _reinitializing, app_state

    if _reinitializing:
        raise HTTPException(status_code=409, detail="Reinitialization already in progress")

    if not config_service.is_configured():
        raise HTTPException(status_code=400, detail="Application is not configured yet. Save config first.")

    # Force config service to re-read from disk
    config_service.reload_config()

    _reinitializing = True
    app_state = "initializing"

    async def _do_reinitialize():
        global file_watcher, event_queue, current_backend, app_state, app_error_message, _reinitializing
        try:
            # Stop existing file watcher
            if file_watcher:
                file_watcher.stop()
                file_watcher = None

            # Close old backend if it's a ModFileBackend
            if current_backend and hasattr(current_backend, 'close'):
                try:
                    current_backend.close()
                except Exception as e:
                    print(f"Warning: error closing old backend: {e}", flush=True)

            # Run heavy sync work in a thread to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _initialize_services)

            # Start file watcher only in json_directory mode
            event_queue = asyncio.Queue(maxsize=100)
            config = config_service.get_config()
            if config.source_mode != "mod_file":
                file_watcher = FileWatcher(get_module_path(), on_file_change)
                file_watcher.start()
        except Exception as e:
            app_state = "error"
            app_error_message = str(e)
            print(f"ERROR during reinitialization: {e}", flush=True)
        finally:
            _reinitializing = False

    asyncio.create_task(_do_reinitialize())

    return {"success": True, "message": "Reinitialization started"}


@app.get("/api/system/dirty")
async def get_dirty_status():
    """Get dirty/unsaved changes status for MOD file mode."""
    if current_backend and hasattr(current_backend, 'has_unsaved_changes'):
        return {
            "has_unsaved_changes": current_backend.has_unsaved_changes,
            "dirty_count": current_backend.dirty_count,
            "dirty_resources": current_backend.dirty_resources
        }
    return {
        "has_unsaved_changes": False,
        "dirty_count": 0,
        "dirty_resources": []
    }


@app.post("/api/system/save")
async def save_mod_file():
    """Save all pending changes to the .mod file (MOD mode only)."""
    if not current_backend or not hasattr(current_backend, 'save'):
        raise HTTPException(
            status_code=400,
            detail="Save is only available in MOD file mode"
        )
    if not current_backend.has_unsaved_changes:
        return {"success": True, "message": "No unsaved changes"}

    try:
        current_backend.save()
        return {"success": True, "message": "Changes saved to .mod file"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/system/reindex")
async def reindex(full: bool = False):
    """Reindex the module.

    Args:
        full: If True, forces a full rebuild. Otherwise uses incremental sync.
    """
    if full:
        counts = indexer.reindex_all()
        return {"success": True, "mode": "full", "counts": counts}
    else:
        counts = indexer.smart_reindex_all()
        return {"success": True, "mode": "incremental", "counts": counts}


@app.get("/api/system/events")
async def event_stream():
    """SSE endpoint for file change notifications."""
    async def generate() -> AsyncGenerator[dict, None]:
        while True:
            try:
                event = await asyncio.wait_for(
                    event_queue.get(),
                    timeout=30.0
                )
                yield {
                    "event": event["event"],
                    "data": str(event["data"])
                }
            except asyncio.TimeoutError:
                # Send keepalive
                yield {"event": "keepalive", "data": ""}

    return EventSourceResponse(generate())


# Root route - serve frontend
@app.get("/")
async def serve_root():
    """Serve the frontend application."""
    index_path = FRONTEND_DIST / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {
        "error": "Frontend not built. Run setup.bat first.",
        "api_docs": "http://127.0.0.1:8000/docs"
    }


# Catch-all for SPA routing (must be LAST)
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Catch-all route for SPA client-side routing."""
    # Don't catch API routes
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")

    # Serve index.html for all other routes (SPA handles routing)
    index_path = FRONTEND_DIST / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {
        "error": "Frontend not built. Run setup.bat first.",
        "api_docs": "http://127.0.0.1:8000/docs"
    }


if __name__ == "__main__":
    import uvicorn
    
    # Detect if running as a bundled PyInstaller executable
    is_frozen = getattr(sys, 'frozen', False)
    
    if is_frozen:
        # In frozen mode, pass the app object directly - module import won't work
        logger.info("Starting uvicorn in frozen mode (direct app reference)")
        logger.info(f"App object: {app}")
        logger.info(f"App lifespan: {app.router.lifespan_context}")
        try:
            uvicorn.run(
                app,  # Pass app object directly, not string
                host="127.0.0.1",
                port=8000,
                log_level="debug"  # More verbose logging
            )
        except Exception as e:
            logger.exception(f"Uvicorn failed: {e}")
            raise
    else:
        # Development mode - use string reference for hot reload support
        uvicorn.run(
            "main:app",
            host="127.0.0.1",
            port=8000,
            reload=True
        )
