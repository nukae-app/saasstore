"""Recompressió dels vídeos pujats a l'admin (Hero background_video, ver
routers/home_blocks.py) — sempre es recomprimeix, MAI es guarda l'original
tal qual. Un vídeo de fons pesa el que pesa el fitxer servit, i aquest
servidor no té cap CDN al davant (cada tenant pot tenir el seu propi
domini, així que un Cloudflare "per domini" no cobriria tots els tenants
d'un plumatge) — l'única palanca real de cost és que el fitxer final sigui
petit sempre, independentment del que pugi l'admin.

Estratègia de bitrate: `mida_objectiu ÷ durada real`, no un bitrate fix.
Així un clip curt surt més nítid i un de llarg (fins al màxim permès)
sempre pesa el mateix — un bitrate fix faria pesar molt més els vídeos
llargs (el pes escala amb bitrate × durada). MAX_DURATION_SECONDS existeix
per qualitat, no per cost: per sota d'un cert bitrate per segon el vídeo
surt amb blocs i no val la pena — un fons en bucle no necessita ser llarg,
l'efecte és el mateix amb 10s que amb 5 minuts."""

import json
import subprocess

MAX_DURATION_SECONDS = 50
TARGET_SIZE_BYTES = 3 * 1024 * 1024  # ~3MB
MAX_WIDTH = 1280
MIN_BITRATE_KBPS = 300  # mai baixar de tan poc que es vegi il·legible


class VideoTooLongError(Exception):
    pass


def _probe_duration_seconds(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def transcode_for_web(
    input_path: str,
    output_path: str,
    start: float | None = None,
    end: float | None = None,
) -> None:
    """Recomprimeix `input_path` a `output_path` (sempre .mp4, sense àudio,
    amplada màxima MAX_WIDTH) amb un bitrate calculat perquè el resultat
    pesi ~TARGET_SIZE_BYTES sigui quina sigui la durada.

    `start`/`end` (segons, ver VideoTrimmer.jsx) tallen el vídeo abans de
    recomprimir — l'admin pot triar quin tram d'un vídeo més llarg vol fer
    servir, en lloc de rebutjar-lo directament si passa de MAX_DURATION_SECONDS.
    Sense `start`/`end` es fa servir el vídeo sencer.

    Llança ValueError si l'interval no és vàlid, VideoTooLongError si el
    tram (o el vídeo sencer, sense tall) supera MAX_DURATION_SECONDS —
    abans de gastar temps recomprimint — i subprocess.CalledProcessError si
    ffprobe/ffmpeg no poden llegir el fitxer (format no vàlid/corrupte)."""
    full_duration = _probe_duration_seconds(input_path)

    if start is not None and end is not None:
        if start < 0 or end <= start or end > full_duration + 0.5:
            raise ValueError("Interval de tall no vàlid.")
        duration = end - start
    else:
        duration = full_duration

    if duration > MAX_DURATION_SECONDS:
        raise VideoTooLongError(f"El tram dura {duration:.0f}s — el màxim és {MAX_DURATION_SECONDS}s.")

    target_bitrate_kbps = max(MIN_BITRATE_KBPS, int((TARGET_SIZE_BYTES * 8) / duration / 1000))

    cmd = ["ffmpeg", "-y", "-i", input_path]
    if start is not None and end is not None:
        cmd += ["-ss", f"{start}", "-t", f"{duration}"]
    cmd += [
        "-an",
        "-vf", f"scale='min({MAX_WIDTH},iw)':-2",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-b:v", f"{target_bitrate_kbps}k",
        "-maxrate", f"{int(target_bitrate_kbps * 1.2)}k",
        "-bufsize", f"{target_bitrate_kbps * 2}k",
        "-movflags", "+faststart",
        output_path,
    ]
    subprocess.run(cmd, capture_output=True, timeout=120, check=True)
