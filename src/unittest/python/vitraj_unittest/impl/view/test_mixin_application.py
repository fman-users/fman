"""Verify DragAndDrop + ContextMenuMixin apply correctly to both views.

These guard against subtle Qt MRO + setter-order regressions:
- ``QListView.setMovement(Static)`` silently disables ``dragEnabled`` and
  resets ``dragDropMode``; ``GalleryView`` must re-install the mixin
  defaults after its own setup or drag stops working.
- Both views must inherit ``contextMenuEvent`` from the shared mixin so
  the get-context-menu callable can flow through the constructor instead
  of being assigned post-hoc.
"""
from unittest import TestCase

from PyQt5.QtWidgets import QAbstractItemView, QApplication

from vitraj.impl.view import FileListView
from vitraj.impl.view.context_menu import ContextMenuMixin
from vitraj.impl.view.drag_and_drop import DragAndDrop
from vitraj.impl.view.gallery import GalleryView


_app = QApplication.instance() or QApplication([])


def _no_op_context_menu(*_args, **_kwargs):
	return []


class DragAndDropMixinApplicationTest(TestCase):
	def test_gallery_view_has_drag_flags_after_setMovement(self):
		view = GalleryView(None, get_context_menu=_no_op_context_menu)
		# These would all be wrong if _install_drag_and_drop weren't called
		# after setMovement(Static) clobbers them.
		self.assertTrue(view.dragEnabled())
		self.assertTrue(view.acceptDrops())
		self.assertEqual(QAbstractItemView.DragDrop, view.dragDropMode())
		self.assertTrue(view.dragDropOverwriteMode())

	def test_file_list_view_has_drag_flags(self):
		view = FileListView(None, _no_op_context_menu)
		self.assertTrue(view.dragEnabled())
		self.assertTrue(view.acceptDrops())
		self.assertEqual(QAbstractItemView.DragDrop, view.dragDropMode())

	def test_both_views_inherit_mixin_drag_methods(self):
		# Confirms the shared mixin really is the implementation, not
		# leftover copies in either subclass.
		self.assertIs(GalleryView.mouseMoveEvent, DragAndDrop.mouseMoveEvent)
		self.assertIs(GalleryView.startDrag, DragAndDrop.startDrag)
		self.assertIs(GalleryView.dropEvent, DragAndDrop.dropEvent)


class ContextMenuMixinApplicationTest(TestCase):
	def test_both_views_share_contextMenuEvent(self):
		self.assertIs(
			GalleryView.contextMenuEvent, ContextMenuMixin.contextMenuEvent
		)
		self.assertIs(
			FileListView.contextMenuEvent, ContextMenuMixin.contextMenuEvent
		)

	def test_constructor_stores_get_context_menu(self):
		gallery = GalleryView(None, get_context_menu=_no_op_context_menu)
		file_view = FileListView(None, _no_op_context_menu)
		self.assertIs(_no_op_context_menu, gallery._get_context_menu)
		self.assertIs(_no_op_context_menu, file_view._get_context_menu)

	def test_file_list_view_overrides_context_menu_position(self):
		# FileListView corrects for header height on keyboard-triggered menus;
		# GalleryView (no header) uses the default.
		self.assertIsNot(
			FileListView._context_menu_position,
			ContextMenuMixin._context_menu_position,
		)
		self.assertIs(
			GalleryView._context_menu_position,
			ContextMenuMixin._context_menu_position,
		)
