# 🎧 H-DJ – Automatic Song Mixer & Smart Player

**H-DJ** is a drag-and-drop DJ application that lets you smoothly transition between `.mp3` tracks with beat-aware crossfades, BPM + key analysis, live waveform display, and a retro-inspired UI.

---

## 🚀 Features

- 📂 **Drag & drop** your music folder into the app — no terminal needed
- 🧠 **Automatic BPM detection** using audio analysis (`librosa`)
- 🎼 **Musical Key notation detection** for harmonic mixing
- 🎚️ **15-second crossfade transitions** for seamless track blending
- 📊 **Waveform visualization** of currently playing track
- ⏱️ **Live time counter** showing current playback time
- 🔈 **Volume sliders per channel** (Channel A / B)
- 🌀 Auto-sorts tracks by BPM and Key (Camelot) for energy flow
- ⏯️ **Pause / Play toggle button**
- 👆 Clickable "**Next Track**" button or press `SPACE` to transition
- 🎧 Stylized UI with real-time song loading feedback

---

## 🖥️ Requirements

- Python 3.8+
- [ffmpeg](https://ffmpeg.org/download.html) (required by `librosa` for decoding mp3s)

### 📦 Install dependencies

```bash
pip install -r requirements.txt


