# Temporary Wallpaper (Windows)

A Windows-only desktop utility that temporarily applies an image wallpaper or video wallpaper. It remembers the last selection, saves a backup of the current wallpaper in Downloads, and registers a one-time logon restore so the original wallpaper comes back after Windows restarts.

## Build

The GitHub Actions workflow builds `TemporaryWallpaper.exe` on Windows and uploads it as an artifact. Download it from the workflow run's **Artifacts** section.

## Supported formats

- Images: PNG, JPG, JPEG, BMP, GIF, WEBP, TIFF
- Videos: MP4, WEBM, MKV, MOV, AVI, WMV, M4V (mpv is downloaded automatically on first launch)

Video wallpaper support uses mpv. On first launch, the application downloads the latest 64-bit Windows mpv build from the `zhongfly/mpv-winbuild` GitHub releases and extracts it under `%LOCALAPPDATA%\\TemporaryWallpaper\\mpv`. An internet connection is required for this first-time setup. If the download fails, image wallpapers remain available and the app reports the video setup error.

## Advanced non-AI image enhancement

The app uses a classical image-processing pipeline that runs locally on the CPU. It does not download AI models and does not require CUDA, Vulkan, OpenCV, or a supported graphics card.

- **Luminance deblurring:** applies a conservative Richardson-Lucy-style deconvolution pass to brightness detail before enlargement.
- **Color-safe processing:** performs detail recovery on luminance, then enlarges the color channels separately to reduce colored halos.
- **High-quality resampling:** uses Lanczos interpolation to scale the image to the detected virtual desktop resolution.
- **Edge-gated sharpening:** strengthens visible boundaries while avoiding aggressive sharpening of flat areas and gradients.
- **Resolution-aware output:** prepares the image for the full virtual desktop before the final cover crop.

This is conventional, non-AI enhancement. It can make existing edges look clearer, but it cannot recover photographic details that were never captured. A tiny, heavily compressed, or badly blurred source will still have a limit; the best result comes from starting with the highest-quality original available.

## Behavior

- The last selected path is saved in the current user's Local AppData.
- Before applying, the current Windows wallpaper is copied to Downloads when its source file is accessible.
- A RunOnce entry restores the original wallpaper at the next sign-in. The application itself does not add a permanent startup entry.
- Run the application again after restarting to apply the remembered selection again.

## Notes

This is a per-user Windows desktop utility. Video playback is a separate desktop process; Windows terminates it during shutdown. Windows may show its normal wallpaper during sign-in before the RunOnce restore completes.
