from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import tempfile
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
import winreg
import urllib.request
import tempfile
import zipfile
import py7zr

from PIL import Image, ImageOps, ImageFilter

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
        backup_path = downloads / "Original-Wallpaper-Backup.bmp"
        try:
            with Image.open(source) as image:
                image.convert("RGB").save(backup_path, "BMP")
            backup = str(backup_path)
        except Exception:
            try:
                backup_path = downloads / f"Original-Wallpaper-Backup{source.suffix or '.bak'}"
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


def download_mpv() -> str:
    install_dir = APPDATA / "mpv"
    install_dir.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request("https://api.github.com/repos/zhongfly/mpv-winbuild/releases/latest", headers={"User-Agent": "TemporaryWallpaper"})
    with urllib.request.urlopen(request, timeout=30) as response:
        release = json.loads(response.read().decode("utf-8"))
    assets = [a for a in release.get("assets", []) if a.get("name", "").lower().startswith("mpv-x86_64-") and a.get("name", "").lower().endswith(".7z")]
    if not assets:
        raise RuntimeError("No compatible 64-bit mpv release archive was found.")
    asset = assets[0]
    # Use a unique temporary archive name so two app launches cannot collide.
    fd, archive_name = tempfile.mkstemp(prefix="mpv-download-", suffix=".7z", dir=install_dir)
    os.close(fd)
    archive = Path(archive_name)
    req = urllib.request.Request(asset["browser_download_url"], headers={"User-Agent": "TemporaryWallpaper"})
    try:
        with urllib.request.urlopen(req, timeout=120) as response, archive.open("wb") as output:
            shutil.copyfileobj(response, output)
        # Close the 7z reader before attempting to remove the archive (required on Windows).
        with py7zr.SevenZipFile(archive, mode="r") as sevenzip:
            sevenzip.extractall(path=install_dir)
    finally:
        try:
            archive.unlink(missing_ok=True)
        except OSError:
            # A transient Windows file lock should not turn a successful install into a failure.
            pass
    exe = next(install_dir.rglob("mpv.exe"), None)
    if exe is None:
        raise RuntimeError("mpv.exe was not found after extracting the download.")
    target = install_dir / "mpv.exe"
    if exe != target:
        shutil.copy2(exe, target)
        for item in exe.parent.iterdir():
            if item.is_file() and item.name.lower() != "mpv.exe":
                shutil.copy2(item, install_dir / item.name)
    return str(target)

def find_mpv() -> str | None:
    locations = [Path(sys.executable).resolve().parent, Path(__file__).resolve().parent]
    for folder in locations:
        candidate = folder / "mpv.exe"
        if candidate.is_file():
            return str(candidate)
    installed = APPDATA / "mpv" / "mpv.exe"
    if installed.is_file():
        return str(installed)
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


def desktop_resolution() -> tuple[int, int]:
    # Use the full virtual desktop size so multi-monitor desktops are covered.
    user32 = ctypes.windll.user32
    width = user32.GetSystemMetrics(78)
    height = user32.GetSystemMetrics(79)
    if width < 1 or height < 1:
        width = user32.GetSystemMetrics(0)
        height = user32.GetSystemMetrics(1)
    return max(width, 1), max(height, 1)


def ensure_ai_upscaler() -> Path:
    """Install the portable Real-ESRGAN upscaler for genuine AI super-resolution."""
    folder = APPDATA / "upscaler"
    executable = folder / "realesrgan-ncnn-vulkan.exe"
    model = folder / "models" / "realesrgan-x4plus.param"
    if executable.is_file() and model.is_file():
        return executable

    folder.mkdir(parents=True, exist_ok=True)
    api = "https://api.github.com/repos/xinntao/Real-ESRGAN-ncnn-vulkan/releases/latest"
    request = urllib.request.Request(api, headers={"User-Agent": "TemporaryWallpaper"})
    with urllib.request.urlopen(request, timeout=30) as response:
        release = json.loads(response.read().decode("utf-8"))
    asset = next((a for a in release.get("assets", [])
                  if a.get("name", "").endswith("windows.zip")), None)
    if asset is None:
        raise RuntimeError("Could not find the Windows AI upscaler download.")

    archive = folder / "realesrgan-windows.zip"
    req = urllib.request.Request(asset["browser_download_url"],
                                 headers={"User-Agent": "TemporaryWallpaper"})
    with urllib.request.urlopen(req, timeout=120) as response, archive.open("wb") as output:
        shutil.copyfileobj(response, output)
    with zipfile.ZipFile(archive, "r") as bundle:
        bundle.extractall(folder)
    try:
        archive.unlink(missing_ok=True)
    except OSError:
        pass

    found = next(folder.rglob("realesrgan-ncnn-vulkan.exe"), None)
    if found is None:
        raise RuntimeError("The AI upscaler executable was missing from its download.")
    if found != executable:
        for item in found.parent.iterdir():
            destination = folder / item.name
            if item.is_file():
                shutil.copy2(item, destination)
            elif item.is_dir() and item.name.lower() == "models":
                shutil.copytree(item, destination, dirs_exist_ok=True)
    if not model.is_file():
        raise RuntimeError("The Real-ESRGAN x4plus AI model was not installed.")
    return executable


def apply_image(path: Path) -> None:
    APPDATA.mkdir(parents=True, exist_ok=True)
    converted = APPDATA / "temporary-wallpaper-hd.bmp"
    target_width, target_height = desktop_resolution()
    upscaled = APPDATA / "temporary-wallpaper-ai-upscaled.png"

    # Real-ESRGAN generates new image detail at 4x resolution. If the PC does
    # not support the Vulkan runtime, retain a high-quality Lanczos fallback.
    ai_error = None
    try:
        upscaler = ensure_ai_upscaler()
        result = subprocess.run(
            [str(upscaler), "-i", str(path), "-o", str(upscaled),
             "-n", "realesrgan-x4plus", "-s", "4", "-f", "png"],
            capture_output=True, text=True, timeout=900,
            cwd=str(upscaler.parent),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0 or not upscaled.is_file():
            detail = (result.stderr or result.stdout or "Unknown upscaler error").strip()
            raise RuntimeError(detail[-1200:])
    except Exception as exc:
        ai_error = str(exc)

    with Image.open(upscaled if ai_error is None else path) as source:
        image = ImageOps.exif_transpose(source)
        if image.mode in ("RGBA", "LA") or "transparency" in image.info:
            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, (18, 18, 18, 255))
            image = Image.alpha_composite(background, rgba).convert("RGB")
        else:
            image = image.convert("RGB")

        image = ImageOps.fit(
            image, (target_width, target_height),
            method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)
        )
        if ai_error is not None:
            image = image.filter(ImageFilter.UnsharpMask(radius=1.5, percent=150, threshold=2))
        image.save(converted, "BMP")

    # Tell Windows to fill the display with our already-sized bitmap.
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                        r"Control Panel\Desktop", 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, "10")
        winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, "0")
    set_wallpaper(str(converted))
    global ai_warning
    ai_warning = (
        "AI upscaling was unavailable; a standard high-quality resize was used. "
        "Update your graphics driver for Vulkan support. Details: " + ai_error
        if ai_error is not None else ""
    )


def apply_video(path: Path) -> None:
    mpv = find_mpv() or download_mpv()
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
    status = tk.StringVar(value=globals().get("mpv_status", "Choose an image or video for your temporary wallpaper."))

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
            warning = globals().get("ai_warning", "")
            status.set(
                "Applied with standard resizing (AI upscaling unavailable)."
                if warning else
                "AI-upscaled and applied. Your original wallpaper will be restored at your next Windows sign-in."
            )
            if warning:
                messagebox.showwarning(APP_NAME, warning)
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
    try:
        ensure_status = "Video support is ready." if (find_mpv() or download_mpv()) else "Video support unavailable."
    except Exception as exc:
        ensure_status = f"Video support download failed: {exc}"
    mpv_status = ensure_status
    run_gui()
