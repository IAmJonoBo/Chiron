#!/bin/bash
set -e

echo "Setting up Chiron development environment..."

# Install uv
echo "Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.cargo/bin:$PATH"

# Install dependencies
echo "Installing project dependencies..."
uv pip install -e ".[dev]"

# Install pre-commit hooks
echo "Installing pre-commit hooks..."
pre-commit install

echo "Development environment setup complete!"
