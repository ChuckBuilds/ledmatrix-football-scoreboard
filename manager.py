"""
Football Scoreboard Plugin for LEDMatrix

This plugin follows the exact structure of the football.py base class,
providing the same functionality as the original nfl_manager but using
the new plugin system and display_controller dynamic calls.
"""

import logging
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path

import pytz
import requests
from PIL import Image, ImageDraw, ImageFont

try:
    from src.plugin_system.base_plugin import BasePlugin
    from src.background_data_service import get_background_service
    from src.logo_downloader import LogoDownloader, download_missing_logo
except ImportError:
    BasePlugin = None
    get_background_service = None
    LogoDownloader = None
    download_missing_logo = None

logger = logging.getLogger(__name__)


class FootballScoreboardPlugin(BasePlugin if BasePlugin else object):
    """
    Football scoreboard plugin following the exact structure of football.py base class.

    This plugin provides the same functionality as the original nfl_manager but
    uses the new plugin system and display_controller dynamic calls.
    """

    def __init__(
        self,
        plugin_id: str,
        config: Dict[str, Any],
        display_manager,
        cache_manager,
        plugin_manager,
    ):
        """Initialize the football scoreboard plugin following football.py structure."""
        if BasePlugin:
            super().__init__(
                plugin_id, config, display_manager, cache_manager, plugin_manager
            )
        else:
            # Fallback initialization
            self.plugin_id = plugin_id
            self.config = config
            self.display_manager = display_manager
            self.cache_manager = cache_manager
            self.plugin_manager = plugin_manager
            self.logger = logging.getLogger(f"plugin.{plugin_id}")
        
        self.logger.setLevel(logging.INFO)

        # Plugin configuration - following football.py structure
        self.is_enabled = config.get("enabled", True)
        self.display_width = self.display_manager.matrix.width
        self.display_height = self.display_manager.matrix.height

        # League configuration - simplified structure like original
        self.leagues = {
            "nfl": {
                "enabled": config.get("nfl", {}).get("enabled", True),
                "favorite_teams": config.get("nfl", {}).get("favorite_teams", []),
                "display_modes": config.get("nfl", {}).get(
                    "display_modes",
                    {"show_live": True, "show_recent": True, "show_upcoming": True},
                ),
                "filtering": config.get("nfl", {}).get(
                    "filtering",
                    {"show_favorite_teams_only": False, "show_all_live": True},
                ),
                "recent_games_to_show": config.get("nfl", {}).get(
                    "recent_games_to_show", 5
                ),
                "upcoming_games_to_show": config.get("nfl", {}).get(
                    "upcoming_games_to_show", 10
                ),
                "logo_dir": "assets/sports/nfl_logos",
            },
            "ncaa_fb": {
                "enabled": config.get("ncaa_fb", {}).get("enabled", False),
                "favorite_teams": config.get("ncaa_fb", {}).get("favorite_teams", []),
                "display_modes": config.get("ncaa_fb", {}).get(
                    "display_modes",
                    {"show_live": True, "show_recent": True, "show_upcoming": True},
                ),
                "filtering": config.get("ncaa_fb", {}).get(
                    "filtering",
                    {"show_favorite_teams_only": False, "show_all_live": True},
                ),
                "recent_games_to_show": config.get("ncaa_fb", {}).get(
                    "recent_games_to_show", 5
                ),
                "upcoming_games_to_show": config.get("ncaa_fb", {}).get(
                    "upcoming_games_to_show", 10
                ),
                "logo_dir": "assets/sports/ncaa_logos",
            },
        }

        # Global settings
        self.display_duration = float(config.get("display_duration", 30))
        self.game_display_duration = float(config.get("game_display_duration", 15))

        # State - following football.py structure
        self.current_games = []
        self.current_game = None
        self.current_game_index = 0 
        self.last_game_switch = 0
        self.last_update = 0
        self.initialized = True
        
        # Mode cycling for NFL display modes (separate from future NCAA FB modes)
        self.current_display_mode = "nfl_live"
        self.nfl_display_modes = ["nfl_live", "nfl_recent", "nfl_upcoming"]
        self.mode_index = 0
        self.last_mode_switch = 0

        # Load fonts - following football.py structure
        self.fonts = self._load_fonts()
        
        # Background service and shared data - following NFL manager structure
        self.background_service = None
        self.background_fetch_requests = {}
        self.shared_data = None
        self.last_shared_update = 0

        if get_background_service:
            try:
                self.background_service = get_background_service(
                    cache_manager, max_workers=1
                )
                self.logger.info("Background service initialized")
            except Exception as e:
                self.logger.warning(f"Could not initialize background service: {e}")

        # Warning tracking - following NFL manager structure
        self._no_data_warning_logged = False
        self._last_warning_time = 0
        self._warning_cooldown = 60  # Only log warnings once per minute

        self.logger.info(
            f"Football scoreboard plugin initialized - {self.display_width}x{self.display_height}"
        )

    def _get_timezone(self):
        """Get timezone from the config file - following original nfl_manager pattern."""
        try:
            timezone_str = self.config.get("timezone", "UTC")
            return pytz.timezone(timezone_str)
        except Exception:
            self.logger.warning(
                f"Unknown timezone: {timezone_str}, falling back to UTC"
            )
            return pytz.utc

    def _load_fonts(self):
        """Load fonts used by the scoreboard - following football.py structure."""
        fonts = {}
        try:
            fonts["score"] = ImageFont.truetype(
                "assets/fonts/PressStart2P-Regular.ttf", 10
            )
            fonts["time"] = ImageFont.truetype(
                "assets/fonts/PressStart2P-Regular.ttf", 8
            )
            fonts["team"] = ImageFont.truetype(
                "assets/fonts/PressStart2P-Regular.ttf", 8
            )
            fonts["status"] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 6)
            fonts["detail"] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 6)
            fonts["rank"] = ImageFont.truetype(
                "assets/fonts/PressStart2P-Regular.ttf", 10
            )
            self.logger.info("Successfully loaded fonts")
        except IOError as e:
            self.logger.warning(f"Fonts not found, using default PIL font: {e}")
            fonts["score"] = ImageFont.load_default()
            fonts["time"] = ImageFont.load_default()
            fonts["team"] = ImageFont.load_default()
            fonts["status"] = ImageFont.load_default()
            fonts["detail"] = ImageFont.load_default()
            fonts["rank"] = ImageFont.load_default()
        return fonts

    def update(self) -> None:
        """Update football game data - following football.py structure."""
        if not self.initialized:
            return

        # Check if we should update based on interval
        if not self._should_update():
            self.logger.debug("Skipping update - not time yet")
            return
        
        try:
            self.logger.info("Starting football data update...")
            self.current_games = []

            # Check shared data first - following NFL manager structure
            if self._check_shared_data():
                self.logger.info("Using shared data for football games")
            else:
                # Fetch data for each enabled league
                for league_key, league_config in self.leagues.items():
                    if league_config.get("enabled", False):
                        self.logger.info(f"Fetching data for {league_key}...")
                        games = self._fetch_league_data(league_key, league_config)
                        if games:
                            self.current_games.extend(games)
                            self.logger.info(f"Added {len(games)} {league_key} games")
                        else:
                            self.logger.warning(f"No games found for {league_key}")

            # Sort games by priority
            self._sort_games()
            self.last_update = time.time()
            
            # Log filtering status
            nfl_config = self.leagues.get("nfl", {})
            filtering = nfl_config.get("filtering", {})
            show_favorite_teams_only = filtering.get("show_favorite_teams_only", False)
            favorite_teams = nfl_config.get("favorite_teams", [])

            if show_favorite_teams_only and favorite_teams:
                self.logger.info(
                    f"Football filtering enabled: showing only favorite teams {favorite_teams}"
                )
            else:
                self.logger.info("Football filtering disabled: showing all teams")

            # Log detailed game information
            nfl_games = [g for g in self.current_games if g.get("league") == "nfl"]
            if nfl_games:
                live_games = [g for g in nfl_games if g.get("is_live")]
                recent_games = [g for g in nfl_games if g.get("is_final")]
                upcoming_games = [g for g in nfl_games if g.get("is_upcoming")]

                self.logger.info(f"NFL Games Summary: {len(live_games)} live, {len(recent_games)} recent, {len(upcoming_games)} upcoming")

                # Log upcoming games details
                if upcoming_games:
                    for i, game in enumerate(upcoming_games):
                        is_favorite = self._is_favorite_game(game)
                        favorite_indicator = " [FAVORITE]" if is_favorite else ""
                        self.logger.info(
                            f"Upcoming game {i+1}: {game.get('away_abbr', '?')}@{game.get('home_abbr', '?')}"
                            f" - {game.get('game_time', 'No time')}{favorite_indicator}"
                        )
                else:
                    self.logger.warning("No upcoming NFL games found in data")
            else:
                self.logger.warning("No NFL games found in current_games")

            self.logger.info(
                f"Football data updated: {len(self.current_games)} total games"
            )

        except Exception as e:
            self.logger.error(f"Error updating football data: {e}")

    def _should_update(self) -> bool:
        """Check if we should update data based on interval."""
        if not hasattr(self, "last_update") or self.last_update == 0:
            return True

        current_time = time.time()
        update_interval = self.config.get(
            "update_interval_seconds", 300
        )  # Default 5 minutes

        return (current_time - self.last_update) >= update_interval

    def _fetch_league_data(self, league_key: str, league_config: Dict) -> List[Dict]:
        """Fetch game data for a specific league using NFL manager data logic."""
        # Use smart caching and background fetching like the original NFL manager
        if league_key == "nfl":
            data = self._fetch_nfl_api_data(use_cache=True)
        else:
            data = self._fetch_ncaa_fb_api_data(use_cache=True)

        if data:
            games = self._process_api_response(data, league_key, league_config)
            return games

        return []

    def _fetch_nfl_api_data(self, use_cache: bool = True) -> Optional[Dict]:
        """Fetches the full season schedule for NFL using background threading."""
        now = datetime.now(pytz.utc)
        season_year = now.year
        if now.month < 8:
            season_year = now.year - 1
        datestring = f"{season_year}0801-{season_year+1}0301"
        cache_key = f"nfl_schedule_{season_year}"

        # Check cache first
        if use_cache and hasattr(self.plugin_manager, "cache_manager"):
            cached_data = self.plugin_manager.cache_manager.get(cache_key)
            if cached_data:
                # Validate cached data structure
                if isinstance(cached_data, dict) and "events" in cached_data:
                    self.logger.info(f"Using cached NFL schedule for {season_year}")
                    return cached_data
                elif isinstance(cached_data, list):
                    # Handle old cache format (list of events)
                    self.logger.info(
                        f"Using cached NFL schedule for {season_year} (legacy format)"
                    )
                    return {"events": cached_data}
        else:
                    self.logger.warning(
                        f"Invalid cached data format for {season_year}: {type(cached_data)}"
                    )
                    # Clear invalid cache
                    self.plugin_manager.cache_manager.clear_cache(cache_key)

        # Start background fetch if background service is available
        if self.background_service:
            self._start_background_fetch("nfl", season_year, datestring, cache_key)

        # For immediate response, try to get today's games
        # But also try to get some upcoming games beyond the 7-day window
        return self._fetch_extended_games("nfl")

    def _fetch_ncaa_fb_api_data(self, use_cache: bool = True) -> Optional[Dict]:
        """Fetches the full season schedule for NCAA FB using background threading."""
        now = datetime.now(pytz.utc)
        season_year = now.year
        if now.month < 8:
            season_year = now.year - 1
        datestring = f"{season_year}0801-{season_year+1}0301"
        cache_key = f"ncaa_fb_schedule_{season_year}"

        # Check cache first
        if use_cache and hasattr(self.plugin_manager, "cache_manager"):
            cached_data = self.plugin_manager.cache_manager.get(cache_key)
            if cached_data:
                # Validate cached data structure
                if isinstance(cached_data, dict) and "events" in cached_data:
                    self.logger.info(f"Using cached NCAA FB schedule for {season_year}")
                    return cached_data
                elif isinstance(cached_data, list):
                    # Handle old cache format (list of events)
                    self.logger.info(
                        f"Using cached NCAA FB schedule for {season_year} (legacy format)"
                    )
                    return {"events": cached_data}
                else:
                    self.logger.warning(
                        f"Invalid cached data format for {season_year}: {type(cached_data)}"
                    )
                    # Clear invalid cache
                    self.plugin_manager.cache_manager.clear_cache(cache_key)

        # Start background fetch if background service is available
        if self.background_service:
            self._start_background_fetch("ncaa_fb", season_year, datestring, cache_key)

        # For immediate response, try to get today's games
        return self._fetch_todays_games("ncaa_fb")

    def _fetch_extended_games(self, league: str) -> Optional[Dict]:
        """Fetch games for an extended period to cover upcoming games beyond the next few days."""
        try:
            now = datetime.now()

            # Fetch games from the past 7 days to today + 14 days to cover more upcoming games
            all_events = []
            for days_offset in range(-7, 15):  # -7 days to +14 days
                target_date = now + timedelta(days=days_offset)
                formatted_date = target_date.strftime("%Y%m%d")

                if league == "nfl":
                    url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
                else:
                    url = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"

                headers = {"User-Agent": "LEDMatrix/1.0", "Accept": "application/json"}

                try:
                    response = requests.get(
                        url,
                        params={"dates": formatted_date, "limit": 1000},
                        headers=headers,
                        timeout=15,
                    )
                    response.raise_for_status()

                    data = response.json()
                    events = data.get("events", [])
                    all_events.extend(events)

                    self.logger.debug(
                        f"Fetched {len(events)} games for {league} on {formatted_date}"
                    )

                except Exception as e:
                    self.logger.debug(
                        f"Error fetching games for {league} on {formatted_date}: {e}"
                    )
                    continue

            self.logger.info(
                f"Fetched {len(all_events)} total games for {league} across extended date range"
            )
            return {"events": all_events}

        except Exception as e:
            self.logger.error(f"Error fetching extended games for {league}: {e}")
            return None

    def _fetch_todays_games(self, league: str) -> Optional[Dict]:
        """Fetch games for the past few days to cover live, recent, and upcoming games."""
        try:
            now = datetime.now()

            # Fetch games from the past 3 days to today + 3 days to cover recent, live, and upcoming
            all_events = []
            for days_offset in range(-3, 4):  # -3 days to +3 days
                target_date = now + timedelta(days=days_offset)
                formatted_date = target_date.strftime("%Y%m%d")

                if league == "nfl":
                    url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
                else:
                    url = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"

                headers = {"User-Agent": "LEDMatrix/1.0", "Accept": "application/json"}

                try:
                    response = requests.get(
                        url,
                        params={"dates": formatted_date, "limit": 1000},
                        headers=headers,
                        timeout=15,
                    )
                    response.raise_for_status()

                    data = response.json()
                    events = data.get("events", [])
                    all_events.extend(events)

                    self.logger.debug(
                        f"Fetched {len(events)} games for {league} on {formatted_date}"
                    )

                except Exception as e:
                    self.logger.debug(
                        f"Error fetching games for {league} on {formatted_date}: {e}"
                    )
                    continue

            self.logger.info(
                f"Fetched {len(all_events)} total games for {league} across date range"
            )
            return {"events": all_events}

        except Exception as e:
            self.logger.error(f"Error fetching games for {league}: {e}")
            return None

    def _start_background_fetch(
        self, league: str, season_year: int, datestring: str, cache_key: str
    ) -> None:
        """Start background fetch for season data - following NFL manager structure."""
        try:
            # Get background service configuration
            background_config = self.config.get("background_service", {})
            timeout = background_config.get("request_timeout", 30)
            max_retries = background_config.get("max_retries", 3)
            priority = background_config.get("priority", 2)

            # ESPN API URLs
            api_urls = {
                "nfl": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
                "ncaa_fb": "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard",
            }

            url = api_urls.get(league)
            if not url:
                return

            def fetch_callback(result):
                """Callback when background fetch completes."""
                if result.success:
                    self.logger.info(
                        f"Background fetch completed for {league} {season_year}: {len(result.data.get('events', []))} events"
                    )
                else:
                    self.logger.error(
                        f"Background fetch failed for {league} {season_year}: {result.error}"
                    )
                
                # Clean up request tracking
                if season_year in self.background_fetch_requests:
                    del self.background_fetch_requests[season_year]
            
            # Submit background fetch request
            request_id = self.background_service.submit_fetch_request(
                sport=league,
                year=season_year,
                url=url,
                cache_key=cache_key,
                params={"dates": datestring, "limit": 1000},
                headers={"User-Agent": "LEDMatrix/1.0", "Accept": "application/json"},
                timeout=timeout,
                max_retries=max_retries,
                priority=priority,
                callback=fetch_callback,
            )

            # Track the request
            self.background_fetch_requests[season_year] = request_id
            
        except Exception as e:
            self.logger.error(f"Error starting background fetch for {league}: {e}")

    def _get_weeks_data(self) -> Optional[Dict]:
        """Get partial data for immediate display - following NFL manager structure."""
        # This would implement the partial data logic from the original NFL manager
        # For now, return None to force API fetch
        return None

    def _check_shared_data(self) -> bool:
        """Check if shared data is available and recent - following NFL manager structure."""
        current_time = time.time()

        # Check if shared data exists and is recent (within 5 minutes)
        if self.shared_data and current_time - self.last_shared_update < 300:
            try:
                # Process shared data
                for league_key, league_config in self.leagues.items():
                    if league_config.get("enabled", False):
                        games = self._process_api_response(
                            self.shared_data, league_key, league_config
                        )
                        if games:
                            self.current_games.extend(games)
                return True
            except Exception as e:
                self.logger.error(f"Error processing shared data: {e}")
                return False

        return False

    def _process_api_response(
        self, data: Dict, league_key: str, league_config: Dict
    ) -> List[Dict]:
        """Process ESPN API response - following football.py structure."""
        games = []

        try:
            events = data.get("events", [])

            for event in events:
                game = self._extract_game_details(event, league_key, league_config)
                if game:
                    games.append(game)

        except Exception as e:
            self.logger.error(f"Error processing API response: {e}")

        return games

    def _extract_game_details(
        self, game_event: Dict, league_key: str, league_config: Dict
    ) -> Optional[Dict]:
        """Extract game details following football.py structure exactly."""
        try:
            competition = game_event["competitions"][0]
            status = competition["status"]
            competitors = competition["competitors"]
            game_date_str = game_event["date"]
            situation = competition.get("situation")
            start_time_utc = None

            try:
                start_time_utc = datetime.fromisoformat(
                    game_date_str.replace("Z", "+00:00")
                )
            except ValueError:
                self.logger.warning(f"Could not parse game date: {game_date_str}")

            home_team = next(
                (c for c in competitors if c.get("homeAway") == "home"), None
            )
            away_team = next(
                (c for c in competitors if c.get("homeAway") == "away"), None
            )

            if not home_team or not away_team:
                self.logger.warning(
                    f"Could not find home or away team in event: {game_event.get('id')}"
                )
                return None

            try:
                home_abbr = home_team["team"]["abbreviation"]
            except KeyError:
                home_abbr = home_team["team"]["name"][:3]
            try:
                away_abbr = away_team["team"]["abbreviation"]
            except KeyError:
                away_abbr = away_team["team"]["name"][:3]

            # Check if this is a favorite team game
            favorite_teams = league_config.get("favorite_teams", [])
            is_favorite_game = (
                home_abbr in favorite_teams or away_abbr in favorite_teams
            )

            # Only log debug info for favorite team games
            if is_favorite_game:
                self.logger.debug(
                    f"Processing favorite team game: {game_event.get('id')}"
                )
                self.logger.debug(
                    f"Found teams: {away_abbr}@{home_abbr}, Status: {status['type']['name']}, State: {status['type']['state']}"
                )

            game_time, game_date = "", ""
            if start_time_utc:
                local_time = start_time_utc.astimezone(self._get_timezone())
                game_time = local_time.strftime("%I:%M%p").lower().lstrip("0")
                game_date = local_time.strftime("%m/%d").lstrip("0").replace("/0", "/")

            home_record = (
                home_team.get("records", [{}])[0].get("summary", "")
                if home_team.get("records")
                else ""
            )
            away_record = (
                away_team.get("records", [{}])[0].get("summary", "")
                if away_team.get("records")
                else ""
            )

            # Don't show "0-0" records - set to blank instead
            if home_record in {"0-0", "0-0-0"}:
                home_record = ""
            if away_record in {"0-0", "0-0-0"}:
                away_record = ""

            # --- Football Specific Details (Following football.py exactly) ---
            down_distance_text = ""
            down_distance_text_long = ""
            possession_indicator = None
            scoring_event = ""
            home_timeouts = 0
            away_timeouts = 0
            is_redzone = False
            possession = None

            if situation and status["type"]["state"] == "in":
                down_distance_text = situation.get("shortDownDistanceText")
                down_distance_text_long = situation.get("downDistanceText")

                # Detect scoring events from status detail
                status_detail = status["type"].get("detail", "").lower()
                status_short = status["type"].get("shortDetail", "").lower()
                is_redzone = situation.get("isRedZone")
                possession = situation.get("possession")

                # Check for scoring events in status text
                if any(keyword in status_detail for keyword in ["touchdown", "td"]):
                    scoring_event = "TOUCHDOWN"
                elif any(keyword in status_detail for keyword in ["field goal", "fg"]):
                    scoring_event = "FIELD GOAL"
                elif any(
                    keyword in status_detail
                    for keyword in ["extra point", "pat", "point after"]
                ):
                    scoring_event = "PAT"
                elif any(keyword in status_short for keyword in ["touchdown", "td"]):
                    scoring_event = "TOUCHDOWN"
                elif any(keyword in status_short for keyword in ["field goal", "fg"]):
                    scoring_event = "FIELD GOAL"
                elif any(keyword in status_short for keyword in ["extra point", "pat"]):
                    scoring_event = "PAT"

                # Determine possession based on team ID
                possession_team_id = situation.get("possession")
                if possession_team_id:
                    if possession_team_id == home_team.get("id"):
                        possession_indicator = "home"
                    elif possession_team_id == away_team.get("id"):
                        possession_indicator = "away"
                
                home_timeouts = situation.get("homeTimeouts", 3)
                away_timeouts = situation.get("awayTimeouts", 3)

            # Format period/quarter
            period = status.get("period", 0)
            period_text = ""
            if status["type"]["state"] == "in":
                if period == 0:
                    period_text = "Start"
                elif period >= 1 and period <= 4:
                    period_text = f"Q{period}"
                elif period > 4:
                    period_text = f"OT{period - 4}"
            elif (
                status["type"]["state"] == "halftime"
                or status["type"]["name"] == "STATUS_HALFTIME"
            ):
                period_text = "HALF"
            elif status["type"]["state"] == "post":
                if period > 4:
                    period_text = "Final/OT"
                else:
                    period_text = "Final"
            elif status["type"]["state"] == "pre":
                period_text = game_time

            details = {
                "id": game_event.get("id"),
                "league": league_key,
                "league_config": league_config,
                "game_time": game_time,
                "game_date": game_date,
                "start_time_utc": start_time_utc,
                "status_text": status["type"]["shortDetail"],
                "is_live": status["type"]["state"] == "in",
                "is_final": status["type"]["state"] == "post",
                "is_upcoming": (
                    status["type"]["state"] == "pre"
                    or status["type"]["name"].lower()
                    in ["scheduled", "pre-game", "status_scheduled"]
                ),
                "is_halftime": status["type"]["state"] == "halftime"
                or status["type"]["name"] == "STATUS_HALFTIME",
                "is_period_break": status["type"]["name"] == "STATUS_END_PERIOD",
                "home_abbr": home_abbr,
                "home_id": home_team["id"],
                "home_score": home_team.get("score", "0"),
                "home_logo_path": Path(
                    league_config.get("logo_dir", "assets/sports/nfl_logos")
                )
                / f"{home_abbr}.png",
                "home_logo_url": home_team["team"].get("logo"),
                "home_record": home_record,
                "away_abbr": away_abbr,
                "away_id": away_team["id"],
                "away_score": away_team.get("score", "0"),
                "away_logo_path": Path(
                    league_config.get("logo_dir", "assets/sports/nfl_logos")
                )
                / f"{away_abbr}.png",
                "away_logo_url": away_team["team"].get("logo"),
                "away_record": away_record,
                "is_within_window": True,
                "period": period,
                "period_text": period_text,
                "clock": status.get("displayClock", "0:00"),
                "home_timeouts": home_timeouts,
                "away_timeouts": away_timeouts,
                "down_distance_text": down_distance_text,
                "down_distance_text_long": down_distance_text_long,
                "is_redzone": is_redzone,
                "possession": possession,
                "possession_indicator": possession_indicator,
                "scoring_event": scoring_event,
            }

            # Basic validation
            if not details["home_abbr"] or not details["away_abbr"]:
                self.logger.warning(
                    f"Missing team abbreviation in event: {details['id']}"
                )
                return None

            self.logger.debug(
                f"Extracted: {details['away_abbr']}@{details['home_abbr']}, Status: {status['type']['name']}, Live: {details['is_live']}, Final: {details['is_final']}, Upcoming: {details['is_upcoming']}"
            )

            return details

        except Exception as e:
            self.logger.error(
                f"Error extracting game details: {e} from event: {game_event.get('id')}",
                exc_info=True,
            )
            return None

    def _sort_games(self):
        """Sort games by priority - following football.py structure."""

        def sort_key(game):
            # Priority 1: Live games first
            is_live = game.get("is_live", False)
            live_score = 0 if is_live else 1

            # Priority 2: Favorite teams
            favorite_score = 0 if self._is_favorite_game(game) else 1

            # Priority 3: Game state
            if game.get("is_final", False):
                state_score = 0  # Recent games
            elif game.get("is_upcoming", False):
                state_score = 1  # Upcoming games
            else:
                state_score = 2

            return (live_score, favorite_score, state_score)

        self.current_games.sort(key=sort_key)

    def _is_favorite_game(self, game: Dict) -> bool:
        """Check if game involves a favorite team - following football.py structure."""
        league_config = game.get("league_config", {})
        favorites = league_config.get("favorite_teams", [])

        if not favorites:
            return False

        home_abbr = game.get("home_abbr", "").upper()
        away_abbr = game.get("away_abbr", "").upper()

        return home_abbr in favorites or away_abbr in favorites

    def _filter_games_by_mode(self, games: List[Dict], mode: str) -> List[Dict]:
        """Filter games based on NFL display mode (nfl_live, nfl_recent, nfl_upcoming)."""
        if not games:
            return []

        filtered_games = []

        for game in games:
            league = game.get("league", "nfl")
            league_config = game.get("league_config", {})
            display_modes = league_config.get("display_modes", {})

            # Only process NFL games for NFL modes
            if league != "nfl":
                continue

            # Check if this NFL mode is enabled
            mode_enabled = False
            if mode == "nfl_live":
                mode_enabled = display_modes.get("show_live", True)
                game_matches = game.get("is_live", False)
            elif mode == "nfl_recent":
                mode_enabled = display_modes.get("show_recent", True)
                game_matches = game.get("is_final", False)
            elif mode == "nfl_upcoming":
                mode_enabled = display_modes.get("show_upcoming", True)
                game_matches = game.get("is_upcoming", False)
            else:
                continue

            # Only include NFL games if the mode is enabled and the game matches the criteria
            if mode_enabled and game_matches:
                filtered_games.append(game)

        # Apply favorite teams filtering if enabled
        if filtered_games:
            league_config = self.leagues.get("nfl", {})
            filtering = league_config.get("filtering", {})
            show_favorite_teams_only = filtering.get("show_favorite_teams_only", False)

            if show_favorite_teams_only:
                favorite_teams = league_config.get("favorite_teams", [])
                if favorite_teams:
                    filtered_games = [
                        game for game in filtered_games if self._is_favorite_game(game)
                    ]

        # Sort filtered games by priority
        filtered_games.sort(
            key=lambda g: (
                0 if g.get("is_live", False) else 1,  # Live games first
                0 if self._is_favorite_game(g) else 1,  # Favorite teams first
                (
                    g.get("period", 0) if g.get("is_live", False) else 0
                ),  # Higher period for live games
            )
        )

        return filtered_games

    def display(self, force_clear: bool = False) -> None:
        """Display NFL games with mode cycling between nfl_live, nfl_recent, and nfl_upcoming."""
        if not self.is_enabled:
            return

        try:
            # Debug logging
            self.logger.debug(
                f"Display called - current_games: {len(self.current_games)}, mode: {self.current_display_mode}"
            )

            # Handle NFL mode cycling
            current_time = time.time()
            if current_time - self.last_mode_switch >= self.display_duration:
                self.mode_index = (self.mode_index + 1) % len(self.nfl_display_modes)
                self.current_display_mode = self.nfl_display_modes[self.mode_index]
                self.last_mode_switch = current_time
                self.current_game_index = 0  # Reset game index when switching modes
                force_clear = True
                self.logger.info(
                    f"Switching to NFL display mode: {self.current_display_mode}"
                )

            # Filter games based on current NFL mode
            filtered_games = self._filter_games_by_mode(
                self.current_games, self.current_display_mode
            )
            self.logger.debug(
                f"Filtered games for {self.current_display_mode}: {len(filtered_games)}"
            )

            # Log which games are being displayed
            if filtered_games:
                for i, game in enumerate(filtered_games):
                    is_favorite = self._is_favorite_game(game)
                    favorite_indicator = " [FAVORITE]" if is_favorite else ""
                    self.logger.info(
                        f"Displaying game {i+1}: {game.get('away_abbr', '?')}@{game.get('home_abbr', '?')}"
                        f" - {game.get('period_text', 'Unknown')}{favorite_indicator}"
                    )
            else:
                # Log what games were available before filtering
                all_nfl_games = [g for g in self.current_games if g.get("league") == "nfl"]
                if all_nfl_games:
                    self.logger.info(f"Total NFL games available: {len(all_nfl_games)}")
                    for i, game in enumerate(all_nfl_games):
                        is_upcoming = game.get("is_upcoming", False)
                        is_favorite = self._is_favorite_game(game)
                        favorite_indicator = " [FAVORITE]" if is_favorite else ""
                        status_indicator = " [UPCOMING]" if is_upcoming else ""
                        self.logger.info(
                            f"Available game {i+1}: {game.get('away_abbr', '?')}@{game.get('home_abbr', '?')}"
                            f" - {game.get('period_text', 'Unknown')}{favorite_indicator}{status_indicator}"
                        )
                else:
                    self.logger.info("No NFL games found in current_games")

            if not filtered_games:
                # Use warning cooldown logic from NFL manager
                if (
                    not self._no_data_warning_logged
                    or current_time - self._last_warning_time > self._warning_cooldown
                ):
                    self.logger.warning(
                        f"No {self.current_display_mode} NFL games available to display"
                    )
                    self._no_data_warning_logged = True
                    self._last_warning_time = current_time

                # Draw a placeholder when no games are available
                self._draw_no_games_placeholder()
                return

            # Handle game rotation within the current NFL mode
            if (
                len(filtered_games) > 1
                and current_time - self.last_game_switch >= self.game_display_duration
            ):
                self.current_game_index = (self.current_game_index + 1) % len(
                    filtered_games
                )
                self.last_game_switch = current_time
                force_clear = True

            # Display current NFL game
            game = filtered_games[self.current_game_index]
            self.logger.debug(
                f"Displaying game: {game.get('away_abbr', '?')}@{game.get('home_abbr', '?')}"
            )
            self._draw_scorebug_layout(game, force_clear)

        except Exception as e:
            self.logger.error(
                f"Error during display call in {self.__class__.__name__}: {e}",
                exc_info=True,
            )

    def _draw_no_games_placeholder(self) -> None:
        """Draw a placeholder when no games are available."""
        try:
            main_img = Image.new(
                "RGBA", (self.display_width, self.display_height), (0, 0, 0, 255)
            )
            overlay = Image.new(
                "RGBA", (self.display_width, self.display_height), (0, 0, 0, 0)
            )
            draw_overlay = ImageDraw.Draw(overlay)

            # Draw "No Games" message
            message = (
                f"No {self.current_display_mode.replace('nfl_', '').title()} Games"
            )
            message_width = draw_overlay.textlength(message, font=self.fonts["time"])
            message_x = (self.display_width - message_width) // 2
            message_y = (self.display_height // 2) - 5
            self._draw_text_with_outline(
                draw_overlay, message, (message_x, message_y), self.fonts["time"]
            )

            # Draw current mode
            mode_text = f"Mode: {self.current_display_mode}"
            mode_width = draw_overlay.textlength(mode_text, font=self.fonts["detail"])
            mode_x = (self.display_width - mode_width) // 2
            mode_y = (self.display_height // 2) + 10
            self._draw_text_with_outline(
                draw_overlay, mode_text, (mode_x, mode_y), self.fonts["detail"]
            )

            # Composite the text overlay onto the main image
            main_img = Image.alpha_composite(main_img, overlay)
            main_img = main_img.convert("RGB")

            # Display the final image
            self.display_manager.image.paste(main_img, (0, 0))
            self.display_manager.update_display()

        except Exception as e:
            self.logger.error(f"Error drawing no games placeholder: {e}", exc_info=True)

    def _draw_scorebug_layout(self, game: Dict, force_clear: bool = False) -> None:
        """Draw the detailed scorebug layout following football.py structure exactly."""
        try:
            main_img = Image.new(
                "RGBA", (self.display_width, self.display_height), (0, 0, 0, 255)
            )
            overlay = Image.new(
                "RGBA", (self.display_width, self.display_height), (0, 0, 0, 0)
            )
            draw_overlay = ImageDraw.Draw(overlay)

            home_logo = self._load_and_resize_logo(
                game["home_id"],
                game["home_abbr"],
                game["home_logo_path"],
                game.get("home_logo_url"),
            )
            away_logo = self._load_and_resize_logo(
                game["away_id"],
                game["away_abbr"],
                game["away_logo_path"],
                game.get("away_logo_url"),
            )

            if not home_logo or not away_logo:
                self.logger.error(f"Failed to load logos for game: {game.get('id')}")
                # Draw placeholder text if logos fail
                draw_final = ImageDraw.Draw(main_img.convert("RGB"))
                self._draw_text_with_outline(
                    draw_final, "Logo Error", (5, 5), self.fonts["status"]
                )
                self.display_manager.image.paste(main_img.convert("RGB"), (0, 0))
                self.display_manager.update_display()
                return

            center_y = self.display_height // 2

            # Draw logos
            home_x = self.display_width - home_logo.width + 10
            home_y = center_y - (home_logo.height // 2)
            main_img.paste(home_logo, (home_x, home_y), home_logo)
            
            away_x = -10
            away_y = center_y - (away_logo.height // 2)
            main_img.paste(away_logo, (away_x, away_y), away_logo)
            
            # Scores (centered, slightly above bottom) - Only show for live and recent games
            if game.get("is_live") or game.get("is_final"):
                home_score = str(game.get("home_score", "0"))
                away_score = str(game.get("away_score", "0"))
                score_text = f"{away_score}-{home_score}"
                score_width = draw_overlay.textlength(
                    score_text, font=self.fonts["score"]
                )
                score_x = (self.display_width - score_width) // 2
                score_y = (self.display_height // 2) - 3
                self._draw_text_with_outline(
                    draw_overlay, score_text, (score_x, score_y), self.fonts["score"]
                )

            # Period/Quarter and Clock (Top center) - Only show clock for live games
            if game.get("is_live"):
                period_clock_text = (
                    f"{game.get('period_text', '')} {game.get('clock', '')}".strip()
                )
                if game.get("is_halftime"):
                    period_clock_text = "Halftime"
                elif game.get("is_period_break"):
                    period_clock_text = game.get("status_text", "Period Break")

                status_width = draw_overlay.textlength(
                    period_clock_text, font=self.fonts["time"]
                )
                status_x = (self.display_width - status_width) // 2
                status_y = 1
                self._draw_text_with_outline(
                    draw_overlay,
                    period_clock_text,
                    (status_x, status_y),
                    self.fonts["time"],
                )

            elif game.get("is_upcoming"):
                # Format upcoming games like the original nfl_manager
                game_date = game.get("game_date", "")
                game_time = game.get("game_time", "")

                # "Next Game" at the top (use smaller status font for smaller displays)
                status_font = self.fonts["status"]
                if self.display_width > 128:
                    status_font = self.fonts["time"]
                status_text = "Next Game"
                status_width = draw_overlay.textlength(status_text, font=status_font)
                status_x = (self.display_width - status_width) // 2
                status_y = 1
                self._draw_text_with_outline(
                    draw_overlay, status_text, (status_x, status_y), status_font
                )
                
                # Date text (centered, below "Next Game")
                date_width = draw_overlay.textlength(game_date, font=self.fonts["time"])
                date_x = (self.display_width - date_width) // 2
                date_y = center_y - 7  # Position above vertical center
                self._draw_text_with_outline(
                    draw_overlay, game_date, (date_x, date_y), self.fonts["time"]
                )
                
                # Time text (centered, below Date)
                time_width = draw_overlay.textlength(game_time, font=self.fonts["time"])
                time_x = (self.display_width - time_width) // 2
                time_y = date_y + 9  # Position below date
                self._draw_text_with_outline(
                    draw_overlay, game_time, (time_x, time_y), self.fonts["time"]
                )

            else:
                # For final games, show "Final" status
                period_clock_text = game.get("period_text", "Final")
                status_width = draw_overlay.textlength(
                    period_clock_text, font=self.fonts["time"]
                )
                status_x = (self.display_width - status_width) // 2
                status_y = 1
                self._draw_text_with_outline(
                    draw_overlay,
                    period_clock_text,
                    (status_x, status_y),
                    self.fonts["time"],
                )

            # Down & Distance or Scoring Event (Below Period/Clock)
            scoring_event = game.get("scoring_event", "")
            down_distance = game.get("down_distance_text", "")
            if self.display_width > 128:
                down_distance = game.get("down_distance_text_long", "")

            # Show scoring event if detected, otherwise show down & distance
            if scoring_event and game.get("is_live"):
                # Display scoring event with special formatting
                event_width = draw_overlay.textlength(
                    scoring_event, font=self.fonts["detail"]
                )
                event_x = (self.display_width - event_width) // 2
                event_y = (self.display_height) - 7

                # Color coding for different scoring events
                if scoring_event == "TOUCHDOWN":
                    event_color = (255, 215, 0)  # Gold
                elif scoring_event == "FIELD GOAL":
                    event_color = (0, 255, 0)  # Green
                elif scoring_event == "PAT":
                    event_color = (255, 165, 0)  # Orange
                else:
                    event_color = (255, 255, 255)  # White

                self._draw_text_with_outline(
                    draw_overlay,
                    scoring_event,
                    (event_x, event_y),
                    self.fonts["detail"],
                    fill=event_color,
                )
            elif down_distance and game.get("is_live"):
                dd_width = draw_overlay.textlength(
                    down_distance, font=self.fonts["detail"]
                )
                dd_x = (self.display_width - dd_width) // 2
                dd_y = (self.display_height) - 7
                down_color = (
                    (200, 200, 0) if not game.get("is_redzone", False) else (255, 0, 0)
                )
                self._draw_text_with_outline(
                    draw_overlay,
                    down_distance,
                    (dd_x, dd_y),
                    self.fonts["detail"],
                    fill=down_color,
                )

                # Possession Indicator (small football icon)
                possession = game.get("possession_indicator")
                if possession:
                    ball_radius_x = 3
                    ball_radius_y = 2
                    ball_color = (139, 69, 19)
                    lace_color = (255, 255, 255)
            
                    detail_font_height_approx = 6
                    ball_y_center = dd_y + (detail_font_height_approx // 2)

                    possession_ball_padding = 3
            
                    if possession == "away":
                        ball_x_center = dd_x - possession_ball_padding - ball_radius_x
                    elif possession == "home":
                        ball_x_center = (
                            dd_x + dd_width + possession_ball_padding + ball_radius_x
                        )
                    else:
                        ball_x_center = 0
                    
                    if ball_x_center > 0:
                        # Draw the football shape (ellipse)
                        draw_overlay.ellipse(
                            (
                                ball_x_center - ball_radius_x,
                                ball_y_center - ball_radius_y,
                                ball_x_center + ball_radius_x,
                                ball_y_center + ball_radius_y,
                            ),
                            fill=ball_color,
                            outline=(0, 0, 0),
                        )
                        # Draw a simple horizontal lace
                        draw_overlay.line(
                            (
                                ball_x_center - 1,
                                ball_y_center,
                                ball_x_center + 1,
                                ball_y_center,
                            ),
                            fill=lace_color,
                            width=1,
                        )

            # Timeouts (Bottom corners) - Only show for live games
            if game.get("is_live"):
                timeout_bar_width = 4
                timeout_bar_height = 2
                timeout_spacing = 1
                timeout_y = self.display_height - timeout_bar_height - 1
            
                # Away Timeouts (Bottom Left)
                away_timeouts_remaining = game.get("away_timeouts", 0)
                for i in range(3):
                    to_x = 2 + i * (timeout_bar_width + timeout_spacing)
                    color = (
                        (255, 255, 255) if i < away_timeouts_remaining else (80, 80, 80)
                    )
                    draw_overlay.rectangle(
                        [
                            to_x,
                            timeout_y,
                            to_x + timeout_bar_width,
                            timeout_y + timeout_bar_height,
                        ],
                        fill=color,
                        outline=(0, 0, 0),
                    )

                # Home Timeouts (Bottom Right)
                home_timeouts_remaining = game.get("home_timeouts", 0)
                for i in range(3):
                    to_x = (
                        self.display_width
                        - 2
                        - timeout_bar_width
                        - (2 - i) * (timeout_bar_width + timeout_spacing)
                    )
                    color = (
                        (255, 255, 255) if i < home_timeouts_remaining else (80, 80, 80)
                    )
                    draw_overlay.rectangle(
                        [
                            to_x,
                            timeout_y,
                            to_x + timeout_bar_width,
                            timeout_y + timeout_bar_height,
                        ],
                        fill=color,
                        outline=(0, 0, 0),
                    )

            # Composite the text overlay onto the main image
            main_img = Image.alpha_composite(main_img, overlay)
            main_img = main_img.convert("RGB")

            # Display the final image
            self.display_manager.image.paste(main_img, (0, 0))
            self.display_manager.update_display()

        except Exception as e:
            self.logger.error(f"Error displaying Football game: {e}", exc_info=True)

    def _load_and_resize_logo(
        self, team_id: str, team_abbr: str, logo_path: Path, logo_url: str = None
    ) -> Optional[Image.Image]:
        """Load and resize team logo - following football.py structure."""
        try:
            # Try to load from local path first
            if logo_path and logo_path.exists():
                logo = Image.open(logo_path).convert("RGBA")
            elif logo_url and download_missing_logo:
                # Try to download missing logo
                try:
                    download_missing_logo(
                        "football", team_id, team_abbr, logo_path, logo_url
                    )
                    if logo_path.exists():
                        logo = Image.open(logo_path).convert("RGBA")
                    else:
                        return None
                except Exception as e:
                    self.logger.warning(f"Failed to download logo for {team_abbr}: {e}")
                    return None
            else:
                return None

            # Resize logo
            max_width = int(self.display_width * 1.5)
            max_height = int(self.display_height * 1.5)
            logo.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

            return logo

        except Exception as e:
            self.logger.debug(f"Could not load logo for {team_abbr}: {e}")
            return None

    def _draw_text_with_outline(
        self,
        draw: ImageDraw.Draw,
        text: str,
        position: tuple,
        font,
        fill=(255, 255, 255),
        outline_color=(0, 0, 0),
    ):
        """Draw text with outline - following football.py structure."""
        try:
            x, y = position
            # Draw outline
            for dx, dy in [
                (-1, -1),
                (-1, 0),
                (-1, 1),
                (0, -1),
                (0, 1),
                (1, -1),
                (1, 0),
                (1, 1),
            ]:
                draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
            # Draw main text
            draw.text((x, y), text, font=font, fill=fill)
        except Exception as e:
            self.logger.error(f"Error drawing text with outline: {e}")

    def get_display_duration(self) -> float:
        """Get display duration from config."""
        return self.display_duration

    def get_info(self) -> Dict[str, Any]:
        """Return plugin info."""
        if BasePlugin:
            info = super().get_info()
        else:
            info = {
                "plugin_id": self.plugin_id,
                "enabled": self.is_enabled,
                "version": "1.0.0",
            }

        info.update(
            {
                "total_games": len(self.current_games),
                "current_game_index": self.current_game_index,
                "last_update": self.last_update,
                "display_duration": self.display_duration,
                "current_display_mode": self.current_display_mode,
                "nfl_display_modes": self.nfl_display_modes,
            }
        )
        return info

    def cleanup(self) -> None:
        """Cleanup resources."""
        self.current_games = []
        self.current_game = None
        self.logger.info("Football scoreboard plugin cleaned up")
