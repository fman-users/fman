from fbs_runtime.platform import is_mac, is_windows
from fman import load_json, show_alert, CANCEL, OK
from fman.impl.onboarding import Tour, TourStep
from fman.impl.util import is_below_dir
from fman.impl.util.qt import connect_once
from fman.impl.util.qt.thread import run_in_main_thread, is_in_main_thread
from fman.url import as_url, splitscheme, as_human_readable
from os.path import expanduser, relpath, realpath, splitdrive, basename, \
	normpath, dirname
from pathlib import PurePath
from platform import mac_ver
from PyQt5.QtCore import QFileInfo
from PyQt5.QtWidgets import QFileDialog
from time import time, sleep

import fman.url
import os.path
import webbrowser

class Tutorial(Tour):
	def __init__(self, is_first_run, *args, **kwargs):
		if is_mac():
			self._cmd_p = 'Cmd+P'
			self._native_fm = 'Finder'
			self._delete_key = 'Cmd+Backspace'
			self._cmd_shift_p = 'Cmd+Shift+P'
		else:
			self._cmd_p = 'Ctrl+P'
			if is_windows():
				self._native_fm = 'Explorer'
			else:
				self._native_fm = 'your native file manager'
			self._delete_key = 'Delete'
			self._cmd_shift_p = 'Ctrl+Shift+P'
		super().__init__('Tutorial', *args, **kwargs)
		self._is_first_run = is_first_run
		self._dst_url = self._src_url = self._start_time = self._time_taken \
			= None
		self._encouragements = [
			e + '. ' for e in ('Great', 'Cool', 'Well done', 'Nice')
		]
		self._encouragement_index = 0
		self._last_step = ''
	def on_close(self):
		if self._is_first_run and _is_macos_catalina_or_later():
			response = show_alert(
				"On macOS, fman requires extra configuration.<br/>"
				"I'll show you the relevant documentation now.",
				OK | CANCEL, OK
			)
			if response == OK:
				webbrowser.open('https://fman.io/docs/macos?s=f')
	def _get_steps(self):
		return [
			TourStep(
				'Welcome to fman!',
				[
					"Would you like to take a quick tour of the most useful "
					"features? It takes less than five minutes and lets you "
					"hit the ground running."
				],
				buttons=[('No', self.reject), ('Yes', self._next_step)]
			),
			TourStep(
				'Awesome!',
				[
					'We need an example. Please click the button below to '
					'select a directory. It should be a folder you use often. '
					'Also, it should be a little \"nested\" so you have to '
					'click through a few directories to get to it.'
				],
				buttons=[('Select a folder', self._pick_folder)]
			),
			TourStep('', []),
			TourStep(
				"",
				[
					"Very well done! You opened your *%s* folder in *%.2f* "
					"seconds. Let's see if we can make it faster!",
					"Please click *Reset* to take you back to the directory you "
					"started from."
				],
				buttons=[('Reset', self._reset)]
			),
			TourStep(
				"",
				[
					"We will now use a feature that makes fman unique among "
					"file managers: It's called *GoTo*. Press *%s* to launch "
					"it!" % self._cmd_p
				],
				{
					'before': {
						'GoTo': self._after_dialog_shown(self._before_goto)
					}
				}
			),
			TourStep(
				'',
				[
					"GoTo lets you quickly jump to directories.",
					"%s"
				],
				{
					'after': {
						'GoTo': self._after_goto
					}
				}
			),
			TourStep('', [], buttons=[('Continue', self._next_step)]),
			TourStep(
				'',
				[
					"A limitation of *GoTo* is that it sometimes doesn't "
					"suggest directories you haven't visited yet. If that "
					"happens, simply navigate to the folder manually once."
				],
				buttons=[
					('Okay!', self._next_step)
				]
			),
			TourStep(
				'',
				[
					"If you ever need a special feature from %s, you can fall "
					"back to it by pressing *F10*. Please try this now."
					% self._native_fm
				],
				{
					'after': {
						'OpenNativeFileManager': self._after_native_fm
					}
				}
			),
			TourStep(
				'',
				[
					"Well done! fman opened " + self._native_fm +
					" in your *%s* folder.",
					"Because fman always displays two directories, it is "
					"called a *dual-pane file manager*. Have you used one "
					"before?"
				],
				buttons=[
					('No', self._next_step), ('Yes', self._skip_steps(3))
				]
			),
			TourStep(
				'',
				[
					"Dual-pane file managers make it especially easy to copy "
					"and move files. Would you like to see a brief example?"
				],
				buttons=[
					('No', self._skip_steps(1)), ('Yes', self._next_step)
				]
			),
			TourStep(
				'',
				[
					"Okay! Press *Tab* to move from one side to the other. "
					"Then, select the file you want to copy and press *F5*. "
					"fman will ask you for confirmation. To delete the file "
					"afterwards, press *%s*. Once you are done, click the "
					"button below." % self._delete_key
				],
				buttons=[('Continue', self._skip_steps(1))]
			),
			TourStep(
				'',
				[
					"No problem. In that case, all you need to know for now is "
					"that *Tab* lets you switch between the left and the right "
					"side."
				],
				buttons=[('Continue', self._next_step)]
			),
			TourStep(
				'',
				[
					"Dual-pane file managers rely heavily on keyboard "
					"shortcuts. But how do you remember them?",
					"fman's answer to this question is a searchable list of "
					"features. It's called the *Command Palette*. Please press "
					"*%s* to launch it." % self._cmd_shift_p
				],
				{
					'before': {
						'CommandPalette':
							self._after_dialog_shown(self._next_step)
					}
				}
			),
			TourStep(
				'',
				[
					"Well done! Note how the Command Palette shows fman's "
					"commands as well as the shortcut for each of them.",
					"Say you want to select all files, but don't know how. "
					"Type *select* into the Command Palette. It will suggest "
					"*Select all*. Confirm with *Enter*."
				],
				{
					'after': {
						'SelectAll': self._next_step
					}
				}
			),
			TourStep(
				'',
				[
					"Perfect! The files were selected. Last step: Can you find "
					"a way to _de_select them?",
					"Hint: The shortcut for the Command Palette is *%s*."
					% self._cmd_shift_p
				],
				{
					'after': {
						'Deselect': self._next_step
					}
				}
			),
			TourStep(
				'Great Work!',
				[
					"You've completed the tutorial. Remember:",
					"* *%s* lets you go to any _P_ath." % self._cmd_p,
					"* *F10* opens %s" % self._native_fm,
					"* *%s* opens the Command _P_alette." % self._cmd_shift_p,
					"Have fun with fman! :-)"
				],
				buttons=[('Close', self.complete)]
			)
		]
	@run_in_main_thread
	def _pick_folder(self):
		self._curr_step.close()
		dir_path = QFileDialog.getExistingDirectory(
			self._main_window, 'Pick a folder', expanduser('~'),
			QFileDialog.ShowDirsOnly
		)
		if not dir_path:
			self._curr_step.show(self._main_window)
			return
		# On Windows, QFileDialog.getExistingDirectory(...) returns paths with
		# forward slashes instead of backslashes. Fix this:
		dir_path = normpath(dir_path)
		# fman (currently) resolves paths before entering them: When you open
		# a/, which is a symlink to b/, then fman's location becomes b/. If our
		# implementation tried to guide the user to a/, it could never succeed
		# because b/ will always be reached instead. To fix this, we use
		# realpath(...) to resolve symlinks. This has the drawback that the user
		# chose a/ but will be asked to open b/. It is likely that fman's
		# implementation will eventually not resolve symlinks when opening
		# locations. Once that happens, we can also forgo resolving here:
		dir_path = realpath(dir_path)
		if dir_path.startswith(r'\\'):
			# When the user picks a network folder,
			# QFileDialog.getExistingDirectory(...) returns the server component
			# in lower-case: \\server\Folder. realpath(...) above doesn't change
			# this. fman and Windows Explorer however display server names in
			# upper case: \\SERVER\Folder. Mirror this:
			dir_path = _upper_server(dir_path)
		self._dst_url = as_url(dir_path)
		self._src_url = self._get_src_url(dir_path)
		self._curr_step_index += 1
		self._track_current_step()
		self._go_to_src_url()
	def _go_to_src_url(self):
		"""
		Opens `self._src_url` and calls `self._navigate()` once it's loaded.

		The "obvious" implementation for this method would be to use the
		callback=... parameter of DirectoryPaneWidget#set_location(...) to call
		_navigate(). However, this has a problem: _navigate() registers a
		location_changed listener. FileSystemModel#set_location(...)
		calls callback() before broadcasting location_changed. This would lead
		to _navigate() being called twice: First as the callback() and then
		again as a location_changed listener.

		The first intuitive solution to this problem would be to not use
		callback=... but simply connect _navigate() to location_changed once.
		But this too has a problem: location_changed isn't called when the
		location doesn't actually change.

		To solve all of the above, we handle the case where we're already at the
		correct location separately. Only if we're not do we use
		connect_once(location_changed, ...):
		"""
		if self._src_url == self._get_location():
			self._navigate()
		else:
			navigate = lambda _: self._navigate()
			connect_once(self._pane_widget.location_changed, navigate)
			self._set_location(self._src_url)
	def _navigate(self):
		if self._start_time is None:
			self._start_time = time()
		steps = self._get_navigation_steps(self._dst_url, self._get_location())
		if not steps:
			# We have arrived:
			self._time_taken = time() - self._start_time
			current_dir = fman.url.basename(self._get_location())
			self._format_next_step_paragraph((current_dir, self._time_taken))
			self._next_step()
			return
		instruction, path = steps[0]
		paragraphs = self._get_step_paragraphs(instruction, path)
		actions = {'on': {'location_changed': self._navigate}}
		if instruction == 'toggle hidden files':
			actions['after'] = {'ToggleHiddenFiles': self._navigate}
		self._steps[self._curr_step_index] = TourStep('', paragraphs, actions)
		if instruction == 'open' and path != '..':
			self._highlight(fman.url.join(self._get_location(), path))
		self._show_current_screen()
	def _get_step_paragraphs(self, instruction, path):
		result = []
		if not self._last_step:
			result.append(
				"fman always shows the contents of two directories. We will "
				"now navigate to your *%s* folder in the left pane." %
				fman.url.basename(self._dst_url)
			)
		encouragement = self._get_encouragement() if self._last_step else ''
		if instruction == 'show drives':
			drive = splitdrive(as_human_readable(self._dst_url))[0]
			if drive.startswith(r'\\'): # Network share
				result.append(
					"First, we need to switch to the overview of your drives. "
					"Please press *Alt+F1* to do this."
				)
			else:
				result.append(
					"First, we need to switch to your *%s* drive. Please press "
					"*Alt+F1* to see an overview of your drives." % drive
				)
		elif instruction == 'open':
			if splitscheme(self._get_location())[0] == 'drives://':
				from core.fs.local.windows.drives import DrivesFileSystem
				if path == DrivesFileSystem.NETWORK:
					folder = '*%s*' % DrivesFileSystem.NETWORK
				else:
					folder = '*%s* drive' % path
			else:
				folder = '*%s* folder' % path
			result.append(
				encouragement +
				"Please%s open your %s, in one of the following ways:"
				% (' now' if self._last_step else '', folder)
			)
			result.append(
				"* Type its name or use *Arrow Up/Down* to select it. "
				"Then, press *Enter*."
			)
			result.append("* Double-click on it with the mouse.")
		elif instruction == 'go up':
			text = encouragement + "We need to go up a%s directory. Please " \
								   "press *Backspace* to do this."
			text %= 'nother' if self._last_step == 'go up' else ''
			result.append(text)
		elif instruction == 'toggle hidden files':
			now = ' now' if self._last_step else ''
			result.append(
				encouragement +
				"We%s want to open your *%s* folder, but it is hidden. Please "
				"press *%s+.* to show hidden files." %
				(now, path, 'Cmd' if is_mac() else 'Ctrl')
			)
		else:
			assert instruction == 'go to'
			text = "We need to go to *%s*. Please press *%s* to open " \
				   "fman's GoTo dialog. There, type *%s* followed by *Enter*."\
				   % (path, self._cmd_p, path)
			result.append(text)
		self._last_step = instruction
		return result
	def _get_encouragement(self):
		result = self._encouragements[self._encouragement_index]
		self._encouragement_index += 1
		self._encouragement_index %= len(self._encouragements)
		return result
	def _highlight(self, file_url, timeout_secs=.25):
		start_time = time()
		while time() < start_time + timeout_secs:
			try:
				self._pane_widget.toggle_selection(file_url)
			except ValueError:
				# This for instance happens when the file was hidden, the user
				# just toggled to show hidden files (an asynchronous operation)
				# and it has not yet completed.
				if is_in_main_thread(): # Never block the main thread
					break
				sleep(.1)
			else:
				break
	def _get_src_url(self, dst_path):
		dst_url = as_url(dst_path)
		steps_from = lambda url: len(self._get_navigation_steps(dst_url, url))
		current = self._get_location()
		if steps_from(current) >= 3:
			return current
		home = expanduser('~')
		home_url = as_url(home)
		if is_below_dir(dst_path, home):
			if steps_from(home_url) >= 3:
				return home_url
		drive_url = as_url(PurePath(dst_path).anchor)
		if steps_from(drive_url) > 0:
			return drive_url
		if steps_from(home_url) > 0:
			return home_url
		return as_url(PurePath(home).anchor)
	def _get_navigation_steps(self, dst_url, src_url):
		try:
			pane_info = load_json('Panes.json', default=[])[0]
		except IndexError:
			showing_hidden_files = False
		else:
			showing_hidden_files = pane_info.get('show_hidden_files', False)
		return _get_navigation_steps(
			dst_url, src_url, _is_hidden, showing_hidden_files
		)
	def _reset(self):
		self._set_location(self._src_url)
		self._next_step()
	def _before_goto(self):
		self._start_time = time()
		if self._dst_url == as_url(expanduser('~')):
			text = "To open your home directory with GoTo, type&nbsp;*~*. " \
				   "Then, press *Enter*."
		else:
			goto_dir = fman.url.basename(self._dst_url)
			text = "Start typing *%s* into the dialog. fman will suggest " \
				   "your directory. Press *Enter* to open it." % goto_dir
		self._format_next_step_paragraph((), text)
		self._next_step()
	def _after_goto(self):
		url = self._get_location()
		if url == self._dst_url:
			time_taken = time() - self._start_time
			if time_taken < self._time_taken:
				paras = [
					"Awesome! Using GoTo, you jumped to your directory in "
					"*%.2f* seconds instead of *%.2f*." %
					(time_taken, self._time_taken),
					"The next time you open *%s* outside of fman, ask "
					"yourself: Isn't it tedious to click through directory "
					"trees all the time? fman is the answer." %
					fman.url.basename(url)
				]
			else:
				paras = [
					"Awesome! Did you see how quick that was? Once you're used "
					"to it, you'll never want to manually navigate directory "
					"trees again."
				]
			self._steps[self._curr_step_index + 1]._paragraphs = paras
			self._next_step()
	def _after_native_fm(self):
		self._format_next_step_paragraph(basename(self._get_location()))
		self._next_step()
	def _get_location(self):
		return self._pane_widget.get_location()
	def _set_location(self, url):
		self._pane_widget.set_location(url)

def _is_hidden(url):
	scheme, path = splitscheme(url)
	if scheme != 'file://':
		return False
	# Copied from core.commands:
	return QFileInfo(as_human_readable(url)).isHidden()

def _is_macos_catalina_or_later():
	if not is_mac():
		return False
	try:
		macos_ver = tuple(map(int, mac_ver()[0].split('.')))
	except ValueError:
		return False
	else:
		return macos_ver >= (10, 15, 0)

def _get_navigation_steps(
	dst_url, src_url, is_hidden=lambda url: False, showing_hidden_files=True
):
	if splitscheme(dst_url)[0] != 'file://':
		raise ValueError(dst_url)
	def continue_from(src_url, showing_hidden_files=showing_hidden_files):
		return _get_navigation_steps(
			dst_url, src_url, is_hidden, showing_hidden_files
		)
	dst_path = as_human_readable(dst_url)
	dst_drive = splitdrive(dst_path)[0]
	dst_is_unc = dst_drive.startswith(r'\\')
	dst_drive_path = \
		(dst_drive + ('' if dst_is_unc else '\\')) if is_windows() else '/'
	src_scheme = splitscheme(src_url)[0]
	if src_scheme == 'drives://':
		if dst_is_unc:
			from core.fs.local.windows.drives import DrivesFileSystem
			return [('open', DrivesFileSystem.NETWORK)] + \
				   continue_from('network://')
		return [('open', dst_drive)] + continue_from(as_url(dst_drive_path))
	if src_scheme == 'network://':
		if dst_is_unc:
			unc_parts = dst_drive[2:].split('\\')
			server = unc_parts[0]
			assert server == server.upper(), server
			src_path = splitscheme(src_url)[1]
			if not src_path:
				return [('open', server)] + continue_from('network://' + server)
			src_server = src_path.split('/')[0]
			if src_server != server:
				return [('go up', '')] + \
					   continue_from(fman.url.dirname(src_url))
			return [('open', unc_parts[1])] + \
				   continue_from(as_url(r'\\' + '\\'.join(unc_parts[:2])))
		return [('show drives', '')] + continue_from('drives://')
	if src_scheme != 'file://':
		return [('go to', dst_drive_path)] +\
			   continue_from(as_url(dst_drive_path))
	src_path = as_human_readable(src_url)
	src_drive = splitdrive(src_path)[0]
	if dst_drive != src_drive:
		return [('show drives', '')] + continue_from('drives://')
	rel = relpath(dst_path, src_path)
	if rel and rel != '.':
		nxt = rel.split(os.sep)[0]
		if nxt == '..':
			return [('go up', '')] + continue_from(as_url(dirname(src_path)))
		nxt_url = as_url(os.path.join(src_path, nxt))
		if not showing_hidden_files and is_hidden(nxt_url):
			return [('toggle hidden files', nxt)] + \
				   continue_from(src_url, showing_hidden_files=True)
		return [('open', nxt)] + continue_from(nxt_url)
	return []

def _upper_server(unc_path):
	r"""
	\\server\Folder -> \\SERVER\Folder
	"""
	assert unc_path.startswith(r'\\'), unc_path
	try:
		i = unc_path.index('\\', 2)
	except ValueError:
		return unc_path.upper()
	return unc_path[:i].upper() + unc_path[i:]