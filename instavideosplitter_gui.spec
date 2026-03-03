# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for InstaVideoSplitter GUI
#
# Usage:
#   pip install pyinstaller
#   pyinstaller instavideosplitter_gui.spec
#
# Output: dist/InstaVideoSplitter/

from pathlib import Path

block_cipher = None

a = Analysis(
    ["instavideosplitter/gui.py"],
    pathex=["."],
    binaries=[],
    datas=[
        # Bundle assets directory (icon, etc.)
        ("assets", "assets"),
        # Bundle docs screenshots
        ("docs", "docs"),
    ],
    hiddenimports=[
        "imageio.plugins.ffmpeg",
        "imageio_ffmpeg",
        "moviepy.video.io.ffmpeg_reader",
        "moviepy.video.io.ffmpeg_writer",
        "moviepy.audio.io.readers",
        "customtkinter",
        "darkdetect",
        "cv2",
        "numpy",
        "PIL",
        "PIL.Image",
        "PIL.ImageTk",
        # Package internals
        "instavideosplitter.core",
        "instavideosplitter.export_part",
        "instavideosplitter.ffmpeg_config",
        "instavideosplitter.ffprobe_utils",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

from PyInstaller.utils.hooks import collect_data_files
a.datas += collect_data_files("customtkinter")

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="InstaVideoSplitter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.png" if Path("assets/icon.png").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="InstaVideoSplitter",
)
