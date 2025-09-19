import json
import os.path
import shutil
import subprocess
import traceback
import urllib.parse
import sys
import os

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# from src.models.cookie import Cookie
# from models.cookie import Cookie



def clear_directory(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
        return

    try:
        for root, dirs, files in os.walk(path, topdown=False):
            for file in files:
                try:
                    file_path = os.path.join(root, file)
                    os.remove(file_path)
                except Exception as e:
                    print(f"Impossible de supprimer {file}: {e}")
            for dir in dirs:
                try:
                    dir_path = os.path.join(root, dir)
                    os.rmdir(dir_path)
                except Exception as e:
                    print(f"Impossible de supprimer le dossier {dir}: {e}")
    except Exception as e:
        print(f"Erreur lors du nettoyage de {path}: {e}")
        try:
            shutil.rmtree(path)
            os.makedirs(path, exist_ok=True)
        except Exception as e2:
            print(f"Erreur critique lors du nettoyage: {e2}")



def get_file_name(file: str):
    filename_parts = file.split('.')
    filename_parts.pop()
    return "".join(filename_parts)



# def upload_cookies(cookies: list[Cookie]):
#     filename = os.path.join(TEMP_COOKIES_FOLDER, f"cookies_{uuid.uuid4().hex}.txt")
#
#     with open(filename, "w", encoding="utf-8") as f:
#         f.write("# Netscape HTTP Cookie File\n")
#         f.write("# This file was generated automatically.\n")
#         f.write("# Format: domain\tflag\tpath\tsecure\texpiration\tname\tvalue\n")
#         f.write("")
#
#         for cookie in cookies:
#             domain = cookie.domain
#
#             include_subdomains = "FALSE" if cookie.hostOnly else "TRUE"
#             if domain.startswith("."):
#                 include_subdomains = "TRUE"
#
#             secure = "TRUE" if cookie.secure else "FALSE"
#             expiry = 0 if cookie.session else cookie.expirationDate
#
#             f.write("\t".join([
#                 domain,
#                 include_subdomains,
#                 cookie.path,
#                 secure,
#                 str(expiry),
#                 cookie.name,
#                 cookie.value
#             ]) + "\n")
#
#     return filename



def download_source_videos(url: str):
    from yt_dlp import YoutubeDL

    print("will download source videos")
    # cookie_filepath = upload_cookies(cookies)
    ydl_opts = {
        # 'cookiefile': cookie_filepath,
        'force_ipv4': True,
        'user_agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) '
            'Gecko/20100101 Firefox/141.0'
        ),
        'noplaylist': True,
        'no_warnings': True,
        'quiet': False,
        'outtmpl': f'{TEMP_VIDEOS_FOLDER}/%(title)s.%(ext)s',
        'external_downloader': 'aria2c',
        'external_downloader_args': ['-x', '8', '-k', '1M'],
        'nocheckcertificate': True,
        'no_call_home': True,
        'socket_timeout': 10,
        'source_address': '0.0.0.0',
        'prefer_ffmpeg': True,
        'cachedir': False,
        'postprocessors': [],
        'restrictfilenames': True
    }

    with YoutubeDL(ydl_opts) as ydl:
        print("Attempt to download source videos")
        ydl.download([url])

    # os.remove(cookie_filepath)

    return {"videos": os.listdir(TEMP_VIDEOS_FOLDER)}



def process_video_synchronously(temp_video_filename):
    temp_audio_filename = os.path.splitext(temp_video_filename)[0] + '.wav'
    temp_video_file_path = os.path.join(TEMP_VIDEOS_FOLDER, temp_video_filename)
    temp_audio_file_path = os.path.join(TEMP_AUDIO_FOLDER, temp_audio_filename)

    extract_audio_from_video(temp_video_file_path, temp_audio_file_path)
    vocals_path = extract_voice_from_audio(temp_audio_file_path)
    concat_video_with_audio(temp_video_file_path, vocals_path)

    print(f"Succès de la conversion : {temp_video_file_path}")



def extract_audio_from_video(video_path, audio_path):
    try:
        print("Extraction de l'audio depuis la vidéo...")
        cmd = [
            'ffmpeg', '-i', video_path,
            '-vn', '-acodec', 'pcm_s16le',
            '-ar', '44100', '-ac', '2',
            '-y', audio_path
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"Audio extrait avec succès : {audio_path}")
    except subprocess.CalledProcessError as e:
        print(f"Erreur lors de l'extraction audio : {e.stderr}")
        raise
    except FileNotFoundError:
        raise Exception("FFmpeg n'est pas installé ou pas dans le PATH")



def extract_voice_from_audio(file_path):
    try:
        print("Extraction des voix")
        from spleeter.separator import Separator
        separator = Separator("spleeter:2stems")
        separator.separate_to_file(file_path, TEMP_AUDIO_CONVERTED_FOLDER)
        return os.path.join(
            TEMP_AUDIO_CONVERTED_FOLDER,
            os.path.splitext(os.path.basename(file_path))[0],
            "vocals.wav"
        )
    except Exception as e:
        print(f"Erreur lors de la séparation audio : {e}")
        raise



def concat_video_with_audio(video_path, vocals_path):
    try:
        print("Fusion de la vidéo avec les voix")
        video_filename = os.path.splitext(os.path.basename(video_path))[0]
        output_path = os.path.join(OUTPUT_VIDEOS_FOLDER, video_filename + ".mp4")

        cmd = [
            'ffmpeg', '-y', '-i', video_path, '-i', vocals_path,
            '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy',
            '-c:a', 'aac', '-b:a', '128k', '-shortest', output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"Vidéo créée avec succès : {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"Erreur lors de la concaténation : {e.stderr}")
        raise




def reset_storage(with_output: bool = False):
    os.makedirs(TEMP_FOLDER_PREFIX, exist_ok=True)

    # os.makedirs(TEMP_COOKIES_FOLDER, exist_ok=True)
    os.makedirs(TEMP_VIDEOS_FOLDER, exist_ok=True)
    os.makedirs(TEMP_AUDIO_FOLDER, exist_ok=True)
    os.makedirs(TEMP_AUDIO_CONVERTED_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_VIDEOS_FOLDER, exist_ok=True)

    # clear_directory(TEMP_COOKIES_FOLDER)
    clear_directory(TEMP_VIDEOS_FOLDER)
    clear_directory(TEMP_AUDIO_FOLDER)
    clear_directory(TEMP_AUDIO_CONVERTED_FOLDER)

    if with_output:
        clear_directory(OUTPUT_VIDEOS_FOLDER)



def _convert_callback(request: Request, url: str):
    try:
        reset_storage(True)
        download_source_videos(url)
    
        if len(os.listdir(TEMP_VIDEOS_FOLDER)) == 0:
            raise HTTPException(status_code=404, detail="Video not found")
    
        print(f"Vidéos trouvées : {os.listdir(TEMP_VIDEOS_FOLDER)}")
    
        for temp_video_filename in os.listdir(TEMP_VIDEOS_FOLDER):
            process_video_synchronously(temp_video_filename)
    
        videos = []
        base_url = str(request.base_url)
    
        for file in os.listdir(OUTPUT_VIDEOS_FOLDER):
            encoded_filename = urllib.parse.quote(file)
            videos.append({
                "filename": get_file_name(file),
                "url": f"{base_url}files/{encoded_filename}"
            })
    
        return JSONResponse(status_code=201, content={ "videos": videos, "error": None })
    except Exception as e:
        print(f"Erreur lors de la conversion: {e}")
        traceback.print_exc()
        raise


if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    base_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    base_path = application_path



TEMP_FOLDER_PREFIX = 'temp'
LOGS_FOLDER_PREFIX = 'logs'

TEMP_VIDEOS_FOLDER = '/'.join([TEMP_FOLDER_PREFIX, 'video'])
TEMP_AUDIO_FOLDER = '/'.join([TEMP_FOLDER_PREFIX, 'audio'])
TEMP_AUDIO_CONVERTED_FOLDER = '/'.join([TEMP_FOLDER_PREFIX, 'audio_converted'])
TEMP_COOKIES_FOLDER = '/'.join([TEMP_FOLDER_PREFIX, 'cookie'])
OUTPUT_VIDEOS_FOLDER = '/'.join([TEMP_FOLDER_PREFIX, 'output'])

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

app.mount("/files", StaticFiles(directory=OUTPUT_VIDEOS_FOLDER), name="output_files")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.post("/convert")
async def convert_endpoint(request: Request, url: str):
    try:
        if url.startswith(request.base_url.__str__()):
            raise HTTPException(status_code=400, detail="Url must not be server")
        print(url, f"/convert appelé")
        result = _convert_callback(request, url)
        print(url, "Done")
        return result
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"videos": [], "error": str(e)})
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"videos": [], "error": str(e)})

def run_server():
    try:
        import uvicorn
        if not check_dependencies():
            print("Dépendances manquantes, arrêt...")
            return

        print("Démarrage du serveur...")
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=55942,
            log_level="info"
        )
    except Exception as e:
        print(f"Erreur lors du démarrage du serveur: {e}")
        traceback.print_exc()

def check_dependencies():
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("✓ FFmpeg disponible")
    except:
        print("✗ FFmpeg non trouvé")
        return False

    try:
        from spleeter.separator import Separator
        print("✓ Spleeter importé")
    except Exception as e:
        print(f"✗ Erreur Spleeter: {e}")
        return False

    try:
        subprocess.run(['yt-dlp', '--version'], capture_output=True, check=True)
        print("✓ yt-dlp disponible")
    except:
        print("✗ yt-dlp non trouvé")
        return False

    return True


if __name__ == '__main__':
    import multiprocessing

    reset_storage(True)
    multiprocessing.freeze_support()
    run_server()
