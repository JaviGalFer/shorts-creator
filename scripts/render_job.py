#!/usr/bin/env python3

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path


def build_ffmpeg_args(project_root: Path, data: dict) -> list[str]:
    scenes = data['script']['scenes']
    job_id = data['jobId']
    args = [
        'docker', 'run', '--rm',
        '-v', f'{project_root}:/workspace',
        'linuxserver/ffmpeg:latest',
        '-y',
    ]

    filter_parts = []
    concat_inputs = []
    input_index = 0

    for scene in scenes:
        scene_num = int(scene['sceneNumber'])
        duration = int(scene['targetDurationSec'])
        image_rel = f'/workspace/data/assets/{job_id}-scene-{scene_num:02}.jpg'
        audio_rel = f'/workspace/data/audio/{job_id}-scene-{scene_num:02}.mp3'
        args.extend(['-loop', '1', '-t', str(duration), '-i', image_rel])
        args.extend(['-i', audio_rel])
        v_label = f'v{scene_num}'
        a_label = f'a{scene_num}'
        filter_parts.append(f'[{input_index}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,format=yuv420p[{v_label}]')
        filter_parts.append(f'[{input_index + 1}:a]aresample=44100[{a_label}]')
        concat_inputs.extend([f'[{v_label}]', f'[{a_label}]'])
        input_index += 2

    filter_parts.append(''.join(concat_inputs) + f'concat=n={len(scenes)}:v=1:a=1[vcat][acat]')
    subtitle_rel = f'/workspace/data/subtitles/{job_id}.srt'
    filter_parts.append("[vcat]subtitles=" + subtitle_rel + ":force_style='FontName=Arial,FontSize=18,Alignment=2,MarginV=60,Outline=2,Shadow=1'[vout]")
    output_rel = f'/workspace/data/renders/{job_id}.mp4'

    args.extend([
        '-filter_complex', ';'.join(filter_parts),
        '-map', '[vout]',
        '-map', '[acat]',
        '-c:v', 'libx264',
        '-preset', 'veryfast',
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-pix_fmt', 'yuv420p',
        output_rel,
    ])
    return args


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('metadata_path')
    args = parser.parse_args()

    metadata_path = Path(args.metadata_path).resolve()
    project_root = metadata_path.parents[2]
    data = json.loads(metadata_path.read_text())

    env = dict(__import__('os').environ)
    env['DOCKER_API_VERSION'] = '1.43'
    subprocess.run(build_ffmpeg_args(project_root, data), check=True, env=env)

    render_path = Path(data['render']['path'])
    data['status'] = 'RENDERED'
    data['render']['path'] = str(render_path)
    data['review'] = {'status': 'PENDING'}
    data['updatedAt'] = datetime.utcnow().isoformat() + 'Z'
    metadata_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'jobId': data['jobId'], 'render': str(render_path)}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
