# LoopCam

A minimalistic, human-centric virtual camera and audio routing tool for Debian-based systems. Beacuse your AI-Slop bores me.

LoopCam was built with a simple philosophy: give users the power to route video and audio without the bloat. Whether you are trying to loop a video file for a waiting room, pipe your IP Webcam into a meeting app, or route your desktop audio through a virtual microphone, LoopCam handles it with a clean GTK3 interface and minimal dependencies.

## Why LoopCam?
- **No Fluff**: Just clean, readable code and a distraction-free interface.
- **Debian Native**: Uses `pkexec` for safe privilege escalation and integrates perfectly with standard Debian desktop environments.
- **Audio + Video**: Combines virtual webcam creation with advanced PulseAudio routing (originally from RhythmRoute) in one unified app.
- **Developer Friendly**: Built by Uzair Mughal. Read the code, fork it, and make it your own.

## Requirements
- Debian-based Linux distribution
- Python 3, GTK3 (`python3-gi`, `gir1.2-gtk-3.0`)
- `v4l2loopback-dkms` and `v4l2loopback-utils`
- `pulseaudio-utils` (pactl)
- `ffmpeg` (for piping video sources to the virtual device)

## Releases & Installation

We believe in making installation as frictionless as possible. LoopCam is packaged natively for Debian-based systems. 

Whenever a new version is tagged and pushed to the repository, our GitHub Actions workflow automatically compiles the source code, bundles the desktop entries, icons, and metadata, and generates a clean `.deb` installer.

## Downloading the Latest Release
1. Head over to the **[Releases Page](https://github.com/uzairdeveloper223/loopcam/releases)**.
2. Download the latest `.deb` file (e.g., `loopcam_1.0.0-1_all.deb`).
3. Install it using your package manager. This ensures all dependencies (like `ffmpeg`, `v4l2loopback`, and `policykit-1`) are automatically fetched and installed.

```bash
# navigate to your downloads folder
cd ~/Downloads

# install the package (apt handles local dependencies automatically)
sudo apt install ./loopcam_1.0.0-1_all.deb
```

### Installation (manual)
```bash
git clone https://github.com/uzairdeveloper223/loopcam.git
cd loopcam
chmod +x loopcam.py
./loopcam.py
```

## The `/dev/video10` Preference
We default to `video_nr=10` (`/dev/video10`). Why? Because many applications (like Zoom or Discord) aggressively scan for cameras starting at `/dev/video0`. By placing our virtual camera at ID 10, it sits quietly until you specifically select it, preventing it from accidentally overriding your physical webcam during system boot.

## Contact & Links
- **Author**: Uzair Mughal
- **Email**: contact@uzair.is-a.dev
- **Website**: [uzair.is-a.dev](https://uzair.is-a.dev)
- **GitHub**: [github.com/uzairdeveloper223](https://github.com/uzairdeveloper223)