"""Turn carousel slides into a swipe-style video with music, so the carousel slot always has a sound that fits.
(TikTok photo posts and Instagram/Facebook carousels sent through the API post silent: no way to attach music.)"""
import os, subprocess, json


def _dur(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
                         capture_output=True, text=True).stdout
    return float(json.loads(out)["format"]["duration"])


def make(slides, music, out, hold=3.0, first=2.6, swipe=0.35, volume=0.75):
    """slides: 1080x1920 images in order. Each slide holds, then swipes left into the next, like a carousel."""
    n = len(slides)
    holds = [first] + [hold] * (n - 2) + [hold + 0.8] if n > 1 else [first + 1.5]
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for s, h in zip(slides, holds):
        cmd += ["-loop", "1", "-t", f"{h + swipe:.2f}", "-i", s]
    total = sum(holds) + swipe
    if music:
        cmd += ["-stream_loop", "-1", "-i", music]
    fc, prev, t = [], "[0:v]", 0.0
    for i in range(n):
        fc.append(f"[{i}:v]scale=1080:1920,setsar=1,fps=30,format=yuv420p[v{i}]")
    prev = "[v0]"
    for i in range(1, n):
        t += holds[i - 1]
        fc.append(f"{prev}[v{i}]xfade=transition=slideleft:duration={swipe}:offset={t:.2f}[x{i}]")
        prev = f"[x{i}]"
    vout = prev
    if music:
        fc.append(f"[{n}:a]atrim=0:{total:.2f},asetpts=N/SR/TB,volume={volume},"
                  f"afade=t=in:d=0.4,afade=t=out:st={total - 1.5:.2f}:d=1.5[a]")
    cmd += ["-filter_complex", ";".join(fc), "-map", vout]
    if music:
        cmd += ["-map", "[a]", "-c:a", "aac", "-b:a", "160k"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30",
            "-t", f"{total:.2f}", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    return out
