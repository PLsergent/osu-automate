from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

import time
import json
import requests
import ntpath
import os


class osuHandler(PatternMatchingEventHandler):
    def __init__(self, pattern):
        super().__init__(
            patterns=pattern,
            ignore_patterns=None,
            ignore_directories=False,
            case_sensitive=False
        )

    def on_created(self, event):
        print(f"hey, {event.src_path} has been created!")
        self.send_song_to_drive(event.src_path)

    def on_moved(self, event):
        print(f"hey, {event.src_path} has been moved to {event.dest_path}!")
        self.send_song_to_drive(event.dest_path)

    def send_song_to_drive(self, path):
        with open("token.json") as token_file:
            token_json = json.load(token_file)
            token_file.close()

        access_token = token_json['access_token']

        metadata = {
            "name": ntpath.basename(path),
            "parents": ["1TibAGp-Y_9AWQKfZoWW3zbx0yNFHidJC"]
        }
        files = {
            'data': ('metadata', json.dumps(metadata), 'application/json'),
            'file': open(path, "rb").read()  # or  open(filedirectory, "rb")
        }

        r = requests.post(
            "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
            headers={"Authorization": "Bearer " + access_token},
            files=files
        )

        print(r.text)


if __name__ == "__main__":
    with open("client_secrets.json") as secrets_file:
        secrets_json = json.load(secrets_file)
        secrets_file.close()
    
    with open("refresh_token.json") as refresh_token_file:
        refresh_token_json = json.load(refresh_token_file)
        refresh_token_file.close()
    
    client_id = secrets_json['installed']['client_id']
    client_secret = secrets_json['installed']['client_secret']
    refresh_token = refresh_token_json['refresh_token']

    os.system('curl -d "client_id='+ client_id +'&client_secret='+ client_secret +'&refresh_token='+ refresh_token +'&grant_type=refresh_token" https://accounts.google.com/o/oauth2/token > token.json')
    
    folder = "/home/psergent/Downloads/"
    pattern = ["*.osk", "*.osz"]
    event_handler = osuHandler(pattern)
    observer = Observer()
    observer.schedule(event_handler, folder, recursive=True)

    observer.start()

    try:
        timer = 0
        while True:
            time.sleep(1)
            timer = timer + 1

            if timer > 3600:
                os.system('curl -d "client_id='+ client_id +'&client_secret='+ client_secret +'&refresh_token='+ refresh_token +'&grant_type=refresh_token" https://accounts.google.com/o/oauth2/token > token.json')
                timer = 0
    except KeyboardInterrupt:
        observer.stop()
        observer.join()