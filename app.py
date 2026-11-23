from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
import winreg

from PIL import Image

APP_NAME = "Temporary Wallpaper"
APPDATA = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "TemporaryWallpaper"
STATE_FILE = APPDATA / "state.json"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv", ".mov", ".avi", ".wmv", ".m4v"}
RUNONCE_KEY = r"Software\Microsoft\Windows\CurrentVersion\RunOnce"
SPI_SETDESKWALLPAPER = 20
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE = 0x02


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    APPDATA.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def current_wallpaper() -> str:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop") as key:
            return winreg.QueryValueEx(key, "WallPaper")[0]
    except OSError:
        return ""


def set_wallpaper(path: str) -> None:
    ok = ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETDESKWALLPAPER, 0, path, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
    )
    if not ok:
        raise ctypes.WinError()


def register_restore() -> None:
    if getattr(sys, "frozen", False):
        command = f'"{sys.executable}" --restore'
    else:
        command = f'"{sys.executable}" "{Path(__file__).resolve()}" --restore'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUNONCE_KEY) as key:
        winreg.SetValueEx(key, "TemporaryWallpaperRestore", 0, winreg.REG_SZ, command)


def backup_original() -> tuple[str, str]:
    # Preserve the first wallpaper captured during this temporary session.
    previous = load_state()
    if previous.get("original_wallpaper"):
        return previous["original_wallpaper"], previous.get("backup_copy", "")

    original = current_wallpaper()
    downloads = Path.home() / "Downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    backup = ""
    source = Path(original) if original else None
    if source and source.is_file():
        backup_path = downloads / f"Original-Wallpaper-Backup{source.suffix or '.img'}"
        try:
            shutil.copy2(source, backup_path)
            backup = str(backup_path)
        except OSError:
            pass
    return original, backup


def restore() -> int:
    state = load_state()
    original = state.get("original_wallpaper", "")
    backup = state.get("backup_copy", "")
    target = original if original and Path(original).is_file() else backup
    if target and Path(target).is_file():
        try:
            set_wallpaper(target)
            return 0
        except Exception:
            return 1
    # Nothing to restore is preferable to leaving a stale RunOnce command.
    return 0


def find_mpv() -> str | None:
    locations = [Path(sys.executable).resolve().parent, Path(__file__).resolve().parent]
    for folder in locations:
        candidate = folder / "mpv.exe"
        if candidate.is_file():
            return str(candidate)
    return shutil.which("mpv.exe") or shutil.which("mpv")


def find_desktop_worker() -> int:
    user32 = ctypes.windll.user32
    progman = user32.FindWindowW("Progman", None)
    if progman:
        result = ctypes.c_ulong()
        user32.SendMessageTimeoutW(progman, 0x052C, 0, 0, 0, 1000, ctypes.byref(result))

    worker = 0
    enum_callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def callback(hwnd, _):
        nonlocal worker
        shell_view = user32.FindWindowExW(hwnd, 0, "SHELLDLL_DefView", None)
        if shell_view:
            worker = user32.FindWindowExW(0, hwnd, "WorkerW", None)
            return False
        return True

    callback_ref = enum_callback_type(callback)
    user32.EnumWindows(callback_ref, 0)
    return worker or progman


def stop_previous_video() -> None:
    pid = load_state().get("video_pid")
    if pid:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)


def apply_image(path: Path) -> None:
    APPDATA.mkdir(parents=True, exist_ok=True)
    converted = APPDATA / "temporary-wallpaper.bmp"
    with Image.open(path) as image:
        image.convert("RGB").save(converted, "BMP")
    set_wallpaper(str(converted))


def apply_video(path: Path) -> None:
    mpv = find_mpv()
    if not mpv:
        raise RuntimeError(
            "Video playback needs mpv.exe. Put mpv.exe in the same folder as TemporaryWallpaper.exe."
        )
    worker = find_desktop_worker()
    if not worker:
        raise RuntimeError("Could not locate the Windows desktop surface for video playback.")
    args = [
        mpv, f"--wid={worker}", "--no-border", "--fullscreen",
        "--loop-file=inf", "--no-audio", "--panscan=1.0",
        "--input-default-bindings=no", "--osc=no", str(path)
    ]
    process = subprocess.Popen(args, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    state = load_state()
    state["video_pid"] = process.pid
    save_state(state)


def apply_selection(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError("The selected file no longer exists.")
    ext = path.suffix.lower()
    if ext not in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
        raise ValueError("That file type is not supported.")

    original, backup = backup_original()
    state = load_state()
    state.update({
        "last_selected": str(path),
        "original_wallpaper": original,
        "backup_copy": backup,
        "video_pid": None,
    })
    save_state(state)
    register_restore()
    stop_previous_video()

    if ext in IMAGE_EXTENSIONS:
        apply_image(path)
    else:
        apply_video(path)


def run_gui() -> None:
    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("540x260")
    root.resizable(False, False)
    root.configure(bg="#171923")

    state = load_state()
    remembered = state.get("last_selected", "")
    selected = tk.StringVar(value=remembered or "No file selected")
    status = tk.StringVar(value="Choose an image or video for your temporary wallpaper.")

    tk.Label(root, text="Temporary Wallpaper", font=("Segoe UI", 19, "bold"),
             fg="#f5f5f5", bg="#171923").pack(pady=(20, 5))
    tk.Label(root, textvariable=selected, font=("Segoe UI", 9), fg="#b7bdcc",
             bg="#171923", wraplength=490).pack(pady=8)

    def choose() -> None:
        path = filedialog.askopenfilename(
            title="Choose a temporary wallpaper",
            filetypes=[
                ("Images and videos", "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff *.mp4 *.webm *.mkv *.mov *.avi *.wmv *.m4v"),
                ("All files", "*.*")
            ]
        )
        if not path:
            return
        selected.set(path)
        try:
            apply_selection(Path(path))
            status.set("Applied. Your original wallpaper will be restored at your next Windows sign-in.")
        except Exception as exc:
            status.set("Could not apply the selected file.")
            messagebox.showerror(APP_NAME, str(exc))

    tk.Button(root, text="Choose image or video", command=choose,
              font=("Segoe UI", 11, "bold"), bg="#4f8cff", fg="white",
              activebackground="#3976df", relief="flat", padx=20, pady=10).pack(pady=12)
    tk.Label(root, textvariable=status, font=("Segoe UI", 9), fg="#aab3c5",
             bg="#171923", wraplength=490).pack(pady=5)
    tk.Label(root, text="Your last selection is remembered for next time.",
             font=("Segoe UI", 8), fg="#737d91", bg="#171923").pack(side="bottom", pady=12)
    root.mainloop()


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("Temporary Wallpaper only runs on Windows.")
    if "--restore" in sys.argv:
        raise SystemExit(restore())
    run_gui()
