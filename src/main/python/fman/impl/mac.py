from objc import loadBundle

_CORE_SERVICES_NS = {}

def get_core_services():
	if not _CORE_SERVICES_NS:
		loadBundle(
			'CoreServices.framework', _CORE_SERVICES_NS,
			bundle_identifier='com.apple.CoreServices'
		)
	return _CORE_SERVICES_NS
