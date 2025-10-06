#!/usr/bin/env python3
"""
Generate pytest snapshot/characterization test scaffolds.

This tool helps create "golden file" or "approval" tests that lock in
current behavior before refactoring. These tests fail on behavior change,
ensuring refactorings are truly behavior-preserving.

Usage:
    python snapshot_scaffold.py --path src/module.py --output tests/snapshots/

Requirements:
    - pytest
    - pytest-snapshot (optional, for snapshot support)

Example:
    python snapshot_scaffold.py --path src/chiron/dev_toolbox.py
"""

import argparse
import ast
import pathlib
import sys
from typing import List, Tuple


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate characterization test scaffolds"
    )
    parser.add_argument(
        "--path",
        required=True,
        help="Python file to generate tests for",
    )
    parser.add_argument(
        "--output",
        default="tests/snapshots",
        help="Output directory for test files (default: tests/snapshots)",
    )
    parser.add_argument(
        "--max-functions",
        type=int,
        default=10,
        help="Maximum functions to generate tests for (default: 10)",
    )
    return parser.parse_args()


def extract_public_functions(source_file: pathlib.Path) -> List[Tuple[str, int]]:
    """
    Extract public function/method names and their line numbers.
    
    Returns list of (name, lineno) tuples.
    """
    source = source_file.read_text(encoding="utf-8")
    
    try:
        tree = ast.parse(source, filename=str(source_file))
    except SyntaxError as e:
        print(f"Error parsing {source_file}: {e}", file=sys.stderr)
        return []
    
    functions = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Skip private functions (starting with _)
            if not node.name.startswith("_"):
                functions.append((node.name, node.lineno))
    
    return functions


def generate_test_scaffold(
    module_path: pathlib.Path,
    function_name: str,
    lineno: int,
) -> str:
    """Generate pytest test scaffold for a function."""
    
    # Derive module import path
    # e.g., src/chiron/dev_toolbox.py -> chiron.dev_toolbox
    parts = module_path.parts
    if "src" in parts:
        idx = parts.index("src")
        module_parts = parts[idx + 1:]
    else:
        module_parts = parts
    
    module_name = ".".join(module_parts).replace(".py", "")
    
    test_code = f'''
def test_{function_name}_characterization(snapshot):
    """
    Characterization test for {function_name}.
    
    This test locks in the current behavior of {function_name} before refactoring.
    If this test fails after refactoring, the behavior has changed.
    
    Source: {module_path}:{lineno}
    """
    from {module_name} import {function_name}
    
    # TODO: Provide appropriate test inputs
    # Example: result = {function_name}(test_input)
    
    # TODO: Choose appropriate assertion
    # Option 1: Snapshot assertion (requires pytest-snapshot)
    # assert result == snapshot
    
    # Option 2: Explicit assertion
    # expected = load_expected_output()
    # assert result == expected
    
    # Option 3: Property assertion
    # assert isinstance(result, ExpectedType)
    # assert len(result) > 0
    
    pytest.skip("TODO: Implement characterization test")


def test_{function_name}_edge_cases():
    """
    Test known edge cases for {function_name}.
    
    Document specific behaviors that must be preserved.
    """
    from {module_name} import {function_name}
    
    # TODO: Test edge cases
    # Example:
    # assert {function_name}(None) raises ValueError
    # assert {function_name}("") == default_value
    # assert {function_name}(large_input) == expected_output
    
    pytest.skip("TODO: Implement edge case tests")
'''
    
    return test_code.strip()


def main():
    """Main entry point."""
    args = parse_args()
    
    source_path = pathlib.Path(args.path)
    if not source_path.is_file():
        print(f"Error: File not found: {args.path}", file=sys.stderr)
        sys.exit(1)
    
    if not source_path.suffix == ".py":
        print(f"Error: Not a Python file: {args.path}", file=sys.stderr)
        sys.exit(1)
    
    # Extract functions
    print(f"Analyzing: {source_path}")
    functions = extract_public_functions(source_path)
    
    if not functions:
        print("No public functions found")
        sys.exit(0)
    
    print(f"Found {len(functions)} public functions")
    
    # Limit to max_functions
    if len(functions) > args.max_functions:
        functions = functions[:args.max_functions]
        print(f"Limiting to first {args.max_functions} functions")
    
    # Generate test file
    output_dir = pathlib.Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Derive test file name
    test_file_name = f"test_characterization_{source_path.stem}.py"
    test_file_path = output_dir / test_file_name
    
    # Generate test content
    test_content = [
        '"""',
        f'Characterization tests for {source_path.name}',
        '',
        'These tests lock in current behavior before refactoring.',
        'If these tests fail after refactoring, behavior has changed.',
        '',
        'Generated by snapshot_scaffold.py',
        '"""',
        '',
        'import pytest',
        '',
    ]
    
    for func_name, lineno in functions:
        test_content.append(generate_test_scaffold(source_path, func_name, lineno))
        test_content.append('')
        test_content.append('')
    
    # Write test file
    test_file_path.write_text('\n'.join(test_content), encoding="utf-8")
    
    print(f"\n✅ Generated test scaffold: {test_file_path}")
    print(f"   Functions: {len(functions)}")
    print()
    print("Next steps:")
    print("1. Edit the generated test file")
    print("2. Provide appropriate test inputs")
    print("3. Capture expected outputs")
    print("4. Run tests to verify: pytest", test_file_path)
    print("5. Proceed with refactoring")


if __name__ == "__main__":
    main()
