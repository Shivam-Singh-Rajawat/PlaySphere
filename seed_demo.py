"""Opt-in fictitious sample data for local evaluation, never run in production."""
from datetime import date, timedelta

from sqlalchemy import select

from app import Achievement, Tournament, User, app, hash_password

SAMPLE_PLAYERS = [
    ('Demo Athlete • Arjun', 'Football', 'Dehradun', 'Winger', 20, {'Goals':'14','Assists':'9'}, 'Fast-paced wide player with a love for creating chances.'),
    ('Demo Athlete • Aanya', 'Badminton', 'Jaipur', 'Singles', 19, {'Wins':'24','Events':'8'}, 'Singles player focusing on footwork and match consistency.'),
    ('Demo Athlete • Kabir', 'Basketball', 'Delhi', 'Point guard', 21, {'PPG':'18.4','APG':'6.2'}, 'Pass-first guard with court vision and quick transition play.'),
    ('Demo Athlete • Meera', 'Cricket', 'Dehradun', 'All-rounder', 22, {'Runs':'482','Wickets':'21'}, 'Dependable middle-order batter and medium-pace bowler.'),
    ('Demo Athlete • Rahul', 'Tennis', 'Chandigarh', 'Singles', 18, {'Wins':'17','Aces':'44'}, 'Baseline competitor building experience in regional draws.'),
    ('Demo Athlete • Isha', 'Athletics', 'Rishikesh', '400m sprinter', 20, {'PB':'56.8s','Meets':'12'}, '400m runner committed to improving form and splits.'),
]


def seed():
    sessionmaker = app.state.sessionmaker
    with sessionmaker() as db:
        if db.scalar(select(User).where(User.email == 'demo.club@playsphere.local')):
            print('Demo data already seeded. No changes made.')
            return
        coach = User(name='Demo Valley Sports Club', email='demo.club@playsphere.local',
                     password_hash=hash_password('DemoPass!123'), role='club', sport='Football', city='Dehradun')
        db.add(coach); db.flush()
        scout = User(name='Demo Scout', email='demo.scout@playsphere.local',
                     password_hash=hash_password('DemoPass!123'), role='scout', sport='Football')
        db.add(scout)
        for i, (name,sport,city,position,age,stats,bio) in enumerate(SAMPLE_PLAYERS):
            import json
            user = User(name=name, email=f'demo.player{i+1}@playsphere.local',
                        password_hash=hash_password('DemoPass!123'), role='player', sport=sport, city=city,
                        position=position, age=age, bio=bio, stats_json=json.dumps(stats))
            db.add(user);db.flush()
            if i in (0,1,2):
                db.add(Achievement(player_id=user.id, title='Demo Regional Tournament Finalist',
                                   issuer='Fictitious Sample Event', year=date.today().year, verified=False))
        today = date.today()
        events = [
            ('Dehradun Open Football Cup', 'Football', 'Dehradun Sports Complex', 'District', 18, 20, 16, 80,
             'Two days of 7-a-side football and community scouting opportunities.'),
            ('North Zone Basketball Showcase', 'Basketball', 'Delhi Indoor Arena', 'Regional', 26, 27, 24, 60,
             'Competitive basketball weekend for emerging youth talent.'),
            ('Valley Cricket Trials', 'Cricket', 'Rajiv Gandhi Ground, Dehradun', 'Open', 9, 9, 7, 120,
             'Open registration for a structured cricket talent trial.'),
            ('Shuttle Rising Open', 'Badminton', 'Jaipur Badminton Centre', 'State', 42, 44, 39, 48,
             'Open singles and doubles categories for emerging athletes.'),
            ('Autumn Five-a-Side Invitational', 'Football', 'Dehradun', 'District', -25, -24, -28, 60,
             'Example of a completed community tournament.'),
        ]
        for title,sport,location,level,start,end,deadline,capacity,description in events:
            db.add(Tournament(owner_id=coach.id, title=f'DEMO · {title}', sport=sport,
                              location=location, level=level, start_date=today+timedelta(days=start),
                              end_date=today+timedelta(days=end),
                              registration_deadline=today+timedelta(days=deadline),
                              capacity=capacity, description=description))
        db.commit()
    print('Added 6 fictitious athlete profiles, 5 demo tournaments, and scout/club demo accounts.')
    print('Demo player login: demo.player1@playsphere.local / DemoPass!123')
    print('Demo scout login: demo.scout@playsphere.local / DemoPass!123')
    print('Demo club login: demo.club@playsphere.local / DemoPass!123')


if __name__ == '__main__':
    seed()
