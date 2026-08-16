# Contributing to gaet

Thank you for considering contributing to **gaet**! We welcome contributions to keep `gaet` stable, fast, zero-dependency, and cross-platform.

---

## Code of Conduct

Be respectful, inclusive, and assume good intent. We adhere to standard open-source community guidelines.

---

## Getting Started

### Prerequisites

- **Python 3.10+** (Standard Library only)
- **PostgreSQL 12+** (with client utilities `psql`, `pg_dump`, `pg_restore`)
- **Git**

> 💡 **Zero External Dependencies**: `gaet` requires no `npm`, `node`, or external `pip` dependencies for running the CLI or Web Dashboard.

### Setting Up Development Environment

```bash
# 1. Clone the repository
git clone https://github.com/ghanirahmans/gaet.git
cd gaet

# 2. Install in editable mode
pip install -e .

# 3. Verify installation
gaet --version
```

### Project Architecture (`src/` Layout)

```text
gaet/
├── gaet.py                # Entry shim
├── pyproject.toml         # Packaging & metadata (v1.0.0 LTS)
├── src/gaet/              # Modular package
│   ├── __init__.py        # Re-exports
│   ├── cli.py             # Argparse dispatch
│   ├── core.py            # Platform detection, env & process runners
│   ├── registry.py        # Command registry (@command decorator)
│   ├── detect.py          # PostgreSQL binary & Unix socket discovery
│   ├── init.py            # Interactive setup wizard
│   ├── status.py          # Status, check, diff, doctor, completion
│   ├── backup.py          # Push & fetch workflows
│   ├── scheduler.py       # OS service manager (systemd, launchd, schtasks)
│   ├── serve.py           # Web dashboard server launcher
│   └── update.py          # Install, update, uninstall
├── dashboard/             # Zero-dependency Web Operations Hub
│   ├── server.py          # Python standard library HTTP server
│   ├── static/index.html  # Responsive HTML/CSS/JS dashboard UI
│   └── public/            # Static assets
├── scripts/               # Service wrappers & installation helpers
├── completions/           # Shell completion scripts (Bash, Zsh, Fish, PS1)
└── tests/                 # Unit test suite (48 tests)
```

---

## Development & Branching Model

We follow the standard open-source branching model:

- **`main`**: Active development branch for upcoming features (`v1.1.0+`).
- **`lts/v1.0`**: Maintenance branch for `v1.0.0 LTS` (security patches and critical bug fixes).

### Creating a Feature or Fix Branch

```bash
git checkout main
git pull origin main
git checkout -b feature/my-cool-feature
# or
git checkout -b fix/my-bug-fix
```

---

## Testing & Quality Requirements

Before submitting a Pull Request, run the local unit test suite:

```bash
# Run full unittest suite
python3 -m unittest discover -s tests -v
```

Ensure all tests pass and your changes do not break cross-platform compatibility across **Linux**, **macOS**, and **Windows**.

---

## Commit & Pull Request Guidelines

### Commit Message Format

Follow standard conventional commit messages:

```bash
git commit -m "fix(detect): support custom PostgreSQL socket directory on macOS"
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`.

### Submitting a Pull Request

1. Push your branch:
   ```bash
   git push origin feature/my-cool-feature
   ```
2. Open a Pull Request on GitHub targetting the `main` branch.
3. Ensure CI matrix tests (Ubuntu, macOS, Windows on Python 3.10, 3.11, 3.12) pass.

---

## Release & Maintenance Process (Maintainers)

1. Bump version in `pyproject.toml` and `src/gaet/core.py`.
2. Update `CHANGELOG.md` with new features / bug fixes.
3. Tag the commit:
   ```bash
   git tag -a v1.0.1 -m "Release v1.0.1"
   git push origin v1.0.1
   ```
4. Merge changes into `lts/v1.0` if it applies to active LTS maintenance.

---

## Questions & Support

- 📖 Read our [README.md](README.md) and [SUPPORT.md](SUPPORT.md)
- 🐛 Report bugs or suggest features on [GitHub Issues](https://github.com/ghanirahmans/gaet/issues)
