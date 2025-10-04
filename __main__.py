"""Chiron CLI entry point."""

import sys

if __name__ == "__main__":
    from chiron.cli.main import cli

    sys.exit(cli())
