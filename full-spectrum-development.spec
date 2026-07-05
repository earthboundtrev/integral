# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — builds Integral.exe"""

import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
ROOT = os.path.dirname(os.path.abspath(SPEC))
ICON = os.path.join(ROOT, "assets", "icon.ico")

matplotlib_datas = collect_data_files("matplotlib")
matplotlib_hidden = collect_submodules("matplotlib.backends")

a = Analysis(
    ["personal_dev_tracker.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("programs", "programs"),
        ("assets", "assets"),
        *matplotlib_datas,
    ],    hiddenimports=[
        *matplotlib_hidden,
        "activity_grid",
        "paths",
        "theme",
        "graphs",
        "fitness_graphs",
        "fitness",
        "fitness.engine",
        "fitness.ui",
        "fitness.intelligence",
        "integral_io",
        "integral_dialogs",
        "vault",
        "milestones",
        "cryptography",
        "cryptography.fernet",
        "insights",
        "insights.engine",
        "insights.playbooks",
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

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Integral",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON if os.path.exists(ICON) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Integral",
)
