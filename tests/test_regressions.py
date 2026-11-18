"""Tests for the tournament timeline and organizer/scout workflows."""
from datetime import date, timedelta

from app import Tournament
from test_api import auth, client, register, tournament_payload


def test_future_events_remain_discoverable_when_history_is_large(client):
    club = register(client, role='club', email='timelineclub@example.org')
    owner_id = client.get('/api/auth/me', headers=auth(club)).json()['id']
    today = date.today()
    db_factory = client.app.state.sessionmaker
    with db_factory() as db:
        db.add_all([Tournament(owner_id=owner_id, title=f'Old tournament {i}', sport='Football',
                               location='Dehradun', level='Open', description='',
                               start_date=today - timedelta(days=180-i),
                               end_date=today - timedelta(days=180-i),
                               registration_deadline=today - timedelta(days=181-i),
                               capacity=20) for i in range(160)])
        db.commit()
    future = client.post('/api/tournaments', headers=auth(club), json=tournament_payload()).json()
    listing = client.get('/api/tournaments')
    assert listing.status_code == 200
    assert future['id'] in [t['id'] for t in listing.json()], 'Upcoming event was lost behind 150 old events'
    past = client.get('/api/tournaments', params={'status': 'recent', 'limit': 20})
    assert past.status_code == 200
    assert len(past.json()) == 20
    assert past.json()[0]['start_date'] > past.json()[-1]['start_date'], 'Recent events should be newest first'
    upcoming = client.get('/api/tournaments', params={'status': 'upcoming'})
    assert [e['id'] for e in upcoming.json()] == [future['id']]
    assert client.get('/api/tournaments', params={'status': 'unexpected'}).status_code == 422


def test_only_organizer_can_view_tournament_attendee_roster(client):
    organizer = register(client, role='coach', email='organizer@example.org')
    other = register(client, role='club', email='otherclub@example.org')
    player = register(client, email='attendee@example.org')
    event = client.post('/api/tournaments', json=tournament_payload(), headers=auth(organizer)).json()
    event_id = event['id']
    assert client.post(f'/api/tournaments/{event_id}/register', headers=auth(player)).status_code == 201
    roster = client.get(f'/api/tournaments/{event_id}/registrations', headers=auth(organizer))
    assert roster.status_code == 200
    assert len(roster.json()) == 1
    assert roster.json()[0]['name'] == 'Taylor Morgan'
    assert 'email' not in roster.json()[0]
    assert client.get(f'/api/tournaments/{event_id}/registrations', headers=auth(other)).status_code == 403
    assert client.get(f'/api/tournaments/{event_id}/registrations', headers=auth(player)).status_code == 403
    assert client.delete(f'/api/tournaments/{event_id}/register', headers=auth(player)).status_code == 204
    assert client.get(f'/api/tournaments/{event_id}/registrations', headers=auth(organizer)).json() == []
