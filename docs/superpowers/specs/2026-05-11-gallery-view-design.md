# Gallery View — Design

**Status:** Approved
**Date:** 2026-05-11
**Scope:** Per-pane toggle between the existing list view and a new grid/gallery view, with image thumbnails, metadata overlays, and keyboard-driven tile resizing.

## Goals

- Add an alternative file view mode (gallery / icon grid) selectable independently on each pane.
- Show image thumbnails for image files, file-type icons for everything else.
- Overlay key metadata directly on image tiles (extension, resolution, size).
- Keep the existing list view untouched and fully working.
- Persist mode and tile size per pane across sessions.

## Non-goals

- Replacing or rewriting the existing `FileListView`.
- Folder-level recursive thumbnail previews (e.g., showing nested image inside a folder tile).
- Video, document, or PDF thumbnail generation (only image formats Qt natively supports).
- Drag-resize via mouse drag (only keyboard `Ctrl/Cmd +/-`).

## Architecture

```
DirectoryPaneWidget
├── LocationBar
└── QStackedWidget                ← new container
    ├── FileListView   (existing — list / table mode)
    └── GalleryView    (new       — icon / grid mode)
```

- Both views are bound to the same `SortedFileSystemModel` and share a single `QItemSelectionModel`, so cursor and selection stay in sync across toggles.
- `DirectoryPaneWidget` exposes:
  - `set_view_mode(mode: 'list' | 'gallery')`
  - `get_view_mode() -> 'list' | 'gallery'`
- Mode + tile size persist in fman's session state (`session.py`), keyed per pane.

## Components

### `GalleryView` — `src/main/python/fman/impl/view/gallery.py`

- Subclass of `QListView` configured with:
  - `viewMode = IconMode`
  - `movement = Static`
  - `resizeMode = Adjust`
  - `wordWrap = True`, `uniformItemSizes = True`, `flow = LeftToRight`
- Reuses the existing `DragAndDrop` mixin so drag/drop matches list view.
- Owns its own `GalleryItemDelegate` for tile rendering.
- Catches `Ctrl/Cmd + Plus / Minus / 0` in `keyPressEvent` for tile resizing.
- Emits the same public signals (`doubleClicked`, context-menu events) that `DirectoryPaneWidget` already listens for.

### `GalleryItemDelegate`

Renders each tile in four layers:

1. **Background** — selection/hover state from the active style.
2. **Thumbnail or icon** — square area at top of tile, sized `tile_size − padding`.
   - Image files: thumbnail via `ThumbnailCache`, file-type icon as placeholder until ready.
   - Non-image files / folders: file-type icon (the existing icon used by list view).
3. **Filename label** — single line beneath the thumbnail, extension stripped, truncated per the rule below.
4. **Metadata overlays** — image files **only**. Two responsive layouts (described below).

### Overlay styling

- Each overlay is a small rounded badge with **semi-transparent dark background** so the image stays partially visible through it.
- Background: `rgba(20, 20, 28, 0.55)` — dark enough for white text contrast (WCAG AA on typical photo content), light enough to see the image underneath.
- A 1 px white-at-20% inner stroke and a subtle `backdrop-filter: blur(2px)` (where supported) preserves legibility over busy thumbnails.
- Text: white, `font-weight: 600`, font-size proportional to tile size — clamped between 9 px and 12 px.
- Corner inset from tile edge: 4 px.
- Inter-badge spacing in stacked mode: 3 px.

### Overlay layouts

The delegate measures the tile width and picks one of two layouts so badges never overlap:

**A. Spread (default, `tile_width ≥ 140 px`)**

```
┌────────────────────────────┐
│ [JPG]            [1920×1080] │   ← top corners
│                            │
│         thumbnail          │
│                            │
│                  [4.2 MB] │   ← bottom-right
└────────────────────────────┘
```

- Top-left: extension (uppercase, e.g. `JPG`).
- Top-right: resolution (e.g. `1920×1080`).
- Bottom-right: file size (human-readable, e.g. `4.2 MB`).

**B. Stacked (small tiles, `tile_width < 140 px`)**

All three badges collapse into a single vertical column in the top-left corner, each on its own line, full-width to the longest badge in the stack:

```
┌──────────────────┐
│ [JPG       ]     │
│ [1920×1080 ]     │
│ [4.2 MB    ]     │
│                  │
│   thumbnail      │
│                  │
└──────────────────┘
```

- Stacked column never exceeds 60% of the tile width — if a badge's natural width would push past that, its text is elided with `…` (resolution gets priority elision: `1920×…`; size text never elides, it's already short).
- This guarantees that the right portion of the thumbnail remains uncovered even on the smallest tiles, and badges never overlap each other.

**Threshold:** the 140 px breakpoint is a constant in the delegate (`STACK_BREAKPOINT_PX`), tuned to be just above where the spread layout's three corner badges start to collide with a typical resolution string. Easy to adjust.

### `ThumbnailCache` — `src/main/python/fman/impl/view/thumbnails.py`

- Persistent disk cache under fman's user cache dir: `<cache_dir>/thumbnails/`.
- Cache key: SHA1 hash of `f"{absolute_path}|{mtime_ns}|{size_bucket}"`.
- Size buckets: **128, 256, 512 px**. Tile renders downscale the nearest-larger bucket; cache size stays bounded regardless of slider position.
- API:
  - `get(url, size_bucket) -> Optional[QPixmap]` — sync cache lookup.
  - `request(url, size_bucket, callback)` — schedules async generation on a `QThreadPool`; callback fires with the new `QPixmap` on the main thread.
- Resolution metadata (width × height) is read once via `QImageReader.size()` and held in an in-memory `WeakValueDictionary` keyed by `(path, mtime)`.
- Supported formats: `QImageReader.supportedImageFormats()`.

## Filename truncation

Filenames in the label follow a two-anchor rule:

- **First 3 characters always visible.** This is the strongest constraint — never sacrificed.
- **Last 5 characters preferred** — kept whenever the tile width allows it.
- **No truncation when avoidable.** If the stripped name fits the tile width, show it whole.

Algorithm:

1. Strip the extension.
2. If the stripped name fits the tile width → show it as-is.
3. Otherwise, try `<first3>…<last5>`. If it fits, show that.
4. If even that doesn't fit → drop the suffix and show `<first3>…`. First 3 wins over last 5.
5. The prefix in step 3 is always exactly the first 3 chars — we don't try to grow it. Simpler, more predictable across the grid.

Examples:

| Original (no ext)                          | Tile width | Output         |
|--------------------------------------------|------------|----------------|
| `report`                                   | 120 px     | `report`       |
| `IMG_20250508_some_long_descriptive_final` | 120 px     | `IMG…final`    |
| `IMG_20250508_some_long_descriptive_final` | 80 px      | `IMG…`         |
| `ab`                                       | any        | `ab` (no truncation, name shorter than first-3) |

## Tile size & Ctrl/Cmd + +/-

- Default: **160 px**.
- Range: **80 px – 400 px**, continuous **±20 px** per key press.
- `Ctrl/Cmd + 0` resets to default.
- Implementation: on each step, set both `iconSize` and `gridSize` on the `QListView` so the thumbnail and tile grow in lockstep.
- Tile size persists per pane.

## View toggle command

- Register a new application command `toggle_gallery_view`.
- Default keybinding: **Ctrl+G** / **Cmd+G**.
- Command palette caption: "Toggle Gallery View".
- The command flips the focused pane's view mode.

## Keyboard navigation

`QListView`'s `IconMode` handles 2D arrow navigation, Home/End, PageUp/PageDown out of the box. `DirectoryPaneWidget`'s existing `move_cursor_*` methods need parallel wiring on the gallery view so the public pane API is uniform — they delegate to `QListView`'s built-ins instead of the custom `QTableView` logic.

## Edge cases

| Case | Behaviour |
|---|---|
| Switching mode mid-load | Both views share the model; loading streams into both. |
| Filter bar active | Works unchanged; it operates on the model. |
| `..` entry / folders | File-type icon, no metadata overlays. |
| Very large folders | Lazy thumbnails + viewport clipping — only visible tiles paint or request thumbnails. |
| Unknown / corrupt image | Falls back to file-type icon; resolution overlay omitted; size overlay still shown. |
| Sort changes while in gallery | Model resorts; gallery reflows naturally. Switching back to list shows the new sort. |
| Drag & drop | Reuses `DragAndDrop` mixin; behaviour matches list view. |

## Testing

### Unit tests (`src/unittest/python/fman_unittest/impl/view/`)

- `test_gallery_filename_truncation.py` — exhaustive cases: short, exact-fit, just-over, very long, names shorter than 3, first-3 always preserved, last-5 dropped when tile too narrow.
- `test_gallery_overlay_layout.py` — overlay layout switches to stacked at `tile_width < 140 px`; badges never overlap each other or the right edge of the tile.
- `test_thumbnail_cache.py` — cache key collisions, mtime invalidation, size-bucket selection, eviction.

### Integration tests (`src/integrationtest/python/`)

- Toggle modes via command, verify cursor + selection preserved.
- `Ctrl++` / `Ctrl+-` step, clamping at min/max, `Ctrl+0` reset.
- Image file shows overlays; non-image file does not.
- Persistence: set gallery + tile 240 px, restart, verify restored.

## File touch list

New:
- `src/main/python/fman/impl/view/gallery.py`
- `src/main/python/fman/impl/view/thumbnails.py`
- `src/unittest/python/fman_unittest/impl/view/test_gallery_filename_truncation.py`
- `src/unittest/python/fman_unittest/impl/view/test_gallery_overlay_layout.py`
- `src/unittest/python/fman_unittest/impl/view/test_thumbnail_cache.py`
- `src/integrationtest/python/fman_integrationtest/plugin_tests/test_gallery_view.py`

Modified:
- `src/main/python/fman/impl/widgets.py` — wrap views in `QStackedWidget`, add `set_view_mode` / `get_view_mode`.
- `src/main/python/fman/impl/session.py` (or equivalent) — persist view mode + tile size per pane.
- Core plugin command registry — register `toggle_gallery_view` + default Ctrl/Cmd+G binding.
