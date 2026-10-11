"""Turn record.js output into demo.mp4, playing the marked segments faster.

record.js shows a 6px corner marker while typing / page loads (magenta = 3x) and while waiting on the assistant
(cyan = 6x). This finds those frames, speeds only those segments up, and crops the marker row off. Captions are
burned into the page and stay at normal reading speed.
Usage: python3 finish.py /path/to/OUT"""
import subprocess, sys

out = sys.argv[1]
FPS = 25
SPEED = {1: 3.0, 2: 6.0}
cfr = f"{out}/cfr.mp4"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{out}/demo.webm", "-r", str(FPS), "-c:v", "libx264", "-crf", "14",
                "-pix_fmt", "yuv420p", cfr], check=True)
raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", cfr, "-vf", "crop=6:6:0:0,scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                     check=True, capture_output=True).stdout
kinds = []
for i in range(0, len(raw), 3):
    r, g, b = raw[i], raw[i + 1], raw[i + 2]
    kinds.append(1 if (r > 150 and b > 150 and g < 120) else 2 if (g > 150 and b > 150 and r < 120) else 0)
# ignore single-frame flickers from encoding
for i in range(1, len(kinds) - 1):
    if kinds[i - 1] == kinds[i + 1] != kinds[i]:
        kinds[i] = kinds[i - 1]
segs, start = [], 0
for i in range(1, len(kinds) + 1):
    if i == len(kinds) or kinds[i] != kinds[start]:
        segs.append((start, i, kinds[start])); start = i
parts, labels = [], []
for n, (a, b, k) in enumerate(segs):
    f = SPEED.get(k, 1.0)
    parts.append(f"[0:v]trim=start_frame={a}:end_frame={b},setpts=(PTS-STARTPTS)/{f}[v{n}]")
    labels.append(f"[v{n}]")
graph = ";".join(parts) + f";{''.join(labels)}concat=n={len(segs)}:v=1:a=0,crop=in_w:in_h-6:0:6,scale=1280:720,setsar=1[v]"
open(f"{out}/graph.txt", "w").write(graph)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", cfr, "-filter_complex_script", f"{out}/graph.txt", "-map", "[v]", "-r", str(FPS),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "22", "-preset", "medium", "-movflags", "+faststart", f"{out}/demo.mp4"], check=True)
dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f"{out}/demo.mp4"]))
raw_s = len(kinds) / FPS
print(f"recorded {raw_s:.0f}s -> demo.mp4 {dur:.0f}s ({sum(1 for k in kinds if k)/FPS:.0f}s sped up); limit 180s")
