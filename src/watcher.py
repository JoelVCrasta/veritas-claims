from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver

logger = logging.getLogger("veritas.watcher")


class JsonFileHandler(FileSystemEventHandler):
    """Watches a directory for arriving JSON medical report files and triggers streaming ingestion."""

    def __init__(self, pipeline: Any) -> None:
        super().__init__()
        self.pipeline = pipeline
        self._processed_timestamps: Dict[str, float] = {}

    def on_created(self, event: Any) -> None:
        self._process_event(event.src_path)

    def on_modified(self, event: Any) -> None:
        self._process_event(event.src_path)

    def on_moved(self, event: Any) -> None:
        self._process_event(getattr(event, "dest_path", event.src_path))

    def _process_event(self, path_str: str) -> None:
        path = Path(path_str)
        if path.is_dir() or path.suffix.lower() != ".json":
            return
        if path.name.startswith(".") or path.name.endswith(".tmp"):
            return

        now = time.time()
        last_time = self._processed_timestamps.get(str(path), 0.0)
        if (now - last_time) < 1.0:
            return
        self._processed_timestamps[str(path)] = now

        time.sleep(0.05)
        try:
            logger.info(f"[STREAM EVENT] New JSON report detected: {path.name}")
            self.pipeline.process_file(path)
        except Exception as exc:
            logger.error(
                f"[STREAM EVENT] Error processing {path.name}: {exc}", exc_info=True
            )


class StreamingEngine:
    """Manages filesystem listener and per-file streaming ingestion."""

    def __init__(self, pipeline: Any, watch_dir: str | Path = "sample_data") -> None:
        self.pipeline = pipeline
        self.watch_dir = Path(watch_dir)
        self.observer: Optional[BaseObserver] = None
        self.is_active = False

    def start(self, process_existing: bool = True) -> None:
        """Start the background watchdog file listener."""
        self.watch_dir.mkdir(parents=True, exist_ok=True)

        if process_existing:
            already_audited = set()
            try:
                if hasattr(self.pipeline, "db") and hasattr(
                    self.pipeline.db, "get_audited_file_names"
                ):
                    already_audited = set(self.pipeline.db.get_audited_file_names())
            except Exception:
                pass

            existing_files = sorted(
                [
                    f
                    for f in self.watch_dir.iterdir()
                    if f.is_file() and f.suffix.lower() == ".json"
                ]
            )
            unaudited_files = [
                f
                for f in existing_files
                if not f.name.startswith(".") and f.name not in already_audited
            ]

            if unaudited_files:
                logger.info(
                    f"StreamingEngine found {len(unaudited_files)} unaudited file(s) in {self.watch_dir}"
                )
                for f in unaudited_files:
                    try:
                        self.pipeline.process_file(f)
                    except Exception as exc:
                        logger.error(f"Error processing unaudited file {f.name}: {exc}")
            else:
                logger.info(
                    f"StreamingEngine verified: all {len(existing_files)} file(s) in {self.watch_dir} are already audited. Skipping re-ingestion."
                )

        handler = JsonFileHandler(self.pipeline)
        self.observer = Observer()
        self.observer.schedule(handler, str(self.watch_dir), recursive=False)
        self.observer.daemon = True
        self.observer.start()
        self.is_active = True
        logger.info(
            f"StreamingEngine active. Watching '{self.watch_dir}' for real-time JSON report drops."
        )

    def stop(self) -> None:
        """Stop the background watchdog listener."""
        if self.observer and self.is_active:
            self.observer.stop()
            self.observer.join(timeout=2.0)
            self.is_active = False
            logger.info("StreamingEngine stopped.")

    def get_status(self) -> Dict[str, Any]:
        """Return live streaming engine health status."""
        return {
            "status": "STREAMING_ACTIVE" if self.is_active else "STOPPED",
            "watch_directory": str(self.watch_dir),
            "engine": "watchdog.inotify",
        }
