from collections import OrderedDict

def describe_type(value):
	if isinstance(value, dict):
		return '{...}'
	if isinstance(value, str):
		return '"..."'
	if isinstance(value, list):
		return '[...]'
	return type(value).__name__

def ordered_set(values):
	return OrderedDict((v, None) for v in values)