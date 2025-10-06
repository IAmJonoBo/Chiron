# Contributing to Chiron

Thank you for your interest in contributing to Chiron! This document provides guidelines and information for contributors.

## Code of Conduct

This project adheres to a code of conduct. By participating, you are expected to uphold this code.

## Getting Started

### Prerequisites

- Python 3.9 or higher
- [uv](https://docs.astral.sh/uv/) for dependency management
- Git for version control

### Development Setup

1. **Fork and clone the repository**

```bash
git clone https://github.com/yourusername/Chiron.git
cd Chiron
```

2. **Set up the development environment**

```bash
# Install dependencies
uv sync --all-extras --dev

# Install pre-commit hooks
uv run pre-commit install
```

3. **Verify the setup**

```bash
# Run tests
uv run pytest

# Run linting
uv run pre-commit run --all-files
```

## Development Workflow

### Making Changes

1. **Create a feature branch**

```bash
git checkout -b feature/your-feature-name
```

2. **Make your changes**
   - Write code following the project standards
   - Add tests for new functionality
   - Update documentation as needed

3. **Test your changes**

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_your_feature.py

# Run with coverage
uv run pytest --cov=chiron
```

4. **Run quality checks**

```bash
# Lint and format
uv run pre-commit run --all-files

# Type checking
uv run mypy src/

# Security scan
uv run bandit -r src/
```

### Commit Guidelines

We use [Conventional Commits](https://www.conventionalcommits.org/) for commit messages:

```
type(scope): description

[optional body]

[optional footer]
```

**Types:**

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `ci`: CI/CD changes

**Examples:**

```
feat(cli): add new doctor command for health checks
fix(core): handle None input in process_data method
docs(api): update FastAPI service documentation
```

### Pull Request Process

1. **Push your changes**

```bash
git push origin feature/your-feature-name
```

2. **Create a pull request**
   - Use a clear, descriptive title
   - Provide a detailed description of changes
   - Link any related issues
   - Ensure all checks pass

3. **Address review feedback**
   - Make requested changes
   - Push updates to the same branch
   - Respond to reviewer comments

## Development Standards

### Code Style

- Follow PEP 8 style guidelines
- Use type hints for all functions and methods
- Write docstrings for all public APIs
- Maximum line length: 88 characters (Black default)

### Testing

- Write tests for all new functionality
- Maintain test coverage above 80%
- Use descriptive test names
- Follow the AAA pattern (Arrange, Act, Assert)

**Test Categories:**

- Unit tests: Test individual functions/methods
- Integration tests: Test component interactions
- Contract tests: Test API contracts
- Security tests: Test security features

### Documentation

- Update documentation for any user-facing changes
- Use Google-style docstrings
- Include examples in docstrings
- Update the changelog for breaking changes

## Project Structure

```
chiron/
├── src/chiron/          # Main package
│   ├── cli/            # Command-line interface
│   ├── service/        # FastAPI service
│   ├── core.py         # Core functionality
│   └── exceptions.py   # Custom exceptions
├── tests/              # Test suite
├── docs/               # Documentation
├── .github/            # GitHub workflows
└── pyproject.toml      # Project configuration
```

## Security

### Reporting Security Issues

Please report security vulnerabilities privately by emailing security@example.com. Do not open public issues for security problems.

### Security Practices

- All dependencies are scanned for vulnerabilities
- Code is analyzed with Bandit and Semgrep
- Artifacts are signed with Sigstore
- SBOMs are generated for all releases

## Release Process

Releases are automated through semantic versioning:

1. Commits trigger version bumps based on conventional commit types
2. CI builds and tests the release
3. Artifacts are signed and SBOMs are generated
4. Release is published to PyPI with GitHub attestations

## Getting Help

- **Documentation**: Check the [docs](https://github.com/IAmJonoBo/Chiron/docs)
- **Discussions**: Use GitHub Discussions for questions
- **Issues**: Report bugs and request features via GitHub Issues
- **Chat**: Join our community chat (link coming soon)

## Recognition

Contributors are recognized in:

- Release notes
- Contributors file
- Documentation acknowledgments

Thank you for contributing to Chiron! 🎉
