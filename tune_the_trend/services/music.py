import httpx
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from tune_the_trend.config import log_structured, settings


class IMusicMetadataProvider(ABC):
    """
    Interface for resolving and enriching track metadata.
    """
    @abstractmethod
    def resolve_track(self, track_title: str, artist: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Queries an external source (e.g. Spotify) to resolve a track,
        returning enriched metadata and audio features.
        """
        pass

    @abstractmethod
    def search_tracks(self, query: str, limit: int = 5) -> list[Dict[str, Any]]:
        """
        Searches for multiple distinct tracks matching the query.
        """
        pass


class MockMusicMetadataProvider(IMusicMetadataProvider):
    """
    Mock provider generating realistic mock Spotify metadata and audio features.
    """
    def resolve_track(self, track_title: str, artist: Optional[str] = None) -> Optional[Dict[str, Any]]:
        log_structured(
            f"Music Resolver (Mock): Resolving track",
            {"track_title": track_title, "artist": artist}
        )
        if not track_title:
            return None
            
        title_lower = track_title.lower()
        artist_lower = (artist or "").lower()
        
        # Determine features based on mock queries
        if "espresso" in title_lower or "sabrina" in artist_lower:
            return {
                "track_title": "Espresso",
                "artist": "Sabrina Carpenter",
                "spotify_id": "4eeaf529a674488fbbaee",
                "spotify_url": "https://open.spotify.com/track/4eeaf529a674488fbbaee",
                "preview_url": "https://p.scdn.co/mp3-preview/espresso",
                "genres": ["pop", "dance-pop"],
                "popularity": 95,
                "energy": 0.76,
                "tempo": 120.0,
                "valence": 0.69,
                "confidence_score": 0.98
            }
        elif "lo-fi" in title_lower or "lofi" in title_lower or "chill" in title_lower:
            return {
                "track_title": "Chill Morning Lofi",
                "artist": "Lofi Kid",
                "spotify_id": "90feea1b12b4e5bbba99",
                "spotify_url": "https://open.spotify.com/track/90feea1b12b4e5bbba99",
                "preview_url": "https://p.scdn.co/mp3-preview/lofi-chill",
                "genres": ["lo-fi", "ambient", "chillhop"],
                "popularity": 70,
                "energy": 0.35,
                "tempo": 82.0,
                "valence": 0.45,
                "confidence_score": 0.90
            }
        elif "hype" in title_lower or "energetic" in title_lower or "gym" in title_lower:
            return {
                "track_title": "Gym Motivation Drop",
                "artist": "Fit Beats",
                "spotify_id": "82beea1b12b4e5bbbc11",
                "spotify_url": "https://open.spotify.com/track/82beea1b12b4e5bbbc11",
                "genres": ["edm", "electro", "house"],
                "popularity": 85,
                "energy": 0.88,
                "tempo": 128.0,
                "valence": 0.75,
                "confidence_score": 0.92
            }
        elif "vlog" in title_lower or "bts" in title_lower or "unfiltered" in title_lower:
            return {
                "track_title": "Unfiltered Vlog Beat",
                "artist": "Creator Audio Labs",
                "spotify_id": "73beea1b12b4e5bbbc33",
                "spotify_url": "https://open.spotify.com/track/73beea1b12b4e5bbbc33",
                "genres": ["indie", "ambient"],
                "popularity": 65,
                "energy": 0.50,
                "tempo": 95.0,
                "valence": 0.60,
                "confidence_score": 0.88
            }
        elif "fashion" in title_lower or "grwm" in title_lower or "pop" in title_lower:
            return {
                "track_title": "Chic Runway Pop",
                "artist": "Glam Sound",
                "spotify_id": "64beea1b12b4e5bbbc44",
                "spotify_url": "https://open.spotify.com/track/64beea1b12b4e5bbbc44",
                "genres": ["pop", "dance-pop"],
                "popularity": 80,
                "energy": 0.75,
                "tempo": 118.0,
                "valence": 0.70,
                "confidence_score": 0.92
            }
        
        # Default fallback metadata
        clean_title = track_title.replace("Trending ", "").replace(" type beat", "").title()
        return {
            "track_title": f"{clean_title} Sound",
            "artist": "Trending Beat Producer",
            "spotify_id": "default_track_id_1234",
            "spotify_url": "https://open.spotify.com/track/default_track_id_1234",
            "preview_url": None,
            "genres": ["pop"],
            "popularity": 50,
            "energy": 0.60,
            "tempo": 105.0,
            "valence": 0.50,
            "confidence_score": 0.50
        }

    def search_tracks(self, query: str, limit: int = 5) -> list[Dict[str, Any]]:
        q = (query or "").lower()
        if "hawaii" in q or "hawaiian" in q:
            return [
                {"track_title": "Oceanic Breeze", "artist": "Sweet Home Hawaii", "spotify_url": "https://www.deezer.com/track/1", "preview_url": "https://cdnt-preview.dzcdn.net/preview-1.mp3", "popularity": 85, "genres": ["hawaiian"], "confidence_score": 0.85},
                {"track_title": "Aloha Oe", "artist": "Gabby Pahinui", "spotify_url": "https://www.deezer.com/track/2", "preview_url": "https://cdnt-preview.dzcdn.net/preview-2.mp3", "popularity": 82, "genres": ["hawaiian"], "confidence_score": 0.85},
                {"track_title": "Island Style", "artist": "John Cruz", "spotify_url": "https://www.deezer.com/track/3", "preview_url": "https://cdnt-preview.dzcdn.net/preview-3.mp3", "popularity": 80, "genres": ["hawaiian"], "confidence_score": 0.85},
                {"track_title": "Over The Rainbow", "artist": "Israel Kamakawiwo'ole", "spotify_url": "https://www.deezer.com/track/4", "preview_url": "https://cdnt-preview.dzcdn.net/preview-4.mp3", "popularity": 92, "genres": ["hawaiian"], "confidence_score": 0.85},
                {"track_title": "Kona Sunset Acoustic", "artist": "Kona Coast Ensemble", "spotify_url": "https://www.deezer.com/track/5", "preview_url": "https://cdnt-preview.dzcdn.net/preview-5.mp3", "popularity": 78, "genres": ["hawaiian"], "confidence_score": 0.85}
            ][:limit]
        single = self.resolve_track(query)
        return [single] if single else []


class SpotifyMusicMetadataProvider(IMusicMetadataProvider):
    """
    Spotify API integration using Client Credentials flow.
    """
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.client = httpx.Client(timeout=10.0)

    def _authenticate(self) -> None:
        """Retrieves Spotify OAuth Token."""
        url = "https://accounts.spotify.com/api/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        res = self.client.post(url, headers=headers, data=data)
        res.raise_for_status()
        self.access_token = res.json()["access_token"]

    def resolve_track(self, track_title: str, artist: Optional[str] = None) -> Optional[Dict[str, Any]]:
        log_structured(
            f"Music Resolver (Spotify): Resolving track",
            {"track_title": track_title, "artist": artist}
        )
        if not self.access_token:
            try:
                self._authenticate()
            except Exception as e:
                log_structured(
                    "Music Resolver Spotify: Authentication failed, falling back to Mock",
                    {"error": str(e)},
                    level=40
                )
                return MockMusicMetadataProvider().resolve_track(track_title, artist)

        # Search Query
        query = f"track:{track_title}"
        if artist:
            query += f" artist:{artist}"
            
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            # 1. Search Track
            search_url = "https://api.spotify.com/v1/search"
            params = {"q": query, "type": "track", "limit": "1"}
            res = self.client.get(search_url, headers=headers, params=params)
            res.raise_for_status()
            
            tracks = res.json().get("tracks", {}).get("items", [])
            if not tracks:
                return None
                
            track = tracks[0]
            track_id = track["id"]
            track_url = track["external_urls"].get("spotify")
            popularity = track.get("popularity", 50)
            preview_url = track.get("preview_url")
            
            # Fetch artist details to get genres
            artist_id = track["artists"][0]["id"]
            artist_res = self.client.get(f"https://api.spotify.com/v1/artists/{artist_id}", headers=headers)
            genres = []
            if artist_res.status_code == 200:
                genres = artist_res.json().get("genres", [])
                
            # 2. Fetch Audio Features
            features_res = self.client.get(f"https://api.spotify.com/v1/audio-features/{track_id}", headers=headers)
            energy, tempo, valence = 0.5, 100.0, 0.5
            if features_res.status_code == 200:
                feat = features_res.json()
                energy = feat.get("energy", energy)
                tempo = feat.get("tempo", tempo)
                valence = feat.get("valence", valence)
                
            return {
                "spotify_id": track_id,
                "spotify_url": track_url,
                "preview_url": preview_url,
                "genres": genres,
                "popularity": popularity,
                "energy": energy,
                "tempo": tempo,
                "valence": valence,
                "confidence_score": 0.95
            }
            
        except Exception as e:
            log_structured(
                "Music Resolver Spotify: Resolve failed, falling back to Mock",
                {"error": str(e)},
                level=40
            )
            return MockMusicMetadataProvider().resolve_track(track_title, artist)

    def search_tracks(self, query: str, limit: int = 5) -> list[Dict[str, Any]]:
        single = self.resolve_track(query)
        return [single] if single else []


class DeezerMusicMetadataProvider(IMusicMetadataProvider):
    """
    Deezer API provider via RapidAPI.
    """
    def __init__(self, rapidapi_key: str, rapidapi_host: str = "deezerdevs-deezer.p.rapidapi.com"):
        self.rapidapi_key = rapidapi_key
        self.rapidapi_host = rapidapi_host
        self.client = httpx.Client(timeout=10.0)

    def resolve_track(self, track_title: str, artist: Optional[str] = None) -> Optional[Dict[str, Any]]:
        tracks = self.search_tracks(f"{track_title} {artist or ''}", limit=1)
        return tracks[0] if tracks else None

    def search_tracks(self, query: str, limit: int = 5) -> list[Dict[str, Any]]:
        search_query = (query or "").replace("Trending ", "").replace(" type beat", "").replace(" Sound", "").replace(" Beat", "").strip()
        if not search_query:
            search_query = "trending hits"
            
        headers = {
            "x-rapidapi-key": self.rapidapi_key,
            "x-rapidapi-host": self.rapidapi_host,
            "Content-Type": "application/json"
        }
        
        try:
            url = f"https://{self.rapidapi_host}/search"
            res = self.client.get(url, headers=headers, params={"q": search_query})
            res.raise_for_status()
            
            data = res.json().get("data", [])
            results = []
            seen = set()
            for track in data:
                t_title = track.get("title", "")
                t_artist = track.get("artist", {}).get("name", "Various Artists")
                key = (t_title.lower().strip(), t_artist.lower().strip())
                if key in seen:
                    continue
                seen.add(key)
                
                track_id = str(track.get("id", ""))
                track_url = track.get("link", "")
                preview_url = track.get("preview", "")
                rank = track.get("rank", 50000)
                popularity = min(100, int(rank / 10000)) if rank else 50
                
                results.append({
                    "track_title": t_title,
                    "artist": t_artist,
                    "spotify_id": f"deezer_{track_id}",
                    "spotify_url": track_url,
                    "preview_url": preview_url,
                    "genres": [search_query],
                    "popularity": popularity,
                    "energy": 0.65,
                    "tempo": 115.0,
                    "valence": 0.55,
                    "confidence_score": 0.85
                })
                if len(results) >= limit:
                    break
            return results
        except Exception as e:
            log_structured("Music Resolver Deezer search_tracks failed", {"error": str(e)}, level=40)
            return MockMusicMetadataProvider().search_tracks(query, limit)


def get_music_provider() -> IMusicMetadataProvider:
    """Factory to retrieve configured music provider."""
    provider = settings.MUSIC_PROVIDER.lower()
    if provider == "deezer":
        if not settings.RAPIDAPI_KEY:
            log_structured(
                "Music Config: Deezer credentials (RAPIDAPI_KEY) missing. Defaulting to Mock music provider.",
                {"provider": provider},
                level=30
            )
            return MockMusicMetadataProvider()
        return DeezerMusicMetadataProvider(
            rapidapi_key=settings.RAPIDAPI_KEY,
            rapidapi_host=settings.RAPIDAPI_HOST
        )
    elif provider == "spotify":
        if not settings.MUSIC_API_CLIENT_ID or not settings.MUSIC_API_CLIENT_SECRET:
            log_structured(
                "Music Config: Spotify credentials missing. Defaulting to Mock music provider.",
                {"provider": provider},
                level=30
            )
            return MockMusicMetadataProvider()
        return SpotifyMusicMetadataProvider(
            client_id=settings.MUSIC_API_CLIENT_ID,
            client_secret=settings.MUSIC_API_CLIENT_SECRET
        )
    
    return MockMusicMetadataProvider()
