import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir() -> Path:
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def duplicate_files(temp_dir: Path) -> list[Path]:
    """Create a set of duplicate files for testing."""
    content = b"test content for deduplication"
    files = []
    for i in range(3):
        f = temp_dir / f"file_{i}.txt"
        f.write_bytes(content)
        files.append(f)
    return files


@pytest.fixture
def unique_files(temp_dir: Path) -> list[Path]:
    """Create a set of unique files for testing."""
    files = []
    for i in range(3):
        f = temp_dir / f"unique_{i}.txt"
        f.write_bytes(f"unique content {i}".encode())
        files.append(f)
    return files
