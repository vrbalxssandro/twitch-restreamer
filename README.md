A Python script that automatically monitors a specified Twitch channel and restream's it to YouTube Live using Streamlink and FFmpeg when the channel goes live. It also sends notifications to a Discord webhook when the restream starts and stops.

## Features

*   **Automatic Live Detection:** Continuously checks the Twitch API to see if the target streamer is live.
*   **Low-Latency Restreaming:** Uses Streamlink to fetch the best available stream quality and pipes it directly to FFmpeg.
*   **Efficient Transcoding (Passthrough):** Configured to copy video and audio codecs (`-c:v copy -c:a copy`) directly, avoiding CPU-intensive re-encoding and preserving original quality.
*   **Discord Notifications:** Sends messages to a configured Discord webhook when the restream starts (including stream title and game) and when it stops.
*   **Configuration File:** Separates settings (API keys, usernames, URLs) into `config.py` for easy management.
*   **Robust Error Handling:** Includes checks for prerequisites (FFmpeg/Streamlink), handles Twitch API token refresh, manages subprocesses, and includes graceful shutdown on interruption (Ctrl+C).
*   **Process Management:** Properly starts, monitors, and cleans up Streamlink and FFmpeg processes.

## Prerequisites

You need:

1.  **Python 3.x:** Download from [python.org](https://www.python.org/).
2.  **FFmpeg:**
    *   Download from [ffmpeg.org](https://ffmpeg.org/download.html).
    *   **Crucially:** Ensure the `ffmpeg` executable is added to your system's PATH environment variable so the script can find it.
3.  **Twitch Developer Application:**
    *   Go to the [Twitch Developer Console](https://dev.twitch.tv/console/).
    *   Register a new application (Category: Chat Bot or other appropriate).
    *   Note down the **Client ID** and generate a **Client Secret**.
4.  **YouTube Account:**
    *   Enabled for Live Streaming.
    *   Access to your YouTube Studio to get your **RTMP Server URL** and **Stream Key**.
5.  **Discord Account:**
    *   A Discord server where you have permission to create webhooks.
    *   Create a webhook in your server settings (Integrations -> Webhooks) and copy the **Webhook URL**.


## How to Run

1.  **Get the Code:**
    *   Clone the repository: `git clone <your-repository-url>` (Replace with your actual repo URL!)
    *   Or download the `twitch-recorder.py` and `config.py` files.

2.  **Install Dependencies:**
    *   Navigate to the script directory in your terminal.
    *   Install the required Python packages:
        ```bash
        pip install requests streamlink
        ```

3.  **Configure:**
    *   Open and edit the `config.py` file.
    *   Fill in **all** the required values:
        *   `twitch_username`: The Twitch channel login name to monitor (e.g., "ninja").
        *   `client_id`: Your Twitch Application Client ID.
        *   `client_secret`: Your Twitch Application Client Secret.
        *   `youtube_rtmp_url_base`: Your YouTube RTMP ingest URL (e.g., `rtmp://a.rtmp.youtube.com/live2`).
        *   `youtube_stream_key`: Your unique YouTube Stream Key.
        *   `webhook_url`: Your Discord Webhook URL for start/stop notifications.
            *   **(Optional) To disable Discord notifications:** Set `webhook_url = ""` (an empty string).
    *   **Security Note:** Your `client_secret`, `youtube_stream_key`, and `webhook_url` are sensitive. Avoid committing `config.py` directly to public repositories. Consider using environment variables or adding `config.py` to your `.gitignore` file.

4.  **Run the Script:**
    *   Make sure you are still in the directory containing the script files in your terminal.
    *   Execute the script:
        ```bash
        python twitch-restreamer.py
        ```
    *   The script will start monitoring. Leave the terminal window open. Use `Ctrl+C` to stop it gracefully.
    

## Troubleshooting

*   **"Command not found: streamlink" / "Command not found: ffmpeg"**: Ensure both are installed correctly AND their directories are included in your system's PATH environment variable. Verify by typing `streamlink --version` and `ffmpeg -version` in your terminal.
*   **"Error getting Twitch access token"**: Verify your `client_id` and `client_secret` in `config.py` are correct and haven't been revoked. Check the Twitch Developer status page.
*   **Restream fails / FFmpeg errors**: Double-check `youtube_rtmp_url_base` and `youtube_stream_key` in `config.py`. Check the script's console output for specific FFmpeg error messages (network issues, invalid key, etc.).
*   **No Discord messages**: Ensure `webhook_url` in `config.py` is correct and the webhook is still valid in your Discord server settings. If you set it to `""`, no messages will be sent.
*   **Script stops unexpectedly**: Check the console output or `nohup.out` (if used) for error messages. Network instability or issues with the source Twitch stream can cause interruptions.



