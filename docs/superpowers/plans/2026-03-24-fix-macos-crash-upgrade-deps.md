# Fix macOS Crash: Upgrade Dependencies for Python 3.9 + macOS 26

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the SIGSEGV crash on macOS 26.3.1 caused by outdated pyobjc-core 7.1 and other dependencies, by upgrading all requirements to Python 3.9-compatible modern versions.

**Architecture:** The crash occurs in `PyObjCClass_NewMetaClass` when the old pyobjc-core 7.1 (built for Python 3.6) tries to load Objective-C classes on macOS 26. The app runs as X86-64 under Rosetta on Apple Silicon. The fix is to upgrade pyobjc-core and all other outdated dependencies to versions compatible with Python 3.9 and modern macOS, then clean up legacy Python 3.5/3.6 compatibility code.

**Tech Stack:** Python 3.9, PyQt5, PyInstaller, pyobjc-core, fbs (fman build system)

---

## Context

### Crash Analysis

From `error.log`:
- **Signal:** `EXC_BAD_ACCESS (SIGSEGV)` at `KERN_INVALID_ADDRESS 0x8`
- **Crash location:** `PyObjCClass_NewMetaClass` in `_objc.cpython-36m-darwin.so`
- **Call chain:** Qt timer fires -> Python slot -> `objc.loadBundle()` -> `PyObjC_GetClassList` -> crash
- **Root cause:** pyobjc-core 7.1 binary (compiled for Python 3.6) is incompatible with macOS 26's Objective-C runtime under Rosetta translation
- **The installed app** at `/Applications/fman.app` was frozen with Python 3.6 binaries (note `cpython-36m-darwin.so`), even though the README says Python 3.9 for development

### Proposed Solution (from app creators) — NOT applicable

The creators suggested `sudo pacman -S qt5-wayland` + `QT_QPA_PLATFORM=wayland` — this is an **Arch Linux/Wayland** fix, not applicable to macOS which uses Cocoa.

### Key Files

```
requirements/
├── base.txt          # Core deps: fbs, PyQt5, PyInstaller, rsa, tinycss, boto3, requests
├── mac.txt           # macOS: osxtrash, pyobjc-core (THE CRASH CULPRIT)
├── linux.txt         # Linux: Send2Trash, distro
├── windows.txt       # Windows: PyQt5 override, Send2Trash, adodbapi, pywinpty, pywin32
├── ubuntu.txt        # Ubuntu: pgi
├── arch.txt          # Arch: (just includes linux.txt)
└── fedora.txt        # Fedora: (just includes ubuntu.txt)

src/main/resources/base/Plugins/Core/core/
├── __init__.py                    # Has Python 3.6 comment (line 102)
└── fs/local/__init__.py           # Has Python 3.5/3.6 compat code (lines 222-229)

src/main/python/fman/impl/plugins/
└── error.py                       # Has Python 3.5.3 comments (lines 69, 86, 101, 117, 122)
```

---

### Task 1: Upgrade macOS Requirements (THE CRASH FIX)

**Files:**
- Modify: `requirements/mac.txt`

- [ ] **Step 1: Update pyobjc-core to latest compatible version**

pyobjc-core 7.1 is the direct cause of the crash. Upgrade to 10.3.1 (latest stable, supports Python 3.9+ and macOS 14+/Apple Silicon natively):

```
-r base.txt
osxtrash==1.6
pyobjc-core==10.3.1
```

Note: `osxtrash==1.6` is kept as-is — it's a simple C extension with no known Python 3.9 issues. If it fails to install in Task 6 testing, replace with `Send2Trash==1.8.3`.

- [ ] **Step 2: Commit**

```bash
git add requirements/mac.txt
git commit -m "fix: upgrade pyobjc-core 7.1 -> 10.3.1 to fix SIGSEGV on macOS 26

pyobjc-core 7.1 (built for CPython 3.6) crashes in PyObjCClass_NewMetaClass
when loading Objective-C classes on macOS 26.3.1 under Rosetta.
Version 10.3.1 has native Apple Silicon support and modern macOS compatibility."
```

---

### Task 2: Upgrade Base Requirements

**Files:**
- Modify: `requirements/base.txt`

- [ ] **Step 1: Update dependency versions**

Current → Target versions with rationale:

| Package | Current | Target | Why |
|---------|---------|--------|-----|
| PyQt5 | 5.15.11 | 5.15.11 | Keep (already latest 5.15.x) |
| PyInstaller | 4.4 | 6.11.1 | 4.4 is EOL, 6.x has Python 3.9+ fixes |
| rsa | 3.4.2 | 4.9 | Security updates, Python 3.9 compat |
| tinycss | 0.4 | 0.4 | Keep (stable, no breaking changes) |
| boto3 | 1.17.26 | 1.35.99 | Major gap from 2021, security/compat fixes |
| requests | 2.25.1 | 2.32.3 | Security patches |

Update `requirements/base.txt` to:

```
http://build-system.fman.io/pro/b5aab865-bd29-4f23-992c-0eb4f3a24f33/0.9.4#egg=fbs[sentry]
PyQt5==5.15.11
PyInstaller==6.11.1
rsa==4.9
tinycss==0.4
boto3==1.35.99
requests==2.32.3
```

Note: The `fbs` URL is a private build system dependency — do NOT change this URL. If fbs 0.9.4 has issues with PyInstaller 6.x, see the troubleshooting section at the end of this plan.

- [ ] **Step 2: Commit**

```bash
git add requirements/base.txt
git commit -m "chore: upgrade base dependencies for Python 3.9 compatibility

PyInstaller 4.4 -> 6.11.1 (EOL fix)
rsa 3.4.2 -> 4.9 (security)
boto3 1.17.26 -> 1.35.99 (3 years of fixes)
requests 2.25.1 -> 2.32.3 (security patches)"
```

---

### Task 3: Upgrade Windows Requirements

**Files:**
- Modify: `requirements/windows.txt`

- [ ] **Step 1: Update dependency versions**

| Package | Current | Target | Why |
|---------|---------|--------|-----|
| PyQt5 | 5.15.4 | 5.15.11 | Align with base.txt |
| Send2Trash | 1.4.2 | 1.8.3 | Python 3.9 compat |
| adodbapi | 2.6.0.7 | 2.6.0.7 | Keep (stable) |
| pywinpty | 0.5.7 (wheel) | 2.0.14 | Old wheel was cp39-specific, 2.x is on PyPI |
| pywin32 | 300 | 308 | Python 3.9+ fixes |

Update `requirements/windows.txt` to:

```
-r base.txt
PyQt5==5.15.11
# Note: Send2Trash 1.5.0 has no effect on Windows!
Send2Trash==1.8.3
adodbapi==2.6.0.7
pywinpty==2.0.14
pywin32==308
```

Note: The old `pywinpty` was installed from a direct wheel URL (`https://download.lfd.uci.edu/...cp39-cp39-win_amd64.whl`). Version 2.x is available directly from PyPI, so the wheel URL is no longer needed.

- [ ] **Step 2: Commit**

```bash
git add requirements/windows.txt
git commit -m "chore: upgrade Windows dependencies

PyQt5 5.15.4 -> 5.15.11 (align with base)
Send2Trash 1.4.2 -> 1.8.3
pywinpty 0.5.7 (wheel) -> 2.0.14 (PyPI)
pywin32 300 -> 308"
```

---

### Task 4: Upgrade Linux Requirements

**Files:**
- Modify: `requirements/linux.txt`

Note: `ubuntu.txt`, `arch.txt`, and `fedora.txt` need no changes — they just reference `linux.txt`. `pgi==0.0.11.1` in ubuntu.txt is unmaintained but only used for GTK integration; leave it as-is.

- [ ] **Step 1: Update linux.txt**

```
-r base.txt
Send2Trash==1.8.3
distro==1.9.0
```

- [ ] **Step 2: Commit**

```bash
git add requirements/linux.txt
git commit -m "chore: upgrade Linux dependencies

Send2Trash 1.5.0 -> 1.8.3
distro 1.0.4 -> 1.9.0"
```

---

### Task 5: Clean Up Legacy Python 3.5/3.6 Compatibility Code

**Files:**
- Modify: `src/main/resources/base/Plugins/Core/core/fs/local/__init__.py:222-229`
- Modify: `src/main/resources/base/Plugins/Core/core/__init__.py:102`
- Modify: `src/main/python/fman/impl/plugins/error.py:69,86,101,117,122`

- [ ] **Step 1: Simplify Path.resolve() in local/__init__.py**

In `src/main/resources/base/Plugins/Core/core/fs/local/__init__.py`, replace lines 222-229:

**Before:**
```python
		try:
			try:
				path = p.resolve(strict=True)
			except TypeError:
				# fman's "production Python version" is 3.6 but we want to be
				# able to develop using 3.5 as well. So add this workaround for
				# Python < 3.6:
				path = p.resolve()
		except FileNotFoundError:
```

**After:**
```python
		try:
			path = p.resolve(strict=True)
		except FileNotFoundError:
```

The inner try/except for `TypeError` is unnecessary — `strict` parameter has been available since Python 3.6 and we require 3.9.

- [ ] **Step 2: Update comment in core/__init__.py**

In `src/main/resources/base/Plugins/Core/core/__init__.py`, line 102, update the comment:

**Before:**
```python
			# This can occur in at least Python 3.6 on Windows. To reproduce:
```

**After:**
```python
			# This can occur on Windows. To reproduce:
```

- [ ] **Step 3: Update comments in error.py**

In `src/main/python/fman/impl/plugins/error.py`, update Python version references in comments. These are documentation-only changes — the code logic is correct and stays the same:

- Line 69: `Copied and adapted from Python 3.5.3's` → `Copied and adapted from Python's`
- Line 86: `# This differs from Python 3.5.3's implementation:` → `# This differs from stdlib's implementation:`
- Line 101: same change as line 86
- Line 117: same change as line 86
- Line 122: same change as line 86

- [ ] **Step 4: Commit**

```bash
git add src/main/resources/base/Plugins/Core/core/fs/local/__init__.py \
        src/main/resources/base/Plugins/Core/core/__init__.py \
        src/main/python/fman/impl/plugins/error.py
git commit -m "chore: remove Python 3.5/3.6 compatibility workarounds

Python 3.9 is the minimum version. Remove unnecessary try/except
for Path.resolve(strict=True) and update version references in comments."
```

---

### Task 6: Verify Installation on macOS

- [ ] **Step 1: Create a fresh virtual environment and install**

```bash
python3.9 -m venv /tmp/fman-test-venv
source /tmp/fman-test-venv/bin/activate
pip install -Ur requirements/mac.txt
```

Expected: All packages install successfully. If `osxtrash==1.6` fails to compile, replace it with `Send2Trash==1.8.3` in `requirements/mac.txt`.

- [ ] **Step 2: Verify fman starts**

```bash
python build.py run
```

Expected: fman launches without SIGSEGV. The dual-pane file manager window should appear.

- [ ] **Step 3: Clean up test venv**

```bash
deactivate
rm -rf /tmp/fman-test-venv
```

- [ ] **Step 4: Commit any fixes from testing**

If any dependency versions needed adjusting during testing, commit those changes.

---

## Troubleshooting

### fbs 0.9.4 incompatible with PyInstaller 6.x

fbs 0.9.4 was built for PyInstaller 4.x. If it fails with PyInstaller 6.x (e.g., import errors or changed APIs), try:

1. **First fallback:** PyInstaller 5.13.2 (last 5.x release) — closer to 4.x API
2. **Second fallback:** PyInstaller 4.10 (last 4.x release) — minimal change from 4.4

Update `requirements/base.txt` accordingly and re-test.

### osxtrash 1.6 fails to compile

osxtrash is a small C extension. If it doesn't compile on modern macOS/Xcode:

1. Replace `osxtrash==1.6` with `Send2Trash==1.8.3` in `requirements/mac.txt`
2. Check if fman's code imports `osxtrash` directly — search for `import osxtrash` and update if needed

### rsa 4.x API changes

rsa 4.x changed some APIs from 3.x. The licensing code in `src/main/python/fman/impl/licensing.py` uses RSA for license key verification. Key changes:
- `rsa.verify()` signature is the same in 4.x
- `rsa.PublicKey.load_pkcs1()` is the same
- If there are import errors, check for `rsa.bigfile` or `rsa.varblock` usage (removed in 4.x)
