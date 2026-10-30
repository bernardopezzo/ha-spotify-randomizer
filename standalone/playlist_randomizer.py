#!/usr/bin/env python3
"""
Standalone Spotify Playlist In-Place Randomizer.

Shuffles a Spotify playlist in-place using the Fisher-Yates algorithm
via the Spotify Web API (spotipy.playlist_reorder_items).

Unlike creating a duplicate "Shuffled" playlist, this directly modifies
the original playlist so that smart speakers, offline downloads, and
car audio players automatically reflect the newly randomized order.
"""

import os
import sys
import random
import spotipy
from spotipy.oauth2 import SpotifyOAuth, CacheFileHandler

# Read credentials from environment variables or prompt
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "your_client_id_here")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "your_client_secret_here")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8080")

# OAuth scopes required to view and modify user playlists
SCOPE = "playlist-read-private playlist-modify-private playlist-modify-public"


def authenticate_user(session_id: str = "default") -> spotipy.Spotify:
    """
    Authenticate with Spotify using OAuth Authorization Code Flow.
    Caches token in a local .cache file per session_id.
    """
    if CLIENT_ID == "your_client_id_here" or CLIENT_SECRET == "your_client_secret_here":
        print("ERROR: Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables.")
        print("Example: export SPOTIFY_CLIENT_ID='...' SPOTIFY_CLIENT_SECRET='...'")
        sys.exit(1)

    cache_handler = CacheFileHandler(cache_path=f".cache-{session_id}")
    auth_manager = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        cache_handler=cache_handler,
        show_dialog=False
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def get_user_playlists(sp: spotipy.Spotify):
    """
    Fetches all playlists owned by the authenticated user.
    """
    user_id = sp.current_user()["id"]
    playlists = []
    results = sp.current_user_playlists(limit=50)

    while results:
        for item in results["items"]:
            # Only include playlists owned by the user (cannot reorder others' playlists)
            if item["owner"]["id"] == user_id:
                playlists.append(item)
        if results["next"]:
            results = sp.next(results)
        else:
            break

    return playlists


def randomize_playlist_in_place(sp: spotipy.Spotify, playlist_id: str):
    """
    Shuffles a Spotify playlist in-place using the Fisher-Yates algorithm.
    """
    print("Fetching tracks from playlist...")
    results = sp.playlist_items(playlist_id)
    tracks = results["items"]

    # Handle pagination
    while results["next"]:
        results = sp.next(results)
        tracks.extend(results["items"])

    total_tracks = len(tracks)
    print(f"Found {total_tracks} tracks. Beginning in-place Fisher-Yates shuffle...")

    if total_tracks <= 1:
        print("Playlist has 1 or fewer tracks. Nothing to shuffle.")
        return

    # Fisher-Yates in-place shuffle
    for i in range(total_tracks - 1, 0, -1):
        j = random.randint(0, i)
        if i != j:
            # Move item at position j to position i
            sp.playlist_reorder_items(
                playlist_id=playlist_id,
                range_start=j,
                insert_before=i + 1
            )
        # Progress indication
        if (total_tracks - i) % 25 == 0 or i == 1:
            print(f"  Processed {total_tracks - i}/{total_tracks} track positions...")

    print("Success! Playlist has been randomized in-place.")


def main():
    print("=== Spotify Playlist In-Place Randomizer ===")
    sp = authenticate_user()
    user = sp.current_user()
    print(f"Logged in as: {user['display_name']} ({user['id']})")

    playlists = get_user_playlists(sp)
    if not playlists:
        print("No owned playlists found.")
        return

    print("\nYour Owned Playlists:")
    for idx, p in enumerate(playlists, start=1):
        print(f"  [{idx}] {p['name']} ({p['tracks']['total']} tracks) - ID: {p['id']}")

    choice = input("\nEnter playlist number to shuffle (or 'q' to quit): ").strip()
    if choice.lower() == 'q':
        return

    try:
        selected_idx = int(choice) - 1
        if 0 <= selected_idx < len(playlists):
            selected_pl = playlists[selected_idx]
            confirm = input(f"Are you sure you want to shuffle '{selected_pl['name']}' in-place? [y/N]: ").strip()
            if confirm.lower() == 'y':
                randomize_playlist_in_place(sp, selected_pl['id'])
            else:
                print("Aborted.")
        else:
            print("Invalid playlist number.")
    except ValueError:
        print("Invalid input.")


if __name__ == "__main__":
    main()
