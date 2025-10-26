"""
Football Scoreboard Plugin for LEDMatrix - Refactored Version

This plugin provides NFL and NCAA FB scoreboard functionality using a modular architecture.
The plugin has been broken down into focused modules for better maintainability.
"""

import logging
import time
from typing import Dict, Any

from PIL import ImageFont

try:
    from src.plugin_system.base_plugin import BasePlugin
    from src.background_data_service import get_background_service
    from src.base_odds_manager import BaseOddsManager
except ImportError:
    BasePlugin = None
    get_background_service = None
    BaseOddsManager = None

# Import our new modules
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import FootballDataFetcher
from game_filter import GameFilter
from scoreboard_renderer import ScoreboardRenderer
from ap_rankings import APRankingsManager

logger = logging.getLogger(__name__)


class FootballScoreboardPlugin(BasePlugin if BasePlugin else object):
    """
    Football scoreboard plugin using modular architecture.
    
    This plugin provides NFL and NCAA FB scoreboard functionality with:
    - Modular data fetching
    - Advanced game filtering
    - AP Top 25/10/5 support
    - Clean rendering system
    """

    def __init__(
        self,
        plugin_id: str,
        config: Dict[str, Any],
        display_manager,
        cache_manager,
        plugin_manager,
    ):
        """Initialize the football scoreboard plugin."""
        if BasePlugin:
            super().__init__(plugin_id, config, display_manager, cache_manager, plugin_manager)
        
        self.plugin_id = plugin_id
        self.config = config
        self.display_manager = display_manager
        self.cache_manager = cache_manager
        self.plugin_manager = plugin_manager
        
        self.logger = logger
        
        # Basic configuration
        self.is_enabled = config.get("enabled", True)
        self.display_width = getattr(display_manager, 'display_width', 128)
        self.display_height = getattr(display_manager, 'display_height', 32)
        
        # League configurations
        self.leagues = {
            "nfl": {
                "enabled": config.get("nfl", {}).get("enabled", False),
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
        
        # Additional settings from old managers
        self.show_records = config.get("show_records", False)
        self.show_ranking = config.get("show_ranking", False)
        self.show_odds = config.get("show_odds", False)
        
        # Initialize odds manager if enabled
        self.odds_manager = None
        if self.show_odds and BaseOddsManager:
            try:
                # Try to get config_manager from cache_manager
                config_manager = getattr(cache_manager, 'config_manager', None)
                self.odds_manager = BaseOddsManager(cache_manager, config_manager)
                self.logger.info("Odds manager initialized")
            except Exception as e:
                self.logger.warning("Could not initialize odds manager: %s", e)
        
        # Team rankings cache (mirrors old managers)
        self._team_rankings_cache = {}
        self._rankings_cache_timestamp = 0
        self._rankings_cache_duration = 3600  # Cache rankings for 1 hour

        # State management
        self.current_games = []
        self.current_game = None
        self.current_game_index = 0 
        self.last_game_switch = 0
        self.last_update = 0
        self.initialized = True
        
        # Live game management
        self.live_games = []
        self.current_live_game_index = 0
        self.last_live_game_switch = 0
        self.live_game_display_duration = float(config.get("live_game_display_duration", 20))
        self.live_update_interval = float(config.get("live_update_interval", 30))
        self.last_live_update = 0
        
        # Game rotation management
        self.current_game_index = 0
        self.last_game_switch = 0
        self.games_list = []  # Filtered list for current display mode
        
        # Mode cycling for NFL and NCAA FB display modes
        self.nfl_display_modes = ["nfl_live", "nfl_recent", "nfl_upcoming"]
        self.ncaa_fb_display_modes = ["ncaa_fb_live", "ncaa_fb_recent", "ncaa_fb_upcoming"]
        
        # Combine all display modes based on enabled leagues
        self.all_display_modes = []
        if self.leagues.get("nfl", {}).get("enabled", False):
            self.all_display_modes.extend(self.nfl_display_modes)
        if self.leagues.get("ncaa_fb", {}).get("enabled", False):
            self.all_display_modes.extend(self.ncaa_fb_display_modes)
        
        # If no leagues enabled, default to NFL
        if not self.all_display_modes:
            self.all_display_modes = self.nfl_display_modes
            
        # Set initial display mode based on available modes
        self.current_display_mode = self.all_display_modes[0]
        self.mode_index = 0
        self.last_mode_switch = 0

        # Load fonts
        self.fonts = self._load_fonts()
        
        # Initialize modules
        self._initialize_modules()
        
        # Warning tracking
        self._no_data_warning_logged = False
        self._last_warning_time = 0
        self._warning_cooldown = 60


        self.logger.info(f"Football scoreboard plugin initialized - {self.display_width}x{self.display_height}")

    def _initialize_modules(self):
        """Initialize all plugin modules."""
        try:
            # Initialize background service
            self.background_service = None
            if get_background_service:
                try:
                    self.background_service = get_background_service(
                        self.cache_manager, max_workers=1
                    )
                    self.logger.info("Background service initialized")
                except Exception as e:
                    self.logger.warning(f"Could not initialize background service: {e}")

            # Initialize AP rankings manager
            self.ap_rankings_manager = APRankingsManager()
            self.logger.info("AP rankings manager initialized")

            # Initialize data fetcher
            self.data_fetcher = FootballDataFetcher(self.cache_manager, self.background_service)
            self.logger.info("Data fetcher initialized")

            # Initialize game filter
            self.game_filter = GameFilter(self.ap_rankings_manager)
            self.logger.info("Game filter initialized")

            # Initialize scoreboard renderer
            self.scoreboard_renderer = ScoreboardRenderer(
                self.display_manager, self.fonts, self.display_width, self.display_height, self.logger
            )
            # Pass additional settings to renderer
            self.scoreboard_renderer.show_records = self.show_records
            self.scoreboard_renderer.show_ranking = self.show_ranking
            self.scoreboard_renderer._team_rankings_cache = self._team_rankings_cache
            self.logger.info("Scoreboard renderer initialized")

        except Exception as e:
            self.logger.error(f"Error initializing modules: {e}")

    def _load_fonts(self):
        """Load fonts used by the scoreboard."""
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
        """Update football game data."""
        if not self.initialized:
            return

        current_time = time.time()
        
        # Check if we need to update live games specifically
        if self._should_update_live_games(current_time):
            self._update_live_games(current_time)
        
        if not self._should_update():
            self.logger.debug("Skipping update - not time yet")
            return


        self.logger.info("Starting football data update...")
        
        # Fetch data for each enabled league
        all_games = []
        for league_key, league_config in self.leagues.items():
            if league_config.get("enabled", False):
                self.logger.info(f"Fetching data for {league_key}...")
                
                # Add league config to each game for filtering
                if league_key == "nfl":
                    data = self.data_fetcher.fetch_nfl_data(use_cache=True)
                else:
                    data = self.data_fetcher.fetch_ncaa_fb_data(use_cache=True)

                if data:
                    games = self.data_fetcher.process_api_response(data, league_key, league_config)
                    all_games.extend(games)
                    self.logger.info(f"Added {len(games)} {league_key} games")

        # Update current games
        self.current_games = all_games
        
        # Update team rankings if enabled
        if self.show_ranking:
            self._update_team_rankings()
        
        # Fetch odds for games if enabled
        if self.show_odds and self.odds_manager:
            self._fetch_odds_for_games(all_games)
        
        # Log summary
        self._log_games_summary()
        
        self.last_update = current_time
        self.logger.info(f"Football data updated: {len(all_games)} total games")

    def _should_update_live_games(self, current_time: float) -> bool:
        """Check if enough time has passed to update live games specifically."""
        return (current_time - self.last_live_update) >= self.live_update_interval

    def _update_live_games(self, current_time: float) -> None:
        """Update live games specifically."""
        self.logger.debug("Updating live games...")
        new_live_games = []
        for game in self.current_games:
            if game.get("is_live", False) or game.get("is_halftime", False):
                league_config = game.get("league_config", {})
                filtering = league_config.get("filtering", {})
                show_favorite_teams_only = filtering.get("show_favorite_teams_only", False)
                if not show_favorite_teams_only or self.game_filter._is_favorite_game(game, league_config.get("favorite_teams", [])):
                    new_live_games.append(game)
        
        if new_live_games != self.live_games:
            self.logger.info(f"Live games updated: {len(new_live_games)} games")
            self.live_games = new_live_games
            self.current_live_game_index = 0
        
        self.last_live_update = current_time

    def _should_update(self) -> bool:
        """Check if enough time has passed since last update."""
        update_interval = float(self.config.get("update_interval_seconds", 300))
        return (time.time() - self.last_update) >= update_interval

    def _log_games_summary(self):
        """Log summary of current games."""
        # Count games by type
        live_count = len([g for g in self.current_games if g.get("is_live", False)])
        recent_count = len([g for g in self.current_games if g.get("is_final", False)])
        upcoming_count = len([g for g in self.current_games if g.get("is_upcoming", False)])
        
        self.logger.info(f"Football Games Summary: {live_count} live, {recent_count} recent, {upcoming_count} upcoming")
    
    def _update_team_rankings(self):
        """Update team rankings cache (mirrors old managers)."""
        try:
            current_time = time.time()
            
            # Check if we need to update rankings
            if (current_time - self._rankings_cache_timestamp) < self._rankings_cache_duration:
                return  # Cache is still valid
            
            # Fetch rankings for both leagues
            total_rankings = 0
            
            # Fetch NCAA FB rankings if NCAA FB is enabled
            if self.leagues.get("ncaa_fb", {}).get("enabled", False):
                ncaa_rankings = self.ap_rankings_manager._fetch_ncaa_fb_rankings()
                if ncaa_rankings:
                    self._team_rankings_cache.update(ncaa_rankings)
                    total_rankings += len(ncaa_rankings)
                    self.logger.info(f"Updated NCAA FB rankings: {len(ncaa_rankings)} teams")
            
            # Fetch NFL rankings if NFL is enabled
            if self.leagues.get("nfl", {}).get("enabled", False):
                nfl_rankings = self.ap_rankings_manager._fetch_nfl_rankings()
                if nfl_rankings:
                    self._team_rankings_cache.update(nfl_rankings)
                    total_rankings += len(nfl_rankings)
                    self.logger.info(f"Updated NFL rankings: {len(nfl_rankings)} teams")
            
            if total_rankings > 0:
                self._rankings_cache_timestamp = current_time
                self.logger.info(f"Updated team rankings: {total_rankings} total teams")
            
            # Update renderer's rankings cache
            if hasattr(self, 'scoreboard_renderer'):
                self.scoreboard_renderer._team_rankings_cache = self._team_rankings_cache
                
        except Exception as e:
            self.logger.error(f"Error updating team rankings: {e}")
    
    def _fetch_odds_for_games(self, games: list) -> None:
        """Fetch odds for all games if enabled (matches old managers)."""
        if not self.show_odds or not self.odds_manager:
            return
        
        try:
            for game in games:
                self._fetch_odds(game)
        except Exception as e:
            self.logger.error(f"Error fetching odds for games: {e}")
    
    def _fetch_odds(self, game: Dict) -> None:
        """Fetch odds for a specific game using BaseOddsManager."""
        try:
            if not self.show_odds or not self.odds_manager:
                return
            
            # Determine sport and league for odds lookup
            league = game.get("league", "nfl")
            if league == "nfl":
                sport = "football"
                league_for_odds = "nfl"
            elif league == "ncaa_fb":
                sport = "football"
                league_for_odds = "ncaa_fb"
            else:
                return
            
            # Determine update interval based on game state
            is_live = game.get('is_live', False)
            update_interval = 60 if is_live else 3600
            
            # Fetch odds using BaseOddsManager
            odds_data = self.odds_manager.get_odds(
                sport=sport,
                league=league_for_odds,
                event_id=game['id'],
                update_interval_seconds=update_interval
            )
            
            if odds_data:
                game['odds'] = odds_data
                self.logger.debug("Attached odds to game %s", game['id'])
                
        except Exception as e:
            self.logger.error("Error fetching odds for game %s: %s", game.get('id', 'N/A'), e)
    

    def display(self, force_clear: bool = False) -> None:
        """Display football games with mode cycling."""
        if not self.is_enabled:
            return


        try:
            current_time = time.time()
            
            # Handle mode cycling for both NFL and NCAA FB
            if current_time - self.last_mode_switch >= self.display_duration:
                self.mode_index = (self.mode_index + 1) % len(self.all_display_modes)
                self.current_display_mode = self.all_display_modes[self.mode_index]
                self.last_mode_switch = current_time
                self.current_game_index = 0
                self.last_game_switch = current_time
                force_clear = True
                self.logger.info(f"Switching to display mode: {self.current_display_mode}")

            # Special handling for live games
            if self.current_display_mode in ["nfl_live", "ncaa_fb_live"]:
                if self.live_games:
                    self.games_list = self.live_games
                    
                    # Handle live game switching
                    if len(self.games_list) > 1 and current_time - self.last_live_game_switch >= self.live_game_display_duration:
                        self.current_live_game_index = (self.current_live_game_index + 1) % len(self.games_list)
                        self.last_live_game_switch = current_time
                        self.current_game_index = self.current_live_game_index
                        force_clear = True
                        self.logger.info(f"Switching to live game {self.current_live_game_index + 1} of {len(self.games_list)}")
                    else:
                        self.current_game_index = self.current_live_game_index
                else:
                    # No live games - skip to next mode
                    self.logger.debug("No live games available, skipping to next mode")
                    self.mode_index = (self.mode_index + 1) % len(self.all_display_modes)
                    self.current_display_mode = self.all_display_modes[self.mode_index]
                    self.last_mode_switch = current_time
                    self.current_game_index = 0
                    self.last_game_switch = current_time
                    force_clear = True
                    self.logger.info(f"No live games, switching to: {self.current_display_mode}")
                    
                    # Filter games for the new mode
                    self.games_list = self.game_filter.filter_games_by_mode(
                        self.current_games, self.current_display_mode, self.leagues
                    )
            else:
                # Regular filtering for non-live modes
                self.games_list = self.game_filter.filter_games_by_mode(
                    self.current_games, self.current_display_mode, self.leagues
                )

            # Handle game rotation within the current mode
            if len(self.games_list) > 1 and current_time - self.last_game_switch >= self.game_display_duration:
                self.current_game_index = (self.current_game_index + 1) % len(self.games_list)
                self.last_game_switch = current_time
                force_clear = True
                
                # Log team switching
                current_game = self.games_list[self.current_game_index]
                away_abbr = current_game.get('away_abbr', 'UNK')
                home_abbr = current_game.get('home_abbr', 'UNK')
                mode_name = self.current_display_mode.replace('nfl_', '').replace('ncaa_fb_', '').title()
                self.logger.info(f"[{mode_name}] Rotating to {away_abbr} vs {home_abbr}")

            # Display current game
            if self.games_list and self.current_game_index < len(self.games_list):
                current_game = self.games_list[self.current_game_index]
                success = self.scoreboard_renderer.render_game(current_game, force_clear)
                if not success:
                    self.logger.warning("Failed to render game")
            else:
                # No games to display - skip to next mode immediately
                self.logger.warning(f"No games available for mode: {self.current_display_mode}")
                self.mode_index = (self.mode_index + 1) % len(self.all_display_modes)
                self.current_display_mode = self.all_display_modes[self.mode_index]
                self.last_mode_switch = current_time
                self.current_game_index = 0
                self.last_game_switch = current_time
                force_clear = True
                self.logger.info(f"No games available, switching to: {self.current_display_mode}")
                
                # Filter games for the new mode and try to display
                self.games_list = self.game_filter.filter_games_by_mode(
                    self.current_games, self.current_display_mode, self.leagues
                )
                
                # If there are games in the new mode, display them
                if self.games_list and self.current_game_index < len(self.games_list):
                    current_game = self.games_list[self.current_game_index]
                    success = self.scoreboard_renderer.render_game(current_game, force_clear)
                    if not success:
                        self.logger.warning("Failed to render game")

        except Exception as e:
            self.logger.error(f"Error in display method: {e}")

    def cleanup(self) -> None:
        """Clean up resources."""
        try:
            if hasattr(self, 'background_service') and self.background_service:
                # Clean up background service if needed
                pass
            self.logger.info("Football scoreboard plugin cleanup completed")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
