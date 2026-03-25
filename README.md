# Duperemover

> A Python utility for efficiently deduplicating files in directories.

[![PyPI](https://img.shields.io/pypi/v/duperemover.svg)](https://pypi.org/project/duperemover/)
[![Python](https://img.shields.io/pypi/pyversions/duperemover.svg)](https://pypi.org/project/duperemover/)
[![Coverage](https://codecov.io/gh/daedalus/duperemover/branch/main/graph/badge.svg)](https://codecov.io/gh/daedalus/duperemover)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

## Install

```bash
pip install duperemover
```

## Usage

```python
from duperemover import Deduplicator

dedup = Deduplicator(
    directory="/path/to/directory",
    hash_algorithm="xxhash",
    replace_strategy="hardlink",
    progress=True,
)
dedup.deduplicate()
dedup.print_stats()
```

## CLI

```bash
duperemover --help
```

### Command Syntax

```
duperemover <directory> [options]

Arguments:
  <directory>            Directory to scan for duplicates.
  --hash-file <file>     File to store hashes (default: .hashes.db).
  --buffer-size <size>   Buffer size for hashing (default: 65536, 64KB).
  --hash-algorithm <alg> Hashing algorithm (choices: "xxhash", "blake3", "sha256", default: "xxhash" if available).
  --replace-strategy <strategy> Strategy for handling duplicates (choices: "hardlink", "delete", "rename", default: "hardlink").
  --max-threads <num>    Number of threads to use for processing (default: 4).
  --sync-interval <num>  Sync interval for hashes to disk (default: 100).
  --progress             Show a progress bar while processing files.
  --dry-run              Simulate the deduplication process without making any changes.
  --use-bloom-filter     Use Bloom filter to speed up duplicate checking.
  --exclude PATTERNS     Exclude files matching these patterns.
```

### Examples

```bash
# Basic deduplication (using default hashing algorithm)
duperemover /path/to/directory

# Using SHA256 as the hashing algorithm
duperemover /path/to/directory --hash-algorithm sha256

# Simulate deduplication (dry run)
duperemover /path/to/directory --dry-run

# Create hard links for duplicates, use Bloom filter, and show progress
duperemover /path/to/directory --replace-strategy hardlink --use-bloom-filter --progress
```

## Features

- **Hash Algorithms**: Choose between `xxhash`, `blake3`, and `sha256` for calculating file hashes.
- **Duplicate Handling Strategies**: 
  - `hardlink`: Replace duplicates with hard links.
  - `delete`: Delete duplicate files.
  - `rename`: Rename duplicate files by appending `.duplicate` to their names.
- **Multi-threading**: Process files in parallel to speed up deduplication.
- **Bloom Filter**: Optionally, enable the Bloom filter to speed up duplicate checks by avoiding re-hashing files.
- **Exclusion Patterns**: Exclude files matching specific patterns from the deduplication process.
- **Progress Bar**: Optionally display a progress bar for better visibility during the deduplication process.
- **Dry Run**: Run the deduplication process without making any actual changes (useful for testing).

## API

### Deduplicator

```python
from duperemover import Deduplicator
```

#### Constructor

```python
Deduplicator(
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
)
```

#### Methods

- `deduplicate()`: Scan the directory for duplicates and process each file.
- `print_stats()`: Print deduplication statistics.
- `count_files(directory)`: Count the number of files in a directory.
- `get_file_hash(file_path)`: Calculate and return the hash of a file.
- `are_same_file(file1, file2)`: Check if two files are the same based on their inodes.
- `create_hard_link(source, target)`: Create a hard link from the source file to the target file.
- `delete_duplicate(file_path)`: Delete a duplicate file.
- `rename_duplicate(file_path)`: Rename a duplicate file by appending `.duplicate`.
- `is_excluded(file_path)`: Check if a file matches any exclusion pattern.

## Development

```bash
git clone https://github.com/daedalus/duperemover.git
cd duperemover
pip install -e ".[test]"

# run tests
pytest

# format
ruff format src/ tests/

# lint
ruff check src/ tests/

# type check
mypy src/
```
