# fman

A cross-platform dual-pane file manager.

## Development instructions

Python 3.9 or later is required (tested up to Python 3.14).

Install the requirements for your operating system. For example:

    pip install -Ur requirements/mac.txt      # macOS
    pip install -Ur requirements/ubuntu.txt    # Ubuntu/Debian
    pip install -Ur requirements/arch.txt      # Arch Linux
    pip install -Ur requirements/fedora.txt    # Fedora
    pip install -Ur requirements/windows.txt   # Windows

Then you can use `python build.py` to run, compile etc. fman. For example:

    python build.py run

Call `python build.py` without arguments to see a list of available commands.
This uses [fman build system](https://build-system.fman.io/).

## Key dependencies

| Package | Version | Notes |
|---------|---------|-------|
| PyQt5 | 5.15.11 | GUI framework |
| PyInstaller | 6.19.0 | App freezing/compilation |
| pyobjc-core | 12.1 | macOS Objective-C bridge |
| fbs | 0.9.4 | Build system |

See `requirements/` for the full list per platform.
