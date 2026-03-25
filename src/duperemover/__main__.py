from duperemover._core import Deduplicator, create_cli


def main() -> int:
    """Main CLI entry point."""
    parser = create_cli()
    args = parser.parse_args()

    deduplicator = Deduplicator(
        directory=args.directory,
        hash_file=args.hash_file,
        buffer_size=args.buffer_size,
        hash_algorithm=args.hash_algorithm,
        replace_strategy=args.replace_strategy,
        max_threads=args.max_threads,
        sync_interval=args.sync_interval,
        progress=args.progress,
        dry_run=args.dry_run,
        exclude_patterns=args.exclude,
        use_bloom_filter=args.use_bloom_filter,
        use_reflink=args.use_reflink,
    )

    deduplicator.deduplicate()
    deduplicator.print_stats()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
