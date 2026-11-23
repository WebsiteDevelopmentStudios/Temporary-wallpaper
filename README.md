# Temporary Wallpaper (Windows)

A Windows-only desktop utility that temporarily applies an image wallpaper or video wallpaper. It remembers the last selection, saves a backup of the current wallpaper in Downloads, and registers a one-time logon restore so the original wallpaper comes back after Windows restarts.

## Build

The GitHub Actions workflow builds `TemporaryWallpaper.exe` on Windows and uploads it as an artifact. Download it from the workflow run's **Artifacts** section.

## Supported formats

- Images: PNG, JPG, JPEG, BMP, GIF, WEBP, TIFF
- Videos: MP4, WEBM, MKV, MOV, AVI, WMV, M4V (mpv is downloaded automatically on first launch)

Video wallpaper support uses mpv. On first launch, the application downloads the latest 64-bit Windows mpv build from the `zhongfly/mpv-winbuild` GitHub releases and extracts it under `%LOCALAPPDATA%\\TemporaryWallpaper\\mpv`. An internet connection is required for this first-time setup. If the download fails, image wallpapers remain available and the app reports the video setup error.

## Advanced non-AI image upscaling

Image wallpapers use a custom local image-processing pipeline. It does not download or run AI models and does not need OpenCV, CUDA, Vulkan, or a compatible graphics card.

The pipeline:
- Upscales in multiple bounded stages using high-quality Lanczos resampling to reduce the softness that can appear in one large resize.
- Detects edges and applies sharpening selectively around boundaries instead of sharpening every pixel equally.
- Uses a restrained fine-detail and contrast pass to improve perceived clarity while limiting halos and noise.
- Fits the processed image to the detected desktop resolution, including multi-monitor virtual desktop dimensions.

This is advanced conventional upscaling, not AI super-resolution: it can improve interpolation and perceived sharpness, but it cannot truthfully recreate details that are absent from a tiny or heavily blurred source image. Everything runs locally on the PC.

## Behavior

- The last selected path is saved in the current user's Local AppData.
- Before applying, the current Windows wallpaper is copied to Downloads when its source file is accessible.
- A RunOnce entry restores the original wallpaper at the next sign-in. The application itself does not add a permanent startup entry.
- Run the application again after restarting to apply the remembered selection again.

## Notes

This is a per-user Windows desktop utility. Video playback is a separate desktop process; Windows terminates it during shutdown. Windows may show its normal wallpaper during sign-in before the RunOnce restore completes.
