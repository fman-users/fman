# Test plugin that uses legacy fman imports (not vitraj)
# Verifies the sys.modules compatibility shim works end-to-end

from fman import ApplicationCommand, DirectoryPaneCommand, DirectoryPaneListener
from fman.fs import FileSystem, Column

class FmanCompatCommand(ApplicationCommand):
    def __call__(self):
        pass

class FmanCompatDPC(DirectoryPaneCommand):
    def __call__(self):
        pass

class FmanCompatListener(DirectoryPaneListener):
    def on_path_changed(self):
        pass

class FmanCompatFS(FileSystem):
    scheme = 'fmancompat://'

class FmanCompatColumn(Column):
    display_name = 'FmanCompat'
