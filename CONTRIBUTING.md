# Contributing

Contributions are welcome! Here's how to get started.

## Development Setup

1. Fork and clone the repository.
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
3. Install test dependencies:
   ```bash
   pip install -r requirements_test.txt
   ```

## Running Tests

```bash
pytest tests/
```

## Code Style

- Follow Home Assistant coding standards.
- Use type hints throughout.
- Run linting before submitting:
  ```bash
  ruff check custom_components/
  ```

## Pull Requests

1. Create a feature branch from `main`.
2. Write tests for new functionality.
3. Ensure all tests pass.
4. Submit a pull request with a clear description of changes.

## Reporting Issues

Open an issue on GitHub with:
- Home Assistant version
- Integration version
- Steps to reproduce
- Expected vs actual behavior
