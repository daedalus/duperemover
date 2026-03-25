from duperemover._core import Deduplicator, create_cli


def main() -> int:
    """Main CLI entry point."""
    parser = create_cli()
    args = parser.parse_args()

    deduplicator = Deduplicator(
        args.directory,
        args.hash_file,
        args.buffer_size,
        args.hash_algorithm,
        args.replace_strategy,
        args.max_threads,
        args.sync_interval,
        args.progress,
        args.dry_run,
        args.exclude,
        args.use_bloom_filter,
    )

    deduplicator.deduplicate()
    deduplicator.print_stats()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
