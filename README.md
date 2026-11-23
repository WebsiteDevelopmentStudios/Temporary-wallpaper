# Temporary Wallpaper (Windows)

A Windows-only desktop utility that temporarily applies an image wallpaper or video wallpaper. It remembers the last selection, saves a backup of the current wallpaper in Downloads, and registers a one-time logon restore so the original wallpaper comes back after Windows restarts.

## Build

The GitHub Actions workflow builds `TemporaryWallpaper.exe` on Windows and uploads it as an artifact. Download it from the workflow run's **Artifacts** section.

## Supported formats

- Images: PNG, JPG, JPEG, BMP, GIF, WEBP, TIFF
- Videos: MP4, WEBM, MKV, MOV, AVI, WMV, M4V (mpv is downloaded automatically on first launch)

Video wallpaper support uses mpv. On first launch, the application downloads the latest 64-bit Windows mpv build from the `zhongfly/mpv-winbuild` GitHub releases and extracts it under `%LOCALAPPDATA%\\TemporaryWallpaper\\mpv`. An internet connection is required for this first-time setup. If the download fails, image wallpapers remain available and the app reports the video setup error.

## Advanced non-AI image upscaling

The app uses a custom classical super-resolution pipeline that runs locally on the CPU. It does not download AI models and does not require CUDA, Vulkan, OpenCV, or a supported graphics card.

- **Iterative back-projection:** repeatedly compares a simulated downscaled result with the original pixels, then projects the residual back into the enlarged image.
- **Multi-channel refinement:** processes RGB channels independently to keep memory use manageable.
- **Edge-aware sharpening:** detects boundaries and applies stronger sharpening there while limiting changes in smooth regions.
- **Local contrast enhancement:** selectively boosts fine edge contrast after enlargement.
- **Resolution-aware output:** prepares the image for the detected virtual desktop size before the final cover crop.

This is a more advanced conventional approach than simply resizing and sharpening, but it cannot recreate real details that are not present in the source. A very small or badly blurred image will still have an upper limit without AI or a higher-resolution original.

## Behavior

- The last selected path is saved in the current user's Local AppData.
- Before applying, the current Windows wallpaper is copied to Downloads when its source file is accessible.
- A RunOnce entry restores the original wallpaper at the next sign-in. The application itself does not add a permanent startup entry.
- Run the application again after restarting to apply the remembered selection again.

## Notes

This is a per-user Windows desktop utility. Video playback is a separate desktop process; Windows terminates it during shutdown. Windows may show its normal wallpaper during sign-in before the RunOnce restore completes.
