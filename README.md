# fman

A cross-platform dual-pane file manager.

## Features

- **Dual-pane file browsing** with keyboard-driven navigation
- **File preview (F3)** — press F3, Cmd+Y (Mac), or Shift+F3 to preview files in the opposite pane:
  - Text files with monospace font (100+ extensions + UTF-8 auto-detection)
  - Images: PNG, JPG, GIF, BMP, SVG, ICO, WEBP, AVIF with resolution info
  - PDF rendering (first page at 150 DPI with page count)
  - Directory stats (file/folder count, total size)
  - Live updates as you navigate with arrow keys
- **Parent directory entry (..)** — toggle via Command Palette to show `..` at the top of every directory
- **GoTo (Cmd+P / Ctrl+P)** — quick directory navigation with Spotlight integration on macOS
- **Command Palette (Cmd+Shift+P / Ctrl+Shift+P)** — access all commands by name

## Development instructions

Python 3.9 or later is required (tested up to Python 3.14).

Install the requirements for your operating system:

    pip install -Ur requirements/mac.txt      # macOS
    pip install -Ur requirements/ubuntu.txt    # Ubuntu/Debian
    pip install -Ur requirements/arch.txt      # Arch Linux
    pip install -Ur requirements/fedora.txt    # Fedora
    pip install -Ur requirements/windows.txt   # Windows

Run from source:

    python build.py run

Compile a standalone app:

    python build.py freeze

Call `python build.py` without arguments to see all available commands.
This uses [fman build system](https://build-system.fman.io/).

## Key dependencies

| Package | Version | Notes |
|---------|---------|-------|
| PyQt5 | 5.15.11 | GUI framework |
| PyInstaller | 6.19.0 | App freezing/compilation |
| PyMuPDF | 1.27.2.2 | PDF preview rendering |
| Pillow | 11.2.1 | AVIF image support |
| pyobjc-core | 12.1 | macOS Objective-C bridge |
| fbs | 0.9.4 | Build system |

See `requirements/` for the full list per platform.

## AI agent instructions

See [AGENTS.md](AGENTS.md) for guidance when working on this codebase with AI agents.
