"""Verify the view-mode and gallery-tile-size methods on the public
``DirectoryPane`` facade delegate through to the underlying widget.

Pure unit test — no Qt instantiation. ``DirectoryPane`` is constructed
with a recording stub widget so each delegate call can be asserted.
"""
from unittest import TestCase
from unittest.mock import MagicMock

from vitraj import DirectoryPane


def _make_pane():
	widget = MagicMock()
	# DirectoryPane.__init__ reads widget but does not exercise it.
	return DirectoryPane(window=None, widget=widget, command_registry=None), widget


class DirectoryPaneViewModeFacadeTest(TestCase):
	def test_get_view_mode_delegates(self):
		pane, widget = _make_pane()
		widget.get_view_mode.return_value = 'gallery'
		self.assertEqual('gallery', pane.get_view_mode())
		widget.get_view_mode.assert_called_once_with()

	def test_set_view_mode_delegates(self):
		pane, widget = _make_pane()
		pane.set_view_mode('gallery')
		widget.set_view_mode.assert_called_once_with('gallery')

	def test_toggle_view_mode_delegates(self):
		pane, widget = _make_pane()
		pane.toggle_view_mode()
		widget.toggle_view_mode.assert_called_once_with()

	def test_get_gallery_tile_size_delegates(self):
		pane, widget = _make_pane()
		widget.get_gallery_tile_size.return_value = 160
		self.assertEqual(160, pane.get_gallery_tile_size())
		widget.get_gallery_tile_size.assert_called_once_with()

	def test_set_gallery_tile_size_delegates(self):
		pane, widget = _make_pane()
		pane.set_gallery_tile_size(220)
		widget.set_gallery_tile_size.assert_called_once_with(220)
