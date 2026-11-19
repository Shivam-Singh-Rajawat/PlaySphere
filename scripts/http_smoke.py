"""Start the real FastAPI server on localhost and smoke test HTTP requests.

Uses a temporary SQLite database and exits without leaving a running server.
This checks HTTP wiring only; scripts/smoke_neon.py tests real Neon Postgres.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def request(url, *, data=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    payload = json.dumps(data).encode() if data is not None else None
    with urlopen(Request(url, data=payload, headers=headers), timeout=3) as res:
        raw = res.read().decode('utf-8')
        return res.status, json.loads(raw) if 'json' in res.headers.get('Content-Type', '') else raw


def main():
    with tempfile.TemporaryDirectory(prefix='playsphere-http-') as tmp:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        env = os.environ.copy()
        env['PLAYSPHERE_DATABASE_URL'] = 'sqlite:///' + str(Path(tmp) / 'smoke.db').replace('\\', '/')
        env['PLAYSPHERE_SECRET_KEY'] = 'local-http-smoke-only-' + 'k' * 32
        env.pop('VERCEL', None)
        proc = subprocess.Popen(
            [sys.executable, '-m', 'uvicorn', 'app:app', '--host', '127.0.0.1', '--port', str(port)],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        base = f'http://127.0.0.1:{port}'
        try:
            for _ in range(70):
                if proc.poll() is not None:
                    raise AssertionError('FastAPI server stopped before becoming ready')
                try:
                    status, health = request(base + '/api/health')
                    if status == 200:
                        break
                except (URLError, TimeoutError):
                    time.sleep(.2)
            else:
                raise AssertionError('FastAPI server startup timed out')
            assert health['status'] == 'ok', health
            status, ready = request(base + '/api/ready')
            assert status == 200 and ready['database'] == 'connected'
            status, html = request(base + '/')
            assert status == 200 and 'PlaySphere' in html
            status, js = request(base + '/assets/app.js')
            assert status == 200 and len(js) > 500
            status, registered = request(base + '/api/auth/register', data={
                'name': 'HTTP Smoke User', 'email': 'http-smoke@example.org',
                'password': 'CorrectHorseBattery11', 'sport': 'Football', 'role': 'player'})
            assert status == 201 and registered['token']
            status, who = request(base + '/api/auth/me', token=registered['token'])
            assert status == 200 and who['role'] == 'player'
            print('PASS: FastAPI started; GET /, /assets/app.js, /api/health, /api/ready;')
            print('      POST /api/auth/register and GET /api/auth/me over real local HTTP.')
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            # Windows can hold the recently closed SQLite database handle briefly.
            time.sleep(1.0)


if __name__ == '__main__':
    main()
