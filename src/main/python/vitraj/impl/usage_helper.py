from vitraj import show_alert, OK, CANCEL
from vitraj.impl.html_style import highlight as b, underline as u

class UsageHelper:
	def __init__(self, is_first_run):
		self._is_first_run = is_first_run
	def on_location_bar_clicked(self, pane, past_events):
		return self._on_mouse_action(pane, past_events)
	def on_doubleclicked(self, pane, past_events):
		return self._on_mouse_action(pane, past_events)
	def on_context_menu(self, pane, via, past_events):
		return via == 'Mouse' and self._on_mouse_action(pane, past_events)
	def _on_mouse_action(self, pane, events):
		if not self._is_first_run:
			return False
		assert events, events
		if events[-1] == 'AbortedTour' and 'AbortedTour' not in events[:-1]:
			response = show_alert(
				"Hey, sorry to bother again. You just used the mouse. That "
				"works, but fman isn't really optimized for it. Maybe you do "
				"briefly want to see what makes fman special?",
				OK | CANCEL, OK
			)
			if response == OK:
				pane.run_command('tutorial', {'step': 1})
			return True
		if events[-1] == 'CompletedTour':
			show_alert(
				"Hey, sorry to bother one last time. You just used the mouse. "
				"To make the most of fman, please use the keyboard instead:"
				"<ul>"
					"<li>Jump to files by typing their name.</li>"
					"<li>Use %s to open them.</li>"
					"<li>Press %s to go up.</li>"
					"<li>To open a different %sath, use %s.</li>"
					"<li>For other features, press %s.</li>"
				"</ul>"
				"It's like riding a bike: With a little practice, you'll be "
				"faster than ever before!" % (
					b('Enter'), b('Backspace'), u('P'), b('Ctrl+P'),
					b('Ctrl+Shift+P')
				)

			)
			return True
		return False