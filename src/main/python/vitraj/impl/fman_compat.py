"""Legacy fman plugin compatibility.

Many third-party plugins were written for the original *fman* app and import
from the ``fman`` namespace: ``from fman import ...``, ``from fman.fs import
...`` and occasionally deep paths such as ``from fman.impl.util.qt.thread
import run_in_main_thread``.

Aliasing only the top-level packages in ``sys.modules`` (``fman``, ``fman.fs``,
...) was not enough: a deep ``fman.impl.*`` import made Python *re-execute*
``impl``, ``impl.util``, ... under the ``fman`` name. Because
``sys.modules['fman'] is vitraj``, importlib's ``setattr(parent, child,
submodule)`` then clobbered ``vitraj.impl`` with the freshly executed (and
incomplete) ``fman.impl`` tree -- which was missing siblings such as
``vitraj.impl.util.path`` -> ``AttributeError`` at runtime.

The fix is a meta-path finder that maps every ``fman[.X]`` import onto the
identical ``vitraj[.X]`` module object, so no duplicate tree is ever created.
"""

import importlib
import importlib.util
import sys

_SRC = 'fman'
_DST = 'vitraj'


class _FmanCompatLoader:
    """Loader that returns the matching ``vitraj`` module, unmodified."""

    def create_module(self, spec):
        target = _DST + spec.name[len(_SRC):]
        return importlib.import_module(target)

    def exec_module(self, module):
        # The vitraj module is already executed; nothing to do.
        pass


class _FmanCompatFinder:
    """Resolve ``fman`` and ``fman.*`` to the identical ``vitraj`` module."""

    def find_spec(self, fullname, path=None, target=None):
        if fullname != _SRC and not fullname.startswith(_SRC + '.'):
            return None
        return importlib.util.spec_from_loader(fullname, _FmanCompatLoader())


def install():
    """Install the fman -> vitraj import shim. Idempotent."""
    if any(isinstance(finder, _FmanCompatFinder) for finder in sys.meta_path):
        return
    # Make sure the real package is importable before we start redirecting.
    import vitraj  # noqa: F401
    sys.meta_path.insert(0, _FmanCompatFinder())
