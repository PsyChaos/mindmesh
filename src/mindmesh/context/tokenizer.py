"""Context size measurement and limit checking."""

from typing import Any

from pydantic import BaseModel, Field

from mindmesh.config import LimitsConfig
from mindmesh.context.collector import FileContext


class ContextSize(BaseModel):
    """Context size information."""

    total_bytes: int
    total_kb: float = Field(ge=0)
    file_sizes: list[tuple[str, float]] = []
    file_count: int

    def __init__(self, **data: Any) -> None:
        """Initialize ContextSize with rounding total_kb to 2 decimals."""
        super().__init__(**data)
        self.total_kb = round(self.total_kb, 2)


class ContextSizer:
    """Measures context size and checks against limits."""

    def measure_files(self, files: list[FileContext]) -> ContextSize:
        """Measure total size of files.

        Args:
            files: List of FileContext objects.

        Returns:
            ContextSize with total bytes, KB, and per-file breakdown.
        """
        total_bytes = 0
        file_sizes: list[tuple[str, float]] = []

        for file in files:
            byte_size = len(file.content.encode("utf-8"))
            total_bytes += byte_size
            kb_size = byte_size / 1024.0
            file_sizes.append((file.path, kb_size))

        # Sort by size descending
        file_sizes.sort(key=lambda x: x[1], reverse=True)

        total_kb = total_bytes / 1024.0

        return ContextSize(
            total_bytes=total_bytes,
            total_kb=total_kb,
            file_sizes=file_sizes,
            file_count=len(files),
        )

    def check_limits(
        self, size: ContextSize, limits: LimitsConfig
    ) -> list[str]:
        """Check if context exceeds limits.

        Args:
            size: ContextSize from measure_files().
            limits: LimitsConfig with maximum allowed sizes.

        Returns:
            List of warning messages. Empty if all limits respected.
        """
        warnings: list[str] = []

        if size.total_kb > limits.max_total_context_kb:
            warnings.append(
                f"Total context size {size.total_kb:.2f} KB exceeds limit "
                f"of {limits.max_total_context_kb} KB"
            )

        for path, kb in size.file_sizes:
            if kb > limits.max_file_size_kb:
                warnings.append(
                    f"File '{path}' size {kb:.2f} KB exceeds limit "
                    f"of {limits.max_file_size_kb} KB"
                )

        if size.file_count > limits.max_files:
            warnings.append(
                f"File count {size.file_count} exceeds limit of {limits.max_files}"
            )

        return warnings
