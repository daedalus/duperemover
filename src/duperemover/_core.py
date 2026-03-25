import argparse
import fnmatch
import hashlib
import logging
import os
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Any

import mmappickle
from pybloom_live import BloomFilter
from tqdm import tqdm

try:
    import xxhash
except ImportError:
    xxhash = None

try:
    import blake3
except ImportError:
    blake3 = None


logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

HASH_ALGORITHMS: dict[str, Any] = {
    "xxhash": None,
    "blake3": None,
    "sha256": hashlib.sha256(),
}

HashType = Any

if xxhash is not None:
    HASH_ALGORITHMS["xxhash"] = xxhash.xxh64()

if blake3 is not None:
    HASH_ALGORITHMS["blake3"] = blake3.blake3()


def _get_default_algorithm() -> str:
    """Determine the default hash algorithm based on availability."""
    if xxhash is not None:
        return "xxhash"
    if blake3 is not None:
        return "blake3"
    return "sha256"


DEFAULT_ALGORITHM = _get_default_algorithm()


class Deduplicator:
    """A utility class for identifying and handling duplicate files in a directory."""

    def __init__(
        self,
        directory: str,
        hash_file: str = ".hashes.db",
        buffer_size: int = 65536,
        hash_algorithm: str | None = None,
        replace_strategy: str = "hardlink",
        max_threads: int = 4,
        sync_interval: int = 100,
        progress: bool = False,
        dry_run: bool = False,
        exclude_patterns: list[str] | None = None,
        use_bloom_filter: bool = False,
    ) -> None:
        """Initialize the Deduplicator.

        Args:
            directory: Directory to scan for duplicates.
            hash_file: File to store hashes (default: .hashes.db).
            buffer_size: Buffer size for hashing (default: 65536).
            hash_algorithm: Hashing algorithm (default: xxhash if available).
            replace_strategy: Strategy for handling duplicates (hardlink, delete, rename).
            max_threads: Number of threads for processing (default: 4).
            sync_interval: Sync interval for hashes to disk (default: 100).
            progress: Show progress bar (default: False).
            dry_run: Simulate without making changes (default: False).
            exclude_patterns: List of exclusion patterns (default: ['*.tmp_duperemover']).
            use_bloom_filter: Use Bloom filter for faster lookups (default: False).
        """
        self.directory = directory.strip()
        self.hash_file = hash_file
        self.buffer_size = buffer_size
        self.hash_algorithm = hash_algorithm if hash_algorithm else DEFAULT_ALGORITHM
        self.replace_strategy = replace_strategy
        self.max_threads = max_threads
        self.sync_interval = sync_interval
        self.progress = progress
        self.dry_run = dry_run
        self.exclude_patterns = exclude_patterns or ["*.tmp_duperemover"]
        self.use_bloom_filter = use_bloom_filter

        self.hashes: mmappickle.mmapdict = self._mmap_hashes_file()
        self.bloom_filter: BloomFilter | None = None
        self.file_sizes: dict[int, str] = {}
        self.stats: dict[str, int | float] = {
            "total_files": 0,
            "duplicates_found": 0,
            "duplicates_removed": 0,
            "hard_links_created": 0,
            "space_saved": 0,
        }
        self.hashes_lock = Lock()
        self.file_sizes_lock = Lock()
        self.stats_lock = Lock()

        if self.use_bloom_filter:
            logging.info("Using Bloom filter to speed up duplicate checking.")
            self._load_bloom_filter()
        else:
            logging.info("Bloom filter is not enabled.")

    def count_files(self, directory: str) -> int:
        """Count the number of files in a given directory.

        Args:
            directory: Directory path to count files in.

        Returns:
            Total number of files in the directory tree.
        """
        file_count = 0
        for root, _, files in os.walk(directory):
            file_count += len(files)
        return file_count

    def _mmap_hashes_file(self) -> mmappickle.mmapdict:
        """Load or create the mmapdict for storing file hashes."""
        logging.info(f"Creating or loading hash file at {self.hash_file}")
        return mmappickle.mmapdict(self.hash_file)

    def _load_bloom_filter(self) -> None:
        """Preload the Bloom filter with all existing hashes."""
        logging.info("Initializing Bloom filter...")
        capacity = self.count_files(self.directory)
        self.bloom_filter = BloomFilter(capacity, error_rate=0.001)
        values = self.hashes.values()
        for file_hash in values():
            self.bloom_filter.add(file_hash)
        logging.info("Bloom filter loaded with existing hashes.")

    def get_file_hash(self, file_path: str) -> str | None:
        """Calculate file hash using the selected algorithm.

        Args:
            file_path: Path to the file to hash.

        Returns:
            Hex digest of the file hash, or None on error.
        """
        hash_function = HASH_ALGORITHMS.get(self.hash_algorithm)
        if not hash_function:
            logging.error(
                f"Unknown hash algorithm: {self.hash_algorithm}, defaulting to sha256."
            )
            hash_function = hashlib.sha256
        try:
            logging.debug(
                f"Calculating hash for file {file_path} using {self.hash_algorithm}..."
            )
            with open(file_path, "rb") as f:
                while chunk := f.read(self.buffer_size):
                    hash_function.update(chunk)  # type: ignore[union-attr]
        except OSError as e:
            logging.error(f"Error reading file {file_path}: {e}")
            logging.error(traceback.format_exc())
            return None
        hash_result = hash_function.hexdigest()  # type: ignore[union-attr]
        logging.debug(f"Hash for file {file_path}: {hash_result}")
        return hash_result  # type: ignore[no-any-return]

    def are_same_file(self, file1: str, file2: str) -> bool:
        """Check if two files are the same (same inode).

        Args:
            file1: First file path.
            file2: Second file path.

        Returns:
            True if files are the same, False otherwise.
        """
        try:
            result = os.path.samefile(file1, file2)
            logging.debug(
                f"Files {file1} and {file2} are {'the same' if result else 'different'}."
            )
            return result
        except OSError as e:
            logging.error(f"Error comparing files {file1} and {file2}: {e}")
            logging.error(traceback.format_exc())
            return False

    def create_hard_link(self, source: str, target: str) -> None:
        """Replace a duplicate file with a hard link.

        Args:
            source: Source file path (original).
            target: Target file path (duplicate to replace).
        """
        if self.dry_run:
            logging.info(f"Would create hard link: {target} -> {source}")
            return

        try:
            st_ino_source, st_ino_target = (
                os.stat(source).st_ino,
                os.stat(target).st_ino,
            )
            if st_ino_source == st_ino_target:
                logging.debug(
                    f"Skipping due Inodes: source: {os.stat(source).st_ino}, "
                    f"target: {os.stat(target).st_ino} are the same, already deduped!"
                )
                return

            target_size = os.path.getsize(target)
            logging.debug(
                f"Renaming {target} to {target}.tmp_duperemover before creating hard link."
            )
            logging.debug(
                f"Inodes before: source: {st_ino_source}, target: {st_ino_target}"
            )
            os.rename(target, target + ".tmp_duperemover")
            os.link(source, target)
            os.remove(target + ".tmp_duperemover")
            logging.debug(
                f"Inodes after: source: {os.stat(source).st_ino}, "
                f"target: {os.stat(target).st_ino}"
            )
            with self.stats_lock:
                self.stats["hard_links_created"] += 1
                self.stats["space_saved"] += target_size
            logging.info(f"Hard link created: {target} -> {source}")
        except Exception as e:
            logging.error(f"Error linking {target} to {source}: {e}")
            logging.error(traceback.format_exc())

    def delete_duplicate(self, file_path: str) -> None:
        """Delete a duplicate file.

        Args:
            file_path: Path to the file to delete.
        """
        if self.dry_run:
            logging.info(f"Would delete duplicate: {file_path}")
            return

        try:
            os.remove(file_path)
            with self.stats_lock:
                self.stats["duplicates_removed"] += 1
            logging.info(f"Deleted duplicate file: {file_path}")
        except Exception as e:
            logging.error(f"Error deleting file {file_path}: {e}")
            logging.error(traceback.format_exc())

    def rename_duplicate(self, file_path: str) -> None:
        """Rename a duplicate file by appending .duplicate.

        Args:
            file_path: Path to the file to rename.
        """
        if self.dry_run:
            logging.info(
                f"Would rename duplicate: {file_path} -> {file_path}.duplicate"
            )
            return

        try:
            new_name = file_path + ".duplicate"
            os.rename(file_path, new_name)
            logging.info(f"Renamed duplicate file: {file_path} -> {new_name}")
        except Exception as e:
            logging.error(f"Error renaming file {file_path}: {e}")
            logging.error(traceback.format_exc())

    def is_excluded(self, file_path: str) -> bool:
        """Check if a file matches any exclusion pattern.

        Args:
            file_path: Path to check against exclusion patterns.

        Returns:
            True if file matches any exclusion pattern, False otherwise.
        """
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(file_path, pattern):
                logging.debug(f"File {file_path} matches exclusion pattern {pattern}.")
                return True
        return False

    def add_file_hash_database(self, file_hash: str | None, file_path: str) -> None:
        """Add a hash to the database.

        Args:
            file_hash: Hash string to store.
            file_path: File path associated with the hash.
        """
        if file_hash is None:
            return
        with self.hashes_lock:
            self.hashes[file_hash] = file_path
            logging.debug(f"Hash for {file_path} added to hash database.")
            if self.stats["total_files"] % self.sync_interval == 0:
                self.hashes._file.flush()
                logging.debug("Synced hashes to disk.")

    def process_file(self, file_path: str) -> None:
        """Process a single file: check for duplicates and handle them.

        Args:
            file_path: Path to the file to process.
        """
        if self.is_excluded(file_path):
            logging.info(f"Skipping excluded file: {file_path}")
            return

        with self.stats_lock:
            self.stats["total_files"] += 1
        logging.debug(f"Processing file: {file_path}")

        if os.path.islink(file_path):
            logging.debug(f"Skipping symbolic link: {file_path}")
            return

        file_size = os.path.getsize(file_path)

        with self.file_sizes_lock:
            existing_file = self.file_sizes.get(file_size, None)
            if not existing_file:
                self.file_sizes[file_size] = file_path
                logging.debug(f"File size {file_size} recorded for {file_path}")
            else:
                logging.debug(
                    f"Found a file with the same size {file_size} as {existing_file}."
                )

        file_hash = self.get_file_hash(file_path)

        if existing_file:
            if file_hash and (
                not self.use_bloom_filter or file_hash in self.bloom_filter  # type: ignore[operator]
            ):
                if file_hash in self.hashes:
                    with self.stats_lock:
                        self.stats["duplicates_found"] += 1
                    logging.info(f"Duplicate found: {file_path} (hash: {file_hash})")
                    if self.replace_strategy == "hardlink":
                        self.create_hard_link(self.hashes[file_hash], file_path)
                    elif self.replace_strategy == "delete":
                        self.delete_duplicate(file_path)
                    elif self.replace_strategy == "rename":
                        self.rename_duplicate(file_path)
            else:
                logging.debug(
                    f"File {file_path} hash not found in Bloom filter or failed to compute hash."
                )
        self.add_file_hash_database(file_hash, file_path)

    def deduplicate(self) -> None:
        """Deduplicate files in the directory."""
        total_files = sum(len(files) for _, _, files in os.walk(self.directory))
        logging.info(f"Total files to process: {total_files}")

        if total_files == 0:
            logging.info("No files found.")
            return

        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            futures = []
            for dirpath, _, filenames in os.walk(self.directory):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    futures.append(executor.submit(self.process_file, file_path))

            if self.progress:
                with tqdm(
                    total=total_files, desc="Processing files", unit="file"
                ) as pbar:
                    for future in as_completed(futures):
                        future.result()
                        pbar.update(1)
            else:
                for future in as_completed(futures):
                    future.result()

    def print_stats(self) -> None:
        """Print deduplication statistics."""
        logging.info("\n=== Deduplication Statistics ===")
        logging.info(f"Total files processed: {self.stats['total_files']}")
        logging.info(f"Duplicate files found: {self.stats['duplicates_found']}")
        logging.info(f"Duplicates removed: {self.stats['duplicates_removed']}")
        logging.info(f"Hard links created: {self.stats['hard_links_created']}")
        logging.info(
            f"Total space saved: {self.stats['space_saved'] / (1024 * 1024):.2f} MB"
        )


def create_cli() -> argparse.ArgumentParser:
    """Create the CLI argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description="Deduplicate files by hashing and replacing duplicates."
    )
    parser.add_argument("directory", type=str, help="Directory to scan for duplicates.")
    parser.add_argument(
        "--hash-file", type=str, default=".hashes.db", help="File to store hashes."
    )
    parser.add_argument(
        "--buffer-size",
        type=int,
        default=65536,
        help="Buffer size for hashing (default: 64KB).",
    )
    parser.add_argument(
        "--hash-algorithm",
        type=str,
        choices=["xxhash", "blake3", "sha256"],
        default=None,
        help="Hashing algorithm (default: xxhash if available).",
    )
    parser.add_argument(
        "--replace-strategy",
        type=str,
        choices=["hardlink", "delete", "rename"],
        default="hardlink",
        help="Action for duplicates.",
    )
    parser.add_argument(
        "--max-threads", type=int, default=4, help="Number of threads (default: 4)."
    )
    parser.add_argument(
        "--sync-interval",
        type=int,
        default=100,
        help="How often to sync hashes to disk (default: 100).",
    )
    parser.add_argument("--progress", action="store_true", help="Show progress bar.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate deduplication without making changes.",
    )
    parser.add_argument(
        "--exclude",
        type=str,
        nargs="*",
        default=["*.tmp_duperemover"],
        help="Exclude files matching these patterns (e.g., '*.tmp', 'backup/*').",
    )
    parser.add_argument(
        "--use-bloom-filter",
        action="store_true",
        help="Use Bloom filter to speed up duplicate checking.",
    )
    return parser
