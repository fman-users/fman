from os.path import basename

import os

def path_starts_with(path, query):
	# We do want to return ~/Downloads when query is ~/Downloads/:
	query = query.rstrip(os.sep)
	if path.lower().startswith(query.lower()):
		return list(range(len(query)))

def basename_starts_with(path, query):
	name = basename(path.lower())
	if name.startswith(query.lower()):
		offset = len(path) - len(name)
		return [i + offset for i in range(len(query))]

def contains_chars(text, query):
	text_lower = text.lower()
	query_lower = query.lower()
	indices = []
	i = 0
	for char in query_lower:
		try:
			i += text_lower[i:].index(char)
		except ValueError:
			return None
		indices.append(i)
		i += 1
	return indices

def contains_substring(text, query):
	try:
		start = text.lower().index(query.lower())
	except ValueError:
		return None
	return list(range(start, start + len(query)))

def contains_chars_after_separator(separator):
	def result(text, query):
		result_ = []
		skip_to_next_part = False
		for i, char in enumerate(text):
			if skip_to_next_part:
				if char == separator:
					skip_to_next_part = False
				continue
			if not query:
				break
			if char == query[0]:
				result_.append(i)
				query = query[1:]
			else:
				skip_to_next_part = char != separator
		if query:
			return None
		return result_
	return result