from google_auth import GoogleAuth
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

import argparse
import time
import ntpath
import os
import io


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

    def on_created(self, event):
        print(f"hey, {event.src_path} has been created!")
        os.startfile(event.dest_path, 'open')
        self.send_song_to_drive(event.src_path)

    def on_moved(self, event):
        print(f"hey, {event.src_path} has been moved to {event.dest_path}!")
        os.startfile(event.dest_path, 'open')
        self.send_song_to_drive(event.dest_path)

    def send_song_to_drive(self, path):
        filename = ntpath.basename(path)

        response_data = self.gdrive_service.files().list(q=f"parents='{args.google_drive_folder_id}'").execute()
        list_remote = [data['name'] for data in response_data['files']]

        if filename in list_remote:
            print("Already in cloud...")
        else:
            metadata = {
                "name": filename,
                "parents": [args.google_drive_folder_id] # Parent folder id
            }

            media = MediaFileUpload(path, mimetype='application/octet-stream')
            self.gdrive_service.files().create(body=metadata,
                                        media_body=media,
                                        fields='id').execute()
            print("Uploaded to cloud.")

    
class StartupCheck:
    def __init__(self, service):
        self.gdrive_service = service

    def check_songs_on_startup(self):
        response_data = self.gdrive_service.files().list(q=f"parents='{args.google_drive_folder_id}'").execute()

        list_remote = [(data['id'], data['name']) for data in response_data['files']] # Get song drive id
        list_local  = [file.split(" ")[0] for file in os.listdir(args.osu_songs_folder)]

        # remote[0] = id, remote[1] = filename
        for remote in list_remote:
            if remote[1].split(" ")[0] not in list_local:
                script_path = os.getcwd()
                os.chdir(args.download_folder)
                
                file_id = remote[0]
                request = self.gdrive_service.files().get_media(fileId=file_id)
                fh = io.BytesIO()
                print(f"Downloading {remote[1]}...")
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                    print("Download %d%%." % int(status.progress() * 100))

                with io.open(remote[1], 'wb') as f:
                    fh.seek(0)
                    f.write(fh.read())
                print("Done")
                os.startfile(remote[1], 'open')
                # shutil.move(remote[1], args.osu_songs_folder)
                os.chdir(script_path)


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description='osu! songs remote storage automation.')
    parser.add_argument("download_folder", help="provide default download folder", type=str)
    parser.add_argument("osu_songs_folder", help="provide osu songs folder", type=str)
    parser.add_argument("google_drive_folder_id", help="provide google drive folder id where songs are going to be stored", type=str)
    args = parser.parse_args()

    folder = args.download_folder
    pattern = ["*.osz"]
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

            if timer >= 3599:
                google_authenticator = GoogleAuth()
                gdrive_service = google_authenticator.service
                event_handler.gdrive_service = gdrive_service
                timer = 0
    except KeyboardInterrupt:
        observer.stop()
        observer.join()