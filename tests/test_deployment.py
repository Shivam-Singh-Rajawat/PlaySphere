"""Vercel and direct-to-cloud video contracts (offline integration tests)."""
import hashlib
from datetime import datetime, timezone

import jwt
import pytest

from app import create_app
from test_api import auth, register, client


def test_vercel_rejects_ephemeral_sqlite(tmp_path, monkeypatch):
    monkeypatch.setenv('VERCEL', '1')
    monkeypatch.setenv('PLAYSPHERE_SECRET_KEY', 'x' * 48)
    with pytest.raises(RuntimeError, match='PostgreSQL'):
        create_app(database_url=f'sqlite:///{tmp_path / "temp.db"}', upload_dir=tmp_path / 'uploads')


def test_vercel_rejects_missing_persistent_secret(tmp_path, monkeypatch):
    monkeypatch.setenv('VERCEL', '1')
    monkeypatch.delenv('PLAYSPHERE_SECRET_KEY', raising=False)
    with pytest.raises(RuntimeError, match='PLAYSPHERE_SECRET_KEY'):
        create_app(database_url='postgresql://fake:fake@localhost/testdb', upload_dir=tmp_path / 'uploads')


def test_cloud_upload_requires_player_and_config(client, monkeypatch):
    player = register(client)
    scout = register(client, 'scout', 'scoutcloud@example.org')
    assert client.post('/api/videos/sign-upload').status_code == 401
    assert client.post('/api/videos/sign-upload', headers=auth(scout), json={'visibility':'public'}).status_code == 403
    assert client.post('/api/videos/sign-upload', headers=auth(player), json={'visibility':'public'}).status_code == 503


def test_cloud_signed_upload_completion_and_private_visibility(client, monkeypatch):
    monkeypatch.setenv('CLOUDINARY_CLOUD_NAME', 'testcloud')
    monkeypatch.setenv('CLOUDINARY_API_KEY', '123456')
    monkeypatch.setenv('CLOUDINARY_API_SECRET', 'server-cloud-secret')
    player = register(client)
    other = register(client, email='player2cloud@example.org')
    me = client.get('/api/auth/me', headers=auth(player)).json()['id']
    signing = client.post('/api/videos/sign-upload', headers=auth(player), json={'visibility': 'public'})
    assert signing.status_code == 200, signing.text
    ticket = signing.json()
    assert 'api_secret' not in str(ticket)
    assert ticket['public_id'].startswith(f'playsphere/u{me}/')
    parts = {k: ticket[k] for k in ('public_id','timestamp','type')}
    expected = hashlib.sha1(('&'.join(f'{k}={parts[k]}' for k in sorted(parts)) + 'server-cloud-secret').encode()).hexdigest()
    assert ticket['signature'] == expected
    receipt = {'public_id':ticket['public_id'], 'version': 1750000000, 'signature':'wrong',
               'resource_type':'video', 'type':'upload', 'format':'mp4', 'bytes':1024}
    bad = client.post('/api/videos/complete-upload', headers=auth(player), json={
        'ticket':ticket['ticket'], 'title':'Finals goal', 'kind':'match', 'asset':receipt})
    assert bad.status_code == 422, bad.text
    receipt['signature'] = hashlib.sha1(
        f"public_id={receipt['public_id']}&version={receipt['version']}server-cloud-secret".encode()
    ).hexdigest()
    assert client.post('/api/videos/complete-upload', headers=auth(other), json={
        'ticket':ticket['ticket'], 'title':'Someone else', 'kind':'match', 'asset':receipt}).status_code == 403
    submitted = client.post('/api/videos/complete-upload', headers=auth(player), json={
        'ticket':ticket['ticket'], 'title':'Finals goal', 'kind':'match', 'asset':receipt})
    assert submitted.status_code == 201, submitted.text
    video = submitted.json()
    assert video['url'].startswith('https://res.cloudinary.com/testcloud/video/upload/')
    assert video['uploaded'] is True
    assert client.get(f'/api/players/{me}').json()['videos'][0]['id'] == video['id']
    assert client.post('/api/videos/complete-upload', headers=auth(player), json={
        'ticket':ticket['ticket'], 'title':'Replay', 'kind':'match', 'asset':receipt}).status_code == 409

    private_sig = client.post('/api/videos/sign-upload', headers=auth(player), json={'visibility':'private'}).json()
    private_receipt = {**receipt, 'public_id':private_sig['public_id'], 'type':'authenticated'}
    private_receipt['signature'] = hashlib.sha1(
        f"public_id={private_receipt['public_id']}&version={private_receipt['version']}server-cloud-secret".encode()
    ).hexdigest()
    private = client.post('/api/videos/complete-upload', headers=auth(player), json={
        'ticket':private_sig['ticket'], 'title':'Private training', 'kind':'training',
        'asset':private_receipt})
    assert private.status_code == 201, private.text
    private_id = private.json()['id']
    assert len(client.get(f'/api/players/{me}').json()['videos']) == 1
    assert client.get(f'/api/videos/{private_id}/access').status_code == 401
    assert client.get(f'/api/videos/{private_id}/access', headers=auth(other)).status_code == 403


def test_no_local_disk_upload_in_serverless(client, monkeypatch):
    monkeypatch.setenv('VERCEL', '1')
    player = register(client)
    import io
    response = client.post('/api/videos/upload', headers=auth(player),
        data={'title':'match play','kind':'match'},
        files={'file':('video.mp4',io.BytesIO(b'\x00\x00\x00\x18ftypisom'), 'video/mp4')})
    assert response.status_code == 503


def test_readiness_reports_database_and_cloud_mode(client, monkeypatch):
    monkeypatch.delenv('CLOUDINARY_API_KEY', raising=False)
    result = client.get('/api/ready')
    assert result.status_code == 200
    assert result.json()['database'] == 'connected'
    assert client.get('/api/config').json()['upload_mode'] == 'local'
