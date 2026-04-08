# vitraj

![image](src/main/icons/src/logo.svg)

An opinionated dual-pane file manager for macOS, forked from [fman](https://github.com/fman-users/fman).

This is a personal rework targeting macOS as the primary platform. While the cross-platform codebase (Windows, Linux) is preserved, development and testing focus on macOS with Python 3.14.

## What changed from fman

### New features

- **Settings panel (Cmd+,)** — centralized preferences replacing scattered dialog popups. Font family, font size, hidden files toggle, parent directory entry, and external tool configuration in one place.
- **Theme editor** — visual color customization with 21 color pickers, live preview, save/load named themes, import/export `.fman-theme` files. Integrates with FmanAlternativeColors plugin for seamless theme switching.
- **File preview (F3 / Cmd+Y)** — preview text, images (PNG, JPG, GIF, BMP, SVG, WEBP, AVIF), PDFs, and directory stats in the opposite pane. Live updates as you navigate.
- **Parent directory entry (..)** — toggleable `..` entry at the top of every directory listing.
- **PanelManager** — unified panel system in core. Settings, theme editor, and file preview all use a single API (`window.activate_panel` / `window.deactivate_panel`). Opening one panel auto-closes another. No more duplicated splitter-swap code across plugins.

### Fixes and modernization

- **macOS 26 crash fix** — upgraded pyobjc-core (7.1 → 12.1) to fix SIGSEGV in `PyObjCClass_NewMetaClass`
- **Python 3.14 compatibility** — fixed float-to-int rejection in Qt calls, removed private `traceback._some_str` usage, fixed read-only `TracebackException.exc_type`
- **PyInstaller 6.x** — upgraded from 4.4 to 6.19.0, fixed `sys._MEIPASS` path change
- **macOS TCC compliance** — ad-hoc codesigning + NS*UsageDescription keys for folder access
- **GoTo performance** — cached CoreServices framework load (800ms → 6ms)
- **Bundle size** — stripped unused Qt frameworks and boto3 from frozen app
- **Security** — Apple credentials moved to environment variables
- **Filter robustness** — `remove_filter` no longer crashes on missing filter; `..` entries immune to all filters at model level

### Architecture changes

- Core Python package renamed from `fman` to `vitraj`
- DATA_DIRECTORY: `~/Library/Application Support/vitraj` (Mac)
- Bundle identifier: `io.vitraj.vitraj`
- New plugin icons generated from custom SVG

## Compilation

### Prerequisites

- Python 3.9+ (tested with 3.14)
- macOS (primary target)
- Xcode Command Line Tools (`xcode-select --install`)

### Setup

```bash
# Clone the repo
git clone https://github.com/usqr/fman.git vitraj
cd vitraj

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -Ur requirements/mac.txt
```

### Build from source

```bash
# Run from source (development mode)
python build.py run

# Run tests (expect 461 tests, 2 pre-existing failures in test_zip.py)
python build.py test

# Compile standalone macOS app
python build.py clean && python build.py freeze
# Output: target/vitraj.app (ad-hoc signed)

# Launch the compiled app
open target/vitraj.app
```

### Build for other platforms

```bash
# Windows
pip install -Ur requirements/windows.txt
python build.py freeze

# Ubuntu/Debian
pip install -Ur requirements/ubuntu.txt
python build.py freeze

# Arch Linux
pip install -Ur requirements/arch.txt
python build.py freeze

# Fedora
pip install -Ur requirements/fedora.txt
python build.py freeze
```

### Optional dependencies

| Package | Purpose | Install |
|---------|---------|---------|
| PyMuPDF | PDF preview | `pip install PyMuPDF` |
| Pillow | AVIF image preview | `pip install Pillow` |

Both are included in `requirements/base.txt`. The app works without them — preview falls back gracefully.

## Key bindings

| Shortcut | Action |
|----------|--------|
| F3 / Cmd+Y | Toggle file preview |
| Cmd+, | Open settings |
| Cmd+P | Go to directory |
| Cmd+Shift+P | Command palette |
| Cmd+. | Toggle hidden files |
| Tab | Switch panes |
| F5 | Copy |
| F6 | Move |
| F7 | Create directory |
| F8 | Move to trash |
| Escape | Close active panel |

## Key dependencies

| Package | Version | Notes |
|---------|---------|-------|
| PyQt5 | 5.15.11 | GUI framework |
| PyInstaller | 6.19.0 | App freezing/compilation |
| PyMuPDF | 1.27.2.2 | PDF preview (optional) |
| Pillow | 11.2.1 | AVIF support (optional) |
| pyobjc-core | 12.1 | macOS Objective-C bridge |
| fbs | 0.9.4 | [Build system](https://build-system.fman.io/) |

See `requirements/` for the full per-platform list.

## Plugin system

vitraj supports the same plugin system as fman. Plugins are auto-discovered from:

1. `src/main/resources/base/Plugins/` (shipped)
2. `~/Library/Application Support/vitraj/Plugins/Third-party/` (installed)
3. `~/Library/Application Support/vitraj/Plugins/User/` (user)

Existing fman plugins should work — just update imports from `fman` to `vitraj` if they import core modules directly.

## AI agent instructions

See [AGENTS.md](AGENTS.md) for guidance when working on this codebase with AI agents.

## License

This is a fork of [fman](https://github.com/fman-users/fman) by Michael Herrmann. See the original repository for license terms.
