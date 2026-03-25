import os
from pathlib import Path

import pytest

from duperemover._core import Deduplicator


class TestDeduplicatorInit:
    """Tests for Deduplicator initialization."""

    def test_default_initialization(self, temp_dir: Path) -> None:
        """Test Deduplicator with default parameters."""
        dedup = Deduplicator(directory=str(temp_dir))
        assert dedup.directory == str(temp_dir)
        assert dedup.hash_file == ".hashes.db"
        assert dedup.buffer_size == 65536
        assert dedup.replace_strategy == "hardlink"
        assert dedup.max_threads == 4
        assert dedup.dry_run is False
        assert dedup.use_bloom_filter is False

    def test_custom_initialization(self, temp_dir: Path) -> None:
        """Test Deduplicator with custom parameters."""
        dedup = Deduplicator(
            directory=str(temp_dir),
            hash_file=".custom_hashes.db",
            buffer_size=32768,
            hash_algorithm="sha256",
            replace_strategy="delete",
            max_threads=8,
            dry_run=True,
            exclude_patterns=["*.log", "*.tmp"],
            use_bloom_filter=True,
            use_reflink=True,
        )
        assert dedup.hash_file == ".custom_hashes.db"
        assert dedup.buffer_size == 32768
        assert dedup.hash_algorithm == "sha256"
        assert dedup.replace_strategy == "delete"
        assert dedup.max_threads == 8
        assert dedup.dry_run is True
        assert dedup.exclude_patterns == ["*.log", "*.tmp"]
        assert dedup.use_bloom_filter is True
        assert dedup.use_reflink is True

    def test_exclude_patterns_defaults(self, temp_dir: Path) -> None:
        """Test default exclusion patterns."""
        dedup = Deduplicator(directory=str(temp_dir))
        assert "*.tmp_duperemover" in dedup.exclude_patterns


class TestCountFiles:
    """Tests for count_files method."""

    def test_empty_directory(self, temp_dir: Path) -> None:
        """Test count on empty directory returns 0."""
        dedup = Deduplicator(directory=str(temp_dir))
        assert dedup.count_files(str(temp_dir)) == 0

    def test_files_in_directory(self, temp_dir: Path) -> None:
        """Test count with files present."""
        (temp_dir / "file1.txt").touch()
        (temp_dir / "file2.txt").touch()
        (temp_dir / "file3.txt").touch()
        dedup = Deduplicator(directory=str(temp_dir))
        assert dedup.count_files(str(temp_dir)) == 3

    def test_nested_directories(self, temp_dir: Path) -> None:
        """Test count with nested directories."""
        (temp_dir / "file1.txt").touch()
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        (subdir / "file2.txt").touch()
        dedup = Deduplicator(directory=str(temp_dir))
        assert dedup.count_files(str(temp_dir)) == 2


class TestIsExcluded:
    """Tests for is_excluded method."""

    def test_excluded_pattern(self, temp_dir: Path) -> None:
        """Test file matching exclusion pattern."""
        dedup = Deduplicator(
            directory=str(temp_dir), exclude_patterns=["*.tmp", "*.log"]
        )
        assert dedup.is_excluded("test.tmp") is True
        assert dedup.is_excluded("test.log") is True

    def test_not_excluded(self, temp_dir: Path) -> None:
        """Test file not matching exclusion pattern."""
        dedup = Deduplicator(
            directory=str(temp_dir), exclude_patterns=["*.tmp", "*.log"]
        )
        assert dedup.is_excluded("test.txt") is False
        assert dedup.is_excluded("test.py") is False


class TestGetFileHash:
    """Tests for get_file_hash method."""

    def test_hash_sha256(self, temp_dir: Path) -> None:
        """Test file hashing with sha256."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")
        dedup = Deduplicator(directory=str(temp_dir), hash_algorithm="sha256")
        file_hash = dedup.get_file_hash(str(test_file))
        assert file_hash is not None
        assert len(file_hash) == 64  # SHA256 hex digest length

    def test_hash_nonexistent_file(self, temp_dir: Path) -> None:
        """Test hashing nonexistent file returns None."""
        dedup = Deduplicator(directory=str(temp_dir))
        result = dedup.get_file_hash(str(temp_dir / "nonexistent.txt"))
        assert result is None

    def test_same_content_same_hash(self, temp_dir: Path) -> None:
        """Test identical content produces identical hash."""
        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"
        content = "identical content"
        file1.write_text(content)
        file2.write_text(content)
        dedup = Deduplicator(directory=str(temp_dir), hash_algorithm="sha256")
        hash1 = dedup.get_file_hash(str(file1))
        hash2 = dedup.get_file_hash(str(file2))
        assert hash1 == hash2


class TestAreSameFile:
    """Tests for are_same_file method."""

    def test_same_file(self, temp_dir: Path) -> None:
        """Test comparing a file to itself returns True."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")
        dedup = Deduplicator(directory=str(temp_dir))
        assert dedup.are_same_file(str(test_file), str(test_file)) is True

    def test_different_files(self, temp_dir: Path) -> None:
        """Test comparing different files returns False."""
        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"
        file1.write_text("content1")
        file2.write_text("content2")
        dedup = Deduplicator(directory=str(temp_dir))
        assert dedup.are_same_file(str(file1), str(file2)) is False


class TestCreateHardLink:
    """Tests for create_hard_link method."""

    def test_dry_run_no_link(self, temp_dir: Path) -> None:
        """Test dry run does not create hard link."""
        source = temp_dir / "source.txt"
        target = temp_dir / "target.txt"
        source.write_text("content")
        target.write_text("content")
        dedup = Deduplicator(directory=str(temp_dir), dry_run=True)
        dedup.create_hard_link(str(source), str(target))
        assert not os.path.exists(temp_dir / "target")

    def test_create_hard_link(self, temp_dir: Path) -> None:
        """Test creating hard link."""
        source = temp_dir / "source.txt"
        target = temp_dir / "target.txt"
        source.write_text("content")
        target.write_text("content")
        dedup = Deduplicator(directory=str(temp_dir), dry_run=False)
        dedup.create_hard_link(str(source), str(target))
        assert os.path.exists(str(target))
        assert os.stat(str(source)).st_ino == os.stat(str(target)).st_ino


class TestDeleteDuplicate:
    """Tests for delete_duplicate method."""

    def test_dry_run_no_delete(self, temp_dir: Path) -> None:
        """Test dry run does not delete file."""
        test_file = temp_dir / "duplicate.txt"
        test_file.write_text("content")
        dedup = Deduplicator(directory=str(temp_dir), dry_run=True)
        dedup.delete_duplicate(str(test_file))
        assert os.path.exists(str(test_file))

    def test_delete_file(self, temp_dir: Path) -> None:
        """Test deleting duplicate file."""
        test_file = temp_dir / "duplicate.txt"
        test_file.write_text("content")
        dedup = Deduplicator(directory=str(temp_dir), dry_run=False)
        dedup.delete_duplicate(str(test_file))
        assert not os.path.exists(str(test_file))


class TestRenameDuplicate:
    """Tests for rename_duplicate method."""

    def test_dry_run_no_rename(self, temp_dir: Path) -> None:
        """Test dry run does not rename file."""
        test_file = temp_dir / "duplicate.txt"
        test_file.write_text("content")
        dedup = Deduplicator(directory=str(temp_dir), dry_run=True)
        dedup.rename_duplicate(str(test_file))
        assert os.path.exists(str(test_file))
        assert not os.path.exists(str(test_file) + ".duplicate")

    def test_rename_file(self, temp_dir: Path) -> None:
        """Test renaming duplicate file."""
        test_file = temp_dir / "duplicate.txt"
        test_file.write_text("content")
        dedup = Deduplicator(directory=str(temp_dir), dry_run=False)
        dedup.rename_duplicate(str(test_file))
        assert not os.path.exists(str(test_file))
        assert os.path.exists(str(test_file) + ".duplicate")


class TestCreateReflink:
    """Tests for create_reflink method."""

    def test_dry_run_no_reflink(self, temp_dir: Path) -> None:
        """Test dry run does not create reflink."""
        source = temp_dir / "source.txt"
        target = temp_dir / "target.txt"
        source.write_text("content")
        target.write_text("content")
        dedup = Deduplicator(directory=str(temp_dir), dry_run=True, use_reflink=True)
        dedup.create_reflink(str(source), str(target))
        assert not os.path.islink(str(target))

    def test_reflink_not_available_falls_back_to_hardlink(self, temp_dir: Path) -> None:
        """Test reflink falls back to hardlink when not available."""
        source = temp_dir / "source.txt"
        target = temp_dir / "target.txt"
        source.write_text("content")
        target.write_text("content")
        dedup = Deduplicator(directory=str(temp_dir), dry_run=False, use_reflink=True)
        dedup.reflink_available = False
        dedup.create_reflink(str(source), str(target))
        assert os.stat(str(source)).st_ino == os.stat(str(target)).st_ino


class TestDeduplicate:
    """Tests for deduplicate method."""

    def test_empty_directory(self, temp_dir: Path) -> None:
        """Test deduplication on empty directory."""
        dedup = Deduplicator(directory=str(temp_dir))
        dedup.deduplicate()
        assert dedup.stats["total_files"] == 0

    def test_single_file(self, temp_dir: Path) -> None:
        """Test deduplication with single file."""
        (temp_dir / "single.txt").write_text("content")
        dedup = Deduplicator(directory=str(temp_dir))
        dedup.deduplicate()
        assert dedup.stats["total_files"] == 1
        assert dedup.stats["duplicates_found"] == 0


class TestAddFileHashDatabase:
    """Tests for add_file_hash_database method."""

    def test_add_hash(self, temp_dir: Path) -> None:
        """Test adding hash to database."""
        dedup = Deduplicator(
            directory=str(temp_dir), hash_file=str(temp_dir / ".hashes.db")
        )
        dedup.add_file_hash_database("abc123", str(temp_dir / "file.txt"))
        assert "abc123" in dedup.hashes

    def test_add_none_hash(self, temp_dir: Path) -> None:
        """Test adding None hash does not fail."""
        dedup = Deduplicator(
            directory=str(temp_dir), hash_file=str(temp_dir / ".hashes.db")
        )
        dedup.add_file_hash_database(None, str(temp_dir / "file.txt"))  # type: ignore


class TestPrintStats:
    """Tests for print_stats method."""

    def test_print_stats(self, temp_dir: Path, capsys: pytest.CaptureFixture) -> None:
        """Test printing statistics."""
        dedup = Deduplicator(directory=str(temp_dir))
        dedup.print_stats()
        captured = capsys.readouterr()
        assert "Deduplication Statistics" in captured.out
