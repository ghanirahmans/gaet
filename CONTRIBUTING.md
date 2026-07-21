# Contributing to gaet

Thank you for considering contributing to gaet! We believe in making database backups accessible to everyone, and your help makes that possible.

## Code of Conduct

Be respectful, inclusive, and assume good intent. We're all learning.

## Getting Started

### Prerequisites

- Python 3.8+
- PostgreSQL 12+ (with `pg_dump` and `pg_restore`)
- Git
- Node.js 16+ (for dashboard development)

### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/ghanirahmans/gaet.git
cd gaet

# Install in editable mode
pip install -e .

# Install dev dependencies
pip install pytest pytest-cov black flake8

# Verify installation
python gaet.py --version
```

### Project Structure

```
gaet/
├── gaet.py                # Main CLI (single Python file for now)
├── dashboard/             # Web UI (React + Flask)
│   ├── app.py            # API server
│   ├── public/           # Static files
│   └── src/              # React components
├── scripts/
│   ├── installer.py      # Cross-platform setup
│   └── scheduler.py      # OS integration
├── tests/                # Test suite
│   ├── test_backup.py
│   ├── test_restore.py
│   └── test_security.py
└── docs/                 # Documentation
```

## How to Contribute

### Report Bugs

Found a bug? Please open an issue with:

1. **What you did** - Exact steps to reproduce
2. **What happened** - Actual behavior
3. **What should happen** - Expected behavior
4. **Environment** - OS, Python version, PostgreSQL version
5. **Logs** - Output of `gaet log` if relevant

**Example:**
```
Title: gaet push fails with 504 timeout

Steps:
1. gaet init
2. gaet push
3. Wait 120 seconds

Actual: "Connection timeout after 120s"
Expected: Backup completes

Environment:
- OS: Ubuntu 22.04
- Python: 3.10.2
- PostgreSQL: 14.2
- Database size: 2.5GB

Error log:
[ERROR] [2024-01-15 14:22:35] Connection timeout after 120s
```

### Request Features

Have an idea? Open a discussion first before diving into code.

**Questions to answer:**
1. What problem does this solve?
2. How would you use this?
3. Would others benefit?
4. Any alternative approaches?

### Submit Code Changes

We love PRs! Follow this process:

#### 1. Fork and Create Branch

```bash
git checkout -b feature/my-feature
# or
git checkout -b fix/my-bug
# or
git checkout -b docs/my-doc-update
```

#### 2. Make Changes

- Follow PEP 8 style guide (`black gaet.py`)
- Add tests for new functionality
- Update documentation
- Keep commits small and focused

```bash
# Format your code
black gaet.py

# Lint your code
flake8 gaet.py

# Run tests
pytest tests/
```

#### 3. Test Your Changes

```bash
# Test the specific feature
python gaet.py init
python gaet.py check
python gaet.py push --dry-run

# Run full test suite
pytest -v

# Check code coverage
pytest --cov=. tests/
```

#### 4. Commit with Clear Messages

```bash
git commit -m "feature: add support for caching backups locally

- Adds GAET_CACHE_LOCAL flag
- Stores copies in ~/.gaet/cache/
- Improves recovery speed
- Closes #123"
```

**Commit message format:**
```
<type>: <subject>

<body>

Closes #<issue>
```

**Types:** `feature`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

#### 5. Push and Create Pull Request

```bash
git push origin feature/my-feature
```

Then open a PR with:
- Clear title
- Description of changes
- Link to related issues
- Screenshot/video if UI changes

---

## Testing Requirements

All PRs must include tests:

### Backup/Restore Tests

```python
# tests/test_backup.py
def test_backup_creates_valid_dump():
    """Verify backup creates a valid pg_dump file."""
    # Setup
    # Execute
    # Assert

def test_backup_respects_retention_policy():
    """Old backups are deleted automatically."""
    pass

def test_backup_fails_gracefully_on_connection_error():
    """Backup exits cleanly if cloud connection fails."""
    pass
```

### Security Tests

```python
# tests/test_security.py
def test_passwords_not_logged():
    """Passwords never appear in logs."""
    pass

def test_credentials_not_in_shell_history():
    """Commands don't leak passwords."""
    pass

def test_pgpassfile_cleanup():
    """Temp password files are deleted."""
    pass
```

### Integration Tests

```bash
# Full workflow test
gaet init
gaet check
gaet push --dry-run
gaet push
gaet status
gaet fetch --dry-run
```

---

## Code Style

### Python

We use `black` for formatting:

```bash
# Auto-format your code
black gaet.py

# Check without modifying
black --check gaet.py
```

**Style guide:**
- 88 character line length (black default)
- 4 spaces for indentation
- Type hints where helpful
- Docstrings for all public functions

### Git

- Atomic commits (each commit is one logical change)
- Clear, descriptive messages
- Link to issues when relevant
- Avoid merge commits (`git rebase` before pushing)

---

## Documentation

### Update README.md

If your change affects users:

```markdown
### Feature Name

Brief description of what it does.

Usage:
\`\`\`bash
gaet command --flag
\`\`\`

Examples:
\`\`\`bash
gaet command --flag value
\`\`\`
```

### Add to CHANGELOG.md

```markdown
## [Unreleased]

### Added
- New feature description

### Fixed
- Bug fix description

### Changed
- Breaking change description
```

### Docstrings

Use clear, actionable docstrings:

```python
def cmd_backup(env: Dict[str, str]) -> None:
    """Backup local PostgreSQL to cloud.
    
    Creates a compressed dump of local database and restores to cloud.
    Validates integrity before upload.
    
    Args:
        env: Environment variables dict
        
    Raises:
        SystemExit: On connection failure or timeout
        
    Example:
        cmd_backup(os.environ)  # Backup with current env
    """
```

---

## Review Process

### What Reviewers Look For

1. **Does it work?** - Tests pass, no obvious bugs
2. **Is it safe?** - No security vulnerabilities, passwords protected
3. **Is it documented?** - README/docstrings updated
4. **Is it maintainable?** - Clean code, clear intent
5. **Does it fit the vision?** - Aligns with gaet philosophy

### Getting Feedback

- 👍 means "looks good"
- 💬 means "let's discuss"
- 🚫 means "needs changes"

Respond to all comments before approval.

---

## Areas We Need Help With

### High Priority

- [ ] Windows testing (Task Scheduler integration)
- [ ] macOS testing (launchd integration)
- [ ] Performance optimization for 10GB+ databases
- [ ] Documentation improvements
- [ ] Error message clarity

### Medium Priority

- [ ] Dashboard mobile responsiveness
- [ ] API pagination for large backup histories
- [ ] Backup compression benchmarks
- [ ] CLI progress bars
- [ ] Log filtering improvements

### Low Priority

- [ ] Dark mode CSS tweaks
- [ ] Additional cloud provider presets
- [ ] Backup scheduling UI
- [ ] Community dashboard themes
- [ ] CLI color scheme options

---

## Release Process

1. Update version in `gaet.py` (e.g., `VERSION = "1.0.1"`)
2. Update `CHANGELOG.md` with all changes
3. Create git tag: `git tag v1.0.1`
4. Push tag: `git push origin v1.0.1`
5. GitHub Actions publishes to PyPI automatically

---

## Questions?

- 📖 Check [README.md](README.md)
- 🐛 Search [existing issues](https://github.com/ghanirahmans/gaet/issues)
- 💬 Start a [discussion](https://github.com/ghanirahmans/gaet/discussions)
- 📧 Email: support@gaet.dev

---

## Recognition

Contributors will be recognized in:
- `CONTRIBUTORS.md` file
- GitHub "Contributors" page
- Release notes for significant contributions

Thank you for making gaet better! 🚀

