# AI Agent Instructions for vitraj

## Project overview

vitraj (formerly fman) is a cross-platform dual-pane file manager built with Python, PyQt5, and the fbs build system. It supports macOS, Windows, and Linux.

## Architecture

```
src/
  main/
    python/vitraj/              # Core framework (model, view, controller, plugins)
    resources/base/Plugins/     # Core plugin (commands, file systems, preview)
  build/python/build_impl/      # Platform-specific build/freeze scripts
  integrationtest/              # Integration tests
requirements/                   # Per-platform dependency files
```

### Key patterns

- **Plugin system**: Commands extend `DirectoryPaneCommand`, listeners extend `DirectoryPaneListener`. Both are in `core/commands/__init__.py`.
- **Model-View-Controller**: `Model` (file list data) -> `SortedFileSystemModel` (proxy with sorting/filtering) -> `FileListView` (Qt table view).
- **Thread safety**: Model mutations happen in a single worker thread. GUI updates use `@run_in_main_thread` decorator. Never call Qt widget methods from background threads.
- **Filters**: Simple callables `filter(url) -> bool` added/removed via `pane._add_filter()` / `pane._remove_filter()`. See `ToggleHiddenFiles` as the canonical example.
- **Settings**: JSON files loaded via `load_json()` / `save_json()`. Per-pane settings stored in `Panes.json`.
- **PanelManager**: Centralized panel lifecycle in `MainWindow`. Plugins use `window.activate_panel(pane, widget, panel_id)` / `window.deactivate_panel(pane)` instead of manipulating the splitter directly. Only one panel active per pane; activating a new panel auto-deactivates the previous one.

### Key files

| File | Purpose |
|------|---------|
| `src/main/python/vitraj/__init__.py` | Public API: DirectoryPane, DirectoryPaneCommand, DirectoryPaneListener, Window |
| `src/main/python/vitraj/impl/widgets.py` | MainWindow, PanelManager, DirectoryPaneWidget, Splitter |
| `src/main/python/vitraj/impl/model/model.py` | File list model with worker thread |
| `src/main/python/vitraj/impl/model/__init__.py` | SortedFileSystemModel proxy |
| `src/main/python/vitraj/impl/view/__init__.py` | FileListView (QTableView subclass) |
| `src/main/python/vitraj/impl/controller.py` | Keyboard shortcut dispatch |
| `src/main/resources/base/Plugins/Core/core/commands/__init__.py` | All commands and listeners |
| `src/main/resources/base/Plugins/Core/core/fs/local/__init__.py` | Local filesystem implementation |
| `src/main/resources/base/Plugins/Core/Key Bindings.json` | Cross-platform key bindings |
| `src/main/resources/base/Plugins/Core/Key Bindings (Mac).json` | macOS-specific key bindings |
| `src/main/resources/base/Plugins/File Preview/file_preview/__init__.py` | File preview widget (text, images, directories) |
| `src/main/resources/base/Plugins/File Preview PDF/file_preview_pdf/__init__.py` | PDF preview addon (PyMuPDF) |
| `src/main/resources/base/Plugins/Settings/settings/__init__.py` | Settings panel (Cmd+,) |
| `src/main/resources/base/Plugins/Theme Editor/theme_editor/__init__.py` | Theme editor with color pickers |
| `src/build/python/build_impl/mac.py` | macOS freeze/sign/bundle logic |

## Development workflow

```bash
python build.py run       # Run from source
python build.py test      # Run test suite (461 tests)
python build.py freeze    # Compile standalone app
python build.py clean     # Remove build artifacts
```

### Running tests

```bash
pip install -Ur requirements/mac.txt   # or your platform
python build.py test
```

Expected: 461 tests, 2 pre-existing failures in `test_zip.py` (dict ordering with Unicode filenames).

### Building the macOS app

```bash
pip install -Ur requirements/mac.txt
python build.py clean && python build.py freeze
# Output: target/vitraj.app (~120MB, ad-hoc signed)
```

The freeze process: PyInstaller bundles Python + deps -> platform cleanup strips unused Qt/boto3 -> ad-hoc codesign for TCC compliance.

## Plugin system

### How plugins work

Plugins are directories containing a Python package + optional JSON/CSS/TTF files. They are auto-discovered from three locations (load order):

1. **Shipped**: `src/main/resources/base/Plugins/` (Core plugin)
2. **Third-party**: `DATA_DIRECTORY/Plugins/Third-party/`
3. **User**: `DATA_DIRECTORY/Plugins/User/`

Where `DATA_DIRECTORY` is `~/Library/Application Support/vitraj` (Mac), `%APPDATA%/vitraj` (Windows), `~/.config/vitraj` (Linux).

### Plugin directory structure

```
My Plugin/
├── my_plugin/
│   └── __init__.py           # Python classes (auto-discovered)
├── Key Bindings.json         # Optional: shortcut definitions
├── Key Bindings (Mac).json   # Optional: platform-specific overrides
├── Theme.css                 # Optional: QSS styling
└── *.ttf                     # Optional: font files
```

### Class auto-discovery

Any class in `__init__.py` inheriting from these base classes is auto-registered:

| Base class | Registration | Instantiation |
|-----------|-------------|---------------|
| `DirectoryPaneCommand` | Per-pane command registry | Lazy, one per pane |
| `DirectoryPaneListener` | Per-pane listener list | On pane creation |
| `ApplicationCommand` | App command registry | Singleton |
| `FileSystem` | MotherFileSystem by `scheme` | On load |
| `Column` | MotherFileSystem by qualified name | On load |

Class name → command name: `MyCommand` → `my_command` (CamelCase to snake_case).

### Key Bindings.json format

```json
[
  { "keys": ["F3"], "command": "my_command" },
  { "keys": ["Cmd+Shift+X"], "command": "my_command", "args": {"flag": true} }
]
```

### Installing a third-party plugin

Copy the plugin directory to `DATA_DIRECTORY/Plugins/Third-party/`:
```bash
cp -r "My Plugin" "~/Library/Application Support/vitraj/Plugins/Third-party/"
```

### Plugin lifecycle

- `load()`: sys.path extended, packages imported, classes registered, CSS/fonts loaded
- `unload()`: All registrations reversed in LIFO order, sys.path restored
- Error handling: Plugin errors are caught and reported without crashing vitraj

## Common tasks

### Adding a new command

1. Add class to `core/commands/__init__.py` extending `DirectoryPaneCommand`
2. Add key binding to `Key Bindings.json` (and platform-specific files if needed)
3. Set `aliases` tuple for Command Palette visibility

### Adding a new file preview type

1. Register a handler via `PreviewWidget.register_handler('.ext', handler_fn)` in your plugin's `__init__.py`
2. The handler receives `(widget, path)` — use `widget.show_image_pixmap(pixmap, info)` for images
3. See `File Preview PDF` plugin for a complete example

### Adding a panel (PanelManager)

The PanelManager in `MainWindow` handles all panel lifecycle. To add a new panel:

1. Create a panel widget class (extends `QWidget`)
2. In your command's `__call__`:
   ```python
   _PANEL_ID = 'my_panel'
   w = self.pane.window
   if w.is_panel_active(self.pane, _PANEL_ID):
       w.deactivate_panel(self.pane)
   else:
       panel = MyPanel(self.pane)
       w.activate_panel(self.pane, panel, _PANEL_ID)
   ```
3. `activate_panel` auto-closes any other active panel (no mutual exclusion code needed)
4. `PanelModeListener` in Core auto-closes panels on `switch_panes`/`go_to`
5. For cleanup before deactivation (e.g., flushing timers), check `get_active_panel` first:
   ```python
   active = pane.window.get_active_panel(pane)
   if active and active[0] == _PANEL_ID:
       active[1].flush()  # your cleanup
       pane.window.deactivate_panel(pane)
   ```

**Window panel API:**
- `window.activate_panel(pane, widget, panel_id)` → `bool`
- `window.deactivate_panel(pane)` → `panel_id` or `None`
- `window.get_active_panel(pane)` → `(panel_id, widget)` or `None`
- `window.is_panel_active(pane, panel_id=None)` → `bool`

### Adding a new filter

Follow the `ToggleHiddenFiles` / `_hidden_file_filter` pattern:
1. Create a filter function: `def my_filter(url) -> bool` (True = include)
2. Create a Toggle command that calls `pane._add_filter()` / `pane._remove_filter()`
3. Create an Init listener to set up filter state on startup
4. Store settings in `Panes.json` via `_get_pane_info(pane)`

Note: `".."` parent dir entries are always passed through filters at the model level (`Model._accepts`).

### Adding a setting to the Settings panel

1. Add UI widget in `SettingsPanel._build_*_section()` in the Settings plugin
2. Connect to existing commands via `self._pane.run_command('command_name')`
3. For checkboxes that sync with external state: re-read actual state after command, use `blockSignals` to prevent loops
4. The Settings panel's "Edit..." button opens the Theme Editor via `edit_theme` command
5. The event filter forwards Cmd+P/Cmd+Shift+P to the file pane (allows Ctrl+A/C/V/X/Z through)

### Theme customization

- Custom themes are stored in `Custom Theme.json` (active theme) and `Saved Themes.json` (named presets)
- Theme files use `.fman-theme` extension: `{"fman_theme": 1, "name": "...", "colors": {"key": "#hex"}}`
- Colors are applied via QPalette updates + QSS overrides (marker-delimited block in the app stylesheet)
- `_THEME_ELEMENTS` defines all 21 themeable color keys (including `alternate_bg`) with defaults from `styles.qss`
- `InitThemeListener` applies saved custom theme on startup (deferred 500ms + retry for plugin compatibility)
- Panels use `Qt.WA_StyledBackground` to inherit theme colors from QSS `*` rules
- The Settings panel integrates with FmanAlternativeColors plugin for theme switching

## Important constraints

- **Python 3.9+** minimum, tested up to 3.14. Do not use features removed after 3.9.
- **PyQt5 5.15.x** — not PyQt6. Qt5 API only.
- **Python 3.14 gotchas**: No implicit float-to-int in Qt calls (use `int()`), no `traceback._some_str`, `TracebackException.exc_type` is read-only.
- **Cross-platform**: Test changes against macOS, Windows, and Linux code paths. Platform checks use `vitraj.PLATFORM` ('Mac', 'Windows', 'Linux').
- **Thread safety**: Widget manipulation must happen on the main thread. Use `@run_in_main_thread` from `vitraj.impl.util.qt.thread`. Model operations run in the worker thread.
- **fbs build system**: PyInstaller spec is auto-generated by fbs. Add hidden imports to `src/build/settings/base.json`, not to the spec file directly.
- **macOS TCC**: Add `NS*UsageDescription` keys to `src/build/settings/mac.json` `info_plist_extra` for folder access.
- **No unnecessary dependencies**: Prefer PyQt5 built-in capabilities. Use `try/except ImportError` for optional deps (PyMuPDF, Pillow) so the app works without them.
