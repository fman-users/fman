from vitraj.impl.view.multiple_delegates import MultipleDelegates
from vitraj.impl.view.cursor_movement import CursorMovement
from PyQt5.QtCore import Qt, QItemSelectionModel as QISM
from PyQt5.QtWidgets import QAbstractItemView, QStyledItemDelegate, QStyle

class SingleRowMode(
	# We need to extend CursorMovement because we overwrite some of its methods.
	CursorMovement, MultipleDelegates
):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setSelectionBehavior(QAbstractItemView.SelectRows)
		self._single_row_delegate = None
		self._focus_out_reason = None
	def _get_modifiers(self, cursor_action):
		if cursor_action in (self.MoveHome, self.MoveEnd):
			return Qt.ControlModifier
		return super()._get_modifiers(cursor_action)
	def _get_toggle_selection_command(self):
		return super()._get_toggle_selection_command() | QISM.Rows
	def moveCursor(self, cursorAction, modifiers):
		result = super().moveCursor(cursorAction, modifiers)
		if result.isValid() and result.column() != 0:
			result = result.sibling(result.row(), 0)
		return result
	def selectionCommand(self, index, event):
		return super().selectionCommand(index, event) | QISM.Rows
	def setSelectionModel(self, selectionModel):
		if self.selectionModel():
			self.selectionModel().currentRowChanged.disconnect(
				self._current_row_changed
			)
			assert self._single_row_delegate
			self.remove_delegate(self._single_row_delegate)
		super().setSelectionModel(selectionModel)
		selectionModel.currentRowChanged.connect(self._current_row_changed)
		self._single_row_delegate = SingleRowModeDelegate(self)
		self.add_delegate(self._single_row_delegate)
	def focusInEvent(self, event):
		if not self.currentIndex().isValid():
			self.move_cursor_home()
		super().focusInEvent(event)
		self._focus_out_reason = None
	def focusOutEvent(self, event):
		super().focusOutEvent(event)
		self._focus_out_reason = event.reason()
	def _current_row_changed(self, current, previous):
		# When the cursor moves, Qt only repaints the cell that was left and the
		# cell that was entered. But because we are highlighting the entire row
		# the cursor is on, we need to tell Qt to also update the remaining
		# cells of the same row.
		self._update_entire_row(current)
		self._update_entire_row(previous)
	def _update_entire_row(self, index):
		for column in range(self.model().columnCount(self.rootIndex())):
			self.update(index.sibling(index.row(), column))

class SingleRowModeDelegate(QStyledItemDelegate):
	def __init__(self, view):
		super().__init__(view)
		self._view = view
	def adapt_style_option(self, option, index):
		if self._should_draw_cursor(index):
			option.state |= QStyle.State_HasFocus
	def _should_draw_cursor(self, index):
		# Highlight the entire row (rather than just the first column) on focus.
		view = self._view
		if index.row() != view.currentIndex().row():
			return False
		if view.hasFocus():
			return True
		nofocus_reason = view._focus_out_reason
		if view.isActiveWindow():
			# Check if the reason we don't have focus is a context menu:
			return nofocus_reason == Qt.PopupFocusReason
		# QTableView::item:focus is only applied when the window has focus. This
		# means that the cursor disappears when the window is in the background
		# (or behind a modal). This leads to non-pleasant flickering effects.
		# So we always highlight the cursor even when the window doesn't have
		# focus:
		would_have_focus = nofocus_reason in (
			Qt.ActiveWindowFocusReason, Qt.PopupFocusReason,
			Qt.MenuBarFocusReason
		)
		return would_have_focus