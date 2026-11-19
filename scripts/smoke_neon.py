"""Temporary-record end-to-end smoke test against the configured Neon Postgres.

Run from repository root: python scripts/smoke_neon.py
Never prints database passwords, tokens, or connection strings.
"""
import os
import secrets
import sys
from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import delete, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import (Achievement, Registration, Tournament, User, ROOT,
                 create_app, load_local_env)


def main():
    load_local_env(ROOT)
    configured = os.environ.get('PLAYSPHERE_DATABASE_URL') or os.environ.get('DATABASE_URL') or ''
    if not configured.startswith(('postgres://', 'postgresql://', 'postgresql+psycopg://')):
        raise SystemExit('SKIP: Neon PostgreSQL URL missing; run neon login, neon deploy, then retry.')
    application = create_app()
    sessionmaker = application.state.sessionmaker
    player_id = club_id = event_id = None
    unique = secrets.token_hex(6)
    try:
        with sessionmaker() as db:
            assert db.execute(text('SELECT 1')).scalar_one() == 1
        with TestClient(application) as client:
            assert client.get('/api/ready').status_code == 200
            password = secrets.token_urlsafe(20)
            def register(role, email):
                response = client.post('/api/auth/register', json={
                    'name': 'Neon Integration Check', 'email': email,
                    'password': password, 'sport': 'Football', 'role': role})
                assert response.status_code == 201, f'{role} registration failed: {response.status_code}'
                return response.json()['token']
            player = register('player', f'neon-check-player-{unique}@example.org')
            club = register('club', f'neon-check-club-{unique}@example.org')
            phead, chead = ({'Authorization': f'Bearer {token}'} for token in (player, club))
            player_id = client.get('/api/auth/me', headers=phead).json()['id']
            club_id = client.get('/api/auth/me', headers=chead).json()['id']
            assert client.patch('/api/players/me', headers=phead, json={
                'position': 'Midfielder', 'city': 'Dehradun'}).status_code == 200
            achievement = client.post('/api/achievements', headers=phead, json={
                'title': 'Neon Test Achievement', 'issuer': 'PlaySphere QA', 'year': date.today().year})
            assert achievement.status_code == 201
            assert client.get(f'/api/players/{player_id}').json()['achievements'][0]['title'] == 'Neon Test Achievement'
            upcoming = date.today() + timedelta(days=14)
            response = client.post('/api/tournaments', headers=chead, json={
                'title': 'Neon E2E Tournament', 'sport': 'Football',
                'location': 'QA Stadium', 'start_date': upcoming.isoformat(),
                'end_date': (upcoming + timedelta(days=1)).isoformat(),
                'registration_deadline': (upcoming - timedelta(days=2)).isoformat(),
                'capacity': 5})
            assert response.status_code == 201, f'tournament creation failed: {response.status_code}'
            event_id = response.json()['id']
            assert client.post(f'/api/tournaments/{event_id}/register', headers=phead).status_code == 201
            assert client.get(f'/api/tournaments/{event_id}/registrations', headers=chead).json()[0]['id'] == player_id
            print('PASS: Neon SELECT 1, API readiness, authentication, player portfolio, achievements,')
            print('      tournament creation and registration, organizer roster.')
    finally:
        if player_id or club_id:
            with sessionmaker() as db:
                if event_id:
                    db.execute(delete(Registration).where(Registration.tournament_id == event_id))
                    db.execute(delete(Tournament).where(Tournament.id == event_id))
                if player_id:
                    db.execute(delete(Achievement).where(Achievement.player_id == player_id))
                for uid in (player_id, club_id):
                    if uid:
                        db.execute(delete(User).where(User.id == uid))
                db.commit()
            print('PASS: Temporary smoke-test records removed.')


if __name__ == '__main__':
    main()
