import yaml

with open("config.yml", 'r') as stream:
        data = yaml.safe_load(stream)

DOWNLOAD_FOLDER = data["download_folder"]
OSU_SONGS_FOLDER = data["osu_songs_folder"]
GOOGLE_DRIVE_FOLDER_ID = data["google_drive_folder_id"]