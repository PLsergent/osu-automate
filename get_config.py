import os
import yaml

with open("config.yml", 'r') as stream:
        data = yaml.safe_load(stream)

DOWNLOAD_FOLDER = data["download_folder"].replace("$User", os.getlogin())
OSU_SONGS_FOLDER = data["osu_songs_folder"].replace("$User", os.getlogin())
GOOGLE_DRIVE_FOLDER_ID = data["google_drive_folder_id"]
STARTUP_APPS_PATH = data["startup_apps_path"].replace("$User", os.getlogin())