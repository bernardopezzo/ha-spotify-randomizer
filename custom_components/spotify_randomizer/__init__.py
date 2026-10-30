"""
Spotify Playlist Randomizer for Home Assistant.

Custom integration that enables true in-place Fisher-Yates playlist shuffling
via the Spotify Web API. Designed for multi-user Home Assistant setups where
each household user can authenticate their own Spotify account, select from
their owned playlists via Lovelace dashboard controls, and trigger shuffles.
"""

import logging
import random
import spotipy
from spotipy.oauth2 import SpotifyOAuth, CacheFileHandler
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
import homeassistant.helpers.config_validation as cv
from homeassistant.components.http import HomeAssistantView
from aiohttp import web
import voluptuous as vol

# The "domain" is the unique identifier for this integration in Home Assistant.
# It matches the folder name 'spotify_randomizer' inside custom_components.
DOMAIN = "spotify_randomizer"
_LOGGER = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# 1. CONFIGURATION SCHEMA
# -----------------------------------------------------------------------------
# Tells Home Assistant what configuration keys to expect in configuration.yaml
# under the `spotify_randomizer:` block.
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required("client_id"): cv.string,
                vol.Required("client_secret"): cv.string,
                vol.Optional("redirect_uri"): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

# Spotify OAuth permissions required:
# - Read both public and private playlists
# - Modify both public and private playlists in-place
SCOPE = "playlist-read-private playlist-modify-private playlist-modify-public"


# -----------------------------------------------------------------------------
# 2. HTTP VIEW FOR SPOTIFY OAUTH REDIRECT CALLBACK
# -----------------------------------------------------------------------------
# Custom endpoint listening at /api/spotify_randomizer/callback to receive the
# authorization code returned by Spotify after the user grants access in their browser.
class SpotifyAuthCallbackView(HomeAssistantView):
    """View to handle Spotify OAuth callback redirects."""

    url = "/api/spotify_randomizer/callback"
    name = "api:spotify_randomizer:callback"
    requires_auth = False  # Must be false because Spotify redirects external browsers here

    def __init__(self, hass: HomeAssistant, client_id: str, client_secret: str, redirect_uri: str):
        self.hass = hass
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    async def get(self, request):
        """Handle GET request when Spotify redirects back with auth code."""
        code = request.query.get("code")
        state = request.query.get("state")  # Contains the Home Assistant user_id

        if not code or not state:
            return web.Response(text="Error: Missing authorization code or state from Spotify.", status=400)

        user_id = state

        # Spotipy is synchronous/blocking; run token exchange in an executor thread
        def exchange_code():
            cache_handler = CacheFileHandler(cache_path=self.hass.config.path(f".cache-spotify-{user_id}"))
            auth_manager = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope=SCOPE,
                cache_handler=cache_handler,
                open_browser=False
            )
            auth_manager.get_access_token(code)

        await self.hass.async_add_executor_job(exchange_code)

        html_response = """
        <!DOCTYPE html>
        <html>
            <head>
                <meta charset="utf-8">
                <title>Spotify Auth Success</title>
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; text-align: center; margin-top: 60px; background: #0e1117; color: #fff; }
                    .card { display: inline-block; padding: 30px; border-radius: 12px; background: #1a1e24; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
                    h2 { color: #1DB954; margin-bottom: 10px; }
                    p { color: #ccc; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h2>✓ Spotify Account Linked!</h2>
                    <p>Your Spotify session is now authorized with Home Assistant.</p>
                    <p>You can close this tab and return to your dashboard.</p>
                </div>
            </body>
        </html>
        """
        return web.Response(text=html_response, content_type="text/html")


# -----------------------------------------------------------------------------
# 3. MAIN INTEGRATION SETUP
# -----------------------------------------------------------------------------
async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Spotify Randomizer integration."""
    if DOMAIN not in config:
        _LOGGER.error("Spotify Randomizer configuration missing from configuration.yaml")
        return True

    conf = config[DOMAIN]
    client_id = conf["client_id"]
    client_secret = conf["client_secret"]

    # Use configured redirect_uri, or construct a placeholder that prompts user configuration
    default_redirect = "https://<YOUR-HOME-ASSISTANT-DOMAIN-OR-IP>:8123/api/spotify_randomizer/callback"
    redirect_uri = conf.get("redirect_uri", default_redirect)

    # Register the callback HTTP view
    hass.http.register_view(SpotifyAuthCallbackView(hass, client_id, client_secret, redirect_uri))

    def get_spotipy(user_id: str) -> spotipy.Spotify:
        """Helper to get an authenticated Spotipy instance for a specific HA user."""
        cache_handler = CacheFileHandler(cache_path=hass.config.path(f".cache-spotify-{user_id}"))
        auth_manager = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=SCOPE,
            cache_handler=cache_handler,
            open_browser=False
        )
        return spotipy.Spotify(auth_manager=auth_manager)

    # -------------------------------------------------------------------------
    # 4. HOME ASSISTANT SERVICES
    # -------------------------------------------------------------------------
    async def generate_login_url(call):
        """Service: Generate an OAuth authorization URL for the calling user."""
        user_id = call.context.user_id
        if not user_id:
            _LOGGER.error("No user context found for generate_login_url")
            return

        def _get_url():
            auth_manager = SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope=SCOPE,
                state=user_id,  # Passes HA user_id in state parameter
                open_browser=False
            )
            return auth_manager.get_authorize_url()

        url = await hass.async_add_executor_job(_get_url)

        # Store URL in input_text helper entity so Lovelace can render it as a link
        await hass.services.async_call(
            "input_text",
            "set_value",
            {
                "entity_id": "input_text.spotify_login_url",
                "value": url
            },
            blocking=False
        )

    async def fetch_playlists(call):
        """Service: Fetch all playlists owned by the calling user and populate input_select."""
        user_id = call.context.user_id
        if not user_id:
            _LOGGER.error("No user context found for fetch_playlists")
            return

        def _fetch():
            sp = get_spotipy(user_id)
            try:
                spotify_user = sp.current_user()
            except spotipy.SpotifyException as e:
                _LOGGER.error("Spotify authentication failed for user %s: %s", user_id, e)
                return None

            playlists = []
            spotify_user_id = spotify_user["id"]

            results = sp.current_user_playlists(limit=50)
            while results:
                for item in results["items"]:
                    # Only show playlists owned by this user (cannot reorder collaborative/read-only playlists)
                    if item["owner"]["id"] == spotify_user_id:
                        playlists.append(f"{item['name']} ({item['id']})")

                if results["next"]:
                    results = sp.next(results)
                else:
                    break
            return playlists

        playlists = await hass.async_add_executor_job(_fetch)

        if playlists is not None:
            await hass.services.async_call(
                "input_select",
                "set_options",
                {
                    "entity_id": "input_select.spotify_playlists",
                    "options": playlists if playlists else ["No playlists found"]
                },
                blocking=False
            )

    async def shuffle_playlist(call):
        """Service: Perform true in-place Fisher-Yates reordering of the selected playlist."""
        user_id = call.context.user_id
        if not user_id:
            _LOGGER.error("No user context found for shuffle_playlist")
            return

        state = hass.states.get("input_select.spotify_playlists")
        if not state or not state.state or state.state == "No playlists found":
            _LOGGER.error("No valid playlist selected in input_select.spotify_playlists")
            return

        selected_option = state.state
        try:
            # Extract playlist ID from 'Playlist Name (ID)'
            playlist_id = selected_option.split("(")[-1].strip(")")
        except IndexError:
            _LOGGER.error("Could not parse playlist ID from string: %s", selected_option)
            return

        def _shuffle():
            sp = get_spotipy(user_id)
            try:
                sp.current_user()
            except spotipy.SpotifyException as e:
                _LOGGER.error("Spotify authentication invalid or expired: %s", e)
                return

            _LOGGER.info("Fetching tracks for playlist: %s", playlist_id)

            # Paginate through all tracks in playlist
            results = sp.playlist_items(playlist_id)
            tracks = results["items"]
            while results["next"]:
                results = sp.next(results)
                tracks.extend(results["items"])

            total_tracks = len(tracks)
            if total_tracks <= 1:
                _LOGGER.info("Playlist has %d track(s), skipping shuffle", total_tracks)
                return

            _LOGGER.info("Beginning in-place Fisher-Yates shuffle of %d tracks...", total_tracks)

            # -----------------------------------------------------------------
            # Fisher-Yates In-Place Shuffle via Spotify playlist_reorder_items
            # -----------------------------------------------------------------
            for i in range(total_tracks - 1, 0, -1):
                j = random.randint(0, i)
                if i != j:
                    # Move track at index j to index i
                    # 'insert_before=i + 1' places the track at index i
                    sp.playlist_reorder_items(
                        playlist_id=playlist_id,
                        range_start=j,
                        insert_before=i + 1
                    )
            _LOGGER.info("In-place playlist shuffle completed successfully!")

        await hass.async_add_executor_job(_shuffle)

    # Register services
    hass.services.async_register(DOMAIN, "generate_login_url", generate_login_url)
    hass.services.async_register(DOMAIN, "fetch_playlists", fetch_playlists)
    hass.services.async_register(DOMAIN, "shuffle", shuffle_playlist)

    return True
