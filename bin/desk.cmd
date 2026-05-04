set PATH=C:\Windows\SysWOW64\downlevel;C:\Program Files (x86)\NSIS;C:\Program Files (x86)\Windows Kits\10\bin\10.0.18362.0\x86;%PATH%

SET ROOT=%~dp0..
CD %ROOT%

CALL .venv\scripts\activate.bat
DOSKEY run=python build.py run $*
DOSKEY clean=python build.py clean
DOSKEY freeze=python build.py freeze $*
DOSKEY installer=python build.py installer $*
DOSKEY sign=python build.py sign $*
DOSKEY sign_installer=python build.py sign_installer $*
DOSKEY publish=python build.py publish $*
DOSKEY tests=python build.py test $*
DOSKEY release=python build.py release $*