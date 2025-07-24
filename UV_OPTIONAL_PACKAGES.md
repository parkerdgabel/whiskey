# Configuring Optional Packages with UV

This document explains how the Whiskey framework configures optional packages (like the AI plugin) using UV package manager.

## Configuration Approach

We use UV's workspace feature to manage the monorepo structure while keeping packages optional for end users.

### 1. Workspace Setup

In the root `pyproject.toml`:

```toml
[tool.uv.workspace]
members = ["whiskey-*"]  # Includes all whiskey-* subdirectories

[tool.uv.sources]
whiskey-ai = { workspace = true }  # Tells UV this is a workspace member
```

This configuration:
- Treats `whiskey-ai/` as a workspace member during development
- Shares a single `uv.lock` file across all packages
- Enables local development without publishing

### 2. Optional Dependencies

```toml
[project.optional-dependencies]
ai = ["whiskey-ai"]
```

This allows users to install with:
```bash
# Core only
uv pip install whiskey

# With AI features
uv pip install "whiskey[ai]"
```

## Development Workflow

### Installing for Development

```bash
# Install all workspace members (for development)
uv sync

# Install without optional dependencies
uv sync --no-extras

# Install with specific extras
uv sync --extra ai
```

### Running Commands

```bash
# Run in workspace root
uv run pytest

# Run for specific package
uv run --package whiskey-ai pytest

# Install dependencies for specific package
uv sync --package whiskey-ai
```

## Building and Publishing

### Local Development
During development, UV treats `whiskey-ai` as a local package due to the workspace configuration.

### Publishing
When publishing to PyPI:
1. Each package (`whiskey` and `whiskey-ai`) is published separately
2. The `whiskey-ai = { workspace = true }` source is ignored in published packages
3. UV/pip resolves `whiskey-ai` from PyPI when users install

## Benefits

1. **Single Lock File**: All workspace members share `uv.lock`, ensuring consistent dependencies
2. **Local Development**: No need to install packages in editable mode manually
3. **Clear Separation**: Plugins remain optional for end users
4. **Fast Installation**: UV's speed makes working with workspaces efficient

## Testing Optional Dependencies

```bash
# Test that core works without AI
uv sync --no-extras
uv run pytest tests/core

# Test with AI plugin
uv sync --extra ai
uv run pytest tests/

# Test specific plugin
uv run --package whiskey-ai pytest
```

## CI/CD Considerations

For Docker builds or CI:

```dockerfile
# Install core dependencies only
COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-extras --no-install-workspace

# Then copy code and install workspace
COPY . /app/
RUN uv sync --frozen --extra ai
```

## Important Notes

1. **Workspace members must have their own `pyproject.toml`**: Each plugin needs its own package configuration
2. **Entry points work normally**: The plugin discovery system via entry points is unaffected
3. **Version synchronization**: Consider using a tool to keep versions in sync across workspace members

This setup provides the best of both worlds:
- Simple development with all packages in one repository
- Clean separation for end users who only want core functionality
- Standard Python packaging that works with any installer