from fbs_runtime.platform import is_mac
from vitraj.impl.onboarding import Tour, TourStep
from vitraj.url import basename

class CleanupGuide(Tour):
	def __init__(self, *args, **kwargs):
		super().__init__('Cleanup', *args, **kwargs)
	def _get_steps(self):
		if is_mac():
			cmd_p = 'Cmd+P'
			delete_key = 'Cmd+Backspace'
			cmd_shift_p = 'Cmd+Shift+P'
		else:
			cmd_p = 'Ctrl+P'
			delete_key = 'Delete'
			cmd_shift_p = 'Ctrl+Shift+P'
		selection_key = 'Space' if is_mac() else 'Insert'
		panes = self._pane.window.get_panes()
		this_pane_index = panes.index(self._pane)
		other_pane_index = (this_pane_index + 1) % len(panes)
		return [
			TourStep(
				'Clean up your files',
				[
					"Quickly clean up your files with this guide. It takes "
					"less than five minutes. Do you want to continue?"
				],
				buttons=[('No', self.reject), ('Yes', self._next_step)]
			),
			TourStep(
				'Cool!',
				[
					"Please go to the directory you want to clean up. Your "
					"*Downloads* folder is usually a good choice. Press *%s* "
					"to jump to it." % cmd_p,
					"Once you're in the directory you want to clean up, click "
					"Next."
				],
				buttons=[('Next', self._arrived_in_folder)]
			),
			TourStep(
				'',
				[
					"Great! Is there a file in *%s* that you no longer need "
					"and want to delete?"
				],
				buttons=[('No', self._skip_steps(6)), ('Yes', self._next_step)]
			),
			TourStep(
				'',
				[
					"Okay! Please type the name of the file. As you do this, "
					"fman will jump to it. Once you're on the correct file, "
					"press *%s*." % delete_key,
					"*Note:* Avoid using the mouse. fman makes you more "
					"productive, but only when you use it with the keyboard."
				],
				{
					'before': {
						'MoveToTrash': self._after_dialog_shown(self._next_step)
					}
				}
			),
			TourStep(
				'',
				[
					"Good! Press *Enter* to delete the file. (If you're "
					"unsure, you can also press *Escape* to cancel.)"
				],
				{
					'after': {
						'MoveToTrash': self._next_step
					}
				}
			),
			TourStep(
				'',
				[
					"Perfect! Do you have other files you want to delete?"
				],
				buttons=[('No', self._skip_steps(3)), ('Yes', self._next_step)]
			),
			TourStep(
				'',
				[
					"Okay :-) Let's try file selections this time. As before, "
					"type the name of the first file you want to delete. Once "
					"fman has jumped to it, press *%s*." % selection_key
				],
				{
					'after': {
						'MoveCursorDown': self._next_step_if_selection
					}
				}
			),
			TourStep(
				'',
				[
					"Perfect! fman selected the file. If you have other files "
					"you want to delete, you can select them in the same way. "
					"Or you can press *Arrow Down/Up* together with the "
					"*Shift* key.",
					"Once you have selected the files you wish to delete, "
					"press *%s*." % delete_key
				],
				{
					'before': {
						'MoveToTrash': self._after_dialog_shown(self._next_step)
					}
				}
			),
			TourStep(
				'',
				[
					"Good! Press *Enter* to delete the files or *Escape* to "
					"cancel."
				],
				{
					'after': {
						'MoveToTrash': self._clear_selection_then_next_step
					}
				}
			),
			TourStep(
				'',
				[
					"Alright! Do you have a file in this directory that you "
					"want to move to another folder?"
				],
				buttons=[('No', self._skip_steps(5)), ('Yes', self._next_step)]
			),
			TourStep(
				'',
				[
					"Okay! We'll first open this other folder in the opposite "
					"pane. Press *Tab* to switch to it."
				],
				{
					'after': {
						'SwitchPanes': self._next_step
					}
				}
			),
			TourStep(
				'',
				[
					"Good! Navigate to the directory where you want your file "
					"to end up. The fastest way is typically via *%s*. But you "
					"can also:" % cmd_p,
					"* type a folder's name to jump to it,",
					"* press *Enter* to open it,",
					"* use *Backspace* to go up a directory,",
					"* press *Alt+F%d* to switch drives/volumes."
					% (other_pane_index + 1),
					"With a little practice, these shortcuts are much faster "
					"than using the mouse.",
					"When you're in the folder you want, click *Next*."
				],
				buttons=[('Next', self._next_step)]
			),
			TourStep(
				'',
				[
					"Well done! Press *Tab* again to switch back to the first "
					"pane."
				],
				{
					'after': {
						'SwitchPanes': self._next_step
					}
				}
			),
			TourStep(
				'',
				[
					"Good. Now type the name of the file you wish to move. "
					"Once fman has jumped to it, press *F6*.",
					"You can also move several files. To do this, press *%s* "
					"over the first one. Then, select the others with either "
					"*%s* or *Arrow Down / Up* plus *Shift*. Finally, press "
					"*F6*." % (selection_key, selection_key)
				],
				{
					'before': {
						'Move': self._after_dialog_shown(self._next_step)
					}
				}
			),
			TourStep(
				'',
				[
					"fman asks whether you want to move the files to the "
					"folder in the other pane. Press *Enter* to confirm, or "
					"*Escape* to cancel."
				],
				{
					'after': {
						'Move': self._next_step
					}
				}
			),
			TourStep(
				'Well done!',
				[
					"This completes the cleanup. Hopefully we've brought a "
					"little extra order to your files. You can start this "
					"guide again at any time. Simply use the Command Palette "
					"*(%s)*." % cmd_shift_p
				],
				buttons=[('Close', self.complete)]
			)
		]
	def _arrived_in_folder(self):
		folder_name = basename(self._pane_widget.get_location())
		self._format_next_step_paragraph(folder_name)
		self._next_step()
	def _next_step_if_selection(self):
		if self._pane_widget.get_selected_files():
			self._next_step()
	def _clear_selection_then_next_step(self):
		self._pane_widget.clear_selection()
		self._next_step()