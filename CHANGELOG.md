# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0.1] - 2026-03-25

### Added
- Initial release
- File hashing with xxhash, blake3, and sha256 algorithms
- Duplicate detection via hash comparison
- Handling strategies: hardlink, delete, rename
- Multi-threaded file processing
- Progress bar display
- Bloom filter for faster duplicate checks
- Exclusion patterns (glob-style)
- Dry-run mode for simulation
- Memory-mapped hash storage for persistence

[0.1.0.1]: https://github.com/daedalus/duperemover/releases/tag/v0.1.0.1
