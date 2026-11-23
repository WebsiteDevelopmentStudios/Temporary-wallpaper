# Temporary Wallpaper (Windows)

A Windows-only desktop utility that temporarily applies an image wallpaper or video wallpaper. It remembers the last selection, saves a backup of the current wallpaper in Downloads, and registers a one-time logon restore so the original wallpaper comes back after Windows restarts.

## Build

The GitHub Actions workflow builds `TemporaryWallpaper.exe` on Windows and uploads it as an artifact. Download it from the workflow run's **Artifacts** section.

## Supported formats

- Images: PNG, JPG, JPEG, BMP, GIF, WEBP, TIFF
- Videos: MP4, WEBM, MKV, MOV, AVI, WMV, M4V (mpv is downloaded automatically on first launch)

Video wallpaper support uses mpv. On first launch, the application downloads the latest 64-bit Windows mpv build from the `zhongfly/mpv-winbuild` GitHub releases and extracts it under `%LOCALAPPDATA%\\TemporaryWallpaper\\mpv`. An internet connection is required for this first-time setup. If the download fails, image wallpapers remain available and the app reports the video setup error.

## AI image enhancement

For images smaller than the desktop resolution, the app automatically downloads the lightweight FSRCNN-small x2 model (about 10 KB) and runs it through OpenCV on the CPU. It does not require Vulkan, CUDA, or a supported GPU. CPU processing can take longer on older computers. If model download or processing fails, the app falls back to high-quality Lanczos resizing and displays a warning.

## Behavior

- The last selected path is saved in the current user's Local AppData.
- Before applying, the current Windows wallpaper is copied to Downloads when its source file is accessible.
- A RunOnce entry restores the original wallpaper at the next sign-in. The application itself does not add a permanent startup entry.
- Run the application again after restarting to apply the remembered selection again.

## Notes

This is a per-user Windows desktop utility. Video playback is a separate desktop process; Windows terminates it during shutdown. Windows may show its normal wallpaper during sign-in before the RunOnce restore completes.
