from os.path import dirname, pardir, join

def get_resource(rel_path):
	resources_dir = join(dirname(__file__), pardir, pardir, 'resources')
	return join(resources_dir, *rel_path.split('/'))