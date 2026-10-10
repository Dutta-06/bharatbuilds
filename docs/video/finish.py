"""Turn record.js output into demo.mp4 and rescale demo.srt to the video's real length.
Playwright records page loads slower than the script's own clock, so cue times drift by ~5%.
Usage: python3 finish.py /path/to/OUT"""
import re, subprocess, sys
out = sys.argv[1]
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{out}/demo.webm", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-crf", "23", "-preset", "medium", "-movflags", "+faststart", f"{out}/demo.mp4"], check=True)
dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f"{out}/demo.mp4"]))
txt = open(f"{out}/demo.srt").read()
sec = lambda h, m, s, ms: int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
last = [sec(*m) for m in re.findall(r"--> (\d\d):(\d\d):(\d\d),(\d\d\d)", txt)][-1]
k = (dur - 1.0) / last
def fmt(t):
    ms = int(round(t * 1000)); return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
open(f"{out}/demo.srt", "w").write(re.sub(r"(\d\d):(\d\d):(\d\d),(\d\d\d)", lambda m: fmt(sec(*m.groups()) * k), txt))
print(f"demo.mp4 {dur:.0f}s, subtitle scale {k:.3f}")
