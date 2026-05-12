from fbs_runtime.platform import is_windows
from vitraj.url import splitscheme, as_human_readable, as_url
from pathlib import PureWindowsPath
from PyQt5.QtCore import Qt, QObject, QEvent, QUrl

def connect_once(signal, slot):
	def _connect_once(*args, **kwargs):
		signal.disconnect(_connect_once)
		slot(*args, **kwargs)
	signal.connect(_connect_once)

def disable_window_animations_mac(window):
	# We need to access `.winId()` below. This method has an unwanted (and not
	# very well-documented) side effect: Calling it before the window is shown
	# makes Qt turn the window into a "native window". This incurs performance
	# penalties and leads to subtle changes in behaviour. We therefore wait for
	# the Show event:
	def eventFilter(target, event):
		from objc import objc_object
		view = objc_object(c_void_p=int(target.winId()))
		NSWindowAnimationBehaviorNone = 2
		view.window().setAnimationBehavior_(NSWindowAnimationBehaviorNone)
	FilterEventOnce(window, QEvent.Show, eventFilter)

class FilterEventOnce(QObject):
	def __init__(self, parent, event_type, callback):
		super().__init__(parent)
		self._event_type = event_type
		self._callback = callback
		parent.installEventFilter(self)
	def eventFilter(self, target, event):
		if event.type() == self._event_type:
			self.parent().removeEventFilter(self)
			self._callback(target, event)
		return False

def as_qurl(url):
	# fman URLs are very non-standard, in particular because they are free to
	# have only two slashes after the scheme (file:// vs file:///). This
	# function (and its inverse, from_qurl below) convert fman to Qt URLs (and
	# vice versa).
	scheme, path = splitscheme(url)
	if scheme == 'file://':
		path = as_human_readable(url)
		result = QUrl.fromLocalFile(path)
	else:
		if is_windows() and PureWindowsPath(path).is_absolute():
			result = QUrl.fromLocalFile(path)
		else:
			result = QUrl('ftp://' + path)
		result.setScheme(scheme[:-len('://')])
	return result

def from_qurl(qurl):
	"""
	Inverse of as_qurl(...) above.
	"""
	if qurl.isLocalFile():
		return as_url(qurl.toLocalFile())
	result = qurl.toString()
	scheme, path = result.split(':', 1)
	if not path.startswith('//'):
		if not path.startswith('/'):
			# Once saw QUrl('ftp:user:pass@123.45.67.89/dir') on the clipboard
			# on Linux.
			raise ValueError('Invalid URL: %r' % result)
		path = ('/' if is_windows() else '//') + path
	return ':'.join([scheme, path])

AscendingOrder = Qt.AscendingOrder
WA_MacShowFocusRect = Qt.WA_MacShowFocusRect
TextAlignmentRole = Qt.TextAlignmentRole
AlignRight = Qt.AlignRight
AlignTop = Qt.AlignTop
AlignVCenter = Qt.AlignVCenter
FramelessWindowHint = Qt.FramelessWindowHint
ClickFocus = Qt.ClickFocus
NoFocus = Qt.NoFocus
KeyboardModifier = Qt.KeyboardModifier
NoModifier = Qt.NoModifier
ControlModifier = Qt.ControlModifier
ShiftModifier = Qt.ShiftModifier
AltModifier = Qt.AltModifier
MetaModifier = Qt.MetaModifier
KeypadModifier = Qt.KeypadModifier
GroupSwitchModifier = Qt.GroupSwitchModifier
Key_Down = Qt.Key_Down
Key_Up = Qt.Key_Up
Key_Left = Qt.Key_Left
Key_Right = Qt.Key_Right
Key_Home = Qt.Key_Home
Key_End = Qt.Key_End
Key_PageUp = Qt.Key_PageUp
Key_PageDown = Qt.Key_PageDown
Key_Space = Qt.Key_Space
Key_Insert = Qt.Key_Insert
Key_Help = Qt.Key_Help
Key_Backspace = Qt.Key_Backspace
Key_Enter = Qt.Key_Enter
Key_Return = Qt.Key_Return
Key_Escape = Qt.Key_Escape
Key_F2 = Qt.Key_F2
Key_F4 = Qt.Key_F4
Key_F5 = Qt.Key_F5
Key_F6 = Qt.Key_F6
Key_F7 = Qt.Key_F7
Key_F8 = Qt.Key_F8
Key_F9 = Qt.Key_F9
Key_F10 = Qt.Key_F10
Key_F11 = Qt.Key_F11
Key_Delete = Qt.Key_Delete
Key_Tab = Qt.Key_Tab
Key_Shift = Qt.Key_Shift
Key_Control = Qt.Key_Control
Key_Meta = Qt.Key_Meta
Key_Alt = Qt.Key_Alt
Key_AltGr = Qt.Key_AltGr
Key_CapsLock = Qt.Key_CapsLock
Key_NumLock = Qt.Key_NumLock
Key_ScrollLock = Qt.Key_ScrollLock
ItemIsEnabled = Qt.ItemIsEnabled
ItemIsEditable = Qt.ItemIsEditable
ItemIsSelectable = Qt.ItemIsSelectable
EditRole = Qt.EditRole
DisplayRole = Qt.DisplayRole
ToolTipRole = Qt.ToolTipRole
AccessibleTextRole = Qt.AccessibleTextRole
UserRole = Qt.UserRole
SizeHintRole = Qt.SizeHintRole
DecorationRole = Qt.DecorationRole
ItemIsDragEnabled = Qt.ItemIsDragEnabled
ItemIsDropEnabled = Qt.ItemIsDropEnabled
CopyAction = Qt.CopyAction
MoveAction = Qt.MoveAction
IgnoreAction = Qt.IgnoreAction
NoButton = Qt.NoButton