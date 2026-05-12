# Agent guidelines

## Testing

After code changes affecting UI/features, **visual confirmation is required**:
- Launch the compiled app and verify the feature actually works.
- Use AppleScript / `osascript` on macOS to drive the app when possible.
- Don't claim feature success on green tests alone.

## TODO: gallery-view followups

Architectural cleanups deferred from `/simplify` on `feature/gallery-view` — too
broad for a review pass, worth doing as standalone changes:

- [ ] Extract a `DragAndDrop` mixin from `fman.impl.view.drag_and_drop` that
      works on `QAbstractItemView` (not just `QTableView`) so `GalleryView` and
      `FileListView` share one implementation. Currently `GalleryView` duplicates
      `mouseMoveEvent`/`startDrag`/`dropEvent` verbatim.
- [ ] Extract a `ContextMenuMixin` from `FileListView.contextMenuEvent` and
      apply it to `GalleryView`. Pass `get_context_menu` via the constructor
      instead of assigning `_get_context_menu` post-hoc from `widgets.py`.
- [ ] Make `ThumbnailCache` app-global (one instance shared by all panes)
      instead of one per `DirectoryPaneWidget`. Today, left + right panes
      browsing the same directory decode every image twice.
- [ ] Expose view-mode + tile-size on the public `DirectoryPane` facade
      (`get_view_mode`/`set_view_mode`/`toggle_view_mode`/`get_gallery_tile_size`/
      `set_gallery_tile_size`). Then `ToggleGalleryView` and `session.py`
      stop reaching through `pane._widget`.
- [ ] Replace `QStackedWidget` in `DirectoryPaneWidget` with simple
      `show()`/`hide()` on the two views in the same parent layout. Drops one
      Qt layout layer + focus-proxy hop.
- [ ] Move the disk-cached `QPixmap(disk)` decode (`ThumbnailCache.get`) and
      `QImageReader(...).size()` (`get_resolution`) off the UI thread into the
      worker. Eliminates a 200-500ms hang on first paint of a directory whose
      thumbnails are already on disk.
