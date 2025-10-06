#!/usr/bin/env python3
"""
Split large refactoring changes into manageable PR shards.

When refactoring affects many files, this tool helps split changes into
reviewable chunks (default: 50 files per PR).

Usage:
    python shard_pr_list.py --input changed_files.txt [--shard-size 50]
    git diff --name-only | python shard_pr_list.py --stdin

Example:
    # From git diff
    git diff --name-only main > changed.txt
    python shard_pr_list.py --input changed.txt --shard-size 30
    
    # From stdin
    git diff --name-only main | python shard_pr_list.py --stdin
"""

import argparse
import sys
from pathlib import Path
from typing import List


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Split file changes into PR shards"
    )
    
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--input",
        help="File containing list of changed files (one per line)",
    )
    input_group.add_argument(
        "--stdin",
        action="store_true",
        help="Read file list from stdin",
    )
    
    parser.add_argument(
        "--shard-size",
        type=int,
        default=50,
        help="Number of files per PR shard (default: 50)",
    )
    parser.add_argument(
        "--output",
        help="Output file for shard plan (default: stdout)",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "text", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    return parser.parse_args()


def read_files(input_source: str = None, from_stdin: bool = False) -> List[str]:
    """Read list of files from input source."""
    if from_stdin:
        files = [line.strip() for line in sys.stdin if line.strip()]
    else:
        input_path = Path(input_source)
        if not input_path.exists():
            print(f"Error: Input file not found: {input_source}", file=sys.stderr)
            sys.exit(1)
        files = [line.strip() for line in input_path.read_text().splitlines() if line.strip()]
    
    return files


def create_shards(files: List[str], shard_size: int) -> List[List[str]]:
    """Split files into shards of specified size."""
    shards = []
    for i in range(0, len(files), shard_size):
        shard = files[i:i + shard_size]
        shards.append(shard)
    return shards


def format_markdown(shards: List[List[str]]) -> str:
    """Format shards as markdown checklist."""
    lines = [
        "# Refactoring PR Shards",
        "",
        f"Total files: {sum(len(s) for s in shards)}",
        f"Total shards: {len(shards)}",
        "",
    ]
    
    for i, shard in enumerate(shards, 1):
        lines.append(f"## Shard {i} ({len(shard)} files)")
        lines.append("")
        
        for file_path in shard:
            lines.append(f"- [ ] {file_path}")
        
        lines.append("")
        lines.append("**PR Checklist:**")
        lines.append("- [ ] All tests passing")
        lines.append("- [ ] Coverage maintained")
        lines.append("- [ ] Linting/type checks passing")
        lines.append("- [ ] Characterization tests added if needed")
        lines.append("- [ ] Before/after metrics documented")
        lines.append("")
        lines.append("---")
        lines.append("")
    
    return "\n".join(lines)


def format_text(shards: List[List[str]]) -> str:
    """Format shards as plain text."""
    lines = [
        "Refactoring PR Shards",
        "=" * 50,
        "",
        f"Total files: {sum(len(s) for s in shards)}",
        f"Total shards: {len(shards)}",
        "",
    ]
    
    for i, shard in enumerate(shards, 1):
        lines.append(f"Shard {i} ({len(shard)} files):")
        lines.append("-" * 50)
        
        for file_path in shard:
            lines.append(f"  {file_path}")
        
        lines.append("")
    
    return "\n".join(lines)


def format_json(shards: List[List[str]]) -> str:
    """Format shards as JSON."""
    import json
    
    data = {
        "total_files": sum(len(s) for s in shards),
        "total_shards": len(shards),
        "shards": [
            {
                "shard_number": i,
                "file_count": len(shard),
                "files": shard,
            }
            for i, shard in enumerate(shards, 1)
        ],
    }
    
    return json.dumps(data, indent=2)


def main():
    """Main entry point."""
    args = parse_args()
    
    # Read files
    files = read_files(args.input, args.stdin)
    
    if not files:
        print("Error: No files to process", file=sys.stderr)
        sys.exit(1)
    
    # Create shards
    shards = create_shards(files, args.shard_size)
    
    # Format output
    if args.format == "markdown":
        output = format_markdown(shards)
    elif args.format == "text":
        output = format_text(shards)
    elif args.format == "json":
        output = format_json(shards)
    else:
        output = format_text(shards)
    
    # Write output
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
        print(f"✅ Wrote shard plan to: {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
