# Gallery View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-pane "gallery" (icon-grid) view to fman, alongside the existing list view, with image thumbnails, metadata overlays (extension, resolution, size), and keyboard-driven tile resizing via `Ctrl/Cmd + +/-`.

**Architecture:** A new `GalleryView` (`QListView` in `IconMode`) lives beside the existing `FileListView` inside a `QStackedWidget` in `DirectoryPaneWidget`. Both bind to the same model and share one `QItemSelectionModel`. A separate `ThumbnailCache` module handles persistent on-disk thumbnail generation. A new `ToggleGalleryView` command in the Core plugin flips the active view, with `Ctrl/Cmd+G` as the default binding.

**Tech Stack:** Python 3.14, PyQt5, fbs build system. Tests use Python's stdlib `unittest`.

**Spec:** `docs/superpowers/specs/2026-05-11-gallery-view-design.md`

---

## File Structure

**New files:**

| Path | Responsibility |
|---|---|
| `src/main/python/fman/impl/view/gallery.py` | `GalleryView` widget + `GalleryItemDelegate` (paint logic) + pure-function helpers `truncate_filename`, `pick_overlay_layout` |
| `src/main/python/fman/impl/view/thumbnails.py` | `ThumbnailCache` — disk-cached thumbnail generation + in-memory resolution cache + `format_human_size` helper |
| `src/unittest/python/fman_unittest/impl/view/test_gallery_filename_truncation.py` | Unit tests for `truncate_filename` |
| `src/unittest/python/fman_unittest/impl/view/test_gallery_overlay_layout.py` | Unit tests for `pick_overlay_layout` |
| `src/unittest/python/fman_unittest/impl/view/test_thumbnail_cache.py` | Unit tests for `ThumbnailCache` (cache key, mtime invalidation, size buckets) |
| `src/integrationtest/python/fman_integrationtest/plugin_tests/test_gallery_view.py` | End-to-end test: toggle modes, resize tiles, persist state |

**Modified files:**

| Path | Changes |
|---|---|
| `src/main/python/fman/impl/widgets.py` | Wrap `FileListView` in a `QStackedWidget` with `GalleryView`; add `set_view_mode`, `get_view_mode`, `set_gallery_tile_size`, `get_gallery_tile_size` methods |
| `src/main/python/fman/impl/session.py` | Read/write `view_mode` and `gallery_tile_size` per pane in `_init_pane` and `_read_pane_settings` |
| `src/main/resources/base/Plugins/Core/core/commands/__init__.py` | Register `ToggleGalleryView` command |
| `src/main/resources/base/Plugins/Core/Key Bindings (Mac).json` | Add `Cmd+G → toggle_gallery_view` |
| `src/main/resources/base/Plugins/Core/Key Bindings (Linux).json` | Add `Ctrl+G → toggle_gallery_view` |
| `src/main/resources/base/Plugins/Core/Key Bindings (Windows).json` | Add `Ctrl+G → toggle_gallery_view` |
| `src/main/resources/base/Plugins/Core/Key Bindings.json` | Add platform-agnostic default if other files don't override |

---

## Task 1: Pure-function `truncate_filename` (first-3 / last-5 rule)

This is the simplest pure function. Start here to lock down the truncation rule with full TDD before any Qt code.

**Files:**
- Create: `src/main/python/fman/impl/view/gallery.py`
- Test: `src/unittest/python/fman_unittest/impl/view/test_gallery_filename_truncation.py`

- [ ] **Step 1: Write the failing test file**

Create `src/unittest/python/fman_unittest/impl/view/test_gallery_filename_truncation.py`:

```python
from fman.impl.view.gallery import truncate_filename
from unittest import TestCase


class TruncateFilenameTest(TestCase):
	# `truncate_filename(name, max_chars)` — both args drop the extension
	# externally; this function works on a pre-stripped name.
	# Rule: first 3 chars always visible. Last 5 preferred when room.

	def test_short_name_fits_unchanged(self):
		self.assertEqual('report', truncate_filename('report', 10))

	def test_exact_fit(self):
		self.assertEqual('report', truncate_filename('report', 6))

	def test_empty_name(self):
		self.assertEqual('', truncate_filename('', 10))

	def test_name_shorter_than_three(self):
		self.assertEqual('ab', truncate_filename('ab', 10))

	def test_name_shorter_than_three_with_tight_budget(self):
		self.assertEqual('ab', truncate_filename('ab', 2))

	def test_truncates_to_first3_ellipsis_last5(self):
		# 'IMG_20250508_some_long_descriptive_final' (40 chars) at 9 chars
		# → 'IMG' + '…' + 'final' = 9 chars
		self.assertEqual(
			'IMG…final',
			truncate_filename(
				'IMG_20250508_some_long_descriptive_final', 9
			)
		)

	def test_drops_suffix_when_first3_plus_ellipsis_plus_last5_too_wide(self):
		# Budget 4 chars: 'IMG…final' (9) doesn't fit, fall back to 'IMG…'
		self.assertEqual(
			'IMG…',
			truncate_filename(
				'IMG_20250508_some_long_descriptive_final', 4
			)
		)

	def test_first3_always_wins_even_with_zero_budget(self):
		# Budget 0: still show first 3 (we never sacrifice them)
		self.assertEqual(
			'IMG…',
			truncate_filename(
				'IMG_20250508_some_long_descriptive_final', 0
			)
		)

	def test_just_over_threshold(self):
		# Name is 10 chars; budget 9 → triggers truncation
		self.assertEqual('abc…ghijk', truncate_filename('abcdefghijk', 9))

	def test_eight_char_name_fits_at_eight(self):
		# Name is 8 chars and fits within budget 8 → return whole
		self.assertEqual('abcdefgh', truncate_filename('abcdefgh', 8))
```

Also create `src/unittest/python/fman_unittest/impl/view/__init__.py` if missing (it already exists per the codebase; this is a no-op safeguard).

- [ ] **Step 2: Run test to verify it fails**

Run from repo root:

```bash
python -m unittest src.unittest.python.fman_unittest.impl.view.test_gallery_filename_truncation -v
```

Expected: `ModuleNotFoundError` or `ImportError` for `fman.impl.view.gallery.truncate_filename`.

- [ ] **Step 3: Create `gallery.py` with `truncate_filename`**

Create `src/main/python/fman/impl/view/gallery.py`:

```python
"""Gallery view widget and supporting helpers.

The Qt widget classes are defined at the bottom. Pure helpers live at the
top so they can be unit-tested without spinning up a QApplication.
"""

ELLIPSIS = '…'  # "…"

# Filename truncation anchors (see design spec, section "Filename truncation"):
#   first 3 chars are sacred; last 5 are preferred but droppable.
_FIRST_N = 3
_LAST_N = 5


def truncate_filename(name, max_chars):
	"""Truncate `name` to `max_chars` while preserving the first 3 characters.

	- If `name` already fits, return it unchanged.
	- Otherwise return ``first3 + … + last5`` if that fits.
	- Otherwise return ``first3 + …`` (the last 5 are sacrificed before the
	  first 3 ever are).
	- Names shorter than 3 characters are returned unchanged.
	"""
	if len(name) <= max_chars:
		return name
	if len(name) < _FIRST_N:
		return name
	first = name[:_FIRST_N]
	last = name[-_LAST_N:]
	full = first + ELLIPSIS + last
	if len(full) <= max_chars:
		return full
	return first + ELLIPSIS
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m unittest src.unittest.python.fman_unittest.impl.view.test_gallery_filename_truncation -v
```

Expected: 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/main/python/fman/impl/view/gallery.py \
       src/unittest/python/fman_unittest/impl/view/test_gallery_filename_truncation.py
git commit -m "feat(gallery): add filename truncation with first-3/last-5 anchors"
```

---

## Task 2: Pure-function `pick_overlay_layout` (spread vs stacked)

The overlay-layout decision is also a pure function — tile width in, layout name out. TDD before any QPainter code.

**Files:**
- Modify: `src/main/python/fman/impl/view/gallery.py`
- Test: `src/unittest/python/fman_unittest/impl/view/test_gallery_overlay_layout.py`

- [ ] **Step 1: Write the failing test**

Create `src/unittest/python/fman_unittest/impl/view/test_gallery_overlay_layout.py`:

```python
from fman.impl.view.gallery import (
	pick_overlay_layout, STACK_BREAKPOINT_PX, SPREAD, STACKED
)
from unittest import TestCase


class PickOverlayLayoutTest(TestCase):

	def test_breakpoint_is_140(self):
		# Anchor the breakpoint as part of the contract.
		self.assertEqual(140, STACK_BREAKPOINT_PX)

	def test_well_above_breakpoint_is_spread(self):
		self.assertEqual(SPREAD, pick_overlay_layout(200))

	def test_at_breakpoint_is_spread(self):
		# Boundary: tile_width == 140 → SPREAD (the rule is "< 140").
		self.assertEqual(SPREAD, pick_overlay_layout(140))

	def test_one_below_breakpoint_is_stacked(self):
		self.assertEqual(STACKED, pick_overlay_layout(139))

	def test_well_below_breakpoint_is_stacked(self):
		self.assertEqual(STACKED, pick_overlay_layout(80))

	def test_returns_strings(self):
		self.assertEqual('spread', SPREAD)
		self.assertEqual('stacked', STACKED)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m unittest src.unittest.python.fman_unittest.impl.view.test_gallery_overlay_layout -v
```

Expected: `ImportError: cannot import name 'pick_overlay_layout'`.

- [ ] **Step 3: Add `pick_overlay_layout` to `gallery.py`**

Append to `src/main/python/fman/impl/view/gallery.py`:

```python
# Overlay layout (see design spec, section "Overlay layouts").
SPREAD = 'spread'
STACKED = 'stacked'
STACK_BREAKPOINT_PX = 140


def pick_overlay_layout(tile_width_px):
	"""Return ``SPREAD`` or ``STACKED`` based on tile width.

	At or above ``STACK_BREAKPOINT_PX``, the three overlay badges sit in
	the corners (TL, TR, BR). Below it, they collapse into a single
	vertical column in the top-left to avoid overlap.
	"""
	if tile_width_px >= STACK_BREAKPOINT_PX:
		return SPREAD
	return STACKED
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m unittest src.unittest.python.fman_unittest.impl.view.test_gallery_overlay_layout -v
```

Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/main/python/fman/impl/view/gallery.py \
       src/unittest/python/fman_unittest/impl/view/test_gallery_overlay_layout.py
git commit -m "feat(gallery): add overlay layout picker (spread vs stacked at 140 px)"
```

---

## Task 3: `format_human_size` helper for overlay text

Used by the BR/size overlay. Pure function, easy TDD.

**Files:**
- Create: `src/main/python/fman/impl/view/thumbnails.py`
- Test: extend `src/unittest/python/fman_unittest/impl/view/test_thumbnail_cache.py`

- [ ] **Step 1: Write the failing test**

Create `src/unittest/python/fman_unittest/impl/view/test_thumbnail_cache.py`:

```python
from fman.impl.view.thumbnails import format_human_size
from unittest import TestCase


class FormatHumanSizeTest(TestCase):

	def test_bytes(self):
		self.assertEqual('0 B', format_human_size(0))
		self.assertEqual('512 B', format_human_size(512))

	def test_kilobytes(self):
		self.assertEqual('1.0 KB', format_human_size(1024))
		self.assertEqual('1.5 KB', format_human_size(1536))

	def test_megabytes(self):
		self.assertEqual('4.2 MB', format_human_size(4_404_019))  # 4.2 * 1024^2

	def test_gigabytes(self):
		self.assertEqual('2.3 GB', format_human_size(2_469_606_195))

	def test_rounds_to_one_decimal(self):
		self.assertEqual('1.0 MB', format_human_size(1024 * 1024))
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m unittest src.unittest.python.fman_unittest.impl.view.test_thumbnail_cache -v
```

Expected: `ModuleNotFoundError: No module named 'fman.impl.view.thumbnails'`.

- [ ] **Step 3: Create `thumbnails.py` with `format_human_size`**

Create `src/main/python/fman/impl/view/thumbnails.py`:

```python
"""Persistent thumbnail cache and metadata helpers for the gallery view."""

_UNITS = ('B', 'KB', 'MB', 'GB', 'TB')


def format_human_size(num_bytes):
	"""Return a short human-readable file size, e.g. ``'4.2 MB'``."""
	size = float(num_bytes)
	for unit in _UNITS:
		if size < 1024 or unit == _UNITS[-1]:
			if unit == 'B':
				return '%d B' % int(size)
			return '%.1f %s' % (size, unit)
		size /= 1024
	# Unreachable, but keeps linters happy.
	return '%.1f %s' % (size, _UNITS[-1])
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m unittest src.unittest.python.fman_unittest.impl.view.test_thumbnail_cache -v
```

Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/main/python/fman/impl/view/thumbnails.py \
       src/unittest/python/fman_unittest/impl/view/test_thumbnail_cache.py
git commit -m "feat(gallery): add format_human_size helper for size overlays"
```

---

## Task 4: `ThumbnailCache` — cache key and bucket selection (pure logic)

The cache key and bucket-picking logic is pure and testable. Qt-backed thumbnail generation comes in the next task.

**Files:**
- Modify: `src/main/python/fman/impl/view/thumbnails.py`
- Test: extend `src/unittest/python/fman_unittest/impl/view/test_thumbnail_cache.py`

- [ ] **Step 1: Write the failing test**

Append to `src/unittest/python/fman_unittest/impl/view/test_thumbnail_cache.py`:

```python
from fman.impl.view.thumbnails import (
	cache_key, pick_size_bucket, SIZE_BUCKETS
)


class CacheKeyTest(TestCase):

	def test_returns_hex_sha1(self):
		key = cache_key('/tmp/img.jpg', 1234567890, 256)
		self.assertEqual(40, len(key))   # SHA1 hex = 40 chars
		self.assertTrue(all(c in '0123456789abcdef' for c in key))

	def test_same_inputs_same_key(self):
		k1 = cache_key('/tmp/img.jpg', 1234567890, 256)
		k2 = cache_key('/tmp/img.jpg', 1234567890, 256)
		self.assertEqual(k1, k2)

	def test_mtime_invalidates(self):
		k1 = cache_key('/tmp/img.jpg', 1, 256)
		k2 = cache_key('/tmp/img.jpg', 2, 256)
		self.assertNotEqual(k1, k2)

	def test_path_changes_key(self):
		k1 = cache_key('/tmp/img1.jpg', 1, 256)
		k2 = cache_key('/tmp/img2.jpg', 1, 256)
		self.assertNotEqual(k1, k2)

	def test_bucket_changes_key(self):
		k1 = cache_key('/tmp/img.jpg', 1, 128)
		k2 = cache_key('/tmp/img.jpg', 1, 256)
		self.assertNotEqual(k1, k2)


class PickSizeBucketTest(TestCase):

	def test_buckets_are_128_256_512(self):
		self.assertEqual((128, 256, 512), SIZE_BUCKETS)

	def test_smallest_request_uses_128(self):
		self.assertEqual(128, pick_size_bucket(80))
		self.assertEqual(128, pick_size_bucket(128))

	def test_picks_nearest_larger_bucket(self):
		self.assertEqual(256, pick_size_bucket(129))
		self.assertEqual(256, pick_size_bucket(200))
		self.assertEqual(256, pick_size_bucket(256))

	def test_above_max_uses_max(self):
		self.assertEqual(512, pick_size_bucket(513))
		self.assertEqual(512, pick_size_bucket(2048))
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m unittest src.unittest.python.fman_unittest.impl.view.test_thumbnail_cache -v
```

Expected: `ImportError: cannot import name 'cache_key'`.

- [ ] **Step 3: Add `cache_key`, `pick_size_bucket`, `SIZE_BUCKETS` to `thumbnails.py`**

Append to `src/main/python/fman/impl/view/thumbnails.py`:

```python
import hashlib

# Thumbnails are generated at one of these pixel sizes; tiles downscale
# the nearest-larger bucket at paint time. This keeps the on-disk cache
# bounded regardless of where the user puts the tile-size slider.
SIZE_BUCKETS = (128, 256, 512)


def cache_key(absolute_path, mtime_ns, size_bucket):
	"""Return the SHA1 hex key used to store a thumbnail on disk."""
	payload = '%s|%d|%d' % (absolute_path, mtime_ns, size_bucket)
	return hashlib.sha1(payload.encode('utf-8')).hexdigest()


def pick_size_bucket(requested_px):
	"""Return the smallest cache bucket >= ``requested_px``.

	If ``requested_px`` is larger than the biggest bucket, return the biggest.
	"""
	for bucket in SIZE_BUCKETS:
		if requested_px <= bucket:
			return bucket
	return SIZE_BUCKETS[-1]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m unittest src.unittest.python.fman_unittest.impl.view.test_thumbnail_cache -v
```

Expected: 12 tests pass total (5 from previous task + 4 cache_key + 3 pick_size_bucket).

- [ ] **Step 5: Commit**

```bash
git add src/main/python/fman/impl/view/thumbnails.py \
       src/unittest/python/fman_unittest/impl/view/test_thumbnail_cache.py
git commit -m "feat(gallery): add cache_key and size-bucket selection helpers"
```

---

## Task 5: `ThumbnailCache` — full Qt-backed cache

Now the I/O- and Qt-bound class. Uses a `QThreadPool` for generation; caches `QPixmap`s in memory and on disk.

**Files:**
- Modify: `src/main/python/fman/impl/view/thumbnails.py`
- Test: extend `src/unittest/python/fman_unittest/impl/view/test_thumbnail_cache.py`

- [ ] **Step 1: Write the failing test**

Append to `src/unittest/python/fman_unittest/impl/view/test_thumbnail_cache.py`:

```python
import os
import tempfile
from fman.impl.view.thumbnails import ThumbnailCache


class ThumbnailCacheDiskTest(TestCase):

	def setUp(self):
		self._tmp = tempfile.TemporaryDirectory()
		self.cache_dir = self._tmp.name

	def tearDown(self):
		self._tmp.cleanup()

	def test_get_returns_none_for_missing(self):
		cache = ThumbnailCache(self.cache_dir)
		self.assertIsNone(cache.get('/no/such/file.png', 128))

	def test_disk_path_uses_bucket_subdir_and_sha1(self):
		# Verify path layout: <cache_dir>/<bucket>/<sha1>.png
		cache = ThumbnailCache(self.cache_dir)
		path = cache._disk_path('/img.png', mtime_ns=1, size_bucket=256)
		parts = path.replace(self.cache_dir, '').strip(os.sep).split(os.sep)
		self.assertEqual(['256', parts[1]], parts)
		self.assertTrue(parts[1].endswith('.png'))
		self.assertEqual(40 + 4, len(parts[1]))   # 40 hex + '.png'

	def test_cache_dir_is_created_on_init(self):
		new_dir = os.path.join(self.cache_dir, 'subdir', 'thumbs')
		ThumbnailCache(new_dir)
		self.assertTrue(os.path.isdir(new_dir))
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m unittest src.unittest.python.fman_unittest.impl.view.test_thumbnail_cache -v
```

Expected: `ImportError: cannot import name 'ThumbnailCache'`.

- [ ] **Step 3: Implement `ThumbnailCache`**

Append to `src/main/python/fman/impl/view/thumbnails.py`:

```python
import os
from PyQt5.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, Qt, QSize
from PyQt5.QtGui import QImage, QImageReader, QPixmap


class _GeneratorSignals(QObject):
	done = pyqtSignal(str, object)   # (cache_key, QImage or None)


class _Generator(QRunnable):
	def __init__(self, key, source_path, size_bucket, signals):
		super().__init__()
		self._key = key
		self._source_path = source_path
		self._size_bucket = size_bucket
		self._signals = signals

	def run(self):
		reader = QImageReader(self._source_path)
		reader.setAutoTransform(True)
		image = reader.read()
		if image.isNull():
			self._signals.done.emit(self._key, None)
			return
		scaled = image.scaled(
			QSize(self._size_bucket, self._size_bucket),
			Qt.KeepAspectRatio,
			Qt.SmoothTransformation
		)
		self._signals.done.emit(self._key, scaled)


class ThumbnailCache(QObject):
	"""Persistent thumbnail cache.

	Stores generated thumbnails under ``<cache_dir>/<bucket>/<sha1>.png`` so
	they survive across fman restarts. Resolution metadata for source images
	is cached in memory keyed by ``(path, mtime_ns)``.
	"""

	thumbnail_ready = pyqtSignal(str)   # absolute source path

	def __init__(self, cache_dir, parent=None):
		super().__init__(parent)
		self._cache_dir = cache_dir
		os.makedirs(self._cache_dir, exist_ok=True)
		for bucket in SIZE_BUCKETS:
			os.makedirs(os.path.join(self._cache_dir, str(bucket)), exist_ok=True)
		self._mem_pixmaps = {}           # key -> QPixmap
		self._resolutions = {}           # (path, mtime_ns) -> QSize
		self._pending = set()            # set of keys currently generating
		self._signals = _GeneratorSignals()
		self._signals.done.connect(self._on_generated)
		self._pool = QThreadPool.globalInstance()
		# Path -> cache_key, used so the view can find the key to lookup
		# when `thumbnail_ready` fires.
		self._key_for = {}

	# ------------------------------------------------------------------ public
	def get(self, absolute_path, requested_px):
		"""Return a ``QPixmap`` if the thumbnail is cached, else ``None``."""
		try:
			mtime_ns = os.stat(absolute_path).st_mtime_ns
		except OSError:
			return None
		bucket = pick_size_bucket(requested_px)
		key = cache_key(absolute_path, mtime_ns, bucket)
		if key in self._mem_pixmaps:
			return self._mem_pixmaps[key]
		disk = self._disk_path(absolute_path, mtime_ns, bucket)
		if os.path.exists(disk):
			pix = QPixmap(disk)
			if not pix.isNull():
				self._mem_pixmaps[key] = pix
				return pix
		return None

	def request(self, absolute_path, requested_px):
		"""Schedule async thumbnail generation. Emits ``thumbnail_ready``."""
		try:
			mtime_ns = os.stat(absolute_path).st_mtime_ns
		except OSError:
			return
		bucket = pick_size_bucket(requested_px)
		key = cache_key(absolute_path, mtime_ns, bucket)
		if key in self._mem_pixmaps or key in self._pending:
			return
		self._pending.add(key)
		self._key_for[key] = (absolute_path, mtime_ns, bucket)
		self._pool.start(_Generator(key, absolute_path, bucket, self._signals))

	def get_resolution(self, absolute_path):
		"""Return ``QSize(w, h)`` for an image, or ``None`` if unreadable."""
		try:
			mtime_ns = os.stat(absolute_path).st_mtime_ns
		except OSError:
			return None
		cache_k = (absolute_path, mtime_ns)
		if cache_k in self._resolutions:
			return self._resolutions[cache_k]
		size = QImageReader(absolute_path).size()
		if not size.isValid():
			return None
		self._resolutions[cache_k] = size
		return size

	# ----------------------------------------------------------------- private
	def _disk_path(self, absolute_path, mtime_ns, size_bucket):
		key = cache_key(absolute_path, mtime_ns, size_bucket)
		return os.path.join(self._cache_dir, str(size_bucket), key + '.png')

	def _on_generated(self, key, image):
		self._pending.discard(key)
		if image is None or image.isNull():
			return
		path, mtime_ns, bucket = self._key_for.pop(key, (None, None, None))
		if path is None:
			return
		pix = QPixmap.fromImage(image)
		self._mem_pixmaps[key] = pix
		try:
			image.save(self._disk_path(path, mtime_ns, bucket), 'PNG')
		except OSError:
			pass
		self.thumbnail_ready.emit(path)
```

Note: the `os.makedirs(..., exist_ok=True)` line in `__init__` is what makes the "cache_dir is created on init" test pass.

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m unittest src.unittest.python.fman_unittest.impl.view.test_thumbnail_cache -v
```

Expected: 15 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/main/python/fman/impl/view/thumbnails.py \
       src/unittest/python/fman_unittest/impl/view/test_thumbnail_cache.py
git commit -m "feat(gallery): add persistent ThumbnailCache with async generation"
```

---

## Task 6: `GalleryView` widget (no overlay paint yet)

A minimal `QListView` in `IconMode` that can be shown alongside `FileListView`. Tile size is configurable; key handling and delegate paint come in later tasks.

**Files:**
- Modify: `src/main/python/fman/impl/view/gallery.py`

- [ ] **Step 1: Add the `GalleryView` class to `gallery.py`**

Append to `src/main/python/fman/impl/view/gallery.py`:

```python
from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import QListView


DEFAULT_TILE_SIZE_PX = 160
MIN_TILE_SIZE_PX = 80
MAX_TILE_SIZE_PX = 400
TILE_SIZE_STEP_PX = 20

# Vertical padding reserved beneath the icon for the filename label.
_LABEL_AREA_PX = 28
# Horizontal padding around the tile contents.
_TILE_PADDING_PX = 12


class GalleryView(QListView):
	"""Grid/icon view for `DirectoryPaneWidget`.

	Shares the model and selection-model with the pane's `FileListView`.
	"""

	def __init__(self, parent=None):
		super().__init__(parent)
		self.setViewMode(QListView.IconMode)
		self.setMovement(QListView.Static)
		self.setResizeMode(QListView.Adjust)
		self.setWrapping(True)
		self.setFlow(QListView.LeftToRight)
		self.setUniformItemSizes(True)
		self.setWordWrap(True)
		self.setSelectionMode(QListView.ExtendedSelection)
		self.setEditTriggers(QListView.NoEditTriggers)
		self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		self._tile_size = DEFAULT_TILE_SIZE_PX
		self._apply_tile_size()

	def set_tile_size(self, px):
		"""Clamp `px` to [MIN, MAX] and update the icon/grid size."""
		px = max(MIN_TILE_SIZE_PX, min(MAX_TILE_SIZE_PX, int(px)))
		if px == self._tile_size:
			return
		self._tile_size = px
		self._apply_tile_size()

	def get_tile_size(self):
		return self._tile_size

	def _apply_tile_size(self):
		icon_px = self._tile_size
		self.setIconSize(QSize(icon_px, icon_px))
		self.setGridSize(QSize(
			icon_px + _TILE_PADDING_PX,
			icon_px + _LABEL_AREA_PX
		))
```

- [ ] **Step 2: Smoke-check that the module imports cleanly**

```bash
python -c "from fman.impl.view.gallery import GalleryView, truncate_filename, pick_overlay_layout; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Run all existing unit tests to verify nothing broke**

```bash
python -m unittest discover src/unittest/python -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/main/python/fman/impl/view/gallery.py
git commit -m "feat(gallery): add GalleryView widget with tile-size API"
```

---

## Task 7: `GalleryView` keyboard handling — `Ctrl/Cmd + +/-/0`

Tile resize via keyboard. Emits a signal so the pane can persist the new size.

**Files:**
- Modify: `src/main/python/fman/impl/view/gallery.py`

- [ ] **Step 1: Add a tile-size-changed signal and key handler**

In `src/main/python/fman/impl/view/gallery.py`, edit the imports and `GalleryView`:

Change the imports near the QListView line to:

```python
from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import QListView
```

Add at the top of `GalleryView`, just under the class docstring:

```python
	tile_size_changed = pyqtSignal(int)   # new tile size in px
```

Replace `set_tile_size` with:

```python
	def set_tile_size(self, px):
		"""Clamp `px` to [MIN, MAX] and update the icon/grid size."""
		px = max(MIN_TILE_SIZE_PX, min(MAX_TILE_SIZE_PX, int(px)))
		if px == self._tile_size:
			return
		self._tile_size = px
		self._apply_tile_size()
		self.tile_size_changed.emit(px)
```

Add a `keyPressEvent` to `GalleryView`:

```python
	def keyPressEvent(self, event):
		mod = event.modifiers()
		ctrl_or_cmd = bool(mod & Qt.ControlModifier) or bool(mod & Qt.MetaModifier)
		# Qt maps Cmd to Qt.ControlModifier on macOS by default, but accept
		# Meta too in case the user has remapped.
		if ctrl_or_cmd:
			key = event.key()
			if key in (Qt.Key_Plus, Qt.Key_Equal):
				self.set_tile_size(self._tile_size + TILE_SIZE_STEP_PX)
				event.accept()
				return
			if key == Qt.Key_Minus:
				self.set_tile_size(self._tile_size - TILE_SIZE_STEP_PX)
				event.accept()
				return
			if key == Qt.Key_0:
				self.set_tile_size(DEFAULT_TILE_SIZE_PX)
				event.accept()
				return
		super().keyPressEvent(event)
```

(Note: `Qt.Key_Equal` is included because on most US keyboards the `+` key requires Shift; `Ctrl+=` is the natural unshifted form.)

- [ ] **Step 2: Smoke-check**

```bash
python -c "from fman.impl.view.gallery import GalleryView; print(GalleryView.tile_size_changed)"
```

Expected: a `pyqtSignal` object printed, no exceptions.

- [ ] **Step 3: Commit**

```bash
git add src/main/python/fman/impl/view/gallery.py
git commit -m "feat(gallery): handle Ctrl/Cmd + +/-/0 for tile resize"
```

---

## Task 8: `GalleryItemDelegate` — paint thumbnail, label, and overlays

The big paint method. Uses the helpers from tasks 1–4. Falls back to the file-type icon when no thumbnail is available.

**Files:**
- Modify: `src/main/python/fman/impl/view/gallery.py`

- [ ] **Step 1: Implement the delegate**

Append to `src/main/python/fman/impl/view/gallery.py`:

```python
from PyQt5.QtCore import QRect, QRectF
from PyQt5.QtGui import (
	QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
)
from PyQt5.QtWidgets import QStyle, QStyledItemDelegate

from fman.impl.view.thumbnails import format_human_size


_OVERLAY_BG = QColor(20, 20, 28, int(0.55 * 255))
_OVERLAY_STROKE = QColor(255, 255, 255, int(0.18 * 255))
_OVERLAY_TEXT = QColor(255, 255, 255)
_OVERLAY_INSET_PX = 4
_OVERLAY_GAP_PX = 3
_OVERLAY_PADDING_X = 5
_OVERLAY_PADDING_Y = 2
_OVERLAY_RADIUS_PX = 3
_LABEL_GAP_PX = 4
# Image extensions for which we paint overlays. Anything not in this set
# is treated as a non-image (icon-only tile).
_IMAGE_EXTS = frozenset({
	'png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'tif', 'tiff', 'heic',
	'heif', 'avif', 'svg',
})


def _is_image_path(path):
	if not path:
		return False
	dot = path.rfind('.')
	if dot < 0:
		return False
	return path[dot + 1:].lower() in _IMAGE_EXTS


class GalleryItemDelegate(QStyledItemDelegate):
	"""Paints a single gallery tile.

	Layout:
	  ┌───────────────────────────┐
	  │ <thumbnail or icon>       │   (square)
	  │                           │
	  │           ────────        │
	  │            filename       │   (1 line, truncated)
	  └───────────────────────────┘
	Image files additionally get extension / resolution / size overlays —
	spread across the corners when wide, stacked in the top-left when narrow.
	"""

	def __init__(self, get_model_url, get_thumbnail_cache, parent=None):
		super().__init__(parent)
		self._get_model_url = get_model_url
		self._get_cache = get_thumbnail_cache

	def paint(self, painter, option, index):
		painter.save()
		painter.setRenderHint(QPainter.Antialiasing, True)
		painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

		# Background (selection / hover) handled by the style.
		opt = option
		self.parent().style().drawPrimitive(
			QStyle.PE_PanelItemViewItem, opt, painter, opt.widget
		)

		tile_rect = option.rect
		tile_w = tile_rect.width()
		icon_size = min(tile_w, tile_rect.height() - _LABEL_AREA_PX)
		icon_rect = QRect(
			tile_rect.left() + (tile_w - icon_size) // 2,
			tile_rect.top(),
			icon_size,
			icon_size,
		)

		url = self._get_model_url(index) if self._get_model_url else None
		path = _local_path(url) if url else None
		cache = self._get_cache() if self._get_cache else None

		pixmap = None
		if path and _is_image_path(path) and cache is not None:
			pixmap = cache.get(path, icon_size)
			if pixmap is None:
				cache.request(path, icon_size)

		if pixmap is not None and not pixmap.isNull():
			scaled = pixmap.scaled(
				icon_rect.size(),
				Qt.KeepAspectRatio,
				Qt.SmoothTransformation,
			)
			x = icon_rect.left() + (icon_rect.width() - scaled.width()) // 2
			y = icon_rect.top() + (icon_rect.height() - scaled.height()) // 2
			painter.drawPixmap(x, y, scaled)
		else:
			# Fall back to the model's decoration (file-type icon).
			decoration = index.data(Qt.DecorationRole)
			if decoration is not None:
				icon_px = decoration.pixmap(icon_rect.size())
				if not icon_px.isNull():
					px = icon_px.scaled(
						icon_rect.size(),
						Qt.KeepAspectRatio,
						Qt.SmoothTransformation,
					)
					x = icon_rect.left() + (icon_rect.width() - px.width()) // 2
					y = icon_rect.top() + (icon_rect.height() - px.height()) // 2
					painter.drawPixmap(x, y, px)

		# Filename label
		name = index.data(Qt.DisplayRole) or ''
		stripped = _strip_ext(name)
		label_rect = QRect(
			tile_rect.left(),
			icon_rect.bottom() + _LABEL_GAP_PX,
			tile_w,
			_LABEL_AREA_PX - _LABEL_GAP_PX,
		)
		painter.setPen(QPen(option.palette.text().color()))
		font = painter.font()
		fm = QFontMetrics(font)
		max_chars = max(0, label_rect.width() // max(1, fm.averageCharWidth()))
		text = truncate_filename(stripped, max_chars)
		painter.drawText(label_rect, Qt.AlignHCenter | Qt.AlignTop, text)

		# Overlays — image files only
		if path and _is_image_path(path) and cache is not None:
			self._paint_overlays(painter, icon_rect, path, cache)

		painter.restore()

	def _paint_overlays(self, painter, icon_rect, path, cache):
		ext = path.rsplit('.', 1)[-1].upper()
		size_bytes = None
		try:
			size_bytes = os.stat(path).st_size
		except OSError:
			pass
		size_text = format_human_size(size_bytes) if size_bytes is not None else None
		resolution = cache.get_resolution(path)
		res_text = '%d×%d' % (resolution.width(), resolution.height()) \
			if resolution is not None else None

		layout = pick_overlay_layout(icon_rect.width())
		badges = [b for b in (ext, res_text, size_text) if b]
		if not badges:
			return

		if layout == SPREAD:
			# TL: ext, TR: resolution, BR: size
			if ext:
				self._draw_badge(
					painter, ext, icon_rect, anchor='tl'
				)
			if res_text:
				self._draw_badge(
					painter, res_text, icon_rect, anchor='tr'
				)
			if size_text:
				self._draw_badge(
					painter, size_text, icon_rect, anchor='br'
				)
		else:   # STACKED
			max_col_w = int(icon_rect.width() * 0.6)
			fm = QFontMetrics(painter.font())
			y = icon_rect.top() + _OVERLAY_INSET_PX
			x = icon_rect.left() + _OVERLAY_INSET_PX
			for i, text in enumerate(badges):
				display = text
				if i == 1 and res_text is not None:
					# Elide the resolution first if too long.
					display = fm.elidedText(
						text, Qt.ElideRight,
						max_col_w - 2 * _OVERLAY_PADDING_X
					)
				w, h = self._badge_size(painter, display)
				w = min(w, max_col_w)
				self._fill_badge(painter, QRect(x, y, w, h), display)
				y += h + _OVERLAY_GAP_PX

	def _badge_size(self, painter, text):
		fm = QFontMetrics(painter.font())
		w = fm.horizontalAdvance(text) + 2 * _OVERLAY_PADDING_X
		h = fm.height() + 2 * _OVERLAY_PADDING_Y
		return w, h

	def _draw_badge(self, painter, text, icon_rect, anchor):
		w, h = self._badge_size(painter, text)
		if anchor == 'tl':
			rect = QRect(
				icon_rect.left() + _OVERLAY_INSET_PX,
				icon_rect.top() + _OVERLAY_INSET_PX,
				w, h
			)
		elif anchor == 'tr':
			rect = QRect(
				icon_rect.right() - _OVERLAY_INSET_PX - w,
				icon_rect.top() + _OVERLAY_INSET_PX,
				w, h
			)
		else:   # br
			rect = QRect(
				icon_rect.right() - _OVERLAY_INSET_PX - w,
				icon_rect.bottom() - _OVERLAY_INSET_PX - h,
				w, h
			)
		self._fill_badge(painter, rect, text)

	def _fill_badge(self, painter, rect, text):
		path = QPainterPath()
		path.addRoundedRect(
			QRectF(rect),
			_OVERLAY_RADIUS_PX,
			_OVERLAY_RADIUS_PX,
		)
		painter.fillPath(path, _OVERLAY_BG)
		painter.setPen(QPen(_OVERLAY_STROKE, 1))
		painter.drawPath(path)
		painter.setPen(QPen(_OVERLAY_TEXT))
		painter.drawText(rect, Qt.AlignCenter, text)


def _strip_ext(name):
	if not name:
		return ''
	dot = name.rfind('.')
	if dot <= 0:
		return name
	return name[:dot]


def _local_path(url):
	# Only file:// URLs have meaningful thumbnails right now.
	if not url:
		return None
	if url.startswith('file://'):
		return url[len('file://'):]
	return None


# These imports are placed at the bottom of the file because they are only
# needed by the delegate's paint path; keeping them here avoids polluting
# the namespace of consumers that only need the pure helpers.
import os
```

- [ ] **Step 2: Smoke-check imports**

```bash
python -c "from fman.impl.view.gallery import GalleryItemDelegate; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add src/main/python/fman/impl/view/gallery.py
git commit -m "feat(gallery): paint thumbnails, filename labels, and overlay badges"
```

---

## Task 9: Wire `GalleryView` into `DirectoryPaneWidget` via `QStackedWidget`

Both views share the pane's model and selection model. The pane gains `set_view_mode`, `get_view_mode`, `set_gallery_tile_size`, `get_gallery_tile_size`.

**Files:**
- Modify: `src/main/python/fman/impl/widgets.py`

- [ ] **Step 1: Update imports in `widgets.py`**

In `src/main/python/fman/impl/widgets.py`, edit the import line that currently reads:

```python
from fman.impl.view import FileListView, Layout, set_selection
```

Change it to:

```python
from fman.impl.view import FileListView, Layout, set_selection
from fman.impl.view.gallery import GalleryView, GalleryItemDelegate, \
	DEFAULT_TILE_SIZE_PX
from fman.impl.view.thumbnails import ThumbnailCache
```

And in the existing `QtWidgets` import line, add `QStackedWidget`:

```python
from PyQt5.QtWidgets import QWidget, QMainWindow, QSplitter, QStatusBar, \
	QMessageBox, QInputDialog, QLineEdit, QFileDialog, QLabel, QDialog, \
	QHBoxLayout, QPushButton, QVBoxLayout, QSplitterHandle, QApplication, \
	QFrame, QAction, QSizePolicy, QProgressDialog, QProgressBar, QStackedWidget
```

- [ ] **Step 2: Construct gallery view in `DirectoryPaneWidget.__init__`**

In `widgets.py`, locate this block (around line 55-65 in `DirectoryPaneWidget.__init__`):

```python
		self._file_view = FileListView(
			self, lambda *args: controller.on_context_menu(self, *args)
		)
		self._file_view.setModel(self._model)
		self._file_view.doubleClicked.connect(self._on_doubleclicked)
		self._file_view.key_press_event_filter = self._on_key_pressed
		self.setLayout(Layout(self._location_bar, self._file_view))
		self._location_bar.setFocusProxy(self._file_view)
		self.setFocusProxy(self._file_view)
```

Replace it with:

```python
		self._file_view = FileListView(
			self, lambda *args: controller.on_context_menu(self, *args)
		)
		self._file_view.setModel(self._model)
		self._file_view.doubleClicked.connect(self._on_doubleclicked)
		self._file_view.key_press_event_filter = self._on_key_pressed

		# Gallery view shares the same model and selection model.
		self._thumbnail_cache = ThumbnailCache(
			_gallery_cache_dir(), parent=self
		)
		self._gallery_view = GalleryView(self)
		self._gallery_view.setModel(self._model)
		self._gallery_view.setSelectionModel(self._file_view.selectionModel())
		self._gallery_view.setItemDelegate(GalleryItemDelegate(
			get_model_url=self._model.url,
			get_thumbnail_cache=lambda: self._thumbnail_cache,
			parent=self._gallery_view,
		))
		self._gallery_view.doubleClicked.connect(self._on_doubleclicked)
		self._thumbnail_cache.thumbnail_ready.connect(
			lambda _path: self._gallery_view.viewport().update()
		)

		self._view_stack = QStackedWidget(self)
		self._view_stack.addWidget(self._file_view)     # index 0 = 'list'
		self._view_stack.addWidget(self._gallery_view)  # index 1 = 'gallery'

		self.setLayout(Layout(self._location_bar, self._view_stack))
		self._location_bar.setFocusProxy(self._file_view)
		self.setFocusProxy(self._file_view)
```

- [ ] **Step 3: Add `set_view_mode` / `get_view_mode` and tile-size methods**

Append these methods inside `DirectoryPaneWidget` (any sensible spot, e.g. just below `set_column_widths`):

```python
	@run_in_main_thread
	def set_view_mode(self, mode):
		"""Switch between 'list' and 'gallery'."""
		if mode == 'list':
			self._view_stack.setCurrentWidget(self._file_view)
			self.setFocusProxy(self._file_view)
		elif mode == 'gallery':
			self._view_stack.setCurrentWidget(self._gallery_view)
			self.setFocusProxy(self._gallery_view)
		else:
			raise ValueError('Unknown view mode: %r' % mode)
		self.focus()

	@run_in_main_thread
	def get_view_mode(self):
		if self._view_stack.currentWidget() is self._gallery_view:
			return 'gallery'
		return 'list'

	@run_in_main_thread
	def set_gallery_tile_size(self, px):
		self._gallery_view.set_tile_size(px)

	@run_in_main_thread
	def get_gallery_tile_size(self):
		return self._gallery_view.get_tile_size()
```

- [ ] **Step 4: Add the `_gallery_cache_dir()` helper at the bottom of `widgets.py`**

Append at the end of `widgets.py`:

```python
def _gallery_cache_dir():
	from os.path import join
	from fbs_runtime import platform
	if platform.is_windows():
		from os import environ
		base = environ.get('LOCALAPPDATA') or environ.get('APPDATA') or '.'
	elif platform.is_mac():
		from os.path import expanduser
		base = expanduser('~/Library/Caches')
	else:
		from os import environ
		from os.path import expanduser
		base = environ.get('XDG_CACHE_HOME') or expanduser('~/.cache')
	return join(base, 'fman', 'thumbnails')
```

- [ ] **Step 5: Smoke-check imports**

```bash
python -c "from fman.impl.widgets import DirectoryPaneWidget; print('ok')"
```

Expected: `ok`.

- [ ] **Step 6: Run all unit tests**

```bash
python -m unittest discover src/unittest/python -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/main/python/fman/impl/widgets.py
git commit -m "feat(gallery): mount GalleryView next to FileListView in pane"
```

---

## Task 10: Persist view mode + tile size in session

`SessionManager` already reads/writes `pane_infos`. Add two more keys.

**Files:**
- Modify: `src/main/python/fman/impl/session.py`

- [ ] **Step 1: Read mode and tile size on startup**

In `src/main/python/fman/impl/session.py`, find `_init_pane` (around line 94). After the existing `col_widths = pane_info.get('col_widths')` line, add:

```python
		view_mode = pane_info.get('view_mode')
		gallery_tile_size = pane_info.get('gallery_tile_size')
```

And after the existing `if col_widths:` block (around line 143-149), add:

```python
		if gallery_tile_size:
			try:
				pane._widget.set_gallery_tile_size(int(gallery_tile_size))
			except (ValueError, TypeError):
				pass
		if view_mode in ('list', 'gallery'):
			try:
				pane._widget.set_view_mode(view_mode)
			except (ValueError, AttributeError):
				pass
```

- [ ] **Step 2: Write mode and tile size on close**

In the same file, locate `_read_pane_settings` (around line 167):

```python
	def _read_pane_settings(self, pane):
		return {
			'location': pane.get_location(),
			'col_widths': pane.get_column_widths()
		}
```

Replace it with:

```python
	def _read_pane_settings(self, pane):
		widget = pane._widget
		return {
			'location': pane.get_location(),
			'col_widths': pane.get_column_widths(),
			'view_mode': widget.get_view_mode(),
			'gallery_tile_size': widget.get_gallery_tile_size(),
		}
```

- [ ] **Step 3: Smoke-check**

```bash
python -c "from fman.impl.session import SessionManager; print('ok')"
```

Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add src/main/python/fman/impl/session.py
git commit -m "feat(gallery): persist view mode and tile size per pane"
```

---

## Task 11: `ToggleGalleryView` command in the Core plugin

A `DirectoryPaneCommand` that flips the focused pane's view mode.

**Files:**
- Modify: `src/main/resources/base/Plugins/Core/core/commands/__init__.py`

- [ ] **Step 1: Add the command class**

In `src/main/resources/base/Plugins/Core/core/commands/__init__.py`, locate the existing `MoveCursorPageDown` command (around line 79). Below it, add:

```python
class ToggleGalleryView(DirectoryPaneCommand):

	aliases = ('Toggle Gallery View',)

	def __call__(self):
		widget = self.pane._widget
		current = widget.get_view_mode()
		new_mode = 'gallery' if current == 'list' else 'list'
		widget.set_view_mode(new_mode)
```

- [ ] **Step 2: Smoke-check the plugin loads**

```bash
python -c "
import sys
sys.path.insert(0, 'src/main/resources/base/Plugins/Core')
from core.commands import ToggleGalleryView
print(ToggleGalleryView.aliases)
"
```

Expected: `('Toggle Gallery View',)`.

- [ ] **Step 3: Commit**

```bash
git add src/main/resources/base/Plugins/Core/core/commands/__init__.py
git commit -m "feat(gallery): add toggle_gallery_view command"
```

---

## Task 12: Default keyboard bindings for `toggle_gallery_view`

`Ctrl+G` on Linux/Windows, `Cmd+G` on macOS.

**Files:**
- Modify: `src/main/resources/base/Plugins/Core/Key Bindings (Mac).json`
- Modify: `src/main/resources/base/Plugins/Core/Key Bindings (Linux).json`
- Modify: `src/main/resources/base/Plugins/Core/Key Bindings (Windows).json`

- [ ] **Step 1: Mac binding**

In `src/main/resources/base/Plugins/Core/Key Bindings (Mac).json`, find the line containing `"command": "toggle_hidden_files"` (around line 11). On a new line after it (and inside the array), add:

```json
	{ "keys": ["Cmd+G"], "command": "toggle_gallery_view" },
```

- [ ] **Step 2: Linux binding**

In `src/main/resources/base/Plugins/Core/Key Bindings (Linux).json`, find the entry for `toggle_hidden_files` (or similar nearby entry) and add a line in the same array:

```json
	{ "keys": ["Ctrl+G"], "command": "toggle_gallery_view" },
```

- [ ] **Step 3: Windows binding**

In `src/main/resources/base/Plugins/Core/Key Bindings (Windows).json`, add the same Ctrl+G binding:

```json
	{ "keys": ["Ctrl+G"], "command": "toggle_gallery_view" },
```

- [ ] **Step 4: Verify JSON is valid**

```bash
python -c "
import json
for p in [
    'src/main/resources/base/Plugins/Core/Key Bindings (Mac).json',
    'src/main/resources/base/Plugins/Core/Key Bindings (Linux).json',
    'src/main/resources/base/Plugins/Core/Key Bindings (Windows).json',
]:
    json.load(open(p))
print('ok')
"
```

Expected: `ok` (no JSON decode errors).

- [ ] **Step 5: Commit**

```bash
git add "src/main/resources/base/Plugins/Core/Key Bindings (Mac).json" \
       "src/main/resources/base/Plugins/Core/Key Bindings (Linux).json" \
       "src/main/resources/base/Plugins/Core/Key Bindings (Windows).json"
git commit -m "feat(gallery): bind Ctrl/Cmd+G to toggle_gallery_view"
```

---

## Task 13: Integration test — toggle, resize, persist

End-to-end coverage of the user-visible flow. Mirrors the pattern of `src/integrationtest/python/fman_integrationtest/plugin_tests/test_directory_pane_listener.py`.

**Files:**
- Create: `src/integrationtest/python/fman_integrationtest/plugin_tests/test_gallery_view.py`

- [ ] **Step 1: Look at an existing integration test for the pattern**

```bash
head -60 src/integrationtest/python/fman_integrationtest/plugin_tests/test_directory_pane_listener.py
```

Expected output: a test class that uses `self._app` / `self._pane` patterns. Mirror this in the new test.

- [ ] **Step 2: Write the failing integration test**

Create `src/integrationtest/python/fman_integrationtest/plugin_tests/test_gallery_view.py`:

```python
"""Integration tests for the per-pane gallery view feature."""

from fman_integrationtest.fman_test_case import FmanTestCase


class GalleryViewTest(FmanTestCase):

	def test_default_mode_is_list(self):
		pane = self._main_window.get_panes()[0]
		self.assertEqual('list', pane._widget.get_view_mode())

	def test_toggle_command_flips_mode(self):
		pane = self._main_window.get_panes()[0]
		self._main_window.run_command(
			'toggle_gallery_view', pane=pane
		)
		self.assertEqual('gallery', pane._widget.get_view_mode())
		self._main_window.run_command(
			'toggle_gallery_view', pane=pane
		)
		self.assertEqual('list', pane._widget.get_view_mode())

	def test_panes_are_independent(self):
		left, right = self._main_window.get_panes()[:2]
		self._main_window.run_command('toggle_gallery_view', pane=left)
		self.assertEqual('gallery', left._widget.get_view_mode())
		self.assertEqual('list', right._widget.get_view_mode())

	def test_default_tile_size_is_160(self):
		pane = self._main_window.get_panes()[0]
		self.assertEqual(160, pane._widget.get_gallery_tile_size())

	def test_set_tile_size_clamps_to_max(self):
		pane = self._main_window.get_panes()[0]
		pane._widget.set_gallery_tile_size(99_999)
		self.assertEqual(400, pane._widget.get_gallery_tile_size())

	def test_set_tile_size_clamps_to_min(self):
		pane = self._main_window.get_panes()[0]
		pane._widget.set_gallery_tile_size(1)
		self.assertEqual(80, pane._widget.get_gallery_tile_size())
```

If `FmanTestCase` / command-running APIs in this repo differ from the assumptions above, look at `src/integrationtest/python/fman_integrationtest/plugin_tests/test_directory_pane_listener.py` and another existing test to copy the exact pattern (e.g. how to obtain `_main_window`, how to invoke a command).

- [ ] **Step 3: Run the integration test**

The integration test runner is launched the same way other fman integration tests are launched in this repo (consult `src/integrationtest/python/README` if present or look at `build.py` for the entry point). A typical invocation is:

```bash
python -m unittest discover src/integrationtest/python -v -p 'test_gallery_view.py'
```

Expected: 6 tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/integrationtest/python/fman_integrationtest/plugin_tests/test_gallery_view.py
git commit -m "test(gallery): integration tests for toggle, tile size, isolation"
```

---

## Task 14: Manual smoke test in the running app

Verification before merging: type-checking and unit tests verify code correctness, not feature correctness.

**Files:** none

- [ ] **Step 1: Launch fman from source**

```bash
python -m fbs run
```

(Or whatever the repo's launch command is — consult `build.py`.)

- [ ] **Step 2: Verify each acceptance criterion in the running app**

Manually verify each:

  1. Press `Ctrl/Cmd+G` in a pane → it switches to a grid of tiles. Press again → returns to list.
  2. Navigate to a folder with images and non-image files. Images show real thumbnails (may briefly show the file-type icon as placeholder, then update). Non-images show the standard file-type icon, no overlays.
  3. On an image tile, verify (at default 160 px size) **three** overlays in corners: extension TL, resolution TR, size BR. Thumbnail visible through the translucent badges.
  4. Press `Ctrl/Cmd+ -` repeatedly until the tile is below 140 px. The overlays should restack into a single top-left column — no overlap.
  5. Press `Ctrl/Cmd+ +` to grow. Press `Ctrl/Cmd+ 0` to reset to 160 px.
  6. Filenames: at small tile widths, verify the **first 3 characters** of long filenames are visible (e.g. `IMG…final`).
  7. Toggle gallery on one pane only; verify the other pane stays in list view (per-pane independence).
  8. Quit fman. Relaunch. Both the view mode and the chosen tile size should be restored per pane.

- [ ] **Step 3: Note any defects and fix in subsequent tasks**

If any of the above checks fail, file a follow-up task and fix before merging.

- [ ] **Step 4: Final commit (if any fixes were needed) or proceed to PR**

```bash
git status
```

If clean, the branch is ready for PR.

---

## Self-Review

**Spec coverage:** Walked the spec section-by-section.

- Goals (per-pane, thumbnails for images, icons for others, overlays, leave list view untouched, persist mode + size) — covered by tasks 9, 10, 11.
- Non-goals — respected.
- Architecture (QStackedWidget, shared model + selection model) — task 9.
- `GalleryView` — tasks 6, 7.
- `GalleryItemDelegate` (four layers, two layouts, translucency, backdrop blur via stroke approximation) — task 8.
- `ThumbnailCache` (sha1 key, mtime invalidation, buckets, async generation) — tasks 4, 5.
- Filename truncation (first-3 / last-5 rule) — task 1.
- Tile size (160 default, 80–400, ±20 step, Ctrl+0 reset) — task 7.
- View toggle command + binding — tasks 11, 12.
- Keyboard navigation in gallery — `QListView` `IconMode` provides this natively; verified in task 14 manual smoke.
- Edge cases (filter bar, ".." entry, sort changes, drag-drop) — drag/drop and selection inherited via shared selection model + standard `QListView` behaviour; filter bar operates on the shared model. Mentioned in manual smoke. (No code change required.)
- Tests — covered by tasks 1, 2, 4, 5 (unit) + task 13 (integration).

**Placeholder scan:** No `TBD`, no "implement later", no "similar to Task N". All code blocks are complete.

**Type consistency:** Cross-checked method names — `set_view_mode` / `get_view_mode` / `set_gallery_tile_size` / `get_gallery_tile_size` / `set_tile_size` / `get_tile_size` / `toggle_gallery_view` are used consistently across all tasks. `SIZE_BUCKETS`, `STACK_BREAKPOINT_PX`, `SPREAD`, `STACKED` constants line up between definition (tasks 2, 4) and usage (task 8).

One gap: tasks 8 references `format_human_size`, `pick_overlay_layout`, `truncate_filename`, `SPREAD`, `STACKED` — all defined in tasks 1, 2, 3 in `gallery.py` / `thumbnails.py`. Verified the import in task 8 step 1 covers `format_human_size`; the rest are in the same module.
