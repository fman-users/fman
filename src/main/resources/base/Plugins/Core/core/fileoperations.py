from core.util import is_parent
from vitraj import Task, YES, NO, YES_TO_ALL, NO_TO_ALL, ABORT, OK
from vitraj.url import basename, join, dirname, splitscheme, relpath, \
	as_human_readable
from os.path import pardir

import vitraj.fs

class FileTreeOperation(Task):
	def __init__(
		self, descr_verb, files, dest_dir, dest_name=None, fs=vitraj.fs
	):
		if dest_name and len(files) > 1:
			raise ValueError(
				'Destination name can only be given when there is one file.'
			)
		super().__init__(self._get_title(descr_verb, files))
		self._files = files
		self._dest_dir = dest_dir
		self._descr_verb = descr_verb
		self._dest_name = dest_name
		self._fs = fs
		self._src_dir = dirname(files[0])
		self._tasks = []
		self._num_files = 0
		self._cannot_move_to_self_shown = False
		self._override_all = None
		self._ignore_exceptions = False
	def _transfer(self, src, dest):
		raise NotImplementedError()
	def _prepare_transfer(self, src, dest):
		raise NotImplementedError()
	def _can_transfer_samefile(self):
		raise NotImplementedError()
	def _does_postprocess_directory(self):
		return False
	def _postprocess_directory(self, src_dir_path):
		return None
	def __call__(self):
		self.set_text('Gathering files...')
		if not self._gather_files():
			return
		self.set_size(sum(task.get_size() for task in self._tasks))
		for i, task in enumerate(self._iter(self._tasks)):
			is_last = i == len(self._tasks) - 1
			progress_before = self.get_progress()
			try:
				self.run(task)
			except (OSError, IOError) as e:
				title = task.get_title()
				message = 'Error ' + (title[0].lower() + title[1:])
				if not self._handle_exception(message, is_last, e):
					break
				self.set_progress(progress_before + task.get_size())
	def _gather_files(self):
		dest_dir_url = self._get_dest_dir_url()
		self._enqueue([Task(
			'Preparing ' + basename(dest_dir_url), fn=self._fs.makedirs,
			 args=(dest_dir_url,), kwargs={'exist_ok': True}
		)])
		for i, src in enumerate(self._iter(self._files)):
			is_last = i == len(self._files) - 1
			dest = self._get_dest_url(src)
			if is_parent(src, dest, self._fs):
				if src != dest:
					try:
						is_samefile = self._fs.samefile(src, dest)
					except OSError:
						is_samefile = False
					if is_samefile:
						if self._can_transfer_samefile():
							self._enqueue(self._prepare_transfer(src, dest))
							continue
				self.show_alert(
					"You cannot %s a file to itself." % self._descr_verb
				)
				return False
			try:
				is_dir = self._fs.is_dir(src)
			except OSError as e:
				error_message = 'Could not %s %s' % \
								(self._descr_verb, as_human_readable(src))
				if self._handle_exception(error_message, is_last, e):
					continue
				return False
			if is_dir:
				if self._fs.exists(dest):
					if not self._merge_directory(src):
						return False
				else:
					self._enqueue(self._prepare_transfer(src, dest))
			else:
				if self._fs.exists(dest):
					should_overwrite = self._should_overwrite(dest)
					if should_overwrite == NO:
						continue
					elif should_overwrite == ABORT:
						return False
					else:
						assert should_overwrite == YES, should_overwrite
				self._enqueue(self._prepare_transfer(src, dest))
		return True
	def _merge_directory(self, src):
		for file_name in self._fs.iterdir(src):
			file_url = join(src, file_name)
			try:
				src_is_dir = self._fs.is_dir(file_url)
			except OSError:
				src_is_dir = False
			dst = self._get_dest_url(file_url)
			if src_is_dir:
				try:
					dst_is_dir = self._fs.is_dir(dst)
				except OSError:
					dst_is_dir = False
				if dst_is_dir:
					if not self._merge_directory(file_url):
						return False
				else:
					self._enqueue(self._prepare_transfer(file_url, dst))
			else:
				if self._fs.exists(dst):
					should_overwrite = self._should_overwrite(dst)
					if should_overwrite == NO:
						continue
					elif should_overwrite == ABORT:
						return False
					else:
						assert should_overwrite == YES, \
							should_overwrite
				self._enqueue(self._prepare_transfer(file_url, dst))
		if self._does_postprocess_directory():
			# Post-process the parent directories bottom-up. For Move, this
			# ensures that each directory is empty when post-processing.
			self._enqueue([self._postprocess_directory(src)])
		return True
	def _should_overwrite(self, file_url):
		if self._override_all is None:
			choice = self.show_alert(
				"%s exists. Do you want to overwrite it?" % basename(file_url),
				YES | NO | YES_TO_ALL | NO_TO_ALL | ABORT, YES
			)
			if choice & YES:
				return YES
			elif choice & NO:
				return NO
			elif choice & YES_TO_ALL:
				self._override_all = True
			elif choice & NO_TO_ALL:
				self._override_all = False
			else:
				assert choice & ABORT, choice
				return ABORT
		return YES if self._override_all else NO
	def _enqueue(self, tasks):
		for task in self._iter(tasks):
			if task.get_size() > 0:
				self._num_files += 1
				self.set_text(
					'Preparing to {} {:,} files.'
						.format(self._descr_verb, self._num_files)
				)
			self._tasks.append(task)
	def _handle_exception(self, message, is_last, exc):
		if self._ignore_exceptions:
			return True
		if exc.strerror:
			cause = exc.strerror[0].lower() + exc.strerror[1:]
		else:
			cause = exc.__class__.__name__
		message = '%s (%s).' % (message, cause)
		if is_last:
			buttons = OK
			default_button = OK
		else:
			buttons = YES | YES_TO_ALL | ABORT
			default_button = YES
			message += ' Do you want to continue?'
		choice = self.show_alert(message, buttons, default_button)
		if is_last:
			return choice & OK
		else:
			if choice & YES_TO_ALL:
				self._ignore_exceptions = True
			return choice & YES or choice & YES_TO_ALL
	def _get_dest_dir_url(self):
		try:
			splitscheme(self._dest_dir)
		except ValueError as not_a_url:
			is_url = False
		else:
			is_url = True
		return self._dest_dir if is_url else join(self._src_dir, self._dest_dir)
	def _get_dest_url(self, src_file):
		dest_name = self._dest_name or basename(src_file)
		if self._src_dir:
			try:
				rel_path = \
					relpath(join(dirname(src_file), dest_name), self._src_dir)
			except ValueError as e:
				raise ValueError(
					'Could not construct path. '
					'src_file: %r, dest_name: %r, src_dir: %r' %
					(src_file, dest_name, self._src_dir)
				) from e
			is_in_src_dir = not rel_path.startswith(pardir)
			if is_in_src_dir:
				try:
					splitscheme(self._dest_dir)
				except ValueError as no_scheme:
					return join(self._src_dir, self._dest_dir, rel_path)
				else:
					return join(self._dest_dir, rel_path)
		return join(self._dest_dir, dest_name)
	def _iter(self, iterable):
		for item in iterable:
			self.check_canceled()
			yield item
	def _get_title(self, descr_verb, files):
		verb = descr_verb.capitalize()
		result = (verb[:-1] if verb.endswith('e') else verb) + 'ing '
		if len(files) == 1:
			result += basename(files[0])
		else:
			result += '%d files' % len(files)
		return result

class CopyFiles(FileTreeOperation):
	def __init__(self, *super_args, **super_kwargs):
		super().__init__('copy', *super_args, **super_kwargs)
	def _transfer(self, src, dest):
		self._fs.copy(src, dest)
	def _can_transfer_samefile(self):
		# Can never copy to the same file.
		return False
	def _prepare_transfer(self, src, dest):
		return self._fs.prepare_copy(src, dest)

class MoveFiles(FileTreeOperation):
	def __init__(self, *super_args, **super_kwargs):
		super().__init__('move', *super_args, **super_kwargs)
	def _transfer(self, src, dest):
		self._fs.move(src, dest)
	def _can_transfer_samefile(self):
		# May be able to move to the same file on case insensitive file systems.
		# Consider a/ and A/: They are the "same" file yet it does make sense to
		# rename one to the other.
		return True
	def _prepare_transfer(self, src, dest):
		return self._fs.prepare_move(src, dest)
	def _does_postprocess_directory(self):
		return True
	def _postprocess_directory(self, src_dir_path):
		return Task(
			'Postprocessing ' + basename(src_dir_path),
			fn=self._do_postprocess_directory, args=(src_dir_path,)
		)
	def _do_postprocess_directory(self, src_dir_path):
		if self._is_empty(src_dir_path):
			try:
				self._fs.delete(src_dir_path)
			except OSError:
				pass
	def _is_empty(self, dir_url):
		try:
			next(iter(self._fs.iterdir(dir_url)))
		except StopIteration:
			return True
		return False