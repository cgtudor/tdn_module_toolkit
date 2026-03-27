"""File system watcher for auto-reindexing."""
import asyncio
from pathlib import Path
from typing import Callable, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
import threading
import time


class GFFFileHandler(FileSystemEventHandler):
    """Handler for GFF JSON file changes."""

    def __init__(self, callback: Callable[[str, str, str], None]):
        """
        Args:
            callback: Function called with (event_type, file_type, resref)
        """
        self.callback = callback
        self._pending_events: Set[tuple] = set()
        self._lock = threading.Lock()
        self._debounce_timer = None

    def _get_file_info(self, path: str) -> tuple:
        """Extract file type and resref from path."""
        p = Path(path)
        name = p.name

        # Determine file type from extension
        if name.endswith('.uti.json'):
            return 'item', name[:-9]  # Remove .uti.json
        elif name.endswith('.utc.json'):
            return 'creature', name[:-9]
        elif name.endswith('.utm.json'):
            return 'store', name[:-9]
        elif name.endswith('.git.json'):
            return 'area', name[:-9]
        elif name.endswith('.are.json'):
            return 'area_meta', name[:-9]

        return None, None

    def _process_event(self, event: FileSystemEvent, event_type: str):
        """Process a file system event."""
        if event.is_directory:
            return

        file_type, resref = self._get_file_info(event.src_path)
        if file_type and resref:
            with self._lock:
                self._pending_events.add((event_type, file_type, resref))

            # Debounce: wait 500ms before processing
            if self._debounce_timer:
                self._debounce_timer.cancel()

            self._debounce_timer = threading.Timer(
                0.5, self._flush_events
            )
            self._debounce_timer.start()

    def _flush_events(self):
        """Process all pending events."""
        with self._lock:
            events = list(self._pending_events)
            self._pending_events.clear()

        for event_type, file_type, resref in events:
            try:
                self.callback(event_type, file_type, resref)
            except Exception as e:
                print(f"Error processing event: {e}")

    def on_created(self, event: FileSystemEvent):
        self._process_event(event, 'created')

    def on_modified(self, event: FileSystemEvent):
        self._process_event(event, 'modified')

    def on_deleted(self, event: FileSystemEvent):
        self._process_event(event, 'deleted')


class FileWatcher:
    """Watches module directory for file changes."""

    def __init__(self, module_path: str, on_change: Callable[[str, str, str], None]):
        """
        Args:
            module_path: Path to module directory
            on_change: Callback for file changes (event_type, file_type, resref)
        """
        self.module_path = Path(module_path)
        self.on_change = on_change
        self.observer = None
        self._running = False

    def start(self):
        """Start watching for file changes."""
        if self._running:
            return

        handler = GFFFileHandler(self.on_change)
        self.observer = Observer()

        # Watch each subdirectory
        for subdir in ['uti', 'utc', 'utm', 'git', 'are']:
            watch_path = self.module_path / subdir
            if watch_path.exists():
                self.observer.schedule(handler, str(watch_path), recursive=False)

        self.observer.start()
        self._running = True
        print(f"File watcher started for {self.module_path}")

    def stop(self):
        """Stop watching."""
        if self.observer and self._running:
            self.observer.stop()
            self.observer.join()
            self._running = False
            print("File watcher stopped")

    @property
    def is_running(self) -> bool:
        return self._running
