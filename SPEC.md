# SPEC.md — Duperemover

## Purpose
Duperemover is a Python utility that identifies and handles duplicate files within a directory. It hashes files using fast algorithms (xxhash, blake3, sha256) and offers multiple strategies for handling duplicates (hardlink, delete, rename, reflink). The tool supports multi-threading and exclusion patterns.

## Scope
- **In scope:**
  - File hashing with xxhash, blake3, sha256 algorithms
  - Duplicate detection via hash comparison
  - Handling strategies: hardlink, delete, rename, reflink
  - Multi-threaded file processing
  - Progress bar display
  - Bloom filter for faster duplicate checks
  - File size pre-filtering optimization
  - Exclusion patterns (glob-style)
  - Dry-run mode for simulation
  - Memory-mapped hash storage for persistence

- **Not in scope:**
  - Directory watching / real-time deduplication
  - GUI interface
  - Network file support
  - Symbolic link handling (explicitly skipped)

## Public API / Interface

### CLI Command
```
duperemover <directory> [options]
```

**Arguments:**
- `directory` (required): Directory to scan for duplicates

**Options:**
- `--hash-file FILE`: File to store hashes (default: `.hashes.db`)
- `--buffer-size SIZE`: Buffer size for hashing (default: 65536)
- `--hash-algorithm {xxhash,blake3,sha256}`: Hashing algorithm (default: xxhash if available)
- `--replace-strategy {hardlink,delete,rename,reflink}`: How to handle duplicates (default: hardlink)
- `--max-threads N`: Number of threads (default: 4)
- `--sync-interval N`: Sync interval for hashes (default: 100)
- `--progress`: Show progress bar
- `--dry-run`: Simulate without making changes
- `--use-bloom-filter`: Enable Bloom filter for faster lookups
- `--use-reflink`: Use reflink/dedupe for filesystem-level deduplication (btrfs, xfs)
- `--exclude PATTERNS`: Exclusion patterns (can be specified multiple times)

### Python API
```python
from duperemover import Deduplicator

dedup = Deduplicator(
    directory: str,
    hash_file: str = ".hashes.db",
    buffer_size: int = 65536,
    hash_algorithm: str = "xxhash",
    replace_strategy: str = "hardlink",
    max_threads: int = 4,
    sync_interval: int = 100,
    progress: bool = False,
    dry_run: bool = False,
    exclude_patterns: list[str] | None = None,
    use_bloom_filter: bool = False,
    use_reflink: bool = False,
)
dedup.deduplicate()
dedup.print_stats()
```

**Methods:**
- `count_files(directory) -> int`: Count files in directory
- `get_file_hash(file_path) -> str | None`: Calculate file hash
- `are_same_file(file1, file2) -> bool`: Check if files are same via inodes
- `create_hard_link(source, target) -> None`: Create hard link
- `create_reflink(source, target) -> None`: Create reflink (filesystem-level dedup)
- `delete_duplicate(file_path) -> None`: Delete duplicate file
- `rename_duplicate(file_path) -> None`: Rename with `.duplicate` suffix
- `is_excluded(file_path) -> bool`: Check exclusion patterns
- `add_file_hash_database(file_hash, file_path) -> None`: Add hash to database
- `process_file(file_path) -> None`: Process single file
- `deduplicate() -> None`: Main deduplication loop
- `print_stats() -> None`: Print statistics

## Data Formats
- **Hash database:** Memory-mapped dict stored in `.hashes.db` (mmappickle)
- **Hash format:** Hex string (algorithm-dependent)
- **Exclusion patterns:** Glob-style patterns (e.g., `*.tmp`, `.git/*`)

## Edge Cases
1. Empty directory: Should complete without errors, print "No files found"
2. Single file: No duplicates possible, should process normally
3. File deleted between hashing and processing: Handle gracefully, skip
4. Permission denied: Log warning, continue with other files
5. Hash file corrupted/incomplete: Start fresh or warn user
6. Hardlink on same filesystem: Should succeed
7. Hardlink across filesystems: Fail gracefully with message
8. Reflink on unsupported filesystem: Fall back to hardlink
9. Delete file that's already deleted: Handle gracefully
10. Symlinks: Explicitly skipped (not followed)
11. Very large files: Stream-based hashing with configurable buffer size
12. Files with same size but different content: Hash comparison required

## Performance & Constraints
- O(n) hashing where n = total file size
- Multi-threaded processing for independent files
- File size pre-filtering reduces unnecessary hash computations
- Bloom filter reduces re-hashing of known files (optional)
- Memory-mapped storage for large hash databases
- Default buffer size: 64KB (configurable)
- Maximum threads: Limited by GIL for CPU-bound tasks, but file I/O benefits

## Statistics Tracked
- `total_files`: Total files processed
- `duplicates_found`: Number of duplicate files detected
- `duplicates_removed`: Files removed via delete strategy
- `hard_links_created`: Hard links created
- `reflinks_created`: Reflinks created (filesystem-level)
- `space_saved`: Bytes saved via deduplication
