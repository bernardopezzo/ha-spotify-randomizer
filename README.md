# Spotify Playlist Randomizer for Home Assistant

![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Custom%20Component-blue?logo=homeassistant)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python)
![Spotify API](https://img.shields.io/badge/Spotify%20API-Spotipy-1DB954?logo=spotify)

A multi-user **Home Assistant Custom Integration** and standalone CLI tool that performs **true in-place Fisher-Yates shuffling** of your Spotify playlists using the Spotify Web API (`playlist_reorder_items`).

---

## 🎯 Why In-Place Shuffling?

Spotify's native "Shuffle" button has notorious flaws:
- It frequently clusters tracks by the same artist or plays the same predictable subset of songs.
- Other playlist shufflers create duplicate playlists (e.g. *"My Playlist (Shuffled)"*). This breaks shared links, destroys your follower counts, requires re-downloading gigabytes for offline listening, and breaks voice assistant routines (*"Alexa/Google, play My Playlist"*).

**This integration shuffles the actual playlist itself.** The Playlist ID remains identical, preserving all downloads, shares, and voice presets while completely randomizing track order.

---

## ✨ Features

- **True In-Place Fisher-Yates Algorithm**: Every track position has an equal, mathematically fair probability of landing anywhere in the playlist.
- **Multi-User Isolation**: Supports multiple household members in Home Assistant. Each user links their own Spotify account; tokens are stored in isolated per-user cache files (`.cache-spotify-<user_id>`).
- **Dashboard UI Ready**: Easily triggered via simple Lovelace buttons with live status notifications and dropdown selectors.
- **Non-Blocking Architecture**: Spotipy synchronous network requests are executed via Home Assistant's `async_add_executor_job` worker pool, preventing UI freezes.
- **Standalone CLI Tool Included**: Need to shuffle from your terminal? Run [`standalone/playlist_randomizer.py`] directly without Home Assistant.

---

## ⚙️ 1. Spotify Developer Setup

1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and log in.
2. Click **Create App**:
   - **App Name**: `Home Assistant Playlist Randomizer`
   - **App Description**: `In-place playlist shuffler for Home Assistant`
   - **Redirect URI**: 
     - For Home Assistant: `https://<YOUR-HA-DOMAIN-OR-IP>:8123/api/spotify_randomizer/callback`
     - For Standalone CLI: `http://localhost:8080`
   - **APIs Used**: Select **Web API**.
3. Under **Settings**, copy your **Client ID** and **Client Secret**.

---

## 🏠 2. Home Assistant Installation

### Step 1: Copy Integration Files
Copy the [`custom_components/spotify_randomizer`] directory into your Home Assistant `/config/custom_components/` folder:

```text
config/
└── custom_components/
    └── spotify_randomizer/
        ├── __init__.py
        ├── manifest.json
        └── services.yaml
```

### Step 2: Configure `configuration.yaml`
Add the following configuration (see [`examples/configuration.yaml`]):

```yaml
# Helper entities for dashboard UI
input_text:
  spotify_login_url:
    name: "Spotify Login Link"
    max: 500

input_select:
  spotify_playlists:
    name: "Selected Spotify Playlist"
    options:
      - "No playlists found"
    initial: "No playlists found"

# Spotify Randomizer Integration
spotify_randomizer:
  client_id: "YOUR_SPOTIFY_CLIENT_ID"
  client_secret: "YOUR_SPOTIFY_CLIENT_SECRET"
  redirect_uri: "https://your-ha-domain.duckdns.org:8123/api/spotify_randomizer/callback"
```

Restart Home Assistant.

### Step 3: Add the Lovelace Dashboard Card
In your dashboard, add a new card in **Manual YAML mode** and paste the contents of [`examples/lovelace_card.yaml`].

---

## 📱 3. How to Use in Home Assistant

1. **Step 1 - Authorize**: Click **1. Authorize**. A clickable link will appear below the card. Click it, log into Spotify in your browser, and authorize the app. Once authorized, close the browser tab.
2. **Step 2 - Load Playlists**: Click **2. Load Playlists**. The dropdown menu will populate with all playlists owned by your user account.
3. **Step 3 - Shuffle**: Select a playlist from the dropdown and click **3. Shuffle**. The playlist will be reorganized in-place.

---

## 💻 4. Standalone CLI Usage

If you want to shuffle playlists without Home Assistant:

```bash
cd standalone/
pip install -r requirements.txt

export SPOTIFY_CLIENT_ID="your_client_id"
export SPOTIFY_CLIENT_SECRET="your_client_secret"
export SPOTIFY_REDIRECT_URI="http://localhost:8080"

python playlist_randomizer.py
```

The script will open your browser for one-time login, display your owned playlists, and prompt you to select one to shuffle.

---

## 📁 Repository Structure

```
ha-spotify-randomizer/
├── custom_components/
│   └── spotify_randomizer/
│       ├── __init__.py           # Core HA integration and OAuth callback view
│       ├── manifest.json         # Integration manifest and dependencies
│       └── services.yaml         # Service declarations (generate_login_url, fetch, shuffle)
├── standalone/
│   ├── playlist_randomizer.py    # Independent CLI script
│   └── requirements.txt          # Python dependencies (spotipy)
├── examples/
│   ├── configuration.yaml        # Home Assistant configuration example
│   └── lovelace_card.yaml        # Ready-to-paste dashboard card
├── .env.example                  # Template for Spotify credentials
├── .gitignore                    # Python and token cache exclusions
└── README.md                     # Full documentation
```
