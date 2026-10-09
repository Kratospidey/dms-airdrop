"""Compile locally and verify shared-library loading without opening a window."""
import os
from pathlib import Path
import subprocess
import tempfile


def build_picker(root):
    root = Path(root).resolve()
    build = root / ".build/picker"
    try:
        subprocess.run(["cmake", "-S", str(root / "native"), "-B", str(build),
                        "-DCMAKE_BUILD_TYPE=Release"], check=True)
        subprocess.run(["cmake", "--build", str(build), "--parallel", "2"], check=True)
        executable = build / "dms-airdrop-picker"
        if not os.access(executable, os.X_OK): raise ValueError("Build did not produce an executable picker")
        with tempfile.TemporaryDirectory(prefix="dms-picker-verify-") as tmp:
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="",
                       XDG_RUNTIME_DIR=tmp, HOME=tmp, XDG_CONFIG_HOME=tmp,
                       XDG_CACHE_HOME=tmp, XDG_DATA_HOME=tmp, XDG_STATE_HOME=tmp,
                       DBUS_SESSION_BUS_ADDRESS="unix:path=" + tmp + "/no-session-bus")
            # Load Qt's offscreen platform and linked KDE libraries, no dialog.
            result = subprocess.run([str(executable), "--check"], env=env, capture_output=True, text=True, timeout=15, check=True)
            if result.stdout.strip() != '{"ok":true}':
                raise ValueError("Native picker returned an unexpected self-check response")
        print("Native picker built and offscreen loader verified:", executable)
        return executable
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError("Native picker build/loader verification failed. Install Qt6/KF6 development packages, inspect CMake output, or retry install.sh --picker basic. " + str(error)) from error
