from google_auth import GoogleAuth
from get_config import *
from google_utilities import GoogleFunctionUtilities
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

import argparse
import ntpath
import os
import psutil
import shutil
import threading
import time


class OsuHandler(PatternMatchingEventHandler, GoogleFunctionUtilities):
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
        self.queue_removable_files = []
        self.gdrive_service = service
        self.thread_queue = []
        print("Start watching for osu! files...")

    def on_moved(self, event):
        '''
        When a file .osz is being downloaded it will trigger this function
        '''
        song_file = ntpath.basename(event.dest_path)
        print(f"hey, new download: {event.dest_path}!")
        shutil.copy(event.dest_path, song_file)
        '''
        Copy the file.osz to osu-automate folder so we can open a file and upload the other
        Ensure fast opening of the song
        '''

        if args.no_open:
            '''
            If you used the --no-open option we're not going to open the file directly
            but instead move it to the osu! songs folder so you can open them later by pressing f5 in game
            '''
            shutil.move(song_file, os.path.join(OSU_SONGS_FOLDER, song_file))
            print(f"{song_file} has been moved to songs folder, press f5 on osu! to get it")
        else:
            os.startfile(song_file, 'open')

        # Using a thread to upload song to drive to not block the incoming files
        upload_thread = threading.Thread(target=self.upload_song_to_drive, args=(event.dest_path,))
        self.thread_queue.append(upload_thread)

    def check_download_folder(self):
        '''
        Check download folder when app starts, upload and open .osz
        Used if you download songs without having the game opened and if you didn't open them
        Also used after --init
        '''
        list_download_folder  = [dir for dir in os.listdir(DOWNLOAD_FOLDER)]

        for file in list_download_folder:
            if file.endswith(".osz"):
                print(f"CHECK DOWNLOAD FOLDER: {file}")
                '''
                If you used --init or --no-open we're not going to open the files directly
                but instead move them to the osu! songs folder so you can open them later by pressing f5 in game
                '''

                '''
                Copy the file.osz to osu-automate folder so we can open a file and upload the other
                Ensure fast opening of the song
                '''
                if args.init or args.no_open:
                    shutil.copy(os.path.join(DOWNLOAD_FOLDER, file), file)
                    shutil.move(file, os.path.join(OSU_SONGS_FOLDER, file))
                    print(f"{file} has been moved to songs folder, press f5 on osu! to get it")
                else:
                    shutil.copy(os.path.join(DOWNLOAD_FOLDER, file), file)
                    os.startfile(file, 'open')

                # Using a thread to upload song to drive to not block the other files
                upload_thread = threading.Thread(target=self.upload_song_to_drive, args=(os.path.join(DOWNLOAD_FOLDER, file),))
                self.thread_queue.append(upload_thread)

    
class StartupCheck(GoogleFunctionUtilities):
    '''
    The class contain one main method who is going to be called when the app osu! is launched
    The idea is to check if new songs has been added to the drive and that are not on this computer
    Then the app will download them
    '''
    def __init__(self, service):
        self.queue_removable_files = []
        self.gdrive_service = service
        self.thread_queue = []
        print("Start up check...")

    def check_remote_songs_on_startup(self):
        '''
        Check if new songs has been added to the google drive
        If yes, we download them : OsuHandler.check_download_folder will then open them
        '''
        response_data = self.list_files_from_drive()

        list_remote = [(data['id'], data['name']) for data in response_data] # Get songs drive id and name
        list_local  = [dir.split(" ")[0] for dir in os.listdir(OSU_SONGS_FOLDER)] # Get local songs number

        # remote[0] = id, remote[1] = filename
        for remote in list_remote:
            song_name = remote[1]
            if song_name.split(" ")[0] not in list_local:
                print(f"NEW drive: {song_name}")
                script_path = os.getcwd()
                os.chdir(DOWNLOAD_FOLDER)
                self.download_song(remote)
                print("Done")
                os.chdir(script_path)
    
    def check_local_songs_on_startup(self):
        '''
        Check if new songs has been added to the local songs folder
        If yes, we upload them to the drive
        '''
        response_data = self.list_files_from_drive()

        list_remote = [data['name'].split(" ")[0] for data in response_data] # Get songs drive id and name
        list_local  = [dir for dir in os.listdir(OSU_SONGS_FOLDER)] # Get local songs number
        list_download_folder  = [dir.split(" ")[0] for dir in os.listdir(DOWNLOAD_FOLDER)] # Get download folder file list to avoid duplicates

        # remote[0] = id, remote[1] = filename
        for local in list_local:
            if local.split(" ")[0] not in list_remote and local.split(" ")[0] not in list_download_folder and local != "Failed":
                print(f"NEW local: {local}")
                src = os.path.join(OSU_SONGS_FOLDER, local)
                dest = os.path.join(DOWNLOAD_FOLDER, local)

                # Compress folder into zip files
                shutil.make_archive(dest, 'zip', src)
                # Rename to .osz
                shutil.move(f"{dest}.zip", f"{dest}.osz")


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
            2. bis Check if new songs has been added to the locally, if yes upload them
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
        startup.check_remote_songs_on_startup() # Download new from drive
        startup.check_local_songs_on_startup()  # Upload new from local
        event_handler.check_download_folder()   # Process .osz from download folder
        startup.delete_duplicate_songs()        # Delete duplicates in drive

        observer = Observer()
        observer.schedule(event_handler, folder, recursive=True)

        observer.start()
        
        previous_thread_e = ""
        previous_thread_s = ""
        try:
            timer = 0
            while True:
                time.sleep(1)
                timer = timer + 1

                if event_handler.queue_removable_files:
                    os.remove(event_handler.queue_removable_files.pop())

                '''
                Executing uploading thread queues, ensure to execute thread one by one to avoid network overload
                The thread function will delete the uploaded file from the list,
                if the previous thread is deleted from the list the next one starts 
                '''
                if event_handler.thread_queue and previous_thread_e not in event_handler.thread_queue:
                    event_handler.thread_queue[-1].start()
                    previous_thread_e = event_handler.thread_queue[-1]

                if startup.thread_queue and previous_thread_s not in startup.thread_queue:
                    startup.thread_queue[-1].start()
                    previous_thread_s = startup.thread_queue[-1]


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
