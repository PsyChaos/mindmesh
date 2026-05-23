"""Tests for context compressor — skeleton extraction."""

from __future__ import annotations

from mindmesh.context.collector import FileContext
from mindmesh.context.compressor import compress_file, compress_files


def _fc(content: str, language: str = "python") -> FileContext:
    return FileContext(
        path="test.py", content=content,
        language=language, scope_type="file",
    )


# --- Python compression ---


def test_python_function_extracted() -> None:
    source = 'def hello(name: str) -> str:\n    return f"Hello {name}"\n'
    result = compress_file(_fc(source))
    assert "def hello(name: str) -> str: ..." in result.content
    assert "return" not in result.content


def test_python_class_extracted() -> None:
    source = "class Foo(Bar):\n    def method(self) -> None:\n        pass\n"
    result = compress_file(_fc(source))
    assert "class Foo(Bar):" in result.content
    assert "def method(self) -> None: ..." in result.content
    assert "pass" not in result.content


def test_python_async_function() -> None:
    source = "async def fetch(url: str) -> str:\n    return await get(url)\n"
    result = compress_file(_fc(source))
    assert "async def fetch(url: str) -> str: ..." in result.content


def test_python_decorator_preserved() -> None:
    source = "@app.route('/api')\ndef handler() -> None:\n    pass\n"
    result = compress_file(_fc(source))
    assert "@app.route('/api')" in result.content
    assert "def handler() -> None: ..." in result.content


def test_python_empty_file() -> None:
    result = compress_file(_fc(""))
    assert result.content == ""


def test_python_syntax_error_falls_back() -> None:
    source = "def broken(\n"
    result = compress_file(_fc(source))
    assert "def broken(" in result.content


# --- Generic compression ---


def test_generic_function() -> None:
    source = "function hello(name) {\n  return name;\n}\n"
    result = compress_file(_fc(source, "javascript"))
    assert "function hello(name)" in result.content
    assert "return" not in result.content


def test_generic_class() -> None:
    source = "class Foo {\n  constructor() {}\n}\n"
    result = compress_file(_fc(source, "javascript"))
    assert "class Foo" in result.content


def test_generic_no_signatures_returns_truncated() -> None:
    source = "x = 1\ny = 2\nz = 3\n"
    result = compress_file(_fc(source, "text"))
    assert len(result.content) > 0


# --- Batch compression ---


def test_compress_files_batch() -> None:
    files = [
        _fc("def a(): pass\n"),
        _fc("def b(): pass\n"),
    ]
    results = compress_files(files)
    assert len(results) == 2
    assert "def a(): ..." in results[0].content
    assert "def b(): ..." in results[1].content


def test_compress_preserves_metadata() -> None:
    fc = FileContext(
        path="src/main.py", content="def main(): pass\n",
        language="python", scope_type="file",
    )
    result = compress_file(fc)
    assert result.path == "src/main.py"
    assert result.language == "python"
    assert result.scope_type == "file"
