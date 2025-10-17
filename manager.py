"""
Football Scoreboard Plugin for LEDMatrix - Standalone Implementation

This plugin is completely self-contained and does NOT depend on LEDMatrix base classes.
All football functionality is embedded within this plugin.

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
- Completely standalone - no base class dependencies

API Version: 2.0.0
"""

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

import pytz
import requests
from PIL import Image, ImageDraw, ImageFont
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.plugin_system.base_plugin import BasePlugin

# ESPN API endpoints
ESPN_NFL_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
ESPN_NCAAFB_URL = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"

logger = logging.getLogger(__name__)


class FootballScoreboardPlugin(BasePlugin):
    """
    Standalone Football scoreboard plugin - no base class dependencies.
    
    Supports NFL and NCAA Football with live, recent, and upcoming game modes.
    All functionality is self-contained within this plugin.
    """

    def __init__(self, plugin_id: str, config: Dict[str, Any],
                 display_manager, cache_manager, plugin_manager):
        """Initialize the standalone football scoreboard plugin."""
        super().__init__(plugin_id, config, display_manager, cache_manager, plugin_manager)

        # Store managers
        self.display_manager = display_manager
        self.cache_manager = cache_manager
        self.plugin_manager = plugin_manager
        
        # Display dimensions
        self.display_width = display_manager.matrix.width
        self.display_height = display_manager.matrix.height
        
        # Parse flattened config
        self.config = self._parse_config(config)
        
        # Initialize HTTP session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        # Headers for API requests
        self.headers = {
            'User-Agent': 'LEDMatrix-Plugin/2.0',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive'
        }
        
        # Caches
        self._logo_cache = {}
        self._season_cache = {}
        self._team_rankings_cache = {}
        self._rankings_cache_timestamp = 0
        
        # Load fonts
        self.fonts = self._load_fonts()
        
        # State management for each league
        self.nfl_state = {
            'live_games': [],
            'recent_games': [],
            'upcoming_games': [],
            'current_game_index': 0,
            'last_update': 0,
            'last_game_switch': 0
        }
        
        self.ncaa_fb_state = {
            'live_games': [],
            'recent_games': [],
            'upcoming_games': [],
            'current_game_index': 0,
            'last_update': 0,
            'last_game_switch': 0
        }
        
        # Test mode data
        if self.config['nfl']['test_mode']:
            self._init_nfl_test_game()
        if self.config['ncaa_fb']['test_mode']:
            self._init_ncaa_fb_test_game()
        
        self.initialized = True
        self.logger.info(f"Football scoreboard plugin initialized (NFL: {self.config['nfl']['enabled']}, NCAA: {self.config['ncaa_fb']['enabled']})")

    def _parse_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Parse flattened configuration into structured format."""
        parsed = {
            'enabled': config.get('enabled', True),
            'display_duration': config.get('display_duration', 15),
            'show_records': config.get('show_records', False),
            'show_ranking': config.get('show_ranking', False),
            'nfl': {
                'enabled': config.get('nfl_enabled', True),
                'favorite_teams': config.get('nfl_favorite_teams', []),
                'display_modes': {
                    'live': config.get('nfl_display_modes_live', True),
                    'recent': config.get('nfl_display_modes_recent', True),
                    'upcoming': config.get('nfl_display_modes_upcoming', True)
                },
                'recent_games_to_show': config.get('nfl_recent_games_to_show', 5),
                'upcoming_games_to_show': config.get('nfl_upcoming_games_to_show', 10),
                'show_favorite_teams_only': config.get('nfl_show_favorite_teams_only', True),
                'show_all_live': config.get('nfl_show_all_live', False),
                'show_odds': config.get('nfl_show_odds', True),
                'test_mode': config.get('nfl_test_mode', False),
                'update_interval': config.get('nfl_update_interval_seconds', 60),
                'live_update_interval': config.get('nfl_live_update_interval', 30),
                'live_game_duration': config.get('nfl_live_game_duration', 30),
                'logo_dir': Path(config.get('nfl_logo_dir', 'assets/sports/nfl_logos'))
            },
            'ncaa_fb': {
                'enabled': config.get('ncaa_fb_enabled', False),
                'favorite_teams': config.get('ncaa_fb_favorite_teams', []),
                'display_modes': {
                    'live': config.get('ncaa_fb_display_modes_live', True),
                    'recent': config.get('ncaa_fb_display_modes_recent', True),
                    'upcoming': config.get('ncaa_fb_display_modes_upcoming', True)
                },
                'recent_games_to_show': config.get('ncaa_fb_recent_games_to_show', 5),
                'upcoming_games_to_show': config.get('ncaa_fb_upcoming_games_to_show', 10),
                'show_favorite_teams_only': config.get('ncaa_fb_show_favorite_teams_only', True),
                'show_all_live': config.get('ncaa_fb_show_all_live', False),
                'show_odds': config.get('ncaa_fb_show_odds', True),
                'test_mode': config.get('ncaa_fb_test_mode', False),
                'update_interval': config.get('ncaa_fb_update_interval_seconds', 60),
                'live_update_interval': config.get('ncaa_fb_live_update_interval', 30),
                'live_game_duration': config.get('ncaa_fb_live_game_duration', 30),
                'logo_dir': Path(config.get('ncaa_fb_logo_dir', 'assets/sports/ncaa_logos'))
            }
        }
        return parsed

    def _load_fonts(self) -> Dict[str, ImageFont.FreeTypeFont]:
        """Load fonts for scorebug display."""
        fonts = {}
        try:
            fonts['score'] = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 10)
            fonts['time'] = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 8)
            fonts['team'] = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 8)
            fonts['status'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 6)
            fonts['detail'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 6)
            self.logger.info("Successfully loaded fonts")
        except IOError as e:
            self.logger.warning(f"Fonts not found ({e}), using default PIL font")
            default_font = ImageFont.load_default()
            fonts = {
                'score': default_font,
                'time': default_font,
                'team': default_font,
                'status': default_font,
                'detail': default_font
            }
        return fonts

    def _init_nfl_test_game(self):
        """Initialize test game for NFL."""
        test_game = {
            "id": "test_nfl_001",
            "league": "nfl",
            "home_abbr": "TB", "home_id": "27",
            "away_abbr": "DAL", "away_id": "6",
            "home_score": 21, "away_score": 17,
            "period": 4, "period_text": "Q4", "clock": "02:35",
            "down_distance_text": "1st & 10",
            "possession": "27",
            "possession_indicator": "home",
            "home_timeouts": 2, "away_timeouts": 3,
            "home_logo_path": self.config['nfl']['logo_dir'] / "TB.png",
            "away_logo_path": self.config['nfl']['logo_dir'] / "DAL.png",
            "is_redzone": False,
            "is_live": True, "is_final": False, "is_upcoming": False,
            "status_text": "Q4 02:35"
        }
        self.nfl_state['live_games'] = [test_game]
        self.logger.info("Initialized NFL test game: DAL @ TB")

    def _init_ncaa_fb_test_game(self):
        """Initialize test game for NCAA FB."""
        test_game = {
            "id": "test_ncaa_001",
            "league": "ncaa_fb",
            "home_abbr": "UGA", "home_id": "257",
            "away_abbr": "AUB", "away_id": "2",
            "home_score": 28, "away_score": 21,
            "period": 4, "period_text": "Q4", "clock": "01:15",
            "down_distance_text": "2nd & 5",
            "possession": "257",
            "possession_indicator": "home",
            "home_timeouts": 1, "away_timeouts": 2,
            "home_logo_path": self.config['ncaa_fb']['logo_dir'] / "UGA.png",
            "away_logo_path": self.config['ncaa_fb']['logo_dir'] / "AUB.png",
            "is_redzone": False,
            "is_live": True, "is_final": False, "is_upcoming": False,
            "status_text": "Q4 01:15"
        }
        self.ncaa_fb_state['live_games'] = [test_game]
        self.logger.info("Initialized NCAA FB test game: AUB @ UGA")

    # ========================================================================
    # API Data Fetching
    # ========================================================================

    def _fetch_espn_data(self, url: str, params: Dict = None) -> Optional[Dict]:
        """Fetch data from ESPN API."""
        try:
            response = self.session.get(url, params=params, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data
        except requests.RequestException as e:
            self.logger.error(f"ESPN API error: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error parsing ESPN data: {e}")
            return None

    def _fetch_season_data(self, league: str, url: str) -> Optional[Dict]:
        """Fetch full season schedule with caching."""
        now = datetime.now(pytz.utc)
        season_year = now.year if now.month >= 8 else now.year - 1
        
        # Determine date range based on league
        if league == 'nfl':
            datestring = f"{season_year}0801-{season_year+1}0301"
        else:  # ncaa_fb
            datestring = f"{season_year}0801-{season_year+1}0201"
        
        cache_key = f"{league}_schedule_{season_year}"
        
        # Check cache
        cached_data = self.cache_manager.get(cache_key)
        if cached_data:
            if isinstance(cached_data, dict) and 'events' in cached_data:
                self.logger.debug(f"Using cached {league} schedule for {season_year}")
                return cached_data
            elif isinstance(cached_data, list):
                return {'events': cached_data}
        
        # Fetch new data
        self.logger.info(f"Fetching {league} season schedule for {season_year}...")
        params = {"dates": datestring, "limit": 1000}
        data = self._fetch_espn_data(url, params)
        
        if data:
            # Cache for 24 hours
            self.cache_manager.set(cache_key, data, ttl=86400)
            self.logger.info(f"Fetched {len(data.get('events', []))} {league} events")
            return data
        
        return None

    def _fetch_todays_games(self, url: str) -> Optional[Dict]:
        """Fetch today's games for live updates."""
        today = datetime.now().strftime("%Y%m%d")
        params = {"dates": today, "limit": 1000}
        return self._fetch_espn_data(url, params)

    # ========================================================================
    # Game Data Extraction
    # ========================================================================

    def _extract_game_details(self, event: Dict, league: str, logo_dir: Path) -> Optional[Dict]:
        """Extract game details from ESPN event."""
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
            
            # Extract basic info
            game_date_str = event.get('date', '')
            start_time_utc = None
            game_time = ""
            game_date = ""
            
            if game_date_str:
                try:
                    start_time_utc = datetime.fromisoformat(game_date_str.replace("Z", "+00:00"))
                    local_tz = pytz.timezone('America/New_York')  # TODO: Make configurable
                    local_time = start_time_utc.astimezone(local_tz)
                    game_time = local_time.strftime("%I:%M%p").lstrip('0')
                    game_date = local_time.strftime("%-m/%-d")
                except Exception as e:
                    self.logger.warning(f"Could not parse game date: {e}")
            
            # Team abbreviations
            home_abbr = home_team.get('team', {}).get('abbreviation', 'HOME')
            away_abbr = away_team.get('team', {}).get('abbreviation', 'AWAY')
            
            # Game state
            state = status.get('type', {}).get('state', 'unknown')
            is_live = state == 'in'
            is_final = state == 'post'
            is_upcoming = state == 'pre'
            is_halftime = status.get('type', {}).get('name') == 'STATUS_HALFTIME'
            
            # Build base game dict
            game = {
                'id': event.get('id'),
                'league': league,
                'home_abbr': home_abbr,
                'home_id': home_team.get('id'),
                'home_score': int(home_team.get('score', 0)),
                'home_logo_path': logo_dir / f"{self._normalize_abbr(home_abbr)}.png",
                'away_abbr': away_abbr,
                'away_id': away_team.get('id'),
                'away_score': int(away_team.get('score', 0)),
                'away_logo_path': logo_dir / f"{self._normalize_abbr(away_abbr)}.png",
                'start_time_utc': start_time_utc,
                'game_time': game_time,
                'game_date': game_date,
                'status_text': status.get('type', {}).get('shortDetail', ''),
                'is_live': is_live,
                'is_final': is_final,
                'is_upcoming': is_upcoming,
                'is_halftime': is_halftime
            }
            
            # Add football-specific details for live games
            if is_live:
                situation = competition.get('situation', {})
                period = status.get('period', 0)
                
                # Format period text
                if period >= 1 and period <= 4:
                    period_text = f"Q{period}"
                elif period > 4:
                    period_text = f"OT{period - 4}"
                else:
                    period_text = "Start"
                
                # Possession
                possession_id = situation.get('possession')
                possession_indicator = None
                if possession_id:
                    if possession_id == game['home_id']:
                        possession_indicator = 'home'
                    elif possession_id == game['away_id']:
                        possession_indicator = 'away'
                
                game.update({
                    'period': period,
                    'period_text': period_text,
                    'clock': status.get('displayClock', '0:00'),
                    'down_distance_text': situation.get('shortDownDistanceText', ''),
                    'possession': possession_id,
                    'possession_indicator': possession_indicator,
                    'home_timeouts': situation.get('homeTimeouts', 3),
                    'away_timeouts': situation.get('awayTimeouts', 3),
                    'is_redzone': situation.get('isRedZone', False)
                })
            elif is_final:
                period = status.get('period', 0)
                period_text = "Final/OT" if period > 4 else "Final"
                game['period_text'] = period_text
            
            return game
            
        except Exception as e:
            self.logger.error(f"Error extracting game details: {e}")
            return None

    def _normalize_abbr(self, abbr: str) -> str:
        """Normalize team abbreviation for logo filename."""
        # Handle special cases
        replacements = {
            'TA&M': 'TAANDM',
            'T A&M': 'TAANDM'
        }
        return replacements.get(abbr, abbr)

    # ========================================================================
    # Logo Management
    # ========================================================================

    def _load_logo(self, logo_path: Path, team_abbr: str) -> Optional[Image.Image]:
        """Load and cache team logo."""
        if team_abbr in self._logo_cache:
            return self._logo_cache[team_abbr]
        
        try:
            if not logo_path.exists():
                self.logger.warning(f"Logo not found: {logo_path}")
                return None
            
            logo = Image.open(logo_path)
            if logo.mode != 'RGBA':
                logo = logo.convert('RGBA')
            
            # Resize to fit display
            max_width = int(self.display_width * 1.5)
            max_height = int(self.display_height * 1.5)
            logo.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            self._logo_cache[team_abbr] = logo
            return logo
            
        except Exception as e:
            self.logger.error(f"Error loading logo {logo_path}: {e}")
            return None

    # ========================================================================
    # Update Logic
    # ========================================================================

    def update(self) -> None:
        """Update game data for all enabled leagues."""
        if not self.initialized or not self.config['enabled']:
            return

        current_time = time.time()
        
        # Update NFL
        if self.config['nfl']['enabled']:
            self._update_nfl(current_time)
        
        # Update NCAA FB
        if self.config['ncaa_fb']['enabled']:
            self._update_ncaa_fb(current_time)

    def _update_nfl(self, current_time: float):
        """Update NFL game data."""
        cfg = self.config['nfl']
        state = self.nfl_state
        
        # Skip if updated recently (unless there are live games)
        interval = cfg['live_update_interval'] if state['live_games'] else cfg['update_interval']
        if current_time - state['last_update'] < interval:
            return
        
        state['last_update'] = current_time
        
        # Test mode
        if cfg['test_mode']:
            return  # Test games already initialized
        
        # Fetch live games
        if cfg['display_modes']['live']:
            self._update_live_games('nfl', state, ESPN_NFL_URL, cfg)
        
        # Fetch season data for recent/upcoming
        if cfg['display_modes']['recent'] or cfg['display_modes']['upcoming']:
            season_data = self._fetch_season_data('nfl', ESPN_NFL_URL)
            if season_data:
                self._update_recent_games('nfl', state, season_data, cfg)
                self._update_upcoming_games('nfl', state, season_data, cfg)

    def _update_ncaa_fb(self, current_time: float):
        """Update NCAA FB game data."""
        cfg = self.config['ncaa_fb']
        state = self.ncaa_fb_state
        
        # Skip if updated recently (unless there are live games)
        interval = cfg['live_update_interval'] if state['live_games'] else cfg['update_interval']
        if current_time - state['last_update'] < interval:
            return
        
        state['last_update'] = current_time
        
        # Test mode
        if cfg['test_mode']:
            return  # Test games already initialized
        
        # Fetch live games
        if cfg['display_modes']['live']:
            self._update_live_games('ncaa_fb', state, ESPN_NCAAFB_URL, cfg)
        
        # Fetch season data for recent/upcoming
        if cfg['display_modes']['recent'] or cfg['display_modes']['upcoming']:
            season_data = self._fetch_season_data('ncaa_fb', ESPN_NCAAFB_URL)
            if season_data:
                self._update_recent_games('ncaa_fb', state, season_data, cfg)
                self._update_upcoming_games('ncaa_fb', state, season_data, cfg)

    def _update_live_games(self, league: str, state: Dict, url: str, cfg: Dict):
        """Update live games for a league."""
        data = self._fetch_todays_games(url)
        if not data:
            return
        
        live_games = []
        for event in data.get('events', []):
            game = self._extract_game_details(event, league, cfg['logo_dir'])
            if game and game['is_live']:
                # Filter by favorites
                if cfg['show_all_live']:
                    live_games.append(game)
                elif not cfg['show_favorite_teams_only']:
                    live_games.append(game)
                elif game['home_abbr'] in cfg['favorite_teams'] or game['away_abbr'] in cfg['favorite_teams']:
                    live_games.append(game)
        
        if live_games != state['live_games']:
            state['live_games'] = live_games
            state['current_game_index'] = 0
            self.logger.info(f"Found {len(live_games)} live {league} games")

    def _update_recent_games(self, league: str, state: Dict, season_data: Dict, cfg: Dict):
        """Update recent games for a league."""
        now = datetime.now(timezone.utc)
        recent_cutoff = now - timedelta(days=21)
        
        recent_games = []
        for event in season_data.get('events', []):
            game = self._extract_game_details(event, league, cfg['logo_dir'])
            if game and game['is_final']:
                if game['start_time_utc'] and game['start_time_utc'] >= recent_cutoff:
                    # Filter by favorites
                    if cfg['show_favorite_teams_only']:
                        if game['home_abbr'] in cfg['favorite_teams'] or game['away_abbr'] in cfg['favorite_teams']:
                            recent_games.append(game)
                    else:
                        recent_games.append(game)
        
        # Sort by date (most recent first) and limit
        recent_games.sort(key=lambda g: g.get('start_time_utc', datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
        recent_games = recent_games[:cfg['recent_games_to_show']]
        
        if recent_games != state['recent_games']:
            state['recent_games'] = recent_games
            state['current_game_index'] = 0
            self.logger.info(f"Found {len(recent_games)} recent {league} games")

    def _update_upcoming_games(self, league: str, state: Dict, season_data: Dict, cfg: Dict):
        """Update upcoming games for a league."""
        upcoming_games = []
        for event in season_data.get('events', []):
            game = self._extract_game_details(event, league, cfg['logo_dir'])
            if game and game['is_upcoming']:
                # Filter by favorites
                if cfg['show_favorite_teams_only']:
                    if game['home_abbr'] in cfg['favorite_teams'] or game['away_abbr'] in cfg['favorite_teams']:
                        upcoming_games.append(game)
                else:
                    upcoming_games.append(game)
        
        # Sort by date (earliest first) and limit
        upcoming_games.sort(key=lambda g: g.get('start_time_utc', datetime.max.replace(tzinfo=timezone.utc)))
        upcoming_games = upcoming_games[:cfg['upcoming_games_to_show']]
        
        if upcoming_games != state['upcoming_games']:
            state['upcoming_games'] = upcoming_games
            state['current_game_index'] = 0
            self.logger.info(f"Found {len(upcoming_games)} upcoming {league} games")

    # ========================================================================
    # Display Logic
    # ========================================================================

    def display(self, display_mode: str = None, force_clear: bool = False) -> None:
        """Display football games."""
        if not self.initialized or not self.config['enabled']:
            return

        # Determine which game to display
        league, mode_type = self._parse_display_mode(display_mode)
        
        if not league or not mode_type:
            return
        
        # Get state and config for league
        state = self.nfl_state if league == 'nfl' else self.ncaa_fb_state
        cfg = self.config[league]
        
        # Get games list based on mode
        if mode_type == 'live':
            games = state['live_games']
        elif mode_type == 'recent':
            games = state['recent_games']
        else:  # upcoming
            games = state['upcoming_games']
        
        if not games:
            self._display_no_games(mode_type)
            return
        
        # Handle game rotation
        current_time = time.time()
        if len(games) > 1 and current_time - state['last_game_switch'] >= self.config['display_duration']:
            state['current_game_index'] = (state['current_game_index'] + 1) % len(games)
            state['last_game_switch'] = current_time
        
        # Display current game
        game = games[state['current_game_index']]
        self._render_game(game, mode_type)

    def _parse_display_mode(self, display_mode: str) -> tuple[Optional[str], Optional[str]]:
        """Parse display mode string into league and mode type."""
        if not display_mode:
            # Auto-select: prefer live games
            if self.config['nfl']['enabled'] and self.nfl_state['live_games']:
                return 'nfl', 'live'
            if self.config['ncaa_fb']['enabled'] and self.ncaa_fb_state['live_games']:
                return 'ncaa_fb', 'live'
            # Fall back to first enabled league
            if self.config['nfl']['enabled']:
                return 'nfl', 'recent'
            if self.config['ncaa_fb']['enabled']:
                return 'ncaa_fb', 'recent'
            return None, None
        
        # Parse specific modes
        if display_mode.startswith('nfl_'):
            return 'nfl', display_mode.replace('nfl_', '')
        elif display_mode.startswith('ncaa_fb_'):
            return 'ncaa_fb', display_mode.replace('ncaa_fb_', '')
        elif display_mode.startswith('football_'):
            mode_type = display_mode.replace('football_', '')
            # Use first enabled league
            if self.config['nfl']['enabled']:
                return 'nfl', mode_type
            if self.config['ncaa_fb']['enabled']:
                return 'ncaa_fb', mode_type
        
        return None, None

    def _render_game(self, game: Dict, mode_type: str):
        """Render a game to the display."""
        # Create image
        img = Image.new('RGBA', (self.display_width, self.display_height), (0, 0, 0, 255))
        overlay = Image.new('RGBA', (self.display_width, self.display_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        # Load logos
        home_logo = self._load_logo(game['home_logo_path'], game['home_abbr'])
        away_logo = self._load_logo(game['away_logo_path'], game['away_abbr'])
        
        if not home_logo or not away_logo:
            self._display_error("Logo Error")
            return
        
        # Position logos
        center_y = self.display_height // 2
        home_x = self.display_width - home_logo.width + 10
        home_y = center_y - (home_logo.height // 2)
        img.paste(home_logo, (home_x, home_y), home_logo)
        
        away_x = -10
        away_y = center_y - (away_logo.height // 2)
        img.paste(away_logo, (away_x, away_y), away_logo)
        
        # Render based on mode
        if mode_type == 'live':
            self._render_live_game(draw, game)
        elif mode_type == 'recent':
            self._render_recent_game(draw, game)
        else:  # upcoming
            self._render_upcoming_game(draw, game)
        
        # Composite and display
        img = Image.alpha_composite(img, overlay)
        img = img.convert('RGB')
        self.display_manager.image.paste(img, (0, 0))
        self.display_manager.update_display()

    def _render_live_game(self, draw: ImageDraw.Draw, game: Dict):
        """Render live game details."""
        # Scores
        score_text = f"{game['away_score']}-{game['home_score']}"
        score_width = draw.textlength(score_text, font=self.fonts['score'])
        score_x = (self.display_width - score_width) // 2
        score_y = (self.display_height // 2) - 3
        self._draw_text_outline(draw, score_text, (score_x, score_y), self.fonts['score'])
        
        # Period and clock
        status_text = f"{game.get('period_text', '')} {game.get('clock', '')}".strip()
        status_width = draw.textlength(status_text, font=self.fonts['time'])
        status_x = (self.display_width - status_width) // 2
        status_y = 1
        self._draw_text_outline(draw, status_text, (status_x, status_y), self.fonts['time'])
        
        # Down & distance
        down_dist = game.get('down_distance_text', '')
        if down_dist:
            dd_width = draw.textlength(down_dist, font=self.fonts['detail'])
            dd_x = (self.display_width - dd_width) // 2
            dd_y = self.display_height - 7
            color = (255, 0, 0) if game.get('is_redzone') else (200, 200, 0)
            self._draw_text_outline(draw, down_dist, (dd_x, dd_y), self.fonts['detail'], fill=color)
            
            # Possession indicator
            possession = game.get('possession_indicator')
            if possession:
                ball_x = dd_x - 5 if possession == 'away' else dd_x + dd_width + 5
                ball_y = dd_y + 3
                draw.ellipse([ball_x-3, ball_y-2, ball_x+3, ball_y+2], fill=(139, 69, 19), outline=(0,0,0))
                draw.line([ball_x-1, ball_y, ball_x+1, ball_y], fill=(255,255,255), width=1)
        
        # Timeouts
        self._render_timeouts(draw, game)

    def _render_recent_game(self, draw: ImageDraw.Draw, game: Dict):
        """Render recent game details."""
        # Scores
        score_text = f"{game['away_score']}-{game['home_score']}"
        score_width = draw.textlength(score_text, font=self.fonts['score'])
        score_x = (self.display_width - score_width) // 2
        score_y = self.display_height - 14
        self._draw_text_outline(draw, score_text, (score_x, score_y), self.fonts['score'])
        
        # Final status
        status_text = game.get('period_text', 'Final')
        status_width = draw.textlength(status_text, font=self.fonts['time'])
        status_x = (self.display_width - status_width) // 2
        status_y = 1
        self._draw_text_outline(draw, status_text, (status_x, status_y), self.fonts['time'])

    def _render_upcoming_game(self, draw: ImageDraw.Draw, game: Dict):
        """Render upcoming game details."""
        # "Next Game" text
        status_text = "Next Game"
        status_width = draw.textlength(status_text, font=self.fonts['status'])
        status_x = (self.display_width - status_width) // 2
        status_y = 1
        self._draw_text_outline(draw, status_text, (status_x, status_y), self.fonts['status'])
        
        # Date
        date_text = game.get('game_date', '')
        date_width = draw.textlength(date_text, font=self.fonts['time'])
        date_x = (self.display_width - date_width) // 2
        date_y = (self.display_height // 2) - 7
        self._draw_text_outline(draw, date_text, (date_x, date_y), self.fonts['time'])
        
        # Time
        time_text = game.get('game_time', '')
        time_width = draw.textlength(time_text, font=self.fonts['time'])
        time_x = (self.display_width - time_width) // 2
        time_y = date_y + 9
        self._draw_text_outline(draw, time_text, (time_x, time_y), self.fonts['time'])

    def _render_timeouts(self, draw: ImageDraw.Draw, game: Dict):
        """Render timeout indicators."""
        bar_width = 4
        bar_height = 2
        spacing = 1
        y = self.display_height - bar_height - 1
        
        # Away timeouts (left)
        away_timeouts = game.get('away_timeouts', 0)
        for i in range(3):
            x = 2 + i * (bar_width + spacing)
            color = (255, 255, 255) if i < away_timeouts else (80, 80, 80)
            draw.rectangle([x, y, x + bar_width, y + bar_height], fill=color, outline=(0,0,0))
        
        # Home timeouts (right)
        home_timeouts = game.get('home_timeouts', 0)
        for i in range(3):
            x = self.display_width - 2 - bar_width - (2-i) * (bar_width + spacing)
            color = (255, 255, 255) if i < home_timeouts else (80, 80, 80)
            draw.rectangle([x, y, x + bar_width, y + bar_height], fill=color, outline=(0,0,0))

    def _draw_text_outline(self, draw: ImageDraw.Draw, text: str, pos: tuple, font, fill=(255,255,255)):
        """Draw text with black outline."""
        x, y = pos
        # Outline
        for dx, dy in [(-1,-1), (-1,0), (-1,1), (0,-1), (0,1), (1,-1), (1,0), (1,1)]:
            draw.text((x+dx, y+dy), text, font=font, fill=(0,0,0))
        # Text
        draw.text((x, y), text, font=font, fill=fill)

    def _display_no_games(self, mode_type: str):
        """Display 'no games' message."""
        img = Image.new('RGB', (self.display_width, self.display_height), (0,0,0))
        draw = ImageDraw.Draw(img)
        
        messages = {
            'live': "No Live Games",
            'recent': "No Recent Games",
            'upcoming': "No Upcoming"
        }
        text = messages.get(mode_type, "No Games")
        
        draw.text((5, 12), text, fill=(150, 150, 150), font=self.fonts['status'])
        self.display_manager.image.paste(img, (0, 0))
        self.display_manager.update_display()

    def _display_error(self, message: str):
        """Display error message."""
        img = Image.new('RGB', (self.display_width, self.display_height), (0,0,0))
        draw = ImageDraw.Draw(img)
        draw.text((5, 12), message, fill=(255, 0, 0), font=self.fonts['status'])
        self.display_manager.image.paste(img, (0, 0))
        self.display_manager.update_display()

    # ========================================================================
    # Plugin Interface
    # ========================================================================

    def get_display_duration(self) -> float:
        """Get display duration."""
        return self.config['display_duration']

    def get_info(self) -> Dict[str, Any]:
        """Get plugin info."""
        info = super().get_info()
        
        nfl_state = self.nfl_state
        ncaa_state = self.ncaa_fb_state
        
        info.update({
            'nfl_enabled': self.config['nfl']['enabled'],
            'nfl_live_games': len(nfl_state['live_games']),
            'nfl_recent_games': len(nfl_state['recent_games']),
            'nfl_upcoming_games': len(nfl_state['upcoming_games']),
            'ncaa_fb_enabled': self.config['ncaa_fb']['enabled'],
            'ncaa_fb_live_games': len(ncaa_state['live_games']),
            'ncaa_fb_recent_games': len(ncaa_state['recent_games']),
            'ncaa_fb_upcoming_games': len(ncaa_state['upcoming_games']),
            'total_games': (len(nfl_state['live_games']) + len(nfl_state['recent_games']) + 
                           len(nfl_state['upcoming_games']) + len(ncaa_state['live_games']) + 
                           len(ncaa_state['recent_games']) + len(ncaa_state['upcoming_games']))
        })
        return info

    def cleanup(self) -> None:
        """Cleanup resources."""
        self._logo_cache.clear()
        self._season_cache.clear()
        self.logger.info("Football scoreboard plugin cleaned up")
