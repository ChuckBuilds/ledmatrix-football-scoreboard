"""
Football Scoreboard Plugin for LEDMatrix

Displays live, recent, and upcoming football games across NFL and NCAA Football.
Shows real-time scores, game status, down/distance, possession, and team logos.

Features:
- Multiple league support (NFL, NCAA FB)
- Live game tracking with quarters and time
- Recent game results
- Upcoming game schedules
- Favorite team prioritization
- Down & distance tracking
- Possession indicator
- Background data fetching

API Version: 1.0.0
"""

import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pathlib import Path

import pytz
import requests
from PIL import Image, ImageDraw, ImageFont

try:
    # Try importing from LEDMatrix src directory
    from src.plugin_system.base_plugin import BasePlugin
except ImportError:
    try:
        # Try importing from plugin_system directly
        from plugin_system.base_plugin import BasePlugin
    except ImportError:
        BasePlugin = None

logger = logging.getLogger(__name__)


class FootballScoreboardPlugin(BasePlugin if BasePlugin else object):
    """
    Football scoreboard plugin for displaying games across multiple leagues.

    Supports NFL and NCAA Football with live, recent, and upcoming game modes.

    Configuration options:
        leagues: Enable/disable NFL, NCAA FB
        display_modes: Enable live, recent, upcoming modes
        favorite_teams: Team abbreviations per league
        show_records: Display team records
        show_ranking: Display team rankings
        background_service: Data fetching configuration
    """

    # ESPN API endpoints for each league
    ESPN_API_URLS = {
        'nfl': 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard',
        'ncaa_fb': 'https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard'
    }

    def __init__(self, plugin_id: str, config: Dict[str, Any],
                 display_manager, cache_manager, plugin_manager):
        """Initialize the football scoreboard plugin."""
        if BasePlugin:
            super().__init__(plugin_id, config, display_manager, cache_manager, plugin_manager)
        else:
            # Fallback initialization if BasePlugin is not available
            self.plugin_id = plugin_id
            self.config = config
            self.display_manager = display_manager
            self.cache_manager = cache_manager
            self.plugin_manager = plugin_manager
            self.logger = logging.getLogger(f"plugin.{plugin_id}")
        
        # Set logger to INFO level to avoid verbose DEBUG messages
        self.logger.setLevel(logging.INFO)

        # Plugin is self-contained and doesn't depend on base classes

        # Build league configurations from flattened config structure
        # Ensure proper type conversion for all numeric values
        # Helper function to normalize favorite teams arrays
        def normalize_favorite_teams(value):
            """Convert favorite teams to list, handling string/comma-separated values."""
            if isinstance(value, list):
                return [str(team).strip().upper() for team in value if team]
            elif isinstance(value, str) and value:
                # Handle comma-separated strings from web UI
                return [team.strip().upper() for team in value.split(',') if team.strip()]
            return []

        self.leagues = {
            'nfl': {
                'enabled': config.get('nfl_enabled', True),
                'favorite_teams': normalize_favorite_teams(config.get('nfl_favorite_teams', [])),
                'display_modes': {
                    'live': config.get('nfl_show_live', True),
                    'recent': config.get('nfl_show_recent', True),
                    'upcoming': config.get('nfl_show_upcoming', True)
                },
                'recent_games_to_show': int(config.get('nfl_recent_games_to_show', 5)),
                'upcoming_games_to_show': int(config.get('nfl_upcoming_games_to_show', 1)),
                'update_interval_seconds': int(config.get('update_interval_seconds', 3600)),
                'show_records': config.get('nfl_show_records', False),
                'show_ranking': config.get('nfl_show_ranking', False),
                'show_odds': config.get('nfl_show_odds', True),
                'show_favorite_teams_only': config.get('nfl_show_favorite_teams_only', True),
                'show_all_live': config.get('nfl_show_all_live', False),
                'logo_dir': 'assets/sports/nfl_logos'
            },
            'ncaa_fb': {
                'enabled': config.get('ncaa_fb_enabled', False),
                'favorite_teams': normalize_favorite_teams(config.get('ncaa_fb_favorite_teams', [])),
                'display_modes': {
                    'live': config.get('ncaa_fb_show_live', True),
                    'recent': config.get('ncaa_fb_show_recent', True),
                    'upcoming': config.get('ncaa_fb_show_upcoming', True)
                },
                'recent_games_to_show': int(config.get('ncaa_fb_recent_games_to_show', 1)),
                'upcoming_games_to_show': int(config.get('ncaa_fb_upcoming_games_to_show', 1)),
                'update_interval_seconds': int(config.get('update_interval_seconds', 3600)),
                'show_records': config.get('ncaa_fb_show_records', False),
                'show_ranking': config.get('ncaa_fb_show_ranking', True),
                'show_odds': config.get('ncaa_fb_show_odds', True),
                'show_favorite_teams_only': config.get('ncaa_fb_show_favorite_teams_only', True),
                'show_all_live': config.get('ncaa_fb_show_all_live', False),
                'logo_dir': 'assets/sports/ncaa_logos'
            }
        }

        # Global settings - ensure proper type conversion
        self.global_config = config
        self.display_duration = float(config.get('display_duration', 15))

        # Background service configuration (internal only)
        self.background_config = {
            'enabled': True,
            'request_timeout': 30,
            'max_retries': 3,
            'priority': 2
        }

        # State
        self.current_games = []
        self.current_league = None
        self.current_display_mode = None
        self.last_update = 0
        self.initialized = True

        # Load fonts for rendering
        self.fonts = self._load_fonts()
        
        # Team rankings cache (for NCAA primarily)
        self._team_rankings_cache = {}

        # Log throttling to reduce noise
        self._last_cache_log_time = 0
        self._last_update_log_time = 0
        self._last_game_count = 0
        self._log_throttle_seconds = 300  # Only log these messages every 5 minutes

        # Register fonts with font manager (if available)
        self._register_fonts()

        # Log RAW config values for debugging
        self.logger.info("=== Raw Config Values ===")
        self.logger.info(f"  nfl_enabled: {config.get('nfl_enabled')} (type: {type(config.get('nfl_enabled')).__name__})")
        self.logger.info(f"  nfl_favorite_teams: {config.get('nfl_favorite_teams')} (type: {type(config.get('nfl_favorite_teams')).__name__})")
        self.logger.info(f"  ncaa_fb_enabled: {config.get('ncaa_fb_enabled')} (type: {type(config.get('ncaa_fb_enabled')).__name__})")
        self.logger.info(f"  ncaa_fb_favorite_teams: {config.get('ncaa_fb_favorite_teams')} (type: {type(config.get('ncaa_fb_favorite_teams')).__name__})")
        
        # Log enabled leagues and their settings
        self.logger.info("=== Normalized League Config ===")
        enabled_leagues = []
        for league_key, league_config in self.leagues.items():
            if league_config.get('enabled', False):
                enabled_leagues.append(league_key)
                # Log favorite teams for enabled leagues
                favorites = league_config.get('favorite_teams', [])
                self.logger.info(f"  {league_key.upper()} enabled with {len(favorites)} favorite team(s): {favorites}")
            else:
                self.logger.info(f"  {league_key.upper()} disabled")

        self.logger.info("Football scoreboard plugin initialized")
        self.logger.info(f"Enabled leagues: {enabled_leagues}")

    def _register_fonts(self):
        """Register fonts with the font manager."""
        try:
            if not hasattr(self.plugin_manager, 'font_manager'):
                return

            font_manager = self.plugin_manager.font_manager

            # Team name font
            font_manager.register_manager_font(
                manager_id=self.plugin_id,
                element_key=f"{self.plugin_id}.team_name",
                family="press_start",
                size_px=10,
                color=(255, 255, 255)
            )

            # Score font
            font_manager.register_manager_font(
                manager_id=self.plugin_id,
                element_key=f"{self.plugin_id}.score",
                family="press_start",
                size_px=12,
                color=(255, 200, 0)
            )

            # Status font (quarter, time)
            font_manager.register_manager_font(
                manager_id=self.plugin_id,
                element_key=f"{self.plugin_id}.status",
                family="four_by_six",
                size_px=6,
                color=(0, 255, 0)
            )

            # Detail font (down/distance, possession)
            font_manager.register_manager_font(
                manager_id=self.plugin_id,
                element_key=f"{self.plugin_id}.detail",
                family="four_by_six",
                size_px=6,
                color=(200, 200, 0)
            )

            self.logger.info("Football scoreboard fonts registered")
        except Exception as e:
            self.logger.warning(f"Error registering fonts: {e}")

    def _load_fonts(self):
        """Load fonts used by the scoreboard - matching original managers."""
        fonts = {}
        try:
            fonts['score'] = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 10)
            fonts['time'] = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 8)
            fonts['team'] = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 8)
            fonts['status'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 6)
            fonts['detail'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 6)
            fonts['rank'] = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 10)
            self.logger.info("Successfully loaded fonts")
        except IOError as e:
            self.logger.warning(f"Fonts not found, using default PIL font: {e}")
            fonts['score'] = ImageFont.load_default()
            fonts['time'] = ImageFont.load_default()
            fonts['team'] = ImageFont.load_default()
            fonts['status'] = ImageFont.load_default()
            fonts['detail'] = ImageFont.load_default()
            fonts['rank'] = ImageFont.load_default()
        return fonts

    def update(self) -> None:
        """Update football game data for all enabled leagues."""
        if not self.initialized:
            return

        try:
            self.current_games = []

            # Fetch data for each enabled league
            for league_key, league_config in self.leagues.items():
                if league_config.get('enabled', False):
                    games = self._fetch_league_data(league_key, league_config)
                    if games:
                        # Add league info to each game
                        for game in games:
                            game['league_config'] = league_config
                        self.current_games.extend(games)

            # Sort games - prioritize live games and favorites
            self._sort_games()

            self.last_update = time.time()
            
            # Only log occasionally or when game count changes to reduce noise
            current_time = time.time()
            game_count = len(self.current_games)
            if game_count != self._last_game_count or current_time - self._last_update_log_time > self._log_throttle_seconds:
                # Log detailed breakdown by league and state
                nfl_games = [g for g in self.current_games if g.get('league') == 'nfl']
                ncaa_games = [g for g in self.current_games if g.get('league') == 'ncaa_fb']
                live_games = [g for g in self.current_games if g.get('status', {}).get('state') == 'in']
                recent_games = [g for g in self.current_games if g.get('status', {}).get('state') == 'post']
                upcoming_games = [g for g in self.current_games if g.get('status', {}).get('state') == 'pre']
                
                self.logger.info(f"Football data updated: {game_count} total games")
                self.logger.info(f"  NFL: {len(nfl_games)}, NCAA FB: {len(ncaa_games)}")
                self.logger.info(f"  Live: {len(live_games)}, Recent: {len(recent_games)}, Upcoming: {len(upcoming_games)}")
                self._last_update_log_time = current_time
                self._last_game_count = game_count

        except Exception as e:
            self.logger.error(f"Error updating football data: {e}")

    def _sort_games(self):
        """Sort games by priority and favorites."""
        def sort_key(game):
            league_key = game.get('league')
            league_config = game.get('league_config', {})
            status = game.get('status', {})

            # Priority 1: Live games
            is_live = status.get('state') == 'in'
            live_score = 0 if is_live else 1

            # Priority 2: Favorite teams
            favorite_score = 0 if self._is_favorite_game(game) else 1

            # Priority 3: Start time (earlier games first for upcoming, later for recent)
            start_time = game.get('start_time', '')

            return (live_score, favorite_score, start_time)

        self.current_games.sort(key=sort_key)

    def _fetch_league_data(self, league_key: str, league_config: Dict) -> List[Dict]:
        """Fetch game data for a specific league with date range for recent games."""
        cache_key = f"football_{league_key}_{datetime.now().strftime('%Y%m%d')}"
        update_interval = int(league_config.get('update_interval_seconds', 60))

        # Check cache first (use league-specific interval)
        cached_data = self.cache_manager.get(cache_key)
        if cached_data and (time.time() - self.last_update) < update_interval:
            # Only log occasionally to reduce noise
            current_time = time.time()
            if current_time - self._last_cache_log_time > self._log_throttle_seconds:
                self.logger.debug(f"Using cached data for enabled leagues")
                self._last_cache_log_time = current_time
            return cached_data

        # Fetch from API
        try:
            base_url = self.ESPN_API_URLS.get(league_key)
            if not base_url:
                self.logger.error(f"Unknown league key: {league_key}")
                return []

            # Add date range to fetch recent games (last 21 days) and upcoming games
            # This matches the old base class implementation
            from datetime import timedelta
            now = datetime.now()
            start_date = (now - timedelta(days=21)).strftime('%Y%m%d')
            end_date = (now + timedelta(days=14)).strftime('%Y%m%d')
            
            # ESPN API format: dates=YYYYMMDD-YYYYMMDD
            url = f"{base_url}?dates={start_date}-{end_date}"

            self.logger.info(f"Fetching {league_key} data from ESPN API (last 21 days + next 14 days)...")
            response = requests.get(url, timeout=self.background_config.get('request_timeout', 30))
            response.raise_for_status()

            data = response.json()
            games = self._process_api_response(data, league_key, league_config)

            # Cache the games data (TTL is managed by is_cache_valid check)
            self.cache_manager.set(cache_key, games)

            return games

        except requests.RequestException as e:
            self.logger.error(f"Error fetching {league_key} data: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Error processing {league_key} data: {e}")
            return []

    def _process_api_response(self, data: Dict, league_key: str, league_config: Dict) -> List[Dict]:
        """Process ESPN API response into standardized game format."""
        games = []

        try:
            events = data.get('events', [])

            for event in events:
                try:
                    game = self._extract_game_info(event, league_key, league_config)
                    if game:
                        games.append(game)
                except Exception as e:
                    self.logger.error(f"Error extracting game info: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error processing API response: {e}")

        return games

    def _extract_game_info(self, event: Dict, league_key: str, league_config: Dict) -> Optional[Dict]:
        """Extract game information from ESPN event with football-specific details."""
        try:
            competition = event.get('competitions', [{}])[0]
            status = competition.get('status', {})
            competitors = competition.get('competitors', [])

            if len(competitors) < 2:
                return None

            # Find home and away teams
            home_team = next((c for c in competitors if c.get('homeAway') == 'home'), None)
            away_team = next((c for c in competitors if c.get('homeAway') == 'away'), None)

            if not home_team or not away_team:
                return None

            # Extract basic game details
            home_team_id = home_team.get('team', {}).get('id')
            away_team_id = away_team.get('team', {}).get('id')
            
            game = {
                'league': league_key,
                'league_config': league_config,
                'game_id': event.get('id'),
                'home_id': home_team_id,
                'away_id': away_team_id,
                'home_team': {
                    'name': home_team.get('team', {}).get('displayName', 'Unknown'),
                    'abbrev': home_team.get('team', {}).get('abbreviation', 'UNK'),
                    'score': int(home_team.get('score', 0)),
                    'logo': home_team.get('team', {}).get('logo')
                },
                'away_team': {
                    'name': away_team.get('team', {}).get('displayName', 'Unknown'),
                    'abbrev': away_team.get('team', {}).get('abbreviation', 'UNK'),
                    'score': int(away_team.get('score', 0)),
                    'logo': away_team.get('team', {}).get('logo')
                },
                'home_record': home_team.get('records', [{}])[0].get('summary', '') if home_team.get('records') else '',
                'away_record': away_team.get('records', [{}])[0].get('summary', '') if away_team.get('records') else '',
                'status': {
                    'state': status.get('type', {}).get('state', 'unknown'),
                    'detail': status.get('type', {}).get('detail', ''),
                    'short_detail': status.get('type', {}).get('shortDetail', ''),
                    'period': status.get('period', 0),
                    'display_clock': status.get('displayClock', '')
                },
                'start_time': event.get('date', ''),
                'venue': competition.get('venue', {}).get('fullName', 'Unknown Venue'),
                'is_halftime': status.get('type', {}).get('name') == 'STATUS_HALFTIME'
            }

            # Add football-specific details
            situation = competition.get('situation', {})
            possession_indicator = None
            
            if situation:
                game['down_distance'] = situation.get('shortDownDistanceText', '')
                game['possession'] = situation.get('possession')
                game['is_redzone'] = situation.get('isRedZone', False)
                
                # Map possession to home/away indicator (matching original)
                possession_team_id = situation.get('possession')
                if possession_team_id:
                    if possession_team_id == home_team_id:
                        possession_indicator = "home"
                    elif possession_team_id == away_team_id:
                        possession_indicator = "away"
                
                # Add more detailed football info
                game['down'] = situation.get('down')
                game['distance'] = situation.get('distance')
                game['yard_line'] = situation.get('yardLine')
                game['possession_text'] = situation.get('possessionText', '')
                
                # Timeouts (default to 3 if not specified, matching original)
                game['home_timeouts'] = situation.get('homeTimeouts', 3)
                game['away_timeouts'] = situation.get('awayTimeouts', 3)
            else:
                game['down_distance'] = ''
                game['possession'] = None
                game['is_redzone'] = False
                game['home_timeouts'] = 0
                game['away_timeouts'] = 0
            
            # Add possession indicator
            game['possession_indicator'] = possession_indicator
            
            # Add scoring events detection
            game['scoring_event'] = self._detect_scoring_event(status)
            
            # Add game phase info
            game['game_phase'] = self._determine_game_phase(status, league_key)
            
            return game

        except Exception as e:
            self.logger.error(f"Error extracting game info: {e}")
            return None

    def _detect_scoring_event(self, status: Dict) -> str:
        """Detect if there's a scoring event happening."""
        try:
            status_detail = status.get('type', {}).get('detail', '').lower()
            status_short = status.get('type', {}).get('shortDetail', '').lower()
            
            scoring_keywords = ['touchdown', 'field goal', 'safety', 'extra point', 'two-point', 'conversion']
            
            for keyword in scoring_keywords:
                if keyword in status_detail or keyword in status_short:
                    return keyword
            
            return ""
        except:
            return ""

    def _determine_game_phase(self, status: Dict, league: str) -> str:
        """Determine the current phase of the game."""
        try:
            state = status.get('type', {}).get('state', '')
            period = status.get('period', 0)
            
            if state == 'pre':
                return 'pregame'
            elif state == 'in':
                if league == 'nfl':
                    if period <= 4:
                        return f'Q{period}'
                    else:
                        return 'OT'
                else:  # ncaa_fb
                    if period <= 4:
                        return f'Q{period}'
                    else:
                        return 'OT'
            elif state == 'post':
                return 'final'
            else:
                return 'unknown'
        except:
            return 'unknown'

    def _is_favorite_game(self, game: Dict) -> bool:
        """Check if game involves a favorite team - case insensitive."""
        league = game.get('league')
        league_config = game.get('league_config', {})
        favorites = league_config.get('favorite_teams', [])

        if not favorites:
            return False

        home_abbrev = game.get('home_team', {}).get('abbrev', '').upper()
        away_abbrev = game.get('away_team', {}).get('abbrev', '').upper()
        
        # Debug: Log the actual game structure for the first few checks
        if not hasattr(self, '_favorite_check_count'):
            self._favorite_check_count = 0
        
        if self._favorite_check_count < 3:
            self.logger.info(f"=== Favorite Check Debug #{self._favorite_check_count + 1} ===")
            self.logger.info(f"  Game dict keys: {list(game.keys())}")
            self.logger.info(f"  home_team keys: {list(game.get('home_team', {}).keys())}")
            self.logger.info(f"  away_team keys: {list(game.get('away_team', {}).keys())}")
            self.logger.info(f"  home_abbrev from game: '{home_abbrev}'")
            self.logger.info(f"  away_abbrev from game: '{away_abbrev}'")
            self.logger.info(f"  favorites list: {favorites}")
            self.logger.info(f"  home_abbrev in favorites: {home_abbrev in favorites}")
            self.logger.info(f"  away_abbrev in favorites: {away_abbrev in favorites}")
            self._favorite_check_count += 1

        # Favorites are already normalized to uppercase in config
        return home_abbrev in favorites or away_abbrev in favorites

    def display(self, display_mode: str = None, force_clear: bool = False) -> None:
        """
        Display football games.

        Args:
            display_mode: Which mode to display (football_live, football_recent, football_upcoming)
            force_clear: If True, clear display before rendering
        """
        if not self.initialized:
            self._display_error("Football plugin not initialized")
            return

        # Determine which display mode to use - prioritize live games if enabled
        if not display_mode:
            # Auto-select mode based on available games and priorities
            if self._has_live_games():
                display_mode = 'football_live'
            else:
                # Fall back to recent or upcoming
                display_mode = 'football_recent' if self._has_recent_games() else 'football_upcoming'

        self.current_display_mode = display_mode

        # Filter games by display mode
        filtered_games = self._filter_games_by_mode(display_mode)

        if not filtered_games:
            self.logger.debug(f"No games available for {display_mode} after filtering {len(self.current_games)} total games")
            self._display_no_games(display_mode)
            return

        self.logger.debug(f"Displaying {len(filtered_games)} {display_mode} game(s)")

        # Display the first game (rotation handled by LEDMatrix)
        game = filtered_games[0]
        self._display_game(game, display_mode)

    def _filter_games_by_mode(self, mode: str) -> List[Dict]:
        """Filter games based on display mode and per-league settings - matching original managers."""
        filtered = []
        
        # Debug: log filtering info once per call
        self.logger.debug(f"Filtering for mode: {mode}, Total games available: {len(self.current_games)}")

        for game in self.current_games:
            league_key = game.get('league')
            league_config = game.get('league_config', {})
            status = game.get('status', {})
            state = status.get('state')

            # Check if this mode is enabled for this league
            display_modes = league_config.get('display_modes', {})
            mode_enabled = display_modes.get(mode.replace('football_', ''), False)
            if not mode_enabled:
                continue

            # Check favorite team filtering (matching original managers)
            show_favorite_teams_only = league_config.get('show_favorite_teams_only', True)
            show_all_live = league_config.get('show_all_live', False)
            favorite_teams = league_config.get('favorite_teams', [])
            
            is_favorite_game = self._is_favorite_game(game)
            
            # Debug logging for first few games
            if len(filtered) < 3:
                home_abbr = game.get('home_team', {}).get('abbrev', '')
                away_abbr = game.get('away_team', {}).get('abbrev', '')
                home_abbr_upper = home_abbr.upper() if home_abbr else ''
                away_abbr_upper = away_abbr.upper() if away_abbr else ''
                self.logger.debug(f"  Game: {away_abbr}@{home_abbr} ({league_key}, state={state})")
                self.logger.debug(f"    ESPN API returned: away='{away_abbr}' (upper='{away_abbr_upper}'), home='{home_abbr}' (upper='{home_abbr_upper}')")
                self.logger.debug(f"    Favorites list: {favorite_teams}")
                self.logger.debug(f"    Checking: '{away_abbr_upper}' in {favorite_teams} = {away_abbr_upper in favorite_teams}")
                self.logger.debug(f"    Checking: '{home_abbr_upper}' in {favorite_teams} = {home_abbr_upper in favorite_teams}")
                self.logger.debug(f"    Is favorite game: {is_favorite_game}")
                self.logger.debug(f"    show_favorite_teams_only: {show_favorite_teams_only}, show_all_live: {show_all_live}")
            
            # Filter by game state and per-league settings
            if mode == 'football_live' and state == 'in':
                # For live games: check show_all_live OR favorite team filter
                if show_all_live or not show_favorite_teams_only or is_favorite_game:
                    filtered.append(game)

            elif mode == 'football_recent' and state == 'post':
                # For recent games: check favorite team filter
                if not show_favorite_teams_only or is_favorite_game:
                    # Check recent games limit for this league
                    recent_limit = league_config.get('recent_games_to_show', 5)
                    recent_count = len([g for g in filtered if g.get('league') == league_key and g.get('status', {}).get('state') == 'post'])
                    if recent_count >= recent_limit:
                        continue
                    filtered.append(game)

            elif mode == 'football_upcoming' and state == 'pre':
                # For upcoming games: check favorite team filter
                if not show_favorite_teams_only or is_favorite_game:
                    # Check upcoming games limit for this league
                    upcoming_limit = league_config.get('upcoming_games_to_show', 10)
                    upcoming_count = len([g for g in filtered if g.get('league') == league_key and g.get('status', {}).get('state') == 'pre'])
                    if upcoming_count >= upcoming_limit:
                        continue
                    filtered.append(game)

        self.logger.debug(f"Filtered result: {len(filtered)} games for {mode}")
        return filtered

    def _has_live_games(self) -> bool:
        """Check if there are any live games available."""
        return any(game.get('status', {}).get('state') == 'in' for game in self.current_games)

    def _has_recent_games(self) -> bool:
        """Check if there are any recent games available."""
        return any(game.get('status', {}).get('state') == 'post' for game in self.current_games)

    def has_live_content(self) -> bool:
        """
        Override BasePlugin method to indicate when plugin has live content.
        This is used by display controller for live priority system.
        """
        return self._has_live_games()
    
    def get_live_modes(self) -> list:
        """
        Override BasePlugin method to specify which modes to show during live priority.
        Only show the live mode, not recent/upcoming.
        """
        return ['football_live']

    def _display_game(self, game: Dict, mode: str):
        """Display a single game with professional scorebug layout matching old managers."""
        try:
            matrix_width = self.display_manager.matrix.width
            matrix_height = self.display_manager.matrix.height

            # Create image with transparency support
            main_img = Image.new('RGBA', (matrix_width, matrix_height), (0, 0, 0, 255))
            overlay = Image.new('RGBA', (matrix_width, matrix_height), (0, 0, 0, 0))
            draw_overlay = ImageDraw.Draw(overlay)

            # Get team info
            home_team = game.get('home_team', {})
            away_team = game.get('away_team', {})
            status = game.get('status', {})
            
            # Get football-specific info
            down_distance = game.get('down_distance', '')
            possession = game.get('possession', '')
            game_phase = game.get('game_phase', '')
            scoring_event = self._detect_scoring_event(status)
            is_redzone = game.get('is_redzone', False)

            # Team info
            home_abbrev = home_team.get('abbrev', 'HOME')
            away_abbrev = away_team.get('abbrev', 'AWAY')
            home_score = home_team.get('score', 0)
            away_score = away_team.get('score', 0)

            # Load team logos
            home_logo = self._load_team_logo(home_team, game.get('league', ''))
            away_logo = self._load_team_logo(away_team, game.get('league', ''))

            # If logos failed to load, show text fallback
            if not home_logo or not away_logo:
                self.logger.warning("Failed to load team logos, using text fallback")
                self._draw_text_fallback(draw_overlay, home_team, away_team, status, game, matrix_width, matrix_height)
            else:
                # Use different layouts based on game state
                if status.get('state') == 'pre':
                    # Upcoming games: Use special upcoming layout
                    self._draw_upcoming_layout(draw_overlay, main_img, home_logo, away_logo, 
                                            home_team, away_team, status, game, 
                                            matrix_width, matrix_height)
                else:
                    # Live/Recent games: Use professional scorebug layout
                    self._draw_scorebug_layout(draw_overlay, main_img, home_logo, away_logo, 
                                             home_team, away_team, status, game, 
                                             matrix_width, matrix_height)

            # Composite the overlay onto main image
            final_img = Image.alpha_composite(main_img, overlay)
            
            self.display_manager.image = final_img.convert('RGB').copy()
            self.display_manager.update_display()

        except Exception as e:
            self.logger.error(f"Error displaying game: {e}")
            self._display_error("Display error")

    def _load_team_logo(self, team: Dict, league: str) -> Optional[Image.Image]:
        """Load and resize team logo."""
        try:
            # Get logo directory from league configuration
            league_config = self.leagues.get(league, {})
            logo_dir = league_config.get('logo_dir', 'assets/sports/nfl_logos')
            
            # Convert relative path to absolute path by finding LEDMatrix project root
            if not os.path.isabs(logo_dir):
                # Try to find LEDMatrix project root
                current_dir = os.path.dirname(os.path.abspath(__file__))
                # Go up from plugin directory to find LEDMatrix root
                ledmatrix_root = None
                for parent in [current_dir, os.path.dirname(current_dir), os.path.dirname(os.path.dirname(current_dir))]:
                    if os.path.exists(os.path.join(parent, 'assets', 'sports')):
                        ledmatrix_root = parent
                        break
                
                if ledmatrix_root:
                    logo_dir = os.path.join(ledmatrix_root, logo_dir)
                else:
                    # Fallback: try relative to current working directory
                    logo_dir = os.path.abspath(logo_dir)
            
            team_abbrev = team.get('abbrev', '')
            if not team_abbrev:
                return None
            
            # Try different logo file extensions and case variations
            logo_extensions = ['.png', '.jpg', '.jpeg']
            logo_path = None
            
            # Try uppercase first (most common), then lowercase, then original case
            abbrev_variations = [team_abbrev.upper(), team_abbrev.lower(), team_abbrev]
            
            for abbrev in abbrev_variations:
                for ext in logo_extensions:
                    potential_path = os.path.join(logo_dir, f"{abbrev}{ext}")
                    if os.path.exists(potential_path):
                        logo_path = potential_path
                        break
                if logo_path:
                    break
            
            if not logo_path:
                # Try with team name instead of abbreviation
                team_name = team.get('name', '').lower().replace(' ', '_')
                for ext in logo_extensions:
                    potential_path = os.path.join(logo_dir, f"{team_name}{ext}")
                    if os.path.exists(potential_path):
                        logo_path = potential_path
                        break
            
            if not logo_path:
                # Logo not found - fail silently and use text fallback
                return None
            
            # Load and resize logo (matching original managers)
            logo = Image.open(logo_path).convert('RGBA')
            # Use same sizing as original managers: display dimensions * 1.5
            max_width = int(self.display_manager.matrix.width * 1.5)
            max_height = int(self.display_manager.matrix.height * 1.5)
            logo.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            return logo
            
        except Exception as e:
            self.logger.debug(f"Could not load logo for {team.get('abbrev', 'unknown')}: {e}")
            return None

    def _draw_scorebug_layout(self, draw_overlay: ImageDraw.Draw, main_img: Image.Image,
                            home_logo: Image.Image, away_logo: Image.Image,
                            home_team: Dict, away_team: Dict, status: Dict, game: Dict,
                            matrix_width: int, matrix_height: int):
        """Draw professional scorebug layout matching old managers exactly."""
        try:
            center_y = matrix_height // 2
            
            # Draw team logos (matching original positioning)
            home_x = matrix_width - home_logo.width + 10
            home_y = center_y - (home_logo.height // 2)
            main_img.paste(home_logo, (home_x, home_y), home_logo)
            
            away_x = -10
            away_y = center_y - (away_logo.height // 2)
            main_img.paste(away_logo, (away_x, away_y), away_logo)
            
            # Draw scores (centered) - use proper font
            home_score = str(home_team.get('score', 0))
            away_score = str(away_team.get('score', 0))
            score_text = f"{away_score}-{home_score}"
            
            score_width = draw_overlay.textlength(score_text, font=self.fonts['score'])
            score_x = (matrix_width - score_width) // 2
            score_y = (matrix_height // 2) - 3
            self._draw_text_with_outline(draw_overlay, score_text, (score_x, score_y), self.fonts['score'], fill=(255, 200, 0))
            
            # Period/Quarter and Clock (Top center) - use proper font
            period_clock_text = f"{game.get('game_phase', '')} {status.get('display_clock', '')}".strip()
            if game.get('is_halftime'):
                period_clock_text = "Halftime"
            elif status.get('state') == 'post':
                period_clock_text = "FINAL"
            elif status.get('state') == 'pre':
                period_clock_text = "UPCOMING"
            
            status_width = draw_overlay.textlength(period_clock_text, font=self.fonts['time'])
            status_x = (matrix_width - status_width) // 2
            status_y = 1
            self._draw_text_with_outline(draw_overlay, period_clock_text, (status_x, status_y), self.fonts['time'], fill=(0, 255, 0))
            
            # Down & Distance or Scoring Event (Below scores)
            scoring_event = self._detect_scoring_event(status)
            down_distance = game.get('down_distance', '')
            
            # Show scoring event if detected, otherwise show down & distance
            if scoring_event and status.get('state') == 'in':
                # Display scoring event with special formatting
                event_width = draw_overlay.textlength(scoring_event, font=self.fonts['detail'])
                event_x = (matrix_width - event_width) // 2
                event_y = matrix_height - 7
                
                # Color coding for different scoring events (matching original)
                if 'touchdown' in scoring_event.lower():
                    event_color = (255, 215, 0)  # Gold
                elif 'field goal' in scoring_event.lower():
                    event_color = (0, 255, 0)    # Green
                elif 'extra point' in scoring_event.lower() or 'pat' in scoring_event.lower():
                    event_color = (255, 165, 0)  # Orange
                else:
                    event_color = (255, 255, 255)  # White
                
                self._draw_text_with_outline(draw_overlay, scoring_event.upper(), (event_x, event_y), self.fonts['detail'], fill=event_color)
                
            elif down_distance and status.get('state') == 'in':
                # Show down & distance
                dd_width = draw_overlay.textlength(down_distance, font=self.fonts['detail'])
                dd_x = (matrix_width - dd_width) // 2
                dd_y = matrix_height - 7
                down_color = (200, 200, 0) if not game.get('is_redzone', False) else (255, 0, 0)
                self._draw_text_with_outline(draw_overlay, down_distance, (dd_x, dd_y), self.fonts['detail'], fill=down_color)
                
                # Possession Indicator (small football icon)
                possession = game.get('possession_indicator', '')
                if possession:
                    self._draw_possession_indicator(draw_overlay, possession, dd_x, dd_width, dd_y)
            
            # Timeouts (Bottom corners) - only for live games
            if status.get('state') == 'in':
                self._draw_timeouts(draw_overlay, game, matrix_width, matrix_height)
            
            # Draw records or rankings if enabled (matching original)
            league_config = game.get('league_config', {})
            if league_config.get('show_records') or league_config.get('show_ranking'):
                self._draw_records_and_rankings(draw_overlay, game, matrix_width, matrix_height, league_config)
            
        except Exception as e:
            self.logger.error(f"Error drawing scorebug layout: {e}")

    def _draw_upcoming_layout(self, draw_overlay: ImageDraw.Draw, main_img: Image.Image,
                            home_logo: Image.Image, away_logo: Image.Image,
                            home_team: Dict, away_team: Dict, status: Dict, game: Dict,
                            matrix_width: int, matrix_height: int):
        """Draw upcoming game layout matching original NCAA FB manager exactly."""
        try:
            center_y = matrix_height // 2
            
            # Draw team logos (matching original positioning)
            home_x = matrix_width - home_logo.width + 10
            home_y = center_y - (home_logo.height // 2)
            main_img.paste(home_logo, (home_x, home_y), home_logo)
            
            away_x = -10
            away_y = center_y - (away_logo.height // 2)
            main_img.paste(away_logo, (away_x, away_y), away_logo)
            
            # "Next Game" at the top (use smaller status font)
            status_font = self.fonts['status']
            if matrix_width > 128:
                status_font = self.fonts['time']
            status_text = "Next Game"
            status_width = draw_overlay.textlength(status_text, font=status_font)
            status_x = (matrix_width - status_width) // 2
            status_y = 1
            self._draw_text_with_outline(draw_overlay, status_text, (status_x, status_y), status_font)
            
            # Parse game date and time from start_time
            start_time = game.get('start_time', '')
            game_date = ''
            game_time = ''
            
            if start_time:
                try:
                    from datetime import datetime
                    import pytz
                    # Parse the start_time (ISO format)
                    dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    # Convert to local time
                    local_dt = dt.astimezone()
                    # Format date and time
                    game_date = local_dt.strftime('%m/%d')
                    game_time = local_dt.strftime('%I:%M%p').lstrip('0')
                except Exception as e:
                    self.logger.debug(f"Error parsing start_time {start_time}: {e}")
                    game_date = "TBD"
                    game_time = "TBD"
            else:
                game_date = "TBD"
                game_time = "TBD"
            
            # Date text (centered, below "Next Game")
            date_width = draw_overlay.textlength(game_date, font=self.fonts['time'])
            date_x = (matrix_width - date_width) // 2
            date_y = center_y - 7  # Raise date slightly
            self._draw_text_with_outline(draw_overlay, game_date, (date_x, date_y), self.fonts['time'])
            
            # Time text (centered, below Date)
            time_width = draw_overlay.textlength(game_time, font=self.fonts['time'])
            time_x = (matrix_width - time_width) // 2
            time_y = date_y + 9  # Place time below date
            self._draw_text_with_outline(draw_overlay, game_time, (time_x, time_y), self.fonts['time'])
            
            # Draw odds if available and enabled
            league_config = game.get('league_config', {})
            if league_config.get('show_odds') and 'odds' in game and game['odds']:
                self._draw_dynamic_odds(draw_overlay, game['odds'], matrix_width, matrix_height)
            
            # Draw records or rankings if enabled (matching original)
            if league_config.get('show_records') or league_config.get('show_ranking'):
                self._draw_records_and_rankings(draw_overlay, game, matrix_width, matrix_height, league_config)
            
        except Exception as e:
            self.logger.error(f"Error drawing upcoming layout: {e}")

    def _draw_dynamic_odds(self, draw: ImageDraw.Draw, odds: Dict[str, Any], width: int, height: int) -> None:
        """Draw odds with dynamic positioning - only show negative spread and position O/U based on favored team."""
        try:
            home_team_odds = odds.get('home_team_odds', {})
            away_team_odds = odds.get('away_team_odds', {})
            home_spread = home_team_odds.get('spread_odds')
            away_spread = away_team_odds.get('spread_odds')

            # Get top-level spread as fallback
            top_level_spread = odds.get('spread')
            
            # If we have a top-level spread and the individual spreads are None or 0, use the top-level
            if top_level_spread is not None:
                if home_spread is None or home_spread == 0.0:
                    home_spread = top_level_spread
                if away_spread is None:
                    away_spread = -top_level_spread

            # Determine which team is favored (has negative spread)
            home_favored = home_spread is not None and home_spread < 0
            away_favored = away_spread is not None and away_spread < 0
            
            # Only show spread if one team is favored
            if home_favored or away_favored:
                spread_value = home_spread if home_favored else away_spread
                spread_text = f"{spread_value:.1f}"
                
                # Position spread text in top corners
                spread_font = self.fonts['detail']
                spread_width = draw.textlength(spread_text, font=spread_font)
                
                if home_favored:
                    # Home team favored - show spread on right
                    spread_x = width - spread_width - 2
                    spread_y = 1
                else:
                    # Away team favored - show spread on left
                    spread_x = 2
                    spread_y = 1
                
                self._draw_text_with_outline(draw, spread_text, (spread_x, spread_y), spread_font, fill=(0, 255, 0))
            
            # Draw over/under if available
            over_under = odds.get('over_under')
            if over_under is not None:
                ou_text = f"O/U: {over_under:.0f}"
                ou_font = self.fonts['detail']
                ou_width = draw.textlength(ou_text, font=ou_font)
                ou_x = (width - ou_width) // 2
                ou_y = 1
                self._draw_text_with_outline(draw, ou_text, (ou_x, ou_y), ou_font, fill=(0, 255, 0))
                
        except Exception as e:
            self.logger.error(f"Error drawing dynamic odds: {e}")

    def _draw_text_fallback(self, draw_overlay: ImageDraw.Draw, home_team: Dict, away_team: Dict, 
                          status: Dict, game: Dict, matrix_width: int, matrix_height: int):
        """Draw text-only fallback when logos are not available - with proper fonts."""
        try:
            home_abbrev = home_team.get('abbrev', 'HOME')
            away_abbrev = away_team.get('abbrev', 'AWAY')
            home_score = home_team.get('score', 0)
            away_score = away_team.get('score', 0)
            
            # Team matchup
            matchup_text = f"{away_abbrev} @ {home_abbrev}"
            self._draw_text_with_outline(draw_overlay, matchup_text, (2, 2), self.fonts['team'], fill=(255, 255, 255))
            
            # Scores
            score_text = f"{away_score} - {home_score}"
            self._draw_text_with_outline(draw_overlay, score_text, (2, 12), self.fonts['score'], fill=(255, 200, 0))
            
            # Game status
            if status.get('state') == 'in':
                period_clock_text = f"{game.get('game_phase', '')} {status.get('display_clock', '')}"
                self._draw_text_with_outline(draw_overlay, period_clock_text, (2, 22), self.fonts['time'], fill=(0, 255, 0))
                
                # Down & distance
                down_distance = game.get('down_distance', '')
                if down_distance:
                    self._draw_text_with_outline(draw_overlay, down_distance, (2, 32), self.fonts['detail'], fill=(200, 200, 0))
            elif status.get('state') == 'post':
                self._draw_text_with_outline(draw_overlay, "FINAL", (2, 22), self.fonts['time'], fill=(200, 200, 200))
            else:
                self._draw_text_with_outline(draw_overlay, "UPCOMING", (2, 22), self.fonts['time'], fill=(255, 255, 0))
                
        except Exception as e:
            self.logger.error(f"Error drawing text fallback: {e}")

    def _draw_text_with_outline(self, draw: ImageDraw.Draw, text: str, position: tuple, font, fill=(255, 255, 255), outline_color=(0, 0, 0)):
        """Draw text with a black outline for better readability - matching original managers."""
        try:
            x, y = position
            # Draw outline
            for dx, dy in [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]:
                draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
            # Draw main text
            draw.text((x, y), text, font=font, fill=fill)
        except Exception as e:
            self.logger.error(f"Error drawing text with outline: {e}")

    def _draw_possession_indicator(self, draw: ImageDraw.Draw, possession: str, dd_x: int, dd_width: int, dd_y: int):
        """Draw possession indicator (football icon)."""
        try:
            ball_radius_x = 3
            ball_radius_y = 2
            ball_color = (139, 69, 19)  # Brown
            lace_color = (255, 255, 255)  # White
            
            ball_y_center = dd_y + 3  # Center with text
            possession_ball_padding = 3
            
            if possession == "away":
                ball_x_center = dd_x - possession_ball_padding - ball_radius_x
            elif possession == "home":
                ball_x_center = dd_x + dd_width + possession_ball_padding + ball_radius_x
            else:
                return
            
            if ball_x_center > 0:
                # Draw football shape
                draw.ellipse(
                    (ball_x_center - ball_radius_x, ball_y_center - ball_radius_y,
                     ball_x_center + ball_radius_x, ball_y_center + ball_radius_y),
                    fill=ball_color, outline=(0, 0, 0)
                )
                # Draw lace
                draw.line(
                    (ball_x_center - 1, ball_y_center, ball_x_center + 1, ball_y_center),
                    fill=lace_color, width=1
                )
        except Exception as e:
            self.logger.error(f"Error drawing possession indicator: {e}")

    def _draw_timeouts(self, draw: ImageDraw.Draw, game: Dict, matrix_width: int, matrix_height: int):
        """Draw timeout indicators in bottom corners - matching original."""
        try:
            timeout_bar_width = 4
            timeout_bar_height = 2
            timeout_spacing = 1
            timeout_y = matrix_height - timeout_bar_height - 1
            
            # Away timeouts (bottom left)
            away_timeouts = game.get('away_timeouts', 0)
            for i in range(3):
                to_x = 2 + i * (timeout_bar_width + timeout_spacing)
                color = (255, 255, 255) if i < away_timeouts else (80, 80, 80)
                draw.rectangle([to_x, timeout_y, to_x + timeout_bar_width, timeout_y + timeout_bar_height], 
                             fill=color, outline=(0, 0, 0))
            
            # Home timeouts (bottom right)
            home_timeouts = game.get('home_timeouts', 0)
            for i in range(3):
                to_x = matrix_width - 2 - timeout_bar_width - (2 - i) * (timeout_bar_width + timeout_spacing)
                color = (255, 255, 255) if i < home_timeouts else (80, 80, 80)
                draw.rectangle([to_x, timeout_y, to_x + timeout_bar_width, timeout_y + timeout_bar_height], 
                             fill=color, outline=(0, 0, 0))
        except Exception as e:
            self.logger.error(f"Error drawing timeouts: {e}")

    def _draw_records_and_rankings(self, draw: ImageDraw.Draw, game: Dict, matrix_width: int, matrix_height: int, league_config: Dict):
        """Draw team records or rankings - matching original managers."""
        try:
            # Use detail font for records/rankings
            record_font = self.fonts['detail']
            
            # Get team info
            home_abbr = game.get('home_team', {}).get('abbrev', '')
            away_abbr = game.get('away_team', {}).get('abbrev', '')
            
            # Calculate positioning (bottom of screen, above timeouts)
            record_bbox = draw.textbbox((0, 0), "0-0", font=record_font)
            record_height = record_bbox[3] - record_bbox[1]
            record_y = matrix_height - record_height - 4
            
            # Display away team info (left side)
            if away_abbr:
                if league_config.get('show_ranking') and league_config.get('show_records'):
                    # Rankings take priority
                    away_rank = self._team_rankings_cache.get(away_abbr, 0)
                    if away_rank > 0:
                        away_text = f"#{away_rank}"
                    else:
                        away_text = ''
                elif league_config.get('show_ranking'):
                    # Show ranking only
                    away_rank = self._team_rankings_cache.get(away_abbr, 0)
                    if away_rank > 0:
                        away_text = f"#{away_rank}"
                    else:
                        away_text = ''
                elif league_config.get('show_records'):
                    # Show record only
                    away_text = game.get('away_record', '')
                else:
                    away_text = ''
                
                if away_text:
                    away_record_x = 3
                    self._draw_text_with_outline(draw, away_text, (away_record_x, record_y), record_font)
            
            # Display home team info (right side)
            if home_abbr:
                if league_config.get('show_ranking') and league_config.get('show_records'):
                    # Rankings take priority
                    home_rank = self._team_rankings_cache.get(home_abbr, 0)
                    if home_rank > 0:
                        home_text = f"#{home_rank}"
                    else:
                        home_text = ''
                elif league_config.get('show_ranking'):
                    # Show ranking only
                    home_rank = self._team_rankings_cache.get(home_abbr, 0)
                    if home_rank > 0:
                        home_text = f"#{home_rank}"
                    else:
                        home_text = ''
                elif league_config.get('show_records'):
                    # Show record only
                    home_text = game.get('home_record', '')
                else:
                    home_text = ''
                
                if home_text:
                    home_record_bbox = draw.textbbox((0, 0), home_text, font=record_font)
                    home_record_width = home_record_bbox[2] - home_record_bbox[0]
                    home_record_x = matrix_width - home_record_width - 3
                    self._draw_text_with_outline(draw, home_text, (home_record_x, record_y), record_font)
        
        except Exception as e:
            self.logger.error(f"Error drawing records/rankings: {e}")

    def _display_no_games(self, mode: str):
        """Display message when no games are available."""
        img = Image.new('RGB', (self.display_manager.matrix.width,
                               self.display_manager.matrix.height),
                       (0, 0, 0))
        draw = ImageDraw.Draw(img)

        message = {
            'football_live': "No Live Games",
            'football_recent': "No Recent Games",
            'football_upcoming': "No Upcoming Games"
        }.get(mode, "No Games")

        draw.text((5, 12), message, fill=(150, 150, 150))

        self.display_manager.image = img.copy()
        self.display_manager.update_display()

    def _display_error(self, message: str):
        """Display error message."""
        img = Image.new('RGB', (self.display_manager.matrix.width,
                               self.display_manager.matrix.height),
                       (0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.text((5, 12), message, fill=(255, 0, 0))

        self.display_manager.image = img.copy()
        self.display_manager.update_display()

    def get_display_duration(self) -> float:
        """Get display duration from config."""
        return self.display_duration

    def get_info(self) -> Dict[str, Any]:
        """Return plugin info for web UI."""
        if BasePlugin:
            info = super().get_info()
        else:
            # Fallback info structure
            info = {
                'plugin_id': self.plugin_id,
                'enabled': self.enabled,
                'version': '1.0.1'
            }

        # Get league-specific configurations
        leagues_config = {}
        for league_key, league_config in self.leagues.items():
            leagues_config[league_key] = {
                'enabled': league_config.get('enabled', False),
                'favorite_teams': league_config.get('favorite_teams', []),
                'display_modes': league_config.get('display_modes', {}),
                'recent_games_to_show': league_config.get('recent_games_to_show', 5),
                'upcoming_games_to_show': league_config.get('upcoming_games_to_show', 10),
                'update_interval_seconds': league_config.get('update_interval_seconds', 60)
            }

        info.update({
            'total_games': len(self.current_games),
            'enabled_leagues': [k for k, v in self.leagues.items() if v.get('enabled', False)],
            'current_mode': self.current_display_mode,
            'last_update': self.last_update,
            'display_duration': self.display_duration,
            'show_records': self.show_records,
            'show_ranking': self.show_ranking,
            'live_games': len([g for g in self.current_games if g.get('status', {}).get('state') == 'in']),
            'recent_games': len([g for g in self.current_games if g.get('status', {}).get('state') == 'post']),
            'upcoming_games': len([g for g in self.current_games if g.get('status', {}).get('state') == 'pre']),
            'leagues_config': leagues_config,
            'global_config': self.global_config
        })
        return info

    def cleanup(self) -> None:
        """Cleanup resources."""
        self.current_games = []
        self.logger.info("Football scoreboard plugin cleaned up")
