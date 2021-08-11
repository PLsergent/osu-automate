from google_auth import GoogleAuth
from get_config import *
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

import argparse
import io
import ntpath
import os
import psutil
import shutil
import time


class OsuHandler(PatternMatchingEventHandler):
    '''
    Handler to track new .osz files downloaded, upload them to google drive & open them
    '''
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
        '''
        When a file .osz is being downloaded it will trigger this function
        '''
        print(f"hey, {event.src_path} has been moved to {event.dest_path}!")
        shutil.copy(event.dest_path, ntpath.basename(event.dest_path))
        os.startfile(event.dest_path, 'open')
        self.upload_song_to_drive(ntpath.basename(event.dest_path))
        os.remove(ntpath.basename(event.dest_path))

    def list_files_from_drive(self):
        '''
        Function used to list all the files in your google drive folder (based on the id in the config file)
        '''
        token = ""
        results = []
        key = "nextPageToken"
        while True:
            response_data = self.gdrive_service.files().list(
                    q=f"parents='{GOOGLE_DRIVE_FOLDER_ID}'",
                    pageSize=1000,
                    pageToken=token
                ).execute()
            results += response_data["files"]
            if key in response_data:
                token = response_data[key]
            else:
                break
        return results

    def check_download_folder(self):
        '''
        Check download folder when app starts, upload and open .osz
        Used if you download songs without having the game opened and if you didn't open them
        Also used after --init
        '''
        list_download_folder  = [dir for dir in os.listdir(DOWNLOAD_FOLDER)]

        for file in list_download_folder:
            if file.endswith(".osz"):
                print(file)
                self.upload_song_to_drive(os.path.join(DOWNLOAD_FOLDER, file))
                # if you used --init or --no-open we're not going to open the files directly
                # but instead move them to the osu! songs folder so you can open them later by pressing f5 in game
                if args.init or args.no_open:
                    shutil.move(os.path.join(DOWNLOAD_FOLDER, file), os.path.join(OSU_SONGS_FOLDER, file))
                    print(f"{file} has been moved to songs folder, press f5 on osu! to get it")
                else:
                    os.startfile(os.path.join(DOWNLOAD_FOLDER, file), 'open')                   

    def upload_song_to_drive(self, path):
        '''
        Upload a song to your google drive folder
        Happens in self.check_download_folder() or self.on_moved() methods
        It'll check first if the song is not already in the drive to not create duplicates
        '''
        filename = ntpath.basename(path)

        response_data = self.list_files_from_drive()
        list_remote = [data['name'] for data in response_data]

        if filename in list_remote:
            print(f"{filename} already in cloud...")
        else:
            metadata = {
                "name": filename,
                "parents": [GOOGLE_DRIVE_FOLDER_ID] # Parent folder id
            }

            media = MediaFileUpload(path, mimetype='application/octet-stream')
            self.gdrive_service.files().create(body=metadata,
                                        media_body=media,
                                        fields='id').execute()
            print(f"{filename} uploaded to cloud.")

    
class StartupCheck:
    '''
    The class contain one main method who is going to be called when the app osu! is launched
    The idea is to check if new songs has been added to the drive and that are not on this computer
    Then the app will download them
    '''
    def __init__(self, service):
        self.gdrive_service = service

    def list_files_from_drive(self):
        '''
        Function used to list all the files in your google drive folder (based on the id in the config file)
        '''
        token = ""
        results = []
        key = "nextPageToken"
        while True:
            response_data = self.gdrive_service.files().list(
                    q=f"parents='{GOOGLE_DRIVE_FOLDER_ID}'",
                    pageSize=1000,
                    pageToken=token
                ).execute()
            results += response_data["files"]
            if key in response_data:
                token = response_data[key]
            else:
                break
        return results

    def download_song(self, remote):
        '''
        Function used to download a single from file from google drive
        This method will be called only when the game is launched, since we only check for new song in the google drive once at the beginning
        The methods will be called for each new songs detected in the drive
        '''
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

    def delete_duplicate_songs(self):
        '''
        Function first written as a debug purpose but kept overtime
        It will check if there is duplicates of a song after the check_download_folder() and check_songs_on_startup() methods
        This could be usefull in case of manuel operation in the drive folder, a forced stop of the app or a malfunction.
        '''
        results = self.list_files_from_drive()

        removed_item = []
        for item in results:
            if item in removed_item:
                continue
            check_list = results
            check_list.remove(item)

            for check in check_list:
                if item['name'] == check['name']:
                    removed_item.append(check)
                    self.gdrive_service.files().delete(fileId=check['id']).execute()
                    print(f"{check['name']} duplicate found ! Deleted")
        print(f"Duplicates found: {len(removed_item)}")

    def check_songs_on_startup(self):
        '''
        Check if new songs has been added to the google drive
        If yes, we download them : OsuHandler.check_download_folder will then open them
        '''
        response_data = self.list_files_from_drive()

        list_remote = [(data['id'], data['name']) for data in response_data] # Get song drive id
        list_local  = [dir.split(" ")[0] for dir in os.listdir(OSU_SONGS_FOLDER)]

        # remote[0] = id, remote[1] = filename
        for remote in list_remote:
            song_name = remote[1]
            if song_name.split(" ")[0] not in list_local:
                script_path = os.getcwd()
                os.chdir(DOWNLOAD_FOLDER)
                self.download_song(remote)
                print("Done")
                os.chdir(script_path)


if __name__ == "__main__":
        
    parser = argparse.ArgumentParser(description='osu! songs remote storage automation.')
    parser.add_argument("--init", action="store_true", help="retrieve all maps from Songs folder to convert them to .osz and upload them to the cloud")
    parser.add_argument("--no-open", action="store_true", help="doesn't open map when uploaded to cloud - to use when error to upload file to cloud")
    args = parser.parse_args()

    if args.init:
        '''
        When user uses --init option this will retrieve songs folder from the the game folder and convert them into .osz
        '''
        print("\n*********** You choose the --init option ***********")
        print("The app will copy all your folder from the osu! songs folder and convert them into .osz zip file")
        print("It's better to not interrupt the app now! This may take a while...")
        print("You can always use an other map extractor like this one: https://github.com/gameskill123/OsuMapExtractor\n")

        count = 0
        list_osu_songs  = [dir for dir in os.listdir(OSU_SONGS_FOLDER)]

        for folder in list_osu_songs:
            
            src = os.path.join(OSU_SONGS_FOLDER, folder)
            dest = os.path.join(DOWNLOAD_FOLDER, folder)

            # Compress folder into zip files
            shutil.make_archive(dest, 'zip', src)
            # Rename to .osz
            shutil.move(f"{dest}.zip", f"{dest}.osz")
            count += 1
            print(f"{count}/{len(list_osu_songs)} -- {ntpath.basename(dest)} has been exported to .osz")
        print("Done !")
        print("******************************************************\n")

    def startApp():
        '''
        Once osu! is launched the app will proceed this way:
            1. Authentication with Google Auth with the credentials provided in the credentials.json file
            2. Check if new songs has been added to the drive, if yes download them
            3. Check the download folder to see if new songs has been downloaded while osu was closed
            4. Check if there is duplicates on google drive
            5. Start the watcher, waiting for osu! songs to be downloaded
            6. An authentication to Google Auth will be done every hour to ensure the token is still valid
            7. If you close the game the watcher will stop
            8. The app will then be waiting for you to launch osu!
        '''

        folder = DOWNLOAD_FOLDER
        pattern = ["*.osz"]
        google_authenticator = GoogleAuth()
        gdrive_service = google_authenticator.service

        event_handler = OsuHandler(pattern, gdrive_service)

        startup = StartupCheck(gdrive_service)
        startup.check_songs_on_startup()
        event_handler.check_download_folder()
        startup.delete_duplicate_songs()

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

                if "osu!.exe" not in [p.name() for p in psutil.process_iter()]:
                    observer.stop()
                    observer.join()
                    print("osu! has stopped.")
                    break
                    
        except KeyboardInterrupt:
            observer.stop()
            observer.join()

    print("Application ready, waiting for osu! to start...")
    while True:
        time.sleep(1)
        '''
        Check every seconds if the game osu! is launched or not
        Whenever you launch the game, main method startApp() will start
        '''
        if "osu!.exe" in [p.name() for p in psutil.process_iter()]:
            print("osu! has been launched.")
            startApp()
