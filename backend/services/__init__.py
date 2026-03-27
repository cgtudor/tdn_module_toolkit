# Lazy imports to avoid loading optional dependencies
__all__ = ["GFFService", "Indexer", "FileWatcher", "InventoryOperations"]

def __getattr__(name):
    if name == "GFFService":
        from services.gff_service import GFFService
        return GFFService
    elif name == "Indexer":
        from services.indexer import Indexer
        return Indexer
    elif name == "FileWatcher":
        from services.watcher import FileWatcher
        return FileWatcher
    elif name == "InventoryOperations":
        from services.inventory_ops import InventoryOperations
        return InventoryOperations
    raise AttributeError(f"module 'services' has no attribute '{name}'")
