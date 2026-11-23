# Temporary Wallpaper (Windows)

A Windows-only desktop utility that temporarily applies an image wallpaper or video wallpaper. It remembers the last selection, saves a backup of the current wallpaper in Downloads, and registers a one-time logon restore so the original wallpaper comes back after Windows restarts.

## Build

The GitHub Actions workflow builds `TemporaryWallpaper.exe` on Windows and uploads it as an artifact. Download it from the workflow run's **Artifacts** section.

## Supported formats

- Images: PNG, JPG, JPEG, BMP, GIF, WEBP, TIFF
- Videos: MP4, WEBM, MKV, MOV, AVI (requires mpv.exe alongside the application or available on PATH)

Video wallpaper support uses mpv. The application looks for `mpv.exe` in its own folder and then on PATH. Without mpv, image wallpapers still work.

## Behavior

- The last selected path is saved in the current user's Local AppData.
- Before applying, the current Windows wallpaper is copied to Downloads when its source file is accessible.
- A RunOnce entry restores the original wallpaper at the next sign-in. The application itself does not add a permanent startup entry.
- Run the application again after restarting to apply the remembered selection again.

## Notes

This is a per-user Windows desktop utility. Video playback is a separate desktop process; Windows terminates it during shutdown. Windows may show its normal wallpaper during sign-in before the RunOnce restore completes.
