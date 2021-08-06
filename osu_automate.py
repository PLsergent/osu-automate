from google_auth import GoogleAuth
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

import argparse
import time
import ntpath
import os
import io
import subprocess


class OsuHandler(PatternMatchingEventHandler):
    def __init__(self, pattern, service):
        super().__init__(
            patterns=pattern,
            ignore_patterns=None,
            ignore_directories=False,
            case_sensitive=False
        )
        self.gdrive_service = service
        print("Start watching for osu! files...")

    def on_moved(self, event):
        print(f"hey, {event.src_path} has been moved to {event.dest_path}!")
        # os.startfile(event.dest_path) > TODO: open file automatically
        self.send_song_to_drive(event.dest_path)

    def send_song_to_drive(self, path):   
        metadata = {
            "name": ntpath.basename(path),
            "parents": [args.google_drive_folder_id] # Parent folder id
        }

        media = MediaFileUpload(path, mimetype='application/octet-stream')
        self.gdrive_service.files().create(body=metadata,
                                    media_body=media,
                                    fields='id').execute()

    
class StartupCheck:
    def __init__(self, service):
        self.gdrive_service = service

    def check_songs_on_startup(self):
        response_data = self.gdrive_service.files().list(q=f"parents='{args.google_drive_folder_id}'").execute()

        list_remote = [(data['id'], data['name']) for data in response_data['files']] # Get song id
        list_local  = [file.split(" ")[0] for file in os.listdir(args.osu_songs_folder)] # TODO : pass to args

        # remote[0] = id, remote[1] = filename
        for remote in list_remote:
            if remote[1].split(" ")[0] not in list_local:
                script_path = os.getcwd()
                os.chdir(args.download_folder)
                
                file_id = remote[0]
                request = self.gdrive_service.files().export_media(fileId=file_id, mimeType='application/x-zip')
                fh = io.BytesIO()
                print(f"Downloading {remote[1]}...")
                MediaIoBaseDownload(fh, request)

                with open(remote[1], "wb") as outfile:
                    # Copy the BytesIO stream to the output file
                    outfile.write(fh.getbuffer())
                print("Done")
                print(os.getcwd())
                subprocess.run(['open', remote[1]], check=True)
                os.chdir(script_path)


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description='osu! songs remote storage automation.')
    parser.add_argument("download_folder", help="provide default download folder", type=str)
    parser.add_argument("osu_songs_folder", help="provide osu songs folder", type=str)
    parser.add_argument("google_drive_folder_id", help="provide google drive folder id where songs are going to be stored", type=str)
    args = parser.parse_args()

    folder = args.download_folder
    pattern = ["*.osk", "*.osz"]
    google_authenticator = GoogleAuth()
    gdrive_service = google_authenticator.service

    startup = StartupCheck(gdrive_service).check_songs_on_startup()

    event_handler = OsuHandler(pattern, gdrive_service)
    observer = Observer()
    observer.schedule(event_handler, folder, recursive=True)

    observer.start()

    try:
        timer = 0
        while True:
            time.sleep(1)
            timer = timer + 1

            if timer > 3600:
                
                timer = 0
    except KeyboardInterrupt:
        observer.stop()
        observer.join()