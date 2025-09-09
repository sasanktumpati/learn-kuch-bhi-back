"""Video file management utilities for organizing and serving generated videos."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


class VideoFileManager:
    """Manages video file organization and serving paths."""

    def __init__(self, base_videos_dir: str = "videos"):
        """Initialize with base directory for video storage."""
        self.base_dir = Path(base_videos_dir)
        self.serving_dir = self.base_dir / "serving"
        self.temp_dir = self.base_dir / "temp"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.base_dir.mkdir(exist_ok=True)
        self.serving_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)

    def generate_serving_path(
        self, user_id: int, title: str, original_extension: str = "mp4"
    ) -> Path:
        """Generate a clean serving path for a video."""

        user_dir = self.serving_dir / f"user_{user_id}"
        user_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_title = self._sanitize_filename(title)
        filename = f"{timestamp}_{clean_title}.{original_extension}"

        return user_dir / filename

    def move_video_to_serving(
        self, source_path: str | Path, user_id: int, title: str
    ) -> tuple[Path, dict]:
        """Move generated video to serving directory with metadata."""
        source_path = Path(source_path)

        if not source_path.exists():
            raise FileNotFoundError(f"Source video not found: {source_path}")

        serving_path = self.generate_serving_path(
            user_id, title, source_path.suffix[1:]
        )

        shutil.move(str(source_path), str(serving_path))

        metadata = self._get_file_metadata(serving_path)

        self._cleanup_source_directory(source_path.parent)

        return serving_path, metadata

    def copy_video_to_serving(
        self, source_path: str | Path, user_id: int, title: str
    ) -> tuple[Path, dict]:
        """Copy generated video to serving directory with metadata."""
        source_path = Path(source_path)

        if not source_path.exists():
            raise FileNotFoundError(f"Source video not found: {source_path}")

        serving_path = self.generate_serving_path(
            user_id, title, source_path.suffix[1:]
        )

        shutil.copy2(str(source_path), str(serving_path))

        metadata = self._get_file_metadata(serving_path)

        return serving_path, metadata

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe filesystem usage."""

        unsafe_chars = '<>:"/\\|?*'
        for char in unsafe_chars:
            filename = filename.replace(char, "_")

        filename = filename.strip(" .")[:50]

        filename = filename.replace(" ", "_")

        while "__" in filename:
            filename = filename.replace("__", "_")

        return filename or "untitled"

    def _get_file_metadata(self, file_path: Path) -> dict:
        """Get file metadata including size and duration."""
        metadata = {
            "file_size": file_path.stat().st_size,
            "duration": None,
            "created_at": datetime.fromtimestamp(file_path.stat().st_ctime),
            "modified_at": datetime.fromtimestamp(file_path.stat().st_mtime),
        }

        return metadata

    def _cleanup_source_directory(self, directory: Path) -> None:
        """Clean up empty source directory and its parents if empty."""
        try:
            if (
                directory.exists()
                and not any(directory.iterdir())
                and "generated_scenes" in str(directory)
            ):
                directory.rmdir()

                parent = directory.parent
                if (
                    parent.exists()
                    and not any(parent.iterdir())
                    and "generated_scenes" in str(parent)
                ):
                    parent.rmdir()
        except (OSError, PermissionError):
            pass

    def get_serving_url(self, serving_path: Path, base_url: str = "") -> str:
        """Generate public URL for serving video."""

        relative_path = serving_path.relative_to(self.serving_dir)
        return f"{base_url.rstrip('/')}/videos/{relative_path}"

    def cleanup_temp_files(self, max_age_hours: int = 24) -> int:
        """Clean up temporary files older than specified hours."""
        if not self.temp_dir.exists():
            return 0

        current_time = datetime.now().timestamp()
        max_age_seconds = max_age_hours * 3600
        cleaned_count = 0

        for item in self.temp_dir.rglob("*"):
            if item.is_file():
                file_age = current_time - item.stat().st_mtime
                if file_age > max_age_seconds:
                    try:
                        item.unlink()
                        cleaned_count += 1
                    except (OSError, PermissionError):
                        continue

        return cleaned_count


video_manager = VideoFileManager()
