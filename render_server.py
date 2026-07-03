#!/usr/bin/env python3

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import os

PROJECT_ROOT = Path(os.environ.get('PROJECT_HOST_PATH', '/workspace'))
SCRIPTS_DIR = PROJECT_ROOT / 'bin'
HOST = '0.0.0.0'
PORT = 8580


class RenderHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == '/health':
            self._respond(200, {'status': 'ok'})
        else:
            self._respond(404, {'error': 'not found'})

    def do_POST(self):
        if self.path != '/render':
            return self._respond(404, {'error': 'not found'})

        try:
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length))
        except Exception as e:
            return self._respond(400, {'ok': False, 'error': f'invalid body: {e}'})

        job_id = body.get('jobId')
        if not job_id:
            return self._respond(400, {'ok': False, 'error': 'jobId is required'})

        metadata_path = PROJECT_ROOT / 'data' / 'videos' / job_id / 'metadata.json'
        if not metadata_path.exists():
            metadata_path = PROJECT_ROOT / 'data' / 'metadata' / f'{job_id}.json'
        if not metadata_path.exists():
            return self._respond(404, {'ok': False, 'error': f'metadata not found: {job_id}'})

        prep = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / 'prepare_job.py'), str(metadata_path)],
            capture_output=True, text=True, timeout=30,
        )
        if prep.returncode != 0:
            return self._respond(500, {
                'ok': False, 'step': 'prepare_job',
                'error': prep.stderr.strip() or prep.stdout.strip(),
            })

        render = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / 'render_job.py'), str(metadata_path)],
            capture_output=True, text=True, timeout=300,
        )
        if render.returncode != 0:
            return self._respond(500, {
                'ok': False, 'step': 'render_job',
                'error': render.stderr.strip() or render.stdout.strip(),
            })

        data = json.loads(metadata_path.read_text())
        data['review']['status'] = 'REVIEW_PENDING'
        data['updatedAt'] = datetime.utcnow().isoformat() + 'Z'
        metadata_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')

        try:
            output = json.loads(render.stdout.strip())
        except json.JSONDecodeError:
            output = {'raw': render.stdout.strip()}

        return self._respond(200, {'ok': True, 'jobId': job_id, 'result': output})

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        print(f"[render-server] {args[0]} {args[1]} {args[2]}")


if __name__ == '__main__':
    server = HTTPServer((HOST, PORT), RenderHandler)
    print(f"[render-server] listening on {HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[render-server] shutting down")
        server.server_close()
