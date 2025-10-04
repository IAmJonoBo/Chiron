#!/bin/bash

# Post-create script for dev container setup

set -e

echo "🚀 Setting up Chiron development environment..."

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

# Add uv to PATH
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc

# Install dependencies
echo "📦 Installing Python dependencies..."
uv sync --all-extras --dev

# Install pre-commit hooks
echo "🔧 Setting up pre-commit hooks..."
uv run pre-commit install

# Install additional tools
echo "🛠️ Installing additional tools..."

# Install cosign for artifact signing
curl -O -L "https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64"
sudo mv cosign-linux-amd64 /usr/local/bin/cosign
sudo chmod +x /usr/local/bin/cosign

# Install syft for SBOM generation
curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin

# Install grype for vulnerability scanning
curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sh -s -- -b /usr/local/bin

# Create useful aliases
echo "📝 Setting up aliases..."
cat >> ~/.bashrc << 'EOF'

# Chiron development aliases
alias chiron-test="uv run pytest"
alias chiron-lint="uv run pre-commit run --all-files"
alias chiron-build="uv build"
alias chiron-serve="uv run chiron serve --reload"
alias chiron-docs="uv run mkdocs serve"

# Git shortcuts
alias gs="git status"
alias ga="git add"
alias gc="git commit"
alias gp="git push"
alias gl="git log --oneline -10"

EOF

echo "✅ Development environment setup complete!"
echo ""
echo "Available commands:"
echo "  chiron-test  - Run tests"
echo "  chiron-lint  - Run linting"
echo "  chiron-build - Build package"
echo "  chiron-serve - Start development server"
echo "  chiron-docs  - Start documentation server"
echo ""
echo "Happy coding! 🎉"