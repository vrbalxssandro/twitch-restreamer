import requests
import time
import subprocess
import os
import datetime
import json
import shutil
import signal
import config

streamlink_process = None
ffmpeg_process = None
is_restreaming_active = False

TWITCH_API_BASE_URL = "https://api.twitch.tv/helix"
TWITCH_AUTH_URL = "https://id.twitch.tv/oauth2/token"
ACCESS_TOKEN = None
TOKEN_EXPIRY_TIME = 0

def get_twitch_access_token():
    global ACCESS_TOKEN, TOKEN_EXPIRY_TIME
    current_time = time.time()
    if ACCESS_TOKEN and current_time < TOKEN_EXPIRY_TIME - 60:
        return ACCESS_TOKEN
    print("Fetching new Twitch API access token...")
    try:
        response = requests.post(
            TWITCH_AUTH_URL,
            data={
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "grant_type": "client_credentials",
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        ACCESS_TOKEN = data["access_token"]
        TOKEN_EXPIRY_TIME = current_time + data["expires_in"]
        print("Access token obtained successfully.")
        return ACCESS_TOKEN
    except requests.exceptions.RequestException as e:
        print(f"Error getting Twitch access token: {e}")
        ACCESS_TOKEN = None; TOKEN_EXPIRY_TIME = 0
        return None

def is_streamer_live(username):
    token = get_twitch_access_token()
    if not token: return False, None
    headers = {"Client-ID": config.client_id, "Authorization": f"Bearer {token}"}
    params = {"user_login": username}
    try:
        response = requests.get(f"{TWITCH_API_BASE_URL}/streams", headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("data") and data["data"][0].get("type") == "live":
            stream_data = data["data"][0]
            return True, stream_data
        return False, None
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("Twitch API token might have expired. Attempting to refresh.")
            global ACCESS_TOKEN; ACCESS_TOKEN = None
        else: print(f"HTTP Error checking stream status for {username}: {e}")
        return False, None
    except requests.exceptions.RequestException as e:
        print(f"Network error checking stream status for {username}: {e}")
        return False, None

def send_discord_webhook(message_type, username, stream_data=None):
    if not config.webhook_url: return

    color = 15158332
    title_prefix = ":stop_button: Restream STOPPED"
    description = f"Restreaming of {username}'s Twitch stream has stopped."

    if message_type == "start":
        color = 3066993
        title_prefix = ":satellite: Restream STARTED"
        stream_title = stream_data.get("title", "No Title") if stream_data else "N/A"
        game_name = stream_data.get("game_name", "N/A") if stream_data else "N/A"
        description = (f"Now restreaming **{username}** to YouTube.\n"
                       f"Twitch Title: **{stream_title}**\n"
                       f"Game: **{game_name}**\n"
                       f"[Watch on Twitch](https://twitch.tv/{username})")

    data = {
        "content": f"{title_prefix} for **{username}**",
        "embeds": [{
            "title": f"{title_prefix}",
            "description": description,
            "color": color,
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "author": {"name": username, "url": f"https://twitch.tv/{username}"},
            "footer": {"text": "Twitch-to-YouTube Resteramer"}
        }]
    }
    try:
        response = requests.post(config.webhook_url, data=json.dumps(data), headers={"Content-Type": "application/json"}, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error sending Discord webhook for {message_type}: {e}")


def start_restream(username):
    global streamlink_process, ffmpeg_process, is_restreaming_active

    if not config.youtube_stream_key:
        print("ERROR: YouTube Stream Key is missing in config.py. Cannot start restream.")
        return

    stream_url_twitch = f"twitch.tv/{username}"
    stream_url_youtube = f"{config.youtube_rtmp_url_base.strip('/')}/{config.youtube_stream_key}"

    print(f"Attempting to start restream for {username}...")
    print(f"  Twitch Source: {stream_url_twitch}")
    print(f"  YouTube Target: {config.youtube_rtmp_url_base.strip('/')}/<YOUR_STREAM_KEY>")

    sl_command = [
        "streamlink",
        "--stdout",
        stream_url_twitch,
        "best",
        "--twitch-disable-hosting",
        "--hls-live-restart",
        "--retry-streams", "5",
        "--retry-open", "3",
    ]

    ffmpeg_command = [
        "ffmpeg",
        "-hide_banner",
        "-i", "pipe:0",
        "-c:v", "copy",
        "-c:a", "copy",
        "-f", "flv",
        "-map", "0:v",
        "-map", "0:a",
        "-bufsize", "4000k",
        "-loglevel", "error",
        stream_url_youtube
    ]

    try:
        print("Starting Streamlink process...")
        streamlink_process = subprocess.Popen(sl_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"Streamlink PID: {streamlink_process.pid}")

        print("Starting FFmpeg process...")
        ffmpeg_process = subprocess.Popen(ffmpeg_command, stdin=streamlink_process.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        print(f"FFmpeg PID: {ffmpeg_process.pid}")

        if streamlink_process.stdout:
             streamlink_process.stdout.close()

        is_restreaming_active = True

        ffmpeg_stderr_output = ""
        if ffmpeg_process.stderr:
            for line in iter(ffmpeg_process.stderr.readline, b''):
                decoded_line = line.decode('utf-8', errors='ignore').strip()
                ffmpeg_stderr_output += decoded_line + "\n"

                if streamlink_process and streamlink_process.poll() is not None:
                    print(f"Streamlink process (PID: {streamlink_process.pid}) ended unexpectedly (Exit Code: {streamlink_process.poll()}) while FFmpeg was running.")
                    break

            ffmpeg_process.stderr.close()

        print("Waiting for FFmpeg process to exit...")
        ffmpeg_process.wait()
        ff_exit_code = ffmpeg_process.poll()
        print(f"FFmpeg process (PID: {ffmpeg_process.pid}) exited with code: {ff_exit_code}")

        if ff_exit_code != 0:
             print("\n--- FFmpeg Error Log ---")
             print(ffmpeg_stderr_output if ffmpeg_stderr_output else "No stderr output captured.")
             print("--- End FFmpeg Error Log ---\n")

        sl_exit_code = None
        if streamlink_process:
            sl_exit_code = streamlink_process.poll()
            if sl_exit_code is None:
                 print("FFmpeg exited, but Streamlink is still running. Terminating Streamlink...")
                 terminate_process(streamlink_process, "Streamlink")
            else:
                 print(f"Streamlink process had already exited with code: {sl_exit_code}")
                 if streamlink_process.stderr:
                      sl_stderr = streamlink_process.stderr.read().decode('utf-8', errors='ignore').strip()
                      if sl_stderr: print(f"Streamlink STDERR:\n{sl_stderr}")

    except FileNotFoundError as e:
        print(f"ERROR: Command not found. Ensure Streamlink and FFmpeg are installed and in PATH. Details: {e}")
    except Exception as e:
        print(f"An unexpected critical error occurred during restreaming setup or monitoring: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Cleaning up restream processes...")
        cleanup_processes()
        is_restreaming_active = False

def terminate_process(process, name):
    if process and process.poll() is None:
        print(f"Terminating {name} process (PID: {process.pid})...")
        try:
            process.terminate()
            process.wait(timeout=10)
            print(f"{name} process terminated (Exit Code: {process.poll()}).")
        except subprocess.TimeoutExpired:
            print(f"{name} did not terminate gracefully, killing (PID: {process.pid})...")
            process.kill()
            process.wait()
            print(f"{name} process killed (Exit Code: {process.poll()}).")
        except Exception as e:
            print(f"Error during {name} process termination: {e}")

def cleanup_processes():
    global streamlink_process, ffmpeg_process
    terminate_process(ffmpeg_process, "FFmpeg")
    ffmpeg_process = None
    terminate_process(streamlink_process, "Streamlink")
    streamlink_process = None
    print("Process cleanup finished.")

def signal_handler(sig, frame):
    print(f"\nSignal {sig} received. Shutting down gracefully...")
    global is_restreaming_active
    is_restreaming_active = False
    cleanup_processes()
    print("Exiting script.")
    exit(0)

def main():
    global is_restreaming_active
    print("--- Twitch-to-YouTube Restreamer Started ---")
    print(f"Monitoring Twitch User: {config.twitch_username}")
    print(f"YouTube RTMP Base: {config.youtube_rtmp_url_base}")
    if not config.youtube_stream_key:
        print("CRITICAL ERROR: youtube_stream_key is not set in config.py!")
        return
    if not config.client_id or not config.client_secret:
        print("CRITICAL ERROR: Twitch client_id or client_secret missing in config.py!")
        return
    if not shutil.which("streamlink"):
        print("CRITICAL ERROR: 'streamlink' command not found in PATH.")
        return
    if not shutil.which("ffmpeg"):
        print("CRITICAL ERROR: 'ffmpeg' command not found in PATH.")
        return

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    check_interval = 15

    while True:
        try:
            live, stream_data = is_streamer_live(config.twitch_username)

            if live and not is_restreaming_active:
                print(f"\n{config.twitch_username} is LIVE! Starting restream...")
                send_discord_webhook("start", config.twitch_username, stream_data)
                start_restream(config.twitch_username)
                print(f"Restream stopped for {config.twitch_username}.")
                send_discord_webhook("stop", config.twitch_username)
                print("Waiting 60 seconds before next check...")
                time.sleep(60)

            elif not live and is_restreaming_active:
                print(f"{config.twitch_username} appears offline, but restream was marked active. Cleaning up...")
                cleanup_processes()
                is_restreaming_active = False
                send_discord_webhook("stop", config.twitch_username)
                print(f"Waiting {check_interval} seconds...")
                time.sleep(check_interval)

            elif not live and not is_restreaming_active:
                print(f"{config.twitch_username} is offline. Waiting {check_interval} seconds...")
                time.sleep(check_interval)

            elif live and is_restreaming_active:
                print(f"{config.twitch_username} is still live and restreaming. Waiting {check_interval} seconds...")
                time.sleep(check_interval)

        except Exception as e:
            print(f"\n--- ERROR IN MAIN LOOP ---")
            print(f"An unexpected error occurred: {e}")
            import traceback
            traceback.print_exc()
            print("Cleaning up processes due to error...")
            cleanup_processes()
            is_restreaming_active = False
            print(f"Waiting 60 seconds before retrying...\n")
            time.sleep(60)


if __name__ == "__main__":
    main()