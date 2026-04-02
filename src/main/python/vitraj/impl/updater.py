from os.path import join, pardir, dirname

import sys

class MacUpdater:
	def __init__(self, app):
		self.app = app
		self._objc_namespace = dict()
		self._sparkle = None
	def start(self):
		from objc import pathForFramework, loadBundle
		frameworks_dir = join(dirname(sys.executable), pardir, 'Frameworks')
		fmwk_path = pathForFramework(join(frameworks_dir, 'Sparkle.framework'))
		loadBundle('Sparkle', self._objc_namespace, bundle_path=fmwk_path)
		self.app.aboutToQuit.connect(self._about_to_quit)
		SUUpdater = self._objc_namespace['SUUpdater']
		self._sparkle = SUUpdater.sharedUpdater()
		self._sparkle.setAutomaticallyChecksForUpdates_(True)
		self._sparkle.setAutomaticallyDownloadsUpdates_(True)
		self._sparkle.checkForUpdatesInBackground()
	def _about_to_quit(self):
		if self._sparkle.updateInProgress():
			# Installing the update takes quite some time. Hide the dock icon so
			# the user doesn't think fman froze:
			self._hide_dock_window()
		self._notify_sparkle_of_app_shutdown()
	def _hide_dock_window(self):
		NSApplication = self._objc_namespace['NSApplication']
		app = NSApplication.sharedApplication()
		app.setActivationPolicy_(NSApplicationActivationPolicyProhibited)
	def _notify_sparkle_of_app_shutdown(self):
		# Qt apps don't receive the NSApplicationWillTerminateNotification
		# event, which Sparkle relies on. If we broadcast the event manually
		# (via NSNotificationCenter.defaultCenter().postNotificationName(...)),
		# then Sparkle does receive it, however during the update process the
		# event is broadcast again, resulting in a second (failing) run of
		# Sparkle's Autoupdate app - see [1] for more information on the issue.
		# The clean way to have the notification broadcast only once is to call
		# Cocoa's terminate(...) method.
		# [1]: https://github.com/sparkle-project/Sparkle/issues/839
		NSApplication = self._objc_namespace['NSApplication']
		NSApplication.sharedApplication().terminate_(None)

NSApplicationActivationPolicyProhibited = 2