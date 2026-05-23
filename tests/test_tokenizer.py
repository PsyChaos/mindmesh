"""Tests for context tokenizer."""


from mindmesh.config import LimitsConfig
from mindmesh.context.collector import FileContext
from mindmesh.context.tokenizer import ContextSize, ContextSizer


class TestContextSize:
    """Tests for ContextSize model."""

    def test_create_context_size(self):
        """Test creating ContextSize."""
        size = ContextSize(
            total_bytes=1024,
            total_kb=1.0,
            file_sizes=[("file.py", 0.5), ("file.js", 0.5)],
            file_count=2,
        )
        assert size.total_bytes == 1024
        assert size.total_kb == 1.0
        assert size.file_count == 2
        assert len(size.file_sizes) == 2

    def test_total_kb_rounded_to_two_decimals(self):
        """Test total_kb is rounded to 2 decimals."""
        size = ContextSize(
            total_bytes=1234,
            total_kb=1.234567,
            file_sizes=[],
            file_count=0,
        )
        assert size.total_kb == 1.23

    def test_context_size_empty(self):
        """Test ContextSize with no files."""
        size = ContextSize(
            total_bytes=0,
            total_kb=0.0,
            file_sizes=[],
            file_count=0,
        )
        assert size.total_bytes == 0
        assert size.total_kb == 0.0
        assert size.file_count == 0


class TestContextSizerMeasure:
    """Tests for ContextSizer.measure_files."""

    def test_single_file_measurement(self):
        """Test measuring single file."""
        sizer = ContextSizer()
        files = [
            FileContext(
                path="test.py",
                content="hello",
                language="python",
                scope_type="file",
            )
        ]
        size = sizer.measure_files(files)
        assert size.file_count == 1
        assert size.total_bytes == 5
        # total_kb is rounded to 2 decimals, so small files round to 0.0
        assert size.total_kb == 0.0  # 5/1024 = 0.00488... rounds to 0.0

    def test_multiple_files_measurement(self):
        """Test measuring multiple files."""
        sizer = ContextSizer()
        files = [
            FileContext(
                path="file1.py",
                content="a" * 100,
                language="python",
                scope_type="file",
            ),
            FileContext(
                path="file2.py",
                content="b" * 200,
                language="python",
                scope_type="file",
            ),
        ]
        size = sizer.measure_files(files)
        assert size.file_count == 2
        assert size.total_bytes == 300
        assert size.file_sizes[0][0] == "file2.py"  # 200 bytes first
        assert size.file_sizes[1][0] == "file1.py"  # 100 bytes second

    def test_utf8_multibyte_characters(self):
        """Test UTF-8 multibyte character byte counting."""
        sizer = ContextSizer()
        # Turkish characters: ş, ğ, ı, ö, ü take multiple bytes in UTF-8
        content = "şağlık"  # Each character takes 2 bytes in UTF-8
        files = [
            FileContext(
                path="turkish.py",
                content=content,
                language="python",
                scope_type="file",
            )
        ]
        size = sizer.measure_files(files)
        expected_bytes = len(content.encode("utf-8"))
        assert size.total_bytes == expected_bytes
        assert expected_bytes > len(content)  # Multibyte chars

    def test_empty_file(self):
        """Test measuring empty file."""
        sizer = ContextSizer()
        files = [
            FileContext(
                path="empty.py",
                content="",
                language="python",
                scope_type="file",
            )
        ]
        size = sizer.measure_files(files)
        assert size.total_bytes == 0
        assert size.total_kb == 0.0
        assert size.file_count == 1

    def test_file_sizes_sorted_descending(self):
        """Test file_sizes are sorted largest first."""
        sizer = ContextSizer()
        files = [
            FileContext(
                path="small.py",
                content="a" * 50,
                language="python",
                scope_type="file",
            ),
            FileContext(
                path="large.py",
                content="b" * 300,
                language="python",
                scope_type="file",
            ),
            FileContext(
                path="medium.py",
                content="c" * 150,
                language="python",
                scope_type="file",
            ),
        ]
        size = sizer.measure_files(files)
        assert size.file_sizes[0][0] == "large.py"
        assert size.file_sizes[1][0] == "medium.py"
        assert size.file_sizes[2][0] == "small.py"

    def test_file_sizes_kb_values(self):
        """Test file_sizes contains correct KB values."""
        sizer = ContextSizer()
        files = [
            FileContext(
                path="file.py",
                content="x" * 1024,
                language="python",
                scope_type="file",
            )
        ]
        size = sizer.measure_files(files)
        assert size.file_sizes[0][1] == 1.0


class TestContextSizerCheckLimits:
    """Tests for ContextSizer.check_limits."""

    def test_within_all_limits(self):
        """Test no warnings when within all limits."""
        sizer = ContextSizer()
        files = [
            FileContext(
                path="test.py",
                content="x" * 100,
                language="python",
                scope_type="file",
            )
        ]
        size = sizer.measure_files(files)
        limits = LimitsConfig(
            max_total_context_kb=1024,
            max_file_size_kb=100,
            max_files=10,
        )
        warnings = sizer.check_limits(size, limits)
        assert warnings == []

    def test_exceeds_total_context_limit(self):
        """Test warning when total context exceeds limit."""
        sizer = ContextSizer()
        files = [
            FileContext(
                path="large.py",
                content="x" * 2048,
                language="python",
                scope_type="file",
            )
        ]
        size = sizer.measure_files(files)
        limits = LimitsConfig(max_total_context_kb=1)
        warnings = sizer.check_limits(size, limits)
        assert len(warnings) == 1
        assert "Total context size" in warnings[0]
        assert "exceeds limit" in warnings[0]

    def test_exceeds_file_size_limit(self):
        """Test warning when single file exceeds limit."""
        sizer = ContextSizer()
        # Create file larger than 1 KB
        files = [
            FileContext(
                path="toolarge.py",
                content="x" * 2048,
                language="python",
                scope_type="file",
            )
        ]
        size = sizer.measure_files(files)
        limits = LimitsConfig(
            max_total_context_kb=1024,
            max_file_size_kb=1,  # 1 KB limit, file is 2 KB
            max_files=10,
        )
        warnings = sizer.check_limits(size, limits)
        assert len(warnings) == 1
        assert "toolarge.py" in warnings[0]
        assert "exceeds limit" in warnings[0]

    def test_exceeds_file_count_limit(self):
        """Test warning when file count exceeds limit."""
        sizer = ContextSizer()
        files = [
            FileContext(
                path=f"file{i}.py",
                content="x" * 10,
                language="python",
                scope_type="file",
            )
            for i in range(5)
        ]
        size = sizer.measure_files(files)
        limits = LimitsConfig(max_files=3)
        warnings = sizer.check_limits(size, limits)
        assert len(warnings) == 1
        assert "File count" in warnings[0]
        assert "exceeds limit" in warnings[0]

    def test_exceeds_multiple_limits(self):
        """Test warnings for multiple exceeded limits."""
        sizer = ContextSizer()
        files = [
            FileContext(
                path=f"file{i}.py",
                content="x" * 512,  # ~0.5 KB per file
                language="python",
                scope_type="file",
            )
            for i in range(5)  # 5 files = ~2.5 KB total
        ]
        size = sizer.measure_files(files)
        limits = LimitsConfig(
            max_total_context_kb=1,  # Total exceeds (2.5 > 1)
            max_file_size_kb=1,  # No individual file exceeds
            max_files=2,  # File count exceeds (5 > 2)
        )
        warnings = sizer.check_limits(size, limits)
        assert len(warnings) >= 2  # At least total and count

    def test_empty_files_list(self):
        """Test checking limits with no files."""
        sizer = ContextSizer()
        size = sizer.measure_files([])
        limits = LimitsConfig()
        warnings = sizer.check_limits(size, limits)
        assert warnings == []

    def test_file_size_limit_message_contains_filename(self):
        """Test file size warning includes the specific filename."""
        sizer = ContextSizer()
        files = [
            FileContext(
                path="specific_file.py",
                content="x" * 2048,  # 2 KB
                language="python",
                scope_type="file",
            )
        ]
        size = sizer.measure_files(files)
        limits = LimitsConfig(max_file_size_kb=1)  # 1 KB limit
        warnings = sizer.check_limits(size, limits)
        assert "specific_file.py" in warnings[0]

    def test_default_limits_applied(self):
        """Test with default LimitsConfig values."""
        sizer = ContextSizer()
        files = [
            FileContext(
                path="file.py",
                content="x" * 100,
                language="python",
                scope_type="file",
            )
        ]
        size = sizer.measure_files(files)
        limits = LimitsConfig()  # Default values
        warnings = sizer.check_limits(size, limits)
        # Default: max_files=50, max_file_size_kb=120, max_total_context_kb=1024
        assert warnings == []

    def test_large_file_multiple_violations(self):
        """Test file that violates both file size and total limits."""
        sizer = ContextSizer()
        files = [
            FileContext(
                path="huge.py",
                content="x" * 2000,
                language="python",
                scope_type="file",
            )
        ]
        size = sizer.measure_files(files)
        limits = LimitsConfig(
            max_total_context_kb=1,
            max_file_size_kb=1,
        )
        warnings = sizer.check_limits(size, limits)
        assert len(warnings) == 2  # Both total and file size


class TestIntegration:
    """Integration tests for ContextSizer."""

    def test_measure_and_check_workflow(self):
        """Test typical workflow: measure then check."""
        sizer = ContextSizer()
        files = [
            FileContext(
                path="auth.py",
                content="def login():\n    pass" * 10,
                language="python",
                scope_type="file",
            ),
            FileContext(
                path="db.py",
                content="class Database:\n    pass" * 5,
                language="python",
                scope_type="file",
            ),
        ]
        size = sizer.measure_files(files)
        limits = LimitsConfig(
            max_total_context_kb=100,
            max_file_size_kb=50,
            max_files=10,
        )
        warnings = sizer.check_limits(size, limits)
        assert isinstance(size, ContextSize)
        assert isinstance(warnings, list)
        assert size.file_count == 2

    def test_diff_scope_measurement(self):
        """Test measuring files with diff scope."""
        sizer = ContextSizer()
        files = [
            FileContext(
                path="main.py",
                content="+new line\n-old line",
                language="python",
                scope_type="diff",
                start_line=10,
                end_line=15,
            )
        ]
        size = sizer.measure_files(files)
        assert size.file_count == 1
        assert size.total_bytes > 0

    def test_mixed_scope_types(self):
        """Test measuring files with mixed scope types."""
        sizer = ContextSizer()
        files = [
            FileContext(
                path="file1.py",
                content="full content",
                language="python",
                scope_type="file",
            ),
            FileContext(
                path="file2.py",
                content="+modified\n-removed",
                language="python",
                scope_type="diff",
                start_line=5,
                end_line=10,
            ),
        ]
        size = sizer.measure_files(files)
        assert size.file_count == 2
        assert size.total_bytes > 0
