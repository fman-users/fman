from PyQt5.QtCore import QItemSelectionModel as QISM
from PyQt5.QtGui import QContextMenuEvent, QKeySequence
from PyQt5.QtWidgets import QAction


class ContextMenuMixin:
	"""Mixin for ``QAbstractItemView`` subclasses that translates plugin
	command lists into a context menu.

	The view receives a ``get_context_menu(event, file_under_mouse)`` callable
	at construction; the mixin pulls its entries on demand and builds the
	menu. Subclasses with a horizontal header (e.g. ``QTableView``) override
	``_context_menu_position`` to correct the keyboard-triggered position.

	Pure-Python mixin — see ``DragAndDrop`` for the rationale. Place BEFORE
	the view base class in the bases.
	"""

	def __init__(self, *args, get_context_menu=None, **kwargs):
		super().__init__(*args, **kwargs)
		self._get_context_menu = get_context_menu

	def contextMenuEvent(self, event):
		if self._get_context_menu is None:
			return
		# Lazy import: ``view/__init__.py`` imports ``gallery.py`` which imports
		# this module during app startup, so ``Menu`` isn't available yet.
		from vitraj.impl.view import Menu
		index = self.indexAt(event.pos())
		updated_selection = False
		if index.isValid():
			file_under_mouse = self.model().url(index)
			if event.reason() == QContextMenuEvent.Mouse:
				# Our context menu calls plugin commands. Many act on the
				# selected files, or — if no file is selected — on the file
				# under the cursor. This lets the user press Insert to select
				# files and move the cursor down, then perform actions on the
				# selected files above, not the one under the cursor.
				# When the menu is launched by mouse on an unselected file
				# under the cursor, we expect the action to apply to that file.
				# Without special treatment our implementation would still
				# call the command on the selected files. So we reset the
				# selection to the file that was clicked. This mimics Total
				# Commander.
				selection_model = self.selectionModel()
				if not selection_model.isSelected(index):
					selection_model.select(
						index, QISM.ClearAndSelect | QISM.Rows
					)
					updated_selection = True
		else:
			file_under_mouse = None
		try:
			menu = Menu(self)
			entries = self._get_context_menu(event, file_under_mouse)
			if not entries:
				return
			for caption, shortcut, callback in entries:
				if caption == '-':
					menu.addSeparator()
				else:
					action = QAction(caption, self)
					# c=callback binds per-iteration so each lambda closes
					# over its own callback.
					action.triggered.connect(lambda _, c=callback: c())
					if shortcut:
						action.setShortcut(QKeySequence(shortcut))
					menu.addAction(action)
			menu.exec(self._context_menu_position(event))
		finally:
			if updated_selection:
				self.clearSelection()

	def _context_menu_position(self, event):
		"""Return the global position at which the menu should pop up.

		Subclasses with a horizontal header should override this to correct
		the y-offset for keyboard-triggered menus.
		"""
		return event.globalPos()
