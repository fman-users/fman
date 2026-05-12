"""
Visual testing harness for vitraj.

Launches the full app, runs test scenarios, captures screenshots,
and reports results. Tests run in a background thread while the
Qt event loop runs on the main thread (required on macOS).

Usage:
    python visual_test.py                    # Run all tests
    python visual_test.py --list             # List available tests
    python visual_test.py test_name ...      # Run specific tests
    python visual_test.py --interactive      # Launch app with test API
    python visual_test.py --dump-widgets     # Dump widget tree and exit

Screenshots are saved to target/screenshots/.
"""

import os
import sys
import time
import traceback
from threading import Thread, Event
from pathlib import Path

# Set up paths before importing vitraj/PyQt5
_PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_DIR / 'src' / 'main' / 'python'))
sys.path.insert(0, str(_PROJECT_DIR / 'src' / 'main' / 'resources' / 'base' / 'Plugins' / 'Core'))
os.environ.setdefault('PYTHONPATH', '')

from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QWidget

SCREENSHOT_DIR = _PROJECT_DIR / 'target' / 'screenshots'


class TestHarness:
    """Manages the app lifecycle and provides test utilities."""

    def __init__(self):
        self._appctxt = None
        self._main_window = None
        self._app = None
        self._ready = Event()
        self._panes_ready = Event()

    def start_app(self):
        """Start the full app. Must be called on the main thread."""
        from vitraj.impl.application_context import get_application_context
        self._appctxt = get_application_context()

        # Patch to capture when panes are ready
        orig_init_panes = self._appctxt.session_manager._init_panes
        def patched_init_panes(*args, **kwargs):
            orig_init_panes(*args, **kwargs)
            self._panes_ready.set()
        self._appctxt.session_manager._init_panes = patched_init_panes

        # Start the app (this initializes plugins, shows window, etc.)
        self._appctxt.init_logging()
        self._appctxt._start_metrics()
        self._appctxt._load_plugins()

        self._app = self._appctxt.app
        self._main_window = self._appctxt.main_window
        self._window = self._appctxt.window

        # Show the window
        self._appctxt.session_manager.show_main_window(self._window)
        self._ready.set()

        # Run the event loop (blocks until app quits)
        return self._app.exec_()

    def wait_ready(self, timeout=30):
        """Wait for the app to be ready."""
        if not self._ready.wait(timeout):
            raise TimeoutError('App did not start within %d seconds' % timeout)
        if not self._panes_ready.wait(timeout):
            raise TimeoutError('Panes did not load within %d seconds' % timeout)
        # Give the UI a moment to settle
        time.sleep(1)

    @property
    def window(self):
        return self._main_window

    @property
    def app(self):
        return self._app

    def run_on_ui(self, func, *args, **kwargs):
        """Run a function on the Qt main thread and return the result."""
        from vitraj.impl.util.qt.thread import run_in_main_thread

        @run_in_main_thread
        def _wrapper():
            return func(*args, **kwargs)

        return _wrapper()

    def screenshot(self, name='screenshot', widget=None):
        """Capture a screenshot and save it."""
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        path = SCREENSHOT_DIR / ('%s.png' % name)

        def _capture():
            target = widget or self._main_window
            pixmap = target.grab()
            pixmap.save(str(path))
            return not pixmap.isNull()

        ok = self.run_on_ui(_capture)
        if ok:
            print('  Screenshot: %s' % path)
        else:
            print('  Screenshot FAILED: %s' % path)
        return ok

    def get_panes(self):
        """Get directory pane widgets."""
        return self._main_window.get_panes()

    def get_window_panes(self):
        """Get Window-level DirectoryPane wrappers."""
        return self._window.get_panes()

    def navigate(self, pane_index, path):
        """Navigate a pane to a directory and wait for it to load."""
        loaded = Event()

        def _nav():
            from vitraj.url import as_url
            from vitraj.impl.util.qt import connect_once
            panes = self._main_window.get_panes()
            pane = panes[pane_index]
            model = pane._model
            connect_once(model.location_loaded, lambda *_: loaded.set())
            model.set_location(as_url(path))

        self.run_on_ui(_nav)
        if not loaded.wait(10):
            print('  WARNING: Navigation to %s timed out' % path)
        time.sleep(0.5)

    def press_key(self, key, modifiers=None):
        """Simulate a key press on the focused widget."""
        def _press():
            widget = self._app.focusWidget() or self._main_window
            if modifiers:
                QTest.keyClick(widget, key, modifiers)
            else:
                QTest.keyClick(widget, key)

        self.run_on_ui(_press)
        time.sleep(0.3)

    def get_file_list(self, pane_index=0):
        """Get the list of files shown in a pane."""
        def _get():
            panes = self._main_window.get_panes()
            pane = panes[pane_index]
            model = pane._model
            files = []
            for row in range(model.rowCount()):
                index = model.index(row, 0)
                name = model.data(index, Qt.DisplayRole)
                if name:
                    files.append(name)
            return files

        return self.run_on_ui(_get)

    def get_current_location(self, pane_index=0):
        """Get the current directory URL of a pane."""
        def _get():
            panes = self._main_window.get_panes()
            return panes[pane_index]._model.get_location()
        return self.run_on_ui(_get)

    def get_cursor_file(self, pane_index=0):
        """Get the file under the cursor."""
        def _get():
            panes = self._main_window.get_panes()
            pane = panes[pane_index]
            index = pane._file_view.currentIndex()
            if index.isValid():
                return pane._model.data(index, Qt.DisplayRole)
            return None
        return self.run_on_ui(_get)

    def get_window_info(self):
        """Get information about the main window state."""
        def _get():
            w = self._main_window
            pane_widgets = w.get_panes()
            window_panes = self._window.get_panes()
            info = {
                'title': w.windowTitle(),
                'size': '%dx%d' % (w.width(), w.height()),
                'visible': w.isVisible(),
                'num_panes': len(pane_widgets),
                'panes': [],
            }
            for i, p in enumerate(pane_widgets):
                panel = None
                if i < len(window_panes):
                    panel = w.get_active_panel(window_panes[i])
                pane_info = {
                    'index': i,
                    'location': p._model.get_location(),
                    'file_count': p._model.rowCount(),
                    'has_focus': p._file_view.hasFocus(),
                    'active_panel': panel[0] if panel else None,
                }
                info['panes'].append(pane_info)
            return info
        return self.run_on_ui(_get)

    def dump_widget_tree(self, widget=None, indent=0):
        """Print the widget tree for inspection."""
        def _dump():
            target = widget or self._main_window
            lines = []
            _walk_widgets(target, lines, 0)
            return '\n'.join(lines)
        return self.run_on_ui(_dump)

    def quit(self):
        """Quit the app."""
        self.run_on_ui(self._app.quit)


def _walk_widgets(widget, lines, indent):
    """Recursively walk the widget tree."""
    cls = widget.__class__.__name__
    name = widget.objectName() or ''
    size = '%dx%d' % (widget.width(), widget.height())
    visible = 'visible' if widget.isVisible() else 'hidden'
    focus = ' [FOCUSED]' if widget.hasFocus() else ''
    lines.append('%s%s(%s) %s %s%s' % ('  ' * indent, cls, name, size, visible, focus))

    for child in widget.children():
        if isinstance(child, QWidget):
            _walk_widgets(child, lines, indent + 1)


# ── Test definitions ────────────────────────────────────────────────

def test_startup(h):
    """Verify the app starts with two panes and correct layout."""
    info = h.get_window_info()
    assert info['visible'], 'Window not visible'
    assert info['num_panes'] == 2, 'Expected 2 panes, got %d' % info['num_panes']
    h.screenshot('01_startup')
    print('  Window: %s, Panes: %d' % (info['size'], info['num_panes']))
    for p in info['panes']:
        print('    Pane %d: %s (%d files)' % (p['index'], p['location'], p['file_count']))

def test_navigation(h):
    """Navigate to /tmp and verify file list loads."""
    h.navigate(0, '/tmp')
    location = h.get_current_location(0)
    assert '/tmp' in location or '/private/tmp' in location, \
        'Expected /tmp, got %s' % location
    files = h.get_file_list(0)
    assert len(files) > 0, 'No files in /tmp'
    h.screenshot('02_navigation')
    print('  Location: %s' % location)
    print('  Files: %d' % len(files))

def test_cursor_movement(h):
    """Test arrow key navigation and cursor tracking."""
    h.navigate(0, os.path.expanduser('~'))
    time.sleep(0.5)
    h.press_key(Qt.Key_Down)
    h.press_key(Qt.Key_Down)
    h.press_key(Qt.Key_Down)
    cursor = h.get_cursor_file(0)
    h.screenshot('03_cursor_movement')
    print('  Cursor on: %s' % cursor)
    assert cursor is not None, 'No file under cursor'

def test_preview_panel(h):
    """Toggle file preview and verify panel appears."""
    # Navigate to a directory with files
    h.navigate(0, os.path.expanduser('~'))
    time.sleep(0.5)
    h.press_key(Qt.Key_Down)
    time.sleep(0.3)

    # Press F3 to open preview
    h.press_key(Qt.Key_F3)
    time.sleep(1)

    info = h.get_window_info()
    h.screenshot('04_preview_open')
    panel = info['panes'][0].get('active_panel') or info['panes'][1].get('active_panel')
    print('  Active panel: %s' % panel)

    # Navigate through files to test cursor tracking
    h.press_key(Qt.Key_Down)
    time.sleep(0.5)
    h.screenshot('05_preview_cursor_tracking')
    h.press_key(Qt.Key_Down)
    time.sleep(0.5)
    h.screenshot('06_preview_cursor_tracking_2')

    # Close preview
    h.press_key(Qt.Key_F3)
    time.sleep(0.5)
    h.screenshot('07_preview_closed')

def test_settings_panel(h):
    """Open settings panel and verify it displays."""
    # Send Cmd+, (Qt.MetaModifier = Cmd on Mac)
    h.press_key(Qt.Key_Comma, Qt.MetaModifier)
    time.sleep(1)
    h.screenshot('08_settings')

    info = h.get_window_info()
    panel = info['panes'][0].get('active_panel') or info['panes'][1].get('active_panel')
    print('  Active panel: %s' % panel)

    # Close settings with Escape
    h.press_key(Qt.Key_Escape)
    time.sleep(0.5)
    h.screenshot('09_settings_closed')

def test_preview_types(h):
    """Test preview pane for all content types: folder, text, image."""
    project_dir = str(_PROJECT_DIR)
    icons_dir = str(_PROJECT_DIR / 'src' / 'main' / 'icons' / 'base')

    def _focus_and_preview(pane_index=0):
        """Focus the file view and toggle preview via run_command."""
        widget_panes = h._main_window.get_panes()
        widget_panes[pane_index]._file_view.setFocus()
        api_panes = h._window.get_panes()
        api_panes[pane_index].run_command('toggle_preview')

    def _navigate_to_file(filename, pane_index=0):
        """Move cursor to a specific filename in the current listing."""
        def _find():
            panes = h._main_window.get_panes()
            pane = panes[pane_index]
            model = pane._model
            view = pane._file_view
            for row in range(model.rowCount()):
                idx = model.index(row, 0)
                name = model.data(idx, Qt.DisplayRole)
                if name == filename:
                    view.setCurrentIndex(idx)
                    return True
            return False
        return h.run_on_ui(_find)

    # ── Folder preview ────────────────────────────────────────────────
    h.navigate(0, project_dir)
    time.sleep(0.3)
    _navigate_to_file('src')
    time.sleep(0.2)
    h.run_on_ui(_focus_and_preview)
    time.sleep(0.8)
    h.screenshot('preview_folder')
    print('  folder preview captured')

    # ── Text preview ──────────────────────────────────────────────────
    _navigate_to_file('README.md')
    time.sleep(0.2)
    h.run_on_ui(lambda: h._main_window.get_panes()[0]._file_view.setFocus() or None)
    time.sleep(0.5)
    h.screenshot('preview_text')
    print('  text preview captured')

    # ── Image preview ─────────────────────────────────────────────────
    h.navigate(0, icons_dir)
    time.sleep(0.3)
    _navigate_to_file('64.png')
    time.sleep(0.2)
    h.run_on_ui(lambda: h._main_window.get_panes()[0]._file_view.setFocus() or None)
    time.sleep(0.5)
    h.screenshot('preview_image')
    print('  image preview captured')

    # Close preview
    h.run_on_ui(_focus_and_preview)
    time.sleep(0.3)


def test_dual_pane_navigation(h):
    """Navigate both panes to different directories."""
    h.navigate(0, os.path.expanduser('~/Desktop'))
    h.navigate(1, os.path.expanduser('~/Downloads'))
    time.sleep(0.5)
    h.screenshot('10_dual_pane')

    info = h.get_window_info()
    for p in info['panes']:
        print('  Pane %d: %s (%d files)' % (p['index'], p['location'], p['file_count']))

def test_widget_tree(h):
    """Dump the widget tree for inspection."""
    tree = h.dump_widget_tree()
    tree_path = SCREENSHOT_DIR / 'widget_tree.txt'
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    tree_path.write_text(tree)
    print('  Widget tree saved to: %s' % tree_path)
    # Print a summary
    lines = tree.split('\n')
    print('  Total widgets: %d' % len(lines))


# ── Test registry ───────────────────────────────────────────────────

ALL_TESTS = [
    ('startup', test_startup),
    ('navigation', test_navigation),
    ('cursor_movement', test_cursor_movement),
    ('preview_panel', test_preview_panel),
    ('preview_types', test_preview_types),
    ('settings_panel', test_settings_panel),
    ('dual_pane', test_dual_pane_navigation),
    ('widget_tree', test_widget_tree),
]


# ── Runner ──────────────────────────────────────────────────────────

def run_tests(harness, test_names=None):
    """Run selected tests (or all if none specified)."""
    harness.wait_ready()

    tests = ALL_TESTS
    if test_names:
        tests = [(n, f) for n, f in ALL_TESTS if n in test_names]
        if not tests:
            print('No matching tests. Available: %s' %
                  ', '.join(n for n, _ in ALL_TESTS))
            harness.quit()
            return

    passed = 0
    failed = 0
    for name, func in tests:
        print('\n[TEST] %s' % name)
        try:
            func(harness)
            print('  PASS')
            passed += 1
        except Exception as e:
            print('  FAIL: %s' % e)
            traceback.print_exc()
            failed += 1
            try:
                harness.screenshot('FAIL_%s' % name)
            except Exception:
                pass

    print('\n' + '=' * 50)
    print('Results: %d passed, %d failed' % (passed, failed))
    if SCREENSHOT_DIR.exists():
        print('Screenshots: %s' % SCREENSHOT_DIR)
    print('=' * 50)

    harness.quit()


def interactive_mode(harness):
    """Launch app with harness available in a REPL-like mode."""
    harness.wait_ready()
    print('\nInteractive mode. The test harness is available as `h`.')
    print('Examples:')
    print('  h.screenshot("test")')
    print('  h.navigate(0, "/tmp")')
    print('  h.get_file_list()')
    print('  h.get_window_info()')
    print('  h.dump_widget_tree()')
    print('  h.press_key(Qt.Key_F3)')
    print('  h.quit()')
    print()

    import code
    code.interact(local={'h': harness, 'Qt': Qt, 'harness': harness})
    harness.quit()


def main():
    args = sys.argv[1:]

    if '--list' in args:
        print('Available tests:')
        for name, func in ALL_TESTS:
            print('  %-20s %s' % (name, func.__doc__ or ''))
        return

    harness = TestHarness()

    if '--interactive' in args:
        Thread(target=interactive_mode, args=(harness,), daemon=True).start()
    elif '--dump-widgets' in args:
        def _dump(h):
            h.wait_ready()
            tree = h.dump_widget_tree()
            print(tree)
            h.quit()
        Thread(target=_dump, args=(harness,), daemon=True).start()
    else:
        test_names = [a for a in args if not a.startswith('-')]
        Thread(
            target=run_tests,
            args=(harness, test_names or None),
            daemon=True
        ).start()

    # Run Qt event loop on the main thread (required on macOS)
    exit_code = harness.start_app()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
