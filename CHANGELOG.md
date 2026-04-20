# Changelog

## 1.7.4 (unreleased)

### Fixed

- **macOS crash on macOS 26**: Fixed SIGSEGV in `PyObjCClass_NewMetaClass` caused by
  pyobjc-core 7.1 being incompatible with macOS 26's Objective-C runtime under Rosetta.
  Upgraded pyobjc-core from 7.1 to 12.1.
- **Python 3.14 compatibility**: Fixed `ImportError` for `traceback._some_str` (private
  API removed in 3.14), `AttributeError` for read-only `TracebackException.exc_type`
  property, and `TypeError` from float-to-int conversion in `QSize`/`QPoint`/`setPointSize`
  (implicit conversion removed in 3.14).
- **Slow GoTo quicksearch (Cmd+P)**: Cached `CoreServices.framework` loading which took
  ~800ms per Spotlight query with pyobjc-core 12.1. Pre-warms the framework at startup.
- **Frozen app: osxtrash not found**: Moved osxtrash `.so` to `Contents/Frameworks`
  (where PyInstaller 6.x sets `sys._MEIPASS`) instead of `Contents/MacOS`.
- **Escape sequence warning** in `tutorial.py` docstring (`\F` is invalid in Python 3.14+).

### Changed

- **Upgraded all dependencies** for Python 3.9+ / 3.14 compatibility:
  - PyInstaller: 4.4 -> 6.19.0
  - pyobjc-core: 7.1 -> 12.1 (macOS)
  - rsa: 3.4.2 -> 4.9
  - boto3: 1.17.26 -> 1.35.99
  - requests: 2.25.1 -> 2.32.3
  - Send2Trash: 1.4.2/1.5.0 -> 1.8.3 (Windows/Linux)
  - distro: 1.0.4 -> 1.9.0 (Linux)
  - pywinpty: 0.5.7 -> 2.0.14 (Windows)
  - pywin32: 300 -> 308 (Windows)
  - PyQt5: 5.15.4 -> 5.15.11 (Windows, aligned with other platforms)
- **Updated fbs dependency syntax** from egg fragment to PEP 440 Direct URL format
  for compatibility with modern pip.
- **Removed Python 3.5/3.6 compatibility workarounds**: Removed unnecessary
  `try/except TypeError` around `Path.resolve(strict=True)` and updated
  version-specific comments.
- **Reduced macOS app bundle size** from ~110MB to ~77MB by stripping unused
  Qt frameworks (QtQml, QtQuick, QtWebSockets), unused Qt plugins, and
  build-only dependencies (boto3/botocore) from the frozen bundle.
