# Core
The Core plugin implements most of [fman](https://fman.io)'s features, such as copying files, navigating to a folder etc. It relies heavily on the [plugin API](https://fman.io/docs/api). fman uses its own plugin system to ensure that the API is stable and powerful enough for real world use.

## Examples

* [Key Bindings.json](Key%20Bindings.json) defines the default key bindings
* [Theme.css](Theme.css) defines fman's visual appearance (to [some extent](https://github.com/fman-users/fman/issues/45))
* [commands/](core/commands/__init__.py) implements virtually all commands
* [local/](core/fs/local/__init__.py) lets fman work with the files on your local hard drive
* [zip.py](core/fs/zip.py) adds support for ZIP files

## Location in your installation directory
You can also find these source files in your fman installation directory. Their exact path depends on your operating system:

 * **Windows:** `C:/​Users/​<username>/​AppData/​Local/​fman/​Versions/​<version>/​Plugins/​Core`
 * **Mac:** `/​Applications/​fman.app/​Contents/​Resources/​Plugins/​Core`
 * **Linux:** `/opt/​fman/​Plugins/​Core`
