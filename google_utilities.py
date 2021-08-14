from google_auth import GoogleAuth
from get_config import *
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

import io
import ntpath


class GoogleFunctionUtilities:

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

    def upload_song_to_drive(self, path):
            '''
            Thread function
            Upload a song to your google drive folder
            Happens in self.check_download_folder() or self.on_moved() methods
            It'll check first if the song is not already in the drive to not create duplicates
            '''
            filename = ntpath.basename(path)
            print(f"UPLOADING START: {filename}")

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

            '''
            Since we cannot delete the song that is being access by the thread we add it to a remvoe queue to delete it later
            '''
            self.queue_removable_files.append(path)
            self.thread_queue.pop()

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
                    if item['name'].split(" ")[0] == check['name'].split(" ")[0]:
                        removed_item.append(check)
                        self.gdrive_service.files().delete(fileId=check['id']).execute()
                        print(f"{check['name']} duplicate found ! Deleted")
            print(f"Duplicates found: {len(removed_item)}")