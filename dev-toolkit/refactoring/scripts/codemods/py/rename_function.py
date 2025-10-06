#!/usr/bin/env python3
"""
LibCST-based function renaming codemod.

This is a template/example for safe code transformations using LibCST.
LibCST preserves formatting and comments, making it ideal for refactoring.

Usage:
    python rename_function.py --old-name foo --new-name bar file1.py file2.py
    python rename_function.py --old-name foo --new-name bar --dir src/

Requirements:
    pip install libcst

Example:
    # Dry run (default)
    python rename_function.py --old-name old_func --new-name new_func src/module.py

    # Apply changes
    python rename_function.py --old-name old_func --new-name new_func src/module.py --apply
"""

import argparse
import pathlib
import sys

try:
    import libcst as cst
    from libcst import matchers as m
except ImportError:
    print("Error: libcst not installed", file=sys.stderr)
    print("Install with: pip install libcst", file=sys.stderr)
    sys.exit(1)


class RenameFunctionTransformer(cst.CSTTransformer):
    """Transform function calls and definitions from old name to new name."""

    def __init__(self, old_name: str, new_name: str):
        self.old_name = old_name
        self.new_name = new_name
        self.changes_made = 0

    def leave_FunctionDef(
        self,
        original_node: cst.FunctionDef,
        updated_node: cst.FunctionDef,
    ) -> cst.FunctionDef:
        """Rename function definitions."""
        if m.matches(original_node.name, m.Name(value=self.old_name)):
            self.changes_made += 1
            return updated_node.with_changes(name=cst.Name(self.new_name))
        return updated_node

    def leave_Call(
        self,
        original_node: cst.Call,
        updated_node: cst.Call,
    ) -> cst.Call:
        """Rename function calls."""
        if m.matches(original_node.func, m.Name(value=self.old_name)):
            self.changes_made += 1
            return updated_node.with_changes(func=cst.Name(self.new_name))
        return updated_node

    def leave_Attribute(
        self,
        original_node: cst.Attribute,
        updated_node: cst.Attribute,
    ) -> cst.Attribute:
        """Rename method calls (obj.method_name)."""
        if m.matches(original_node.attr, m.Name(value=self.old_name)):
            self.changes_made += 1
            return updated_node.with_changes(attr=cst.Name(self.new_name))
        return updated_node


def transform_file(
    file_path: pathlib.Path,
    old_name: str,
    new_name: str,
    dry_run: bool = True,
) -> int:
    """
    Transform a single Python file.

    Returns number of changes made.
    """
    try:
        source = file_path.read_text(encoding="utf-8")

        # Parse source to CST
        module = cst.parse_module(source)

        # Apply transformation
        transformer = RenameFunctionTransformer(old_name, new_name)
        modified = module.visit(transformer)

        if transformer.changes_made == 0:
            return 0

        # Generate new code
        new_source = modified.code

        if dry_run:
            print(f"  Would change {transformer.changes_made} occurrence(s)")
            return transformer.changes_made
        else:
            # Write back to file
            file_path.write_text(new_source, encoding="utf-8")
            print(f"  Changed {transformer.changes_made} occurrence(s) ✓")
            return transformer.changes_made

    except Exception as e:
        print(f"  Error: {e}", file=sys.stderr)
        return 0


def find_python_files(directory: pathlib.Path) -> list[pathlib.Path]:
    """Find all Python files in directory recursively."""
    return list(directory.rglob("*.py"))


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Rename functions/methods using LibCST"
    )
    parser.add_argument(
        "--old-name",
        required=True,
        help="Current function name to rename",
    )
    parser.add_argument(
        "--new-name",
        required=True,
        help="New function name",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Python files to transform",
    )
    parser.add_argument(
        "--dir",
        help="Directory to scan for Python files (recursive)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (default is dry-run)",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files when scanning directory",
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Collect files to process
    files_to_process = []

    if args.dir:
        dir_path = pathlib.Path(args.dir)
        if not dir_path.is_dir():
            print(f"Error: Not a directory: {args.dir}", file=sys.stderr)
            sys.exit(1)

        files_to_process = find_python_files(dir_path)

        if not args.include_tests:
            files_to_process = [
                f for f in files_to_process
                if not f.name.startswith("test_") and "tests/" not in str(f)
            ]

    if args.files:
        files_to_process.extend(pathlib.Path(f) for f in args.files)

    if not files_to_process:
        print("Error: No files to process", file=sys.stderr)
        print("Specify files or use --dir", file=sys.stderr)
        sys.exit(1)

    # Filter to existing Python files
    files_to_process = [
        f for f in files_to_process
        if f.is_file() and f.suffix == ".py"
    ]

    if not files_to_process:
        print("Error: No Python files found", file=sys.stderr)
        sys.exit(1)

    # Show configuration
    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"Mode: {mode}")
    print(f"Old name: {args.old_name}")
    print(f"New name: {args.new_name}")
    print(f"Files: {len(files_to_process)}")
    print()

    # Process files
    total_changes = 0
    files_changed = 0

    for file_path in files_to_process:
        print(f"Processing: {file_path}")
        changes = transform_file(
            file_path,
            args.old_name,
            args.new_name,
            dry_run=not args.apply,
        )

        if changes > 0:
            total_changes += changes
            files_changed += 1

    # Summary
    print()
    print("Summary:")
    print(f"  Files processed: {len(files_to_process)}")
    print(f"  Files with changes: {files_changed}")
    print(f"  Total changes: {total_changes}")

    if not args.apply and total_changes > 0:
        print()
        print("This was a DRY RUN. Use --apply to make changes.")


if __name__ == "__main__":
    main()
