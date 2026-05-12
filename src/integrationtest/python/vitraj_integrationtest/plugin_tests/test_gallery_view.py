"""Integration tests for the gallery view feature.

These tests exercise the same plumbing that the rest of the integration
test suite uses (see ``fman_integrationtest.plugin_tests.PluginTest``):
- A real ``DirectoryPane`` wrapping a ``StubDirectoryPaneWidget``.
- A ``PaneCommandRegistry`` shared by both panes.
- Commands invoked via ``pane.run_command(...)``.

The shipped Core plugin (which contains ``ToggleGalleryView``) is not
loaded in the integration test bootstrap, so the test registers the
command class directly. The view-mode/tile-size methods do not live on
``StubDirectoryPaneWidget`` either, so the test installs a tiny mixin
stub on each pane's ``_widget`` that mirrors the real
``DirectoryPaneWidget`` contract (``get_view_mode``/``set_view_mode``
and ``get_gallery_tile_size``/``set_gallery_tile_size``) and the tile-
size clamping from ``fman.impl.view.gallery``.
"""

from vitraj_integrationtest.plugin_tests import PluginTest
from vitraj.impl.view.gallery import (
	DEFAULT_TILE_SIZE_PX, MIN_TILE_SIZE_PX, MAX_TILE_SIZE_PX,
)


class _GalleryWidgetMixin:
	"""Adds the view-mode + tile-size methods to a pane widget.

	Mirrors the public contract of ``DirectoryPaneWidget`` that the
	``ToggleGalleryView`` command and ``set_gallery_tile_size`` rely on.
	"""
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._view_mode = 'list'
		self._gallery_tile_size = DEFAULT_TILE_SIZE_PX
	def get_view_mode(self):
		return self._view_mode
	def set_view_mode(self, mode):
		if mode not in ('list', 'gallery'):
			raise ValueError('Unknown view mode: %r' % mode)
		self._view_mode = mode
	def toggle_view_mode(self):
		self.set_view_mode(
			'list' if self._view_mode == 'gallery' else 'gallery'
		)
	def get_gallery_tile_size(self):
		return self._gallery_tile_size
	def set_gallery_tile_size(self, px):
		self._gallery_tile_size = max(
			MIN_TILE_SIZE_PX, min(MAX_TILE_SIZE_PX, int(px))
		)


class GalleryViewTest(PluginTest):
	def setUp(self):
		super().setUp()
		# The shipped Core plugin (which owns ``toggle_gallery_view``) is
		# not loaded by ``PluginTest``. Register the command class directly
		# against the existing pane command registry.
		from core.commands import ToggleGalleryView
		self._panecmd_registry.register_command(
			'toggle_gallery_view', ToggleGalleryView
		)
		# Upgrade both pane widgets so they expose the view-mode and
		# tile-size API that the command (and real session restore) use.
		# We mutate the existing instances rather than swapping them so
		# the registered panes keep pointing at the same widget.
		for pane in (self._left_pane, self._right_pane):
			widget = pane._widget
			widget.__class__ = type(
				'StubDirectoryPaneWidgetWithGallery',
				(_GalleryWidgetMixin, widget.__class__),
				{}
			)
			widget._view_mode = 'list'
			widget._gallery_tile_size = DEFAULT_TILE_SIZE_PX

	def test_default_view_mode_is_list(self):
		self.assertEqual('list', self._left_pane._widget.get_view_mode())
		self.assertEqual('list', self._right_pane._widget.get_view_mode())

	def test_toggle_gallery_view_flips_mode(self):
		self._left_pane.run_command('toggle_gallery_view')
		self.assertEqual('gallery', self._left_pane._widget.get_view_mode())
		self._left_pane.run_command('toggle_gallery_view')
		self.assertEqual('list', self._left_pane._widget.get_view_mode())
		# No errors reported along the way:
		self.assertEqual([], self._error_handler.error_messages)

	def test_toggle_is_per_pane(self):
		self._left_pane.run_command('toggle_gallery_view')
		self.assertEqual('gallery', self._left_pane._widget.get_view_mode())
		self.assertEqual(
			'list', self._right_pane._widget.get_view_mode(),
			'Right pane must not be affected by left-pane toggle.'
		)
		# And the reverse: toggling the right pane must not flip the left.
		self._right_pane.run_command('toggle_gallery_view')
		self.assertEqual('gallery', self._left_pane._widget.get_view_mode())
		self.assertEqual('gallery', self._right_pane._widget.get_view_mode())

	def test_default_gallery_tile_size(self):
		self.assertEqual(
			DEFAULT_TILE_SIZE_PX, self._left_pane._widget.get_gallery_tile_size()
		)
		self.assertEqual(
			DEFAULT_TILE_SIZE_PX, self._right_pane._widget.get_gallery_tile_size()
		)

	def test_set_gallery_tile_size_clamps_to_max(self):
		self._left_pane._widget.set_gallery_tile_size(99_999)
		self.assertEqual(MAX_TILE_SIZE_PX, self._left_pane._widget.get_gallery_tile_size())

	def test_set_gallery_tile_size_clamps_to_min(self):
		self._left_pane._widget.set_gallery_tile_size(1)
		self.assertEqual(MIN_TILE_SIZE_PX, self._left_pane._widget.get_gallery_tile_size())
