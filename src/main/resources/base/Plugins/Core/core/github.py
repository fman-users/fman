from requests import RequestException
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import json
import re
import requests
import sys

def find_repos(topics):
	query = '+'.join('topic:' + topic for topic in topics)
	url = "https://api.github.com/search/repositories?q=" + query
	return list(map(GitHubRepo, _fetch_all_pages(url)))

def _fetch_all_pages(json_url, page_size=100):
	for page in range(1, sys.maxsize):
		data = _get_json(json_url + '&per_page=%d&page=%d' % (page_size, page))
		yield from data['items']
		has_more = page * page_size < data['total_count']
		if not has_more:
			break

class GitHubRepo:
	@classmethod
	def fetch(cls, repo):
		url = 'https://api.github.com/repos/' + repo
		return cls(_get_json(url))
	def __init__(self, data):
		self._data = data
	def __str__(self):
		return self._data['full_name']
	def __repr__(self):
		return '<%s: %s>' % (self.__class__.__name__, self)
	@property
	def num_stars(self):
		return self._data['stargazers_count']
	@property
	def name(self):
		return self._data['name']
	@property
	def description(self):
		return self._data['description']
	@property
	def url(self):
		return self._data['url']
	def get_latest_release(self):
		try:
			data = _get_json(self._url('releases', id='latest'))
		except HTTPError as e:
			if e.code == 404:
				raise LookupError()
			raise
		return data['tag_name']
	def get_latest_commit(self):
		return _get_json(self._url('commits'))[0]['sha']
	def download_zipball(self, ref):
		zipball_url = self._url('archive', archive_format='zipball', ref=ref)
		return _get(zipball_url)
	def _url(self, name, **kwargs):
		url = self._data[name + '_url']
		required_url_params = re.finditer(r'{([^/][^}]+)}', url)
		for match in required_url_params:
			url = url.replace(match.group(0), kwargs[match.group(1)])
		optional_url_params = re.finditer(r'{/([^}]+)}', url)
		for match in optional_url_params:
			param = match.group(1)
			value = '/' + kwargs[param] if param in kwargs else ''
			url = url.replace(match.group(0), value)
		return url

def _get_json(url):
	return json.loads(_get(url).decode('utf-8'))

def _get(url):
	try:
		with urlopen(url, timeout=30) as resp:
			return resp.read()
	except HTTPError:
		raise
	except URLError:
		# Fallback: Some users get "SSL: CERTIFICATE_VERIFY_FAILED" for urlopen.
		try:
			response = requests.get(url, timeout=30)
		except RequestException as e:
			raise URLError(e.__class__.__name__)
		if response.status_code != 200:
			raise HTTPError(
				url, response.status_code, response.reason, response.headers,
				None
			)
		return response.content