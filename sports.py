import json

class User:
    def __init__(self, name, email):
        self.name = name
        self.email = email

class Player(User):
    def __init__(self, name, email, sport, age):
        self.name = name
        self.email = email
        self.sport = sport
        self.age = age
        self.stats = {}
        self.video_link = ""
        self.certificates = []

    def to_dict(self):
        return self.__dict__

class Coach(User):
    def __init__(self, name, email, sport):
        self.name = name
        self.email = email
        self.sport = sport

class Club:
    def __init__(self, name, email, location):
        self.name = name
        self.email = email
        self.location = location

class Event:
    def __init__(self, title, sport, date, location):
        self.title = title
        self.sport = sport
        self.date = date
        self.location = location
        self.registered_players = []

    def to_dict(self):
        return self.__dict__ #here we convert object attribute to dictionary format

def save_data(filename, data):
    with open(filename, 'w') as file:
        json.dump(data, file)

def load_data(filename):
    data = []
    try:
        with open(filename, 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        pass
    return data


def player_sign_in():
    name = input("Enter your registered name: ").strip().lower()
    players = load_data('players.json')
    for player in players:
        if player['name'].strip().lower() == name:
            print(f"Hi {player['name']}, welcome back!")
            print(f"Sport: {player['sport']}, Age: {player['age']}, Email: {player['email']}")
            if player['stats']:
                print(f"Stats: {player['stats']}")
            if player['video_link']:
                print(f"Video Link: {player['video_link']}")
            if player['certificates']:
                print(f"Certificates: {', '.join(player['certificates'])}")
            if input("Search for events? (yes/no): ").strip().lower() == "yes":
                search_events()
            return
    print(" 404 ERROR: Player not found. Please register first.")


def register_player():
    name = input("Enter your name: ")
    email = input("Enter your email: ")
    sport = input("Enter your sport: ")
    age = input("Enter your age: ")

    player = Player(name, email, sport, age)

    print("Enter your stats (E.x-> speed, score):")
    while True:
        stat = input(" Enter the field name you wana update or enter done to end: ")
        if stat.lower() == 'done':
            break
        value = input(f"Enter value for {stat}: ")
        player.stats[stat] = value

    video = input("Upload video link (optional): ")
    if video:
        player.video_link = video

    cert = input("Enter any certifications or achievements: (E.x-> x,y,z): ")
    if cert:
        player.certificates = cert.split(',')

    players = load_data('players.json')
    players.append(player.to_dict())
    save_data('players.json', players)
    print("Player registered successfully!")

    choice = input("Wanna search events? \nPress between (yes/no): ")
    if choice.lower() == "yes":
        search_events()

def club_sign_in():
    name = input("Enter your club name: ").strip().lower()
    clubs = load_data('clubs.json')
    for club in clubs:
        if club['name'].strip().lower() == name:
            print(f"\n Welcome back, {club['name']} Club!")
            print(f"Email: {club['email']} \nLocation: {club['location']}")
            choice = input("\nDo you want to post a new event? (yes/no): ")
            if choice.lower() == 'yes':
                create_event()
            view_players = input("Do you want to view all registered players? (yes/no): ")
            if view_players.lower() == 'yes':
                players = load_data('players.json')
                for player in players:
                    print(f"Name: {player['name']}, Sport: {player['sport']}, Age: {player['age']}")
            return
    print(" 404 ERROR: Club not found. Please register first.")

def register_coach():
    name = input("Enter your name: ")
    email = input("Enter your email: ")
    sport = input("Enter your sport: ")

    coach = Coach(name, email, sport)
    print("Coach registered successfully!")

def register_club():
    print("1. Register as Club")
    print("2. Sign a Player")
    print("3. Sign In")
    choice = input("Enter your choice (1/2/3): ")

    if choice == '1':
        name = input("Enter club name: ")
        email = input("Enter email: ")
        location = input("Enter location: ")

        club = Club(name, email, location)
        print("Club registered successfully!")

        post_event = input("Do you want to post a event? \nPress between (yes/no): ")
        if post_event.lower() == 'yes':
            create_event()

        view_players = input("Wanna take alook of all register player?,\nPress between (yes/no): ")
        if view_players.lower() == 'yes':
            players = load_data('players.json')
            for player in players:
                print(f'''Name: {player['name']}, 
                      Sport: {player['sport']}, 
                      Age: {player['age']}''')

    elif choice == '2':
        sport = input("Enter sport to filter players by: ").strip().lower()
        players = load_data('players.json')
        found = False
        for player in players:
            if player['sport'].lower() == sport:
                found = True
                print(f'''Name: {player['name']}, 
                      Email: {player['email']}, 
                      Age: {player['age']}, 
                      Stats: {player['stats']}''')
        if not found:
            print("No players found !")

    elif choice=='3':
        club_sign_in()        
    else:
        print("Invalid choice.")

def create_event():
    title = input("Enter event title: ")
    sport = input("Enter sport: ")
    date = input("Enter date: ")
    location = input("Enter location: ")

    event=Event(title, sport, date, location)
    events=load_data('events.json')
    events.append(event.to_dict())
    save_data('events.json', events)
    print("Event created successfully!")

def show_events():
    events = load_data('events.json')
    if not events:
        print("No events available.")
        return
    for idx, event in enumerate(events):
        print(f"ID: {idx} | Title: {event['title']} | Date: {event['date']} | Location: {event['location']}")

def search_events():
    events = load_data('events.json')
    if not events:
        print("No events found.")
        return

    sport_flt = input("Enter sport for filter (or leave blank for all): ").strip().lower()

    print("Matching Events:")
    for idx, event in enumerate(events):
        if (not sport_flt or event['sport'].lower() == sport_flt):
            print(f'''
                  ID: {idx},
                  Title: {event['title']},
                  Sport: {event['sport']}, 
                  Date: {event['date']}, 
                  Location: {event['location']},
''')


def player_menu():
    print("1. Register as Player")
    print("2. View Events")
    print("3. Sign In")
    choice =input("Enter your choice (1/2): ")
    if choice == "1":
        register_player()
    elif choice == "2":
        search_events()
    elif choice == "3":
        player_sign_in()
    else:
        print("Invalid choice.")

def main():
    print("-------- Welcome to the PlaySphere ---------")
    print("Select your role: 1. Player  2. Coach  3. Club")
    role = input("Enter your choice (1/2/3): ")

    if role == '1':
        player_menu()
    elif role == '2':
        register_coach()
    elif role == '3':
        register_club()
    else:
        print("Invalid input, Restarting ... ")
        main()

main()