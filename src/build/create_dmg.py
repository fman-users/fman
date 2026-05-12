"""Create a styled DMG installer for vitraj on macOS."""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

W, H = 660, 480
ICON_SIZE = 80
APP_POS = (175, 260)
APPS_POS = (485, 260)
VOL_NAME = 'vitraj'


def _run(cmd, **kwargs):
    print(f'  $ {cmd if isinstance(cmd, str) else " ".join(cmd)}')
    return subprocess.run(cmd, shell=isinstance(cmd, str), check=True, **kwargs)


def _eject_existing():
    for suffix in ['', ' 1', ' 2']:
        vol = f'/Volumes/{VOL_NAME}{suffix}'
        if os.path.exists(vol):
            subprocess.run(
                ['hdiutil', 'detach', vol, '-force'],
                capture_output=True,
            )
            time.sleep(1)


def create_dmg(project_dir: Path):
    app_path = project_dir / 'target' / 'vitraj.app'
    bg_path = project_dir / 'target' / 'dmg_background.png'
    dmg_path = project_dir / 'target' / 'vitraj.dmg'
    rw_dmg = project_dir / 'target' / 'rw.vitraj.dmg'

    if not app_path.exists():
        print('ERROR: target/vitraj.app not found. Run `python build.py freeze` first.')
        sys.exit(1)

    if not bg_path.exists():
        print('Generating background image...')
        from dmg_background import generate
        generate(project_dir, bg_path)

    _eject_existing()

    for old in [dmg_path, rw_dmg]:
        old.unlink(missing_ok=True)

    app_size_mb = sum(
        f.stat().st_size for f in app_path.rglob('*') if f.is_file()
    ) // (1024 * 1024)
    dmg_size_mb = app_size_mb + 20

    print(f'Creating {dmg_size_mb}MB read-write DMG...')
    _run([
        'hdiutil', 'create',
        '-volname', VOL_NAME,
        '-size', f'{dmg_size_mb}m',
        '-fs', 'HFS+',
        '-type', 'UDIF',
        str(rw_dmg),
    ])

    mount_point = f'/Volumes/{VOL_NAME}'

    print('Mounting...')
    _run([
        'hdiutil', 'attach', str(rw_dmg),
        '-readwrite', '-noverify', '-noautoopen',
        '-mountpoint', mount_point,
    ])
    print(f'  Mounted at: {mount_point}')

    try:
        print('Copying app...')
        _run(['cp', '-R', str(app_path), f'{mount_point}/'])
        os.symlink('/Applications', f'{mount_point}/Applications')

        icns_path = project_dir / 'target' / 'Icon.icns'
        if icns_path.exists():
            print('Setting volume icon...')
            shutil.copy2(str(icns_path), f'{mount_point}/.VolumeIcon.icns')
            _run(['SetFile', '-a', 'C', mount_point])

        bg_dir = Path(mount_point) / '.background'
        bg_dir.mkdir()
        shutil.copy2(str(bg_path), str(bg_dir / 'background.png'))

        print('Styling Finder window...')
        applescript = f'''
            tell application "Finder"
                tell disk "{VOL_NAME}"
                    open
                    delay 2
                    set cw to container window
                    set current view of cw to icon view
                    set toolbar visible of cw to false
                    set statusbar visible of cw to false
                    set sidebar width of cw to 0
                    set bounds of cw to {{100, 100, {100 + W}, {100 + H}}}
                    delay 1
                    set theViewOptions to icon view options of cw
                    set arrangement of theViewOptions to not arranged
                    set icon size of theViewOptions to {ICON_SIZE}
                    set text size of theViewOptions to 10
                    set background picture of theViewOptions to file ".background:background.png"
                    delay 1
                    set position of item "vitraj.app" of cw to {{{APP_POS[0]}, {APP_POS[1]}}}
                    set position of item "Applications" of cw to {{{APPS_POS[0]}, {APPS_POS[1]}}}
                    update without registering applications
                    delay 1
                    close
                end tell
            end tell
        '''
        _run(['osascript', '-e', applescript])
        time.sleep(2)

        ds_store = Path(mount_point) / '.DS_Store'
        if ds_store.exists():
            print('  .DS_Store created successfully')

    finally:
        print('Detaching...')
        for attempt in range(5):
            try:
                _run(['hdiutil', 'detach', mount_point, '-quiet'])
                break
            except subprocess.CalledProcessError:
                if attempt < 4:
                    time.sleep(2)
                else:
                    _run(['hdiutil', 'detach', mount_point, '-force'])

    print('Converting to compressed DMG...')
    _run([
        'hdiutil', 'convert', str(rw_dmg),
        '-format', 'UDZO',
        '-imagekey', 'zlib-level=9',
        '-o', str(dmg_path),
    ])

    rw_dmg.unlink(missing_ok=True)

    icns_in_app = app_path / 'Contents' / 'Resources' / 'Icon.icns'
    if icns_in_app.exists():
        print('Setting DMG file icon...')
        _run(['osascript', '-e', (
            'use framework "AppKit"\n'
            'set iconImage to current application\'s NSImage\'s alloc()\'s '
            f'initWithContentsOfFile:"{icns_in_app}"\n'
            'current application\'s NSWorkspace\'s sharedWorkspace()\'s '
            f'setIcon:iconImage forFile:"{dmg_path}" options:0'
        )])

    size_mb = dmg_path.stat().st_size / (1024 * 1024)
    print(f'\nDone: {dmg_path} ({size_mb:.1f} MB)')


if __name__ == '__main__':
    project = Path(__file__).resolve().parent.parent.parent
    create_dmg(project)
