from collections import deque
from fbs_runtime.platform import is_linux
from http.client import HTTPException
from os import makedirs
from os.path import dirname, exists
from queue import Queue
from ssl import CertificateError
from threading import Thread
from urllib.parse import urlencode
from urllib.request import urlopen, Request

import json
import ssl

class MetricsError(Exception):
	pass

class Metrics:
	def __init__(self, json_path, backend, os, fman_version):
		self._json_path = json_path
		self._backend = backend
		self._user = None
		self._super_properties = {
			'os': os,
			'app_version': fman_version
		}
		self._enabled = True
	def initialize(self):
		try:
			json_dict = self._read_json()
		except ValueError:
			self._enabled = False
		except FileNotFoundError:
			try:
				self._user = self._backend.create_user()
			except MetricsError:
				self._enabled = False
			else:
				self._write_json({'uuid': self._user})
		except NotADirectoryError:
			# This happens when part of a path isn't a dir. Eg. install.txt/foo.
			# In this case, we will also not be able to save a generated UUID to
			# the file. So instead of generating a new UUID with every start, we
			# simply disable Metrics:
			self._enabled = False
		else:
			self._enabled = json_dict.get('enabled', True)
			try:
				self._user = json_dict['uuid']
			except KeyError:
				self._enabled = False
		if self._enabled and is_linux():
			# linux_distribution() is expensive. We perform it here (instead of,
			# say, the application context) because the present method is run
			# in a separate thread via AsynchronousMetrics.
			from distro import linux_distribution
			distribution, version = linux_distribution()[:2]
			if version:
				distribution += ' ' + version
			self._super_properties['distribution'] = distribution
	def get_user(self):
		return self._user
	def track(self, event, properties=None):
		if not self._enabled:
			return
		data = dict(self._super_properties)
		if properties:
			data.update(properties)
		try:
			self._backend.track(self._user, event, data)
		except MetricsError:
			pass
	def update_user(self, **properties):
		if not self._enabled:
			return
		try:
			self._backend.update_user(self._user, **properties)
		except MetricsError:
			pass
	def _read_json(self):
		with open(self._json_path, 'r') as f:
			return json.load(f)
	def _write_json(self, data):
		makedirs(dirname(self._json_path), exist_ok=True)
		with open(self._json_path, 'w') as f:
			json.dump(data, f)

class ServerBackend:
	def __init__(self, users_url, events_url):
		self._users_url = users_url
		self._events_url = events_url
	def create_user(self):
		return self._post(self._users_url)
	def track(self, user, event, properties=None):
		data = self.get_data_for_tracking(user, event, properties)
		self._post(self._events_url, data)
	def update_user(self, user, **properties):
		self._put(self._users_url + '/' + user, properties)
	def get_data_for_tracking(self, user, event, properties=None):
		result = {
			'uuid': user,
			'event': event
		}
		if properties:
			result.update(properties)
		return result
	def _post(self, url, data=None):
		return self._send(url, 'POST', data)
	def _put(self, url, data=None):
		return self._send(url, 'PUT', data)
	def _send(self, url, method, data):
		if data:
			errs = 'surrogatepass'
			encoded_data = urlencode(data, errors=errs).encode('utf-8', errs)
		else:
			encoded_data = None
		cafile_linux = '/etc/ssl/certs/ca-certificates.crt'
		cafile = cafile_linux if is_linux() and exists(cafile_linux) else None
		ssl_context = ssl.create_default_context(cafile=cafile)
		request = Request(url, encoded_data, method=method)
		try:
			with urlopen(request, context=ssl_context) as response:
				resp_body = response.read()
		except (OSError, HTTPException, CertificateError) as e:
			raise MetricsError() from e
		if response.status // 100 != 2:
			raise MetricsError('Unexpected HTTP status %d.' % response.status)
		try:
			return resp_body.decode('utf-8')
		except ValueError:
			raise MetricsError('Unexpected response: %r' % resp_body)

class LoggingBackend:
	def __init__(self, backend, max_num_logs=1000):
		self._backend = backend
		self._logs = deque(maxlen=max_num_logs)
	def create_user(self):
		return self._backend.create_user()
	def track(self, user, event, properties=None):
		data = self._backend.get_data_for_tracking(user, event, properties)
		self._logs.append(data)
		self._backend.track(user, event, properties)
	def update_user(self, user, **properties):
		self._backend.update_user(user, **properties)
	def flush(self, log_file_path):
		with open(log_file_path, 'w') as f:
			fmt_log = lambda data: json.dumps(data, indent=4)
			f.write('\n\n'.join(map(fmt_log, self._logs)))

class AsynchronousMetrics:
	def __init__(self, metrics):
		self.past_events = []
		self._metrics = metrics
		self._queue = Queue()
		self._thread = Thread(target=self._work, daemon=True)
	def initialize(self, callback=lambda: None):
		self._queue.put(self._metrics.initialize)
		self._queue.put(callback)
		self._thread.start()
	def get_user(self):
		return self._metrics.get_user()
	def track(self, event, properties=None):
		self.past_events.append(event)
		self._queue.put(lambda: self._metrics.track(event, properties))
	def update_user(self, **properties):
		self._queue.put(lambda: self._metrics.update_user(**properties))
	def _work(self):
		while True:
			self._queue.get()()
			self._queue.task_done()