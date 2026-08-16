#!/usr/bin/env python3
"""Visual type normalization for scene metadata.

Mantiene compatibilidad backward con JSON legacy.
Normaliza escenas a estructura visual.type, visual.path, visual.fit, visual.motion.

Uso:
    from shorts_creator.validation.visual_normalize import normalize_scene_visual
    visual = normalize_scene_visual(scene, video_dir)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def normalize_scene_visual(
    scene: dict,
    video_dir: Path | None = None,
) -> dict:
    """Normaliza una escena a estructura visual estandarizada.

    Escenas legacy (sin campo visual) se normalizan automáticamente.
    Escenas con visual.type=video se dejan intactas (preparación futura).

    Args:
        scene: Escena del metadata.json
        video_dir: Directorio del job (para resolver rutas)

    Returns:
        Dict con type, path, fit, motion
    """
    if "visual" in scene:
        v = scene["visual"]
        v.setdefault("type", "image")
        v.setdefault("fit", "cover")
        v.setdefault("motion", scene.get("motionType", v.get("motion", "static")))
        if not v.get("path"):
            v["path"] = _default_image_path(scene, video_dir)
        v.setdefault("motion", scene.get("motionType", "static"))
        if "motion" in v and v["motion"] != scene.get("motionType", ""):
            pass
        return v

    return {
        "type": "image",
        "path": scene.get("visualPath") or _default_image_path(scene, video_dir),
        "fit": "cover",
        "motion": scene.get("motionType", "static"),
    }


def normalize_all_scenes(
    scenes: list[dict],
    video_dir: Path | None = None,
) -> list[dict]:
    """Normaliza todas las escenas de un job."""
    return [normalize_scene_visual(s, video_dir) for s in scenes]


def _default_image_path(scene: dict, video_dir: Path | None = None) -> str:
    sn = scene.get("sceneNumber", 1)
    return f"scenes/scene-{sn:02}.jpg"


def asset_path_for_scene(
    scene: dict,
    video_dir: Path | None = None,
    fallback: str = "",
) -> str:
    """Resuelve la ruta del asset visual para una escena.

    Compatible con:
    - visual.type=image|video legacy
    - visual.path moderno
    - visualPath legacy
    - segments[n].path para multi-segmento
    - scene-X.jpg fallback

    Returns:
        Ruta relativa al directorio del job
    """
    v = normalize_scene_visual(scene, video_dir)
    if v["type"] == "video":
        return v.get("path", fallback)
    return v.get("path", fallback)
