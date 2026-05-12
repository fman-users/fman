from PyQt5.QtCore import QItemSelectionModel as QISM, QEvent
from PyQt5.QtWidgets import QTableView

class MoveWithoutUpdatingSelection(QTableView):
	def selectionCommand(self, index, event):
		if event:
			if event.type() == QEvent.MouseButtonPress and event.modifiers():
				super_result = super().selectionCommand(index, event)
				# Don't blindly select - toggle:
				return super_result & (~QISM.Select) | QISM.Toggle
		return QISM.NoUpdate