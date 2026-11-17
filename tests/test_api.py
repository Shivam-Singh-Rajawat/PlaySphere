import io
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import create_app


@pytest.fixture
def client(tmp_path):
    application = create_app(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        upload_dir=tmp_path / 'uploads',
    )
    with TestClient(application) as test_client:
        yield test_client


def register(client, role='player', email=None, **fields):
    email = email or f'{role}@test.example'
    response = client.post('/api/auth/register', json={
        'name': 'Taylor Morgan', 'email': email, 'password': 'StrongPass!123',
        'role': role, 'sport': 'Football', **fields,
    })
    assert response.status_code == 201, response.text
    return response.json()['token']


def auth(token):
    return {'Authorization': f'Bearer {token}'}


def tournament_payload(**changes):
    tomorrow = date.today() + timedelta(days=12)
    return {'title': 'Regional Youth Cup', 'sport': 'Football',
            'location': 'Dehradun', 'start_date': tomorrow.isoformat(),
            'end_date': (tomorrow + timedelta(days=2)).isoformat(),
            'registration_deadline': (tomorrow - timedelta(days=1)).isoformat(),
            'capacity': 2, 'level': 'Regional',
            'description': 'Open trials and competitive matches.', **changes}


def test_auth_and_role_guards(client):
    player = register(client)
    response = client.get('/api/auth/me', headers=auth(player))
    assert response.status_code == 200
    assert response.json()['role'] == 'player'
    assert client.post('/api/tournaments', json=tournament_payload(), headers=auth(player)).status_code == 403
    assert client.post('/api/auth/login', json={'email': 'player@test.example', 'password': 'wrong'}).status_code == 401
    assert client.post('/api/auth/register', json={'name': 'Other', 'email': 'player@test.example', 'password': 'StrongPass!123', 'role': 'player'}).status_code == 409
    assert client.get('/api/auth/me').status_code == 401
    assert client.get('/api/auth/me', headers=auth('junk')).status_code == 401


def test_player_portfolio_achievements_and_visibility(client):
    player = register(client)
    me = client.get('/api/auth/me', headers=auth(player)).json()
    update = client.patch('/api/players/me', headers=auth(player), json={
        'bio': 'Midfielder focused on possession and passing.', 'city': 'Dehradun',
        'position': 'Midfielder', 'age': 21, 'stats': {'goals': '12', 'assists': '7'},
    })
    assert update.status_code == 200, update.text
    achievement = client.post('/api/achievements', headers=auth(player), json={
        'title': 'District MVP', 'issuer': 'Regional Cup', 'year': 2025,
        'evidence_url': 'https://example.org/certificate',
    })
    assert achievement.status_code == 201, achievement.text
    assert achievement.json()['verified'] is False
    assert client.post('/api/achievements', headers=auth(player), json={
        'title': 'Unsafe', 'issuer': 'Test', 'year': 2025,
        'evidence_url': 'javascript:alert(1)',
    }).status_code == 422
    profile = client.get(f"/api/players/{me['id']}")
    assert profile.status_code == 200
    assert profile.json()['stats']['goals'] == '12'
    assert profile.json()['achievements'][0]['verified'] is False
    assert 'email' not in profile.json()
    assert len(client.get('/api/players', params={'sport': 'Football'}).json()) == 1
    assert not client.get('/api/players', params={'sport': 'Basketball'}).json()


def test_video_link_and_private_upload(client):
    player = register(client)
    scout = register(client, role='scout', email='scout2@test.example')
    player_id = client.get('/api/auth/me', headers=auth(player)).json()['id']
    link = client.post('/api/videos/link', headers=auth(player), json={
        'title': 'Match against City FC', 'kind': 'match',
        'url': 'https://www.youtube.com/watch?v=abc123', 'visibility': 'public',
    })
    assert link.status_code == 201, link.text
    assert client.post('/api/videos/link', headers=auth(player), json={
        'title': 'Bad', 'kind': 'highlight', 'url': 'file:///etc/passwd',
    }).status_code == 422
    private = client.post('/api/videos/upload', headers=auth(player), data={
        'title': 'Private drill', 'kind': 'training', 'visibility': 'private'
    }, files={'file': ('session.mp4', b'\x00\x00\x00\x18ftypisomtest', 'video/mp4')})
    assert private.status_code == 201, private.text
    private_id = private.json()['id']
    assert client.get(f'/api/videos/{private_id}/file', headers=auth(scout)).status_code == 403
    assert client.get(f'/api/videos/{private_id}/file', headers=auth(player)).status_code == 200
    assert len(client.get(f'/api/players/{player_id}').json()['videos']) == 1
    assert len(client.get('/api/players/me/videos', headers=auth(player)).json()) == 2
    bad = client.post('/api/videos/upload', headers=auth(player), data={
        'title': 'Not video', 'kind': 'match'
    }, files={'file': ('data.html', b'<script>alert(1)</script>', 'text/html')})
    assert bad.status_code == 415


def test_tournaments_registration_and_recent(client):
    player = register(client)
    club = register(client, role='club', email='club2@test.example')
    created = client.post('/api/tournaments', json=tournament_payload(), headers=auth(club))
    assert created.status_code == 201, created.text
    event_id = created.json()['id']
    assert created.json()['status'] == 'upcoming'
    assert client.get('/api/tournaments', params={'status': 'upcoming'}).json()[0]['id'] == event_id
    assert client.post(f'/api/tournaments/{event_id}/register', headers=auth(player)).status_code == 201
    assert client.post(f'/api/tournaments/{event_id}/register', headers=auth(player)).status_code == 409
    assert client.get('/api/tournaments/me/registrations', headers=auth(player)).json()[0]['id'] == event_id
    assert client.get(f'/api/tournaments/{event_id}/registrations', headers=auth(player)).status_code == 403
    assert len(client.get(f'/api/tournaments/{event_id}/registrations', headers=auth(club)).json()) == 1
    assert client.delete(f'/api/tournaments/{event_id}/register', headers=auth(player)).status_code == 204
    assert client.get(f'/api/tournaments/{event_id}').json()['participants_count'] == 0
    old = date.today() - timedelta(days=30)
    past = client.post('/api/tournaments', headers=auth(club), json=tournament_payload(
        title='Autumn Cup', start_date=old.isoformat(),
        end_date=(old + timedelta(days=1)).isoformat(),
        registration_deadline=(old - timedelta(days=1)).isoformat(),
    ))
    assert past.status_code == 201
    assert past.json()['status'] == 'recent'
    assert client.post(f"/api/tournaments/{past.json()['id']}/register", headers=auth(player)).status_code == 400


def test_scout_evaluations_are_private_and_editable(client):
    player = register(client)
    player_id = client.get('/api/auth/me', headers=auth(player)).json()['id']
    coach = register(client, role='coach', email='coach2@test.example')
    other_scout = register(client, role='scout', email='another@test.example')
    scores = {'technique': 4, 'teamwork': 5, 'consistency': 3, 'potential': 4,
              'notes': 'Solid decision making with room to improve pace.'}
    assert client.post(f'/api/scouting/{player_id}/evaluate', headers=auth(player), json=scores).status_code == 403
    evaluation = client.post(f'/api/scouting/{player_id}/evaluate', headers=auth(coach), json=scores)
    assert evaluation.status_code == 200, evaluation.text
    assert evaluation.json()['score'] == 4.0
    assert len(client.get('/api/scouting/my-evaluations', headers=auth(coach)).json()) == 1
    assert client.get('/api/scouting/my-evaluations', headers=auth(other_scout)).json() == []
    assert client.get(f'/api/players/{player_id}').status_code == 200
    assert 'evaluations' not in client.get(f'/api/players/{player_id}').json()
    assert client.post(f'/api/scouting/{player_id}/shortlist', headers=auth(coach)).status_code == 201
    assert client.post(f'/api/scouting/{player_id}/shortlist', headers=auth(coach)).status_code == 200
    assert len(client.get('/api/scouting/shortlist', headers=auth(coach)).json()) == 1
    assert client.delete(f'/api/scouting/{player_id}/shortlist', headers=auth(coach)).status_code == 204
    assert client.post(f'/api/scouting/{player_id}/evaluate', headers=auth(coach), json={**scores, 'potential': 10}).status_code == 422


def test_video_upload_limits_and_cross_account_modification(client):
    a = register(client)
    b = register(client, email='secondplayer@test.example')
    assert client.post('/api/videos/link', headers=auth(a), json={
        'title': 'Unsafe scheme', 'kind': 'highlight', 'url': 'http://example.org/video'
    }).status_code == 422
    broken = client.post('/api/videos/upload', headers=auth(a), data={
        'title': 'Mismatched content', 'kind': 'match'
    }, files={'file': ('notvideo.mp4', b'<html>not a video</html>', 'video/mp4')})
    assert broken.status_code == 415
    uploaded = client.post('/api/videos/upload', headers=auth(a), data={
        'title': 'Final match', 'kind': 'match', 'visibility': 'public'
    }, files={'file': ('final.mp4', b'\x00\x00\x00\x18ftypisomexample', 'video/mp4')})
    assert uploaded.status_code == 201
    video_id = uploaded.json()['id']
    assert client.delete(f'/api/videos/{video_id}', headers=auth(b)).status_code == 404
    assert client.get(f'/api/videos/{video_id}/file').status_code == 200
    assert client.delete(f'/api/videos/{video_id}', headers=auth(a)).status_code == 204
    assert client.get(f'/api/videos/{video_id}/file').status_code == 404
    huge = client.post('/api/videos/upload', headers=auth(a), data={
        'title': 'Over upload cap', 'kind': 'match'
    }, files={'file': ('large.mp4', b'\x00\x00\x00\x18ftypisom' + b'x' * (25*1024*1024), 'video/mp4')})
    assert huge.status_code == 413


def test_tournament_capacity_and_role_separation(client):
    organizer = register(client, role='club')
    first = register(client, email='first@example.org')
    second = register(client, email='second@example.org')
    event = client.post('/api/tournaments', json=tournament_payload(capacity=1), headers=auth(organizer)).json()
    assert client.post(f"/api/tournaments/{event['id']}/register", headers=auth(first)).status_code == 201
    assert client.post(f"/api/tournaments/{event['id']}/register", headers=auth(second)).status_code == 400
    assert client.post(f"/api/tournaments/{event['id']}/register", headers=auth(organizer)).status_code == 403
    assert client.post('/api/tournaments', headers=auth(organizer), json=tournament_payload(
        end_date=(date.today()-timedelta(days=1)).isoformat()
    )).status_code == 422


def test_frontend_and_health_smoke(client):
    assert client.get('/api/health').json()['status'] == 'ok'
    assert client.get('/').status_code == 200
    assert 'EVERY PLAYER' in client.get('/').text
    assert client.get('/assets/app.js').status_code == 200
    assert client.get('/assets/style.css').status_code == 200
