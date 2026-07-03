#!/usr/bin/env python3

import argparse
import json
from datetime import datetime
from pathlib import Path


def fmt_srt_time(seconds: float) -> str:
    ms_total = int(round(seconds * 1000))
    hours = ms_total // 3600000
    ms_total %= 3600000
    minutes = ms_total // 60000
    ms_total %= 60000
    secs = ms_total // 1000
    millis = ms_total % 1000
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('metadata_path')
    args = parser.parse_args()

    metadata_path = Path(args.metadata_path).resolve()
    project_root = metadata_path.parents[2]
    data_dir = project_root / 'data'
    audio_dir = data_dir / 'audio'
    assets_dir = data_dir / 'assets'
    subtitles_dir = data_dir / 'subtitles'
    renders_dir = data_dir / 'renders'

    data = json.loads(metadata_path.read_text())
    job_id = data['jobId']
    scenes = data['script']['scenes']

    subtitles_dir.mkdir(parents=True, exist_ok=True)
    renders_dir.mkdir(parents=True, exist_ok=True)

    srt_lines = []
    current = 0.0
    audio_entries = []
    asset_entries = []

    for idx, scene in enumerate(scenes, start=1):
        scene_num = int(scene['sceneNumber'])
        duration = float(scene['targetDurationSec'])
        audio_path = audio_dir / f"{job_id}-scene-{scene_num:02}.mp3"
        asset_path = assets_dir / f"{job_id}-scene-{scene_num:02}.jpg"

        audio_entries.append({'sceneNumber': scene_num, 'path': str(audio_path), 'exists': audio_path.exists()})
        asset_entries.append({'sceneNumber': scene_num, 'path': str(asset_path), 'exists': asset_path.exists()})

        start = current
        end = current + duration
        subtitle = (scene.get('subtitle') or scene.get('voiceover') or '').strip()
        srt_lines.extend([str(idx), f"{fmt_srt_time(start)} --> {fmt_srt_time(end)}", subtitle, ''])
        current = end

    subtitle_path = subtitles_dir / f"{job_id}.srt"
    subtitle_path.write_text('\n'.join(srt_lines).strip() + '\n')

    all_audio = all(item['exists'] for item in audio_entries)
    all_assets = all(item['exists'] for item in asset_entries)

    data['audio'] = {'provider': 'elevenlabs', 'path': '', 'scenes': audio_entries}
    data['assets'] = asset_entries
    data['subtitles'] = {'path': str(subtitle_path), 'format': 'srt'}
    data['render'] = {'path': str(renders_dir / f"{job_id}.mp4"), 'durationSeconds': int(round(current))}
    data['review'] = {'status': 'PENDING'}
    if all_audio and all_assets:
        data['status'] = 'SUBTITLES_READY'
    elif all_audio:
        data['status'] = 'AUDIO_READY'
    elif all_assets:
        data['status'] = 'ASSETS_READY'
    data['updatedAt'] = datetime.utcnow().isoformat() + 'Z'

    metadata_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'jobId': job_id, 'metadata': str(metadata_path), 'subtitle': str(subtitle_path), 'audioReady': all_audio, 'assetsReady': all_assets, 'renderTarget': data['render']['path']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
