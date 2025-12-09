"""
Football Scoreboard Plugin for LEDMatrix - Using Existing Managers

This plugin provides NFL and NCAA FB scoreboard functionality by reusing
the proven, working manager classes from the LEDMatrix core project.
"""

import logging
import time
from typing import Dict, Any, Set, Optional

from PIL import ImageFont

try:
    from src.plugin_system.base_plugin import BasePlugin
    from src.background_data_service import get_background_service
    from src.base_odds_manager import BaseOddsManager
except ImportError:
    BasePlugin = None
    get_background_service = None
    BaseOddsManager = None

# Import the copied manager classes
from nfl_managers import NFLLiveManager, NFLRecentManager, NFLUpcomingManager
from ncaa_fb_managers import (
    NCAAFBLiveManager,
    NCAAFBRecentManager,
    NCAAFBUpcomingManager,
)

logger = logging.getLogger(__name__)


class FootballScoreboardPlugin(BasePlugin if BasePlugin else object):
    """
    Football scoreboard plugin using existing manager classes.

    This plugin provides NFL and NCAA FB scoreboard functionality by
    delegating to the proven manager classes from LEDMatrix core.
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
            super().__init__(
                plugin_id, config, display_manager, cache_manager, plugin_manager
            )

        self.plugin_id = plugin_id
        self.config = config
        self.display_manager = display_manager
        self.cache_manager = cache_manager
        self.plugin_manager = plugin_manager

        self.logger = logger

        # Basic configuration
        self.is_enabled = config.get("enabled", True)
        # Get display dimensions from display_manager properties
        if hasattr(display_manager, 'matrix') and display_manager.matrix is not None:
            self.display_width = display_manager.matrix.width
            self.display_height = display_manager.matrix.height
        else:
            self.display_width = getattr(display_manager, "width", 128)
            self.display_height = getattr(display_manager, "height", 32)

        # League configurations (defaults come from schema via plugin_manager merge)
        # Debug: Log what config we received
        self.logger.debug(f"Football plugin received config keys: {list(config.keys())}")
        self.logger.debug(f"NFL config: {config.get('nfl', {})}")
        
        self.nfl_enabled = config.get("nfl", {}).get("enabled", False)
        self.ncaa_fb_enabled = config.get("ncaa_fb", {}).get("enabled", False)
        
        self.logger.info(f"League enabled states - NFL: {self.nfl_enabled}, NCAA FB: {self.ncaa_fb_enabled}")

        # Global settings
        self.display_duration = float(config.get("display_duration", 30))
        self.game_display_duration = float(config.get("game_display_duration", 15))

        # Live priority per league
        self.nfl_live_priority = self.config.get("nfl", {}).get("live_priority", False)
        self.ncaa_fb_live_priority = self.config.get("ncaa_fb", {}).get(
            "live_priority", False
        )

        # Initialize background service if available
        self.background_service = None
        if get_background_service:
            try:
                self.background_service = get_background_service(
                    self.cache_manager, max_workers=1
                )
                self.logger.info("Background service initialized")
            except Exception as e:
                self.logger.warning(f"Could not initialize background service: {e}")

        # Initialize managers
        self._initialize_managers()

        # Mode cycling
        self.current_mode_index = 0
        self.last_mode_switch = 0
        self.modes = self._get_available_modes()

        self.logger.info(
            f"Football scoreboard plugin initialized - {self.display_width}x{self.display_height}"
        )
        self.logger.info(
            f"NFL enabled: {self.nfl_enabled}, NCAA FB enabled: {self.ncaa_fb_enabled}"
        )

        # Dynamic duration tracking
        self._dynamic_cycle_seen_modes: Set[str] = set()
        self._dynamic_mode_to_manager_key: Dict[str, str] = {}
        self._dynamic_manager_progress: Dict[str, Set[str]] = {}
        self._dynamic_managers_completed: Set[str] = set()
        self._dynamic_cycle_complete = False
        
        # Track current display context for granular dynamic duration
        self._current_display_league: Optional[str] = None  # 'nfl' or 'ncaa_fb'
        self._current_display_mode_type: Optional[str] = None  # 'live', 'recent', 'upcoming'

    def _initialize_managers(self):
        """Initialize all manager instances."""
        try:
            # Create adapted configs for managers
            nfl_config = self._adapt_config_for_manager("nfl")
            ncaa_fb_config = self._adapt_config_for_manager("ncaa_fb")

            # Initialize NFL managers if enabled
            if self.nfl_enabled:
                self.nfl_live = NFLLiveManager(
                    nfl_config, self.display_manager, self.cache_manager
                )
                self.nfl_recent = NFLRecentManager(
                    nfl_config, self.display_manager, self.cache_manager
                )
                self.nfl_upcoming = NFLUpcomingManager(
                    nfl_config, self.display_manager, self.cache_manager
                )
                self.logger.info("NFL managers initialized")

            # Initialize NCAA FB managers if enabled
            if self.ncaa_fb_enabled:
                self.ncaa_fb_live = NCAAFBLiveManager(
                    ncaa_fb_config, self.display_manager, self.cache_manager
                )
                self.ncaa_fb_recent = NCAAFBRecentManager(
                    ncaa_fb_config, self.display_manager, self.cache_manager
                )
                self.ncaa_fb_upcoming = NCAAFBUpcomingManager(
                    ncaa_fb_config, self.display_manager, self.cache_manager
                )
                self.logger.info("NCAA FB managers initialized")

        except Exception as e:
            self.logger.error(f"Error initializing managers: {e}", exc_info=True)

    def _adapt_config_for_manager(self, league: str) -> Dict[str, Any]:
        """
        Adapt plugin config format to manager expected format.

        Plugin uses: nfl: {...}, ncaa_fb: {...}
        Managers expect: nfl_scoreboard: {...}, ncaa_fb_scoreboard: {...}
        """
        league_config = self.config.get(league, {})
        
        # Debug: Log the entire league_config to see what we're actually getting
        self.logger.debug(f"DEBUG: league_config for {league} = {league_config}")

        # Extract nested configurations
        game_limits = league_config.get("game_limits", {})
        display_options = league_config.get("display_options", {})
        filtering = league_config.get("filtering", {})
        display_modes_config = league_config.get("display_modes", {})

        manager_display_modes = {
            f"{league}_live": display_modes_config.get("show_live", True),
            f"{league}_recent": display_modes_config.get("show_recent", True),
            f"{league}_upcoming": display_modes_config.get("show_upcoming", True),
        }

        # Explicitly check if keys exist, not just if they're truthy
        # This handles False values correctly (False is a valid saved value)
        # Priority: filtering dict first (more reliable), then top-level, then default
        if "show_favorite_teams_only" in filtering:
            show_favorites_only = filtering["show_favorite_teams_only"]
        elif "show_favorite_teams_only" in league_config:
            show_favorites_only = league_config["show_favorite_teams_only"]
        elif "favorite_teams_only" in league_config:
            show_favorites_only = league_config["favorite_teams_only"]
        else:
            # Default to False if not specified (schema default is True, but we want False as default)
            show_favorites_only = False
        
        # Debug logging to diagnose config reading issues
        self.logger.debug(
            f"Config reading for {league}: "
            f"league_config.show_favorite_teams_only={league_config.get('show_favorite_teams_only', 'NOT_SET')}, "
            f"filtering.show_favorite_teams_only={filtering.get('show_favorite_teams_only', 'NOT_SET')}, "
            f"final show_favorites_only={show_favorites_only}"
        )

        # Explicitly check if key exists for show_all_live
        # Priority: filtering dict first (more reliable), then top-level, then default
        if "show_all_live" in filtering:
            show_all_live = filtering["show_all_live"]
        elif "show_all_live" in league_config:
            show_all_live = league_config["show_all_live"]
        else:
            # Default to False if not specified
            show_all_live = False
        
        # Debug logging for show_all_live
        self.logger.debug(
            f"Config reading for {league}: "
            f"league_config.show_all_live={league_config.get('show_all_live', 'NOT_SET')}, "
            f"filtering.show_all_live={filtering.get('show_all_live', 'NOT_SET')}, "
            f"final show_all_live={show_all_live}"
        )

        # Create manager config with expected structure
        manager_config = {
            f"{league}_scoreboard": {
                "enabled": league_config.get("enabled", False),
                "favorite_teams": league_config.get("favorite_teams", []),
                "display_modes": manager_display_modes,
                "recent_games_to_show": game_limits.get("recent_games_to_show", 5),
                "upcoming_games_to_show": game_limits.get("upcoming_games_to_show", 10),
                "show_records": display_options.get("show_records", False),
                "show_ranking": display_options.get("show_ranking", False),
                "show_odds": display_options.get("show_odds", False),
                "update_interval_seconds": league_config.get(
                    "update_interval_seconds", 300
                ),
                "live_update_interval": league_config.get("live_update_interval", 30),
                "live_game_duration": league_config.get("live_game_duration", 20),
                "live_priority": league_config.get("live_priority", False),
                "show_favorite_teams_only": show_favorites_only,
                "show_all_live": show_all_live,
                "filtering": filtering,
                "background_service": {
                    "request_timeout": 30,
                    "max_retries": 3,
                    "priority": 2,
                },
            }
        }

        # Add global config - get timezone from cache_manager's config_manager if available
        timezone_str = self.config.get("timezone")
        if not timezone_str and hasattr(self.cache_manager, 'config_manager'):
            timezone_str = self.cache_manager.config_manager.get_timezone()
        if not timezone_str:
            timezone_str = "UTC"
        
        # Get display config from main config if available
        display_config = self.config.get("display", {})
        if not display_config and hasattr(self.cache_manager, 'config_manager'):
            display_config = self.cache_manager.config_manager.get_display_config()
        
        manager_config.update(
            {
                "timezone": timezone_str,
                "display": display_config,
            }
        )
        
        self.logger.debug(f"Using timezone: {timezone_str} for {league} managers")

        return manager_config

    def _get_available_modes(self) -> list:
        """Get list of available display modes based on enabled leagues."""
        modes = []

        def league_modes(league: str) -> Dict[str, bool]:
            league_config = self.config.get(league, {})
            display_modes = league_config.get("display_modes", {})
            return {
                "live": display_modes.get("show_live", True),
                "recent": display_modes.get("show_recent", True),
                "upcoming": display_modes.get("show_upcoming", True),
            }

        if self.nfl_enabled:
            flags = league_modes("nfl")
            prefix = "nfl"
            if flags["live"]:
                modes.append(f"{prefix}_live")
            if flags["recent"]:
                modes.append(f"{prefix}_recent")
            if flags["upcoming"]:
                modes.append(f"{prefix}_upcoming")

        if self.ncaa_fb_enabled:
            flags = league_modes("ncaa_fb")
            prefix = "ncaa_fb"
            if flags["live"]:
                modes.append(f"{prefix}_live")
            if flags["recent"]:
                modes.append(f"{prefix}_recent")
            if flags["upcoming"]:
                modes.append(f"{prefix}_upcoming")

        # Default to NFL if no leagues enabled
        if not modes:
            modes = ["nfl_live", "nfl_recent", "nfl_upcoming"]

        return modes

    def _get_current_manager(self):
        """Get the current manager based on the current mode."""
        if not self.modes:
            return None

        current_mode = self.modes[self.current_mode_index]

        if current_mode.startswith("nfl_"):
            if not self.nfl_enabled:
                return None
            mode_type = current_mode.split("_", 1)[1]  # "live", "recent", "upcoming"
            if mode_type == "live":
                return self.nfl_live
            elif mode_type == "recent":
                return self.nfl_recent
            elif mode_type == "upcoming":
                return self.nfl_upcoming

        elif current_mode.startswith("ncaa_fb_"):
            if not self.ncaa_fb_enabled:
                return None
            mode_type = current_mode.split("_", 2)[2]  # "live", "recent", "upcoming"
            if mode_type == "live":
                return self.ncaa_fb_live
            elif mode_type == "recent":
                return self.ncaa_fb_recent
            elif mode_type == "upcoming":
                return self.ncaa_fb_upcoming

        return None

    def update(self) -> None:
        """Update football game data."""
        if not self.is_enabled:
            return

        try:
            # Update NFL managers if enabled
            if self.nfl_enabled:
                self.nfl_live.update()
                self.nfl_recent.update()
                self.nfl_upcoming.update()

            # Update NCAA FB managers if enabled
            if self.ncaa_fb_enabled:
                self.ncaa_fb_live.update()
                self.ncaa_fb_recent.update()
                self.ncaa_fb_upcoming.update()

        except Exception as e:
            self.logger.error(f"Error updating managers: {e}")

    def display(self, display_mode: str = None, force_clear: bool = False) -> bool:
        """Display football games with mode cycling.
        
        Args:
            display_mode: Optional mode name (e.g., 'football_live', 'football_recent', 'football_upcoming').
                         If provided, displays that specific mode. If None, uses internal mode cycling.
            force_clear: If True, clear display before rendering
        """
        if not self.is_enabled:
            return False

        try:
            # If display_mode is provided, use it to determine which manager to call
            if display_mode:
                self.logger.debug(f"Display called with mode: {display_mode}")
                # Map external mode names to internal managers
                # External modes: football_live, football_recent, football_upcoming
                # Internal modes: nfl_live, nfl_recent, nfl_upcoming, ncaa_fb_live, etc.
                
                # Extract the mode type (live, recent, upcoming)
                mode_type = None
                if display_mode.endswith('_live'):
                    mode_type = 'live'
                elif display_mode.endswith('_recent'):
                    mode_type = 'recent'
                elif display_mode.endswith('_upcoming'):
                    mode_type = 'upcoming'
                
                if not mode_type:
                    self.logger.warning(f"Unknown display_mode: {display_mode}")
                    return False
                
                self.logger.debug(f"Mode type: {mode_type}, NFL enabled: {self.nfl_enabled}, NCAA FB enabled: {self.ncaa_fb_enabled}")
                
                # Determine which manager to use based on enabled leagues
                # For live mode, prioritize leagues with live content and live_priority enabled
                managers_to_try = []
                
                if mode_type == 'live':
                    # Ensure managers are updated before checking for live games
                    if self.nfl_enabled and hasattr(self, 'nfl_live'):
                        try:
                            self.nfl_live.update()
                        except Exception as e:
                            self.logger.debug(f"Error updating NFL live manager: {e}")
                    
                    if self.ncaa_fb_enabled and hasattr(self, 'ncaa_fb_live'):
                        try:
                            self.ncaa_fb_live.update()
                        except Exception as e:
                            self.logger.debug(f"Error updating NCAA FB live manager: {e}")
                    
                    # Check NFL first (highest priority) - use same logic as has_live_content()
                    if (self.nfl_enabled and self.nfl_live_priority and 
                        hasattr(self, 'nfl_live')):
                        live_games = getattr(self.nfl_live, 'live_games', [])
                        if live_games:
                            # Filter out any games that are final or appear over
                            live_games = [g for g in live_games if not g.get('is_final', False)]
                            # Additional validation using helper method if available
                            if hasattr(self.nfl_live, '_is_game_really_over'):
                                live_games = [g for g in live_games 
                                             if not self.nfl_live._is_game_really_over(g)]
                            
                            if live_games:
                                # If favorite teams are configured, only show if there are live games for favorite teams
                                favorite_teams = getattr(self.nfl_live, 'favorite_teams', [])
                                if favorite_teams:
                                    has_favorite_live = any(
                                        game.get('home_abbr') in favorite_teams
                                        or game.get('away_abbr') in favorite_teams
                                        for game in live_games
                                    )
                                    if has_favorite_live:
                                        managers_to_try.append(self.nfl_live)
                                        self.logger.debug("NFL has live games with favorite teams - prioritizing NFL")
                                else:
                                    # No favorite teams configured, any live game counts
                                    managers_to_try.append(self.nfl_live)
                                    self.logger.debug("NFL has live games - prioritizing NFL")
                    
                    # Check NCAA FB - use same logic as has_live_content()
                    if (self.ncaa_fb_enabled and self.ncaa_fb_live_priority and 
                        hasattr(self, 'ncaa_fb_live')):
                        live_games = getattr(self.ncaa_fb_live, 'live_games', [])
                        if live_games:
                            favorite_teams = getattr(self.ncaa_fb_live, 'favorite_teams', [])
                            if favorite_teams:
                                has_favorite_live = any(
                                    game.get('home_abbr') in favorite_teams
                                    or game.get('away_abbr') in favorite_teams
                                    for game in live_games
                                )
                                if has_favorite_live:
                                    managers_to_try.append(self.ncaa_fb_live)
                                    self.logger.debug("NCAA FB has live games with favorite teams")
                            else:
                                # No favorite teams configured, any live game counts
                                managers_to_try.append(self.ncaa_fb_live)
                                self.logger.debug("NCAA FB has live games")
                    
                    # Fallback: if no live content found, show any enabled live manager (NFL first)
                    if not managers_to_try:
                        if self.nfl_enabled and hasattr(self, 'nfl_live'):
                            managers_to_try.append(self.nfl_live)
                            self.logger.debug("No live content found, falling back to NFL live manager")
                        if self.ncaa_fb_enabled and hasattr(self, 'ncaa_fb_live'):
                            managers_to_try.append(self.ncaa_fb_live)
                            self.logger.debug("No live content found, falling back to NCAA FB live manager")
                else:
                    # For recent and upcoming modes, use standard priority order
                    # NFL > NCAA FB
                    if self.nfl_enabled:
                        if mode_type == 'recent' and hasattr(self, 'nfl_recent'):
                            managers_to_try.append(self.nfl_recent)
                        elif mode_type == 'upcoming' and hasattr(self, 'nfl_upcoming'):
                            managers_to_try.append(self.nfl_upcoming)
                    
                    if self.ncaa_fb_enabled:
                        if mode_type == 'recent' and hasattr(self, 'ncaa_fb_recent'):
                            managers_to_try.append(self.ncaa_fb_recent)
                        elif mode_type == 'upcoming' and hasattr(self, 'ncaa_fb_upcoming'):
                            managers_to_try.append(self.ncaa_fb_upcoming)
                
                # Try each manager until one returns True (has content)
                for current_manager in managers_to_try:
                    if current_manager:
                        # Track which league we're displaying for granular dynamic duration
                        if current_manager == self.nfl_live or current_manager == self.nfl_recent or current_manager == self.nfl_upcoming:
                            self._current_display_league = 'nfl'
                        elif current_manager == self.ncaa_fb_live or current_manager == self.ncaa_fb_recent or current_manager == self.ncaa_fb_upcoming:
                            self._current_display_league = 'ncaa_fb'
                        self._current_display_mode_type = mode_type
                        
                        result = current_manager.display(force_clear)
                        # If display returned True, we have content to show
                        if result is True:
                            try:
                                self._record_dynamic_progress(current_manager)
                            except Exception as progress_err:  # pylint: disable=broad-except
                                self.logger.debug(
                                    "Dynamic progress tracking failed: %s", progress_err
                                )
                            self._evaluate_dynamic_cycle_completion()
                            return result
                        # If result is False, try next manager
                        elif result is False:
                            continue
                        # If result is None or other, assume success
                        else:
                            try:
                                self._record_dynamic_progress(current_manager)
                            except Exception as progress_err:  # pylint: disable=broad-except
                                self.logger.debug(
                                    "Dynamic progress tracking failed: %s", progress_err
                                )
                            self._evaluate_dynamic_cycle_completion()
                            return True
                
                # No manager had content
                if not managers_to_try:
                    # Enhanced diagnostic logging
                    nfl_has_manager = hasattr(self, 'nfl_live') if mode_type == 'live' else (hasattr(self, 'nfl_recent') if mode_type == 'recent' else hasattr(self, 'nfl_upcoming'))
                    ncaa_fb_has_manager = hasattr(self, 'ncaa_fb_live') if mode_type == 'live' else (hasattr(self, 'ncaa_fb_recent') if mode_type == 'recent' else hasattr(self, 'ncaa_fb_upcoming'))
                    self.logger.warning(
                        f"No managers available for mode: {display_mode} "
                        f"(NFL enabled: {self.nfl_enabled}, has manager: {nfl_has_manager}; "
                        f"NCAA FB enabled: {self.ncaa_fb_enabled}, has manager: {ncaa_fb_has_manager})"
                    )
                else:
                    self.logger.debug(f"No content available for mode: {display_mode} after trying {len(managers_to_try)} manager(s)")
                
                # Clear display when no content available (safety measure)
                if force_clear:
                    try:
                        self.display_manager.clear()
                        self.display_manager.update_display()
                    except Exception as clear_err:
                        self.logger.debug(f"Error clearing display when no content: {clear_err}")
                return False
            
            # Fall back to internal mode cycling if no display_mode provided
            current_time = time.time()

            # Check if we should stay on live mode
            should_stay_on_live = False
            if self.has_live_content():
                # Get current mode name
                current_mode = self.modes[self.current_mode_index] if self.modes else None
                # If we're on a live mode, stay there
                if current_mode and current_mode.endswith('_live'):
                    should_stay_on_live = True
                # If we're not on a live mode but have live content, switch to it
                elif not (current_mode and current_mode.endswith('_live')):
                    # Find the first live mode
                    for i, mode in enumerate(self.modes):
                        if mode.endswith('_live'):
                            self.current_mode_index = i
                            force_clear = True
                            self.last_mode_switch = current_time
                            self.logger.info(f"Live content detected - switching to display mode: {mode}")
                            break

            # Handle mode cycling only if not staying on live
            if not should_stay_on_live and current_time - self.last_mode_switch >= self.display_duration:
                self.current_mode_index = (self.current_mode_index + 1) % len(
                    self.modes
                )
                self.last_mode_switch = current_time
                force_clear = True

                current_mode = self.modes[self.current_mode_index]
                self.logger.info(f"Switching to display mode: {current_mode}")

            # Get current manager and display
            current_manager = self._get_current_manager()
            if current_manager:
                # Track which league/mode we're displaying for granular dynamic duration
                current_mode = self.modes[self.current_mode_index] if self.modes else None
                if current_mode:
                    if current_mode.startswith("nfl_"):
                        self._current_display_league = 'nfl'
                        self._current_display_mode_type = current_mode.split("_", 1)[1]
                    elif current_mode.startswith("ncaa_fb_"):
                        self._current_display_league = 'ncaa_fb'
                        self._current_display_mode_type = current_mode.split("_", 2)[2]
                
                result = current_manager.display(force_clear)
                if result is not False:
                    try:
                        self._record_dynamic_progress(current_manager)
                    except Exception as progress_err:  # pylint: disable=broad-except
                        self.logger.debug(
                            "Dynamic progress tracking failed: %s", progress_err
                        )
                else:
                    # Manager returned False (no content) - ensure display is cleared
                    # This is a safety measure in case the manager didn't clear it
                    if force_clear:
                        try:
                            self.display_manager.clear()
                            self.display_manager.update_display()
                        except Exception as clear_err:
                            self.logger.debug(f"Error clearing display when manager returned False: {clear_err}")
                self._evaluate_dynamic_cycle_completion()
                return result
            else:
                self.logger.warning("No manager available for current mode")
                return False

        except Exception as e:
            self.logger.error(f"Error in display method: {e}")
            return False

    def has_live_priority(self) -> bool:
        if not self.is_enabled:
            return False
        return (
            (self.nfl_enabled and self.nfl_live_priority)
            or (self.ncaa_fb_enabled and self.ncaa_fb_live_priority)
        )

    def has_live_content(self) -> bool:
        if not self.is_enabled:
            return False

        # Check NFL live content
        nfl_live = False
        if (
            self.nfl_enabled
            and self.nfl_live_priority
            and hasattr(self, "nfl_live")
        ):
            live_games = getattr(self.nfl_live, "live_games", [])
            if live_games:
                # Filter out any games that are final or appear over
                live_games = [g for g in live_games if not g.get("is_final", False)]
                # Additional validation using helper method if available
                if hasattr(self.nfl_live, "_is_game_really_over"):
                    live_games = [g for g in live_games if not self.nfl_live._is_game_really_over(g)]
                
                if live_games:
                    # If favorite teams are configured, only return True if there are live games for favorite teams
                    favorite_teams = getattr(self.nfl_live, "favorite_teams", [])
                    if favorite_teams:
                        # Check if any live game involves a favorite team
                        nfl_live = any(
                            game.get("home_abbr") in favorite_teams
                            or game.get("away_abbr") in favorite_teams
                            for game in live_games
                        )
                    else:
                        # No favorite teams configured, return True if any live games exist
                        nfl_live = True

        # Check NCAA FB live content
        ncaa_live = False
        if (
            self.ncaa_fb_enabled
            and self.ncaa_fb_live_priority
            and hasattr(self, "ncaa_fb_live")
        ):
            live_games = getattr(self.ncaa_fb_live, "live_games", [])
            if live_games:
                # Filter out any games that are final or appear over
                live_games = [g for g in live_games if not g.get("is_final", False)]
                # Additional validation using helper method if available
                if hasattr(self.ncaa_fb_live, "_is_game_really_over"):
                    live_games = [g for g in live_games if not self.ncaa_fb_live._is_game_really_over(g)]
                
                if live_games:
                    # If favorite teams are configured, only return True if there are live games for favorite teams
                    favorite_teams = getattr(self.ncaa_fb_live, "favorite_teams", [])
                    if favorite_teams:
                        # Check if any live game involves a favorite team
                        ncaa_live = any(
                            game.get("home_abbr") in favorite_teams
                            or game.get("away_abbr") in favorite_teams
                            for game in live_games
                        )
                    else:
                        # No favorite teams configured, return True if any live games exist
                        ncaa_live = True

        return nfl_live or ncaa_live

    def get_live_modes(self) -> list:
        """
        Return the registered plugin mode name(s) that have live content.
        
        This should return the mode names as registered in manifest.json, not internal
        mode names. The plugin is registered with "football_live", "football_recent", "football_upcoming".
        """
        if not self.is_enabled:
            return []

        # Check if any league has live content
        has_any_live = self.has_live_content()
        
        if has_any_live:
            # Return the registered plugin mode name, not internal mode names
            # The plugin is registered with "football_live" in manifest.json
            return ["football_live"]
        
        return []

    def get_info(self) -> Dict[str, Any]:
        """Get plugin information."""
        try:
            current_manager = self._get_current_manager()
            current_mode = self.modes[self.current_mode_index] if self.modes else "none"

            info = {
                "plugin_id": self.plugin_id,
                "name": "Football Scoreboard",
                "version": "2.0.5",
                "enabled": self.is_enabled,
                "display_size": f"{self.display_width}x{self.display_height}",
                "nfl_enabled": self.nfl_enabled,
                "ncaa_fb_enabled": self.ncaa_fb_enabled,
                "current_mode": current_mode,
                "available_modes": self.modes,
                "display_duration": self.display_duration,
                "game_display_duration": self.game_display_duration,
                "live_priority": {
                    "nfl": self.nfl_enabled and self.nfl_live_priority,
                    "ncaa_fb": self.ncaa_fb_enabled and self.ncaa_fb_live_priority,
                },
                "show_records": getattr(current_manager, "mode_config", {}).get(
                    "show_records"
                )
                if current_manager
                else None,
                "show_ranking": getattr(current_manager, "mode_config", {}).get(
                    "show_ranking"
                )
                if current_manager
                else None,
                "show_odds": getattr(current_manager, "mode_config", {}).get(
                    "show_odds"
                )
                if current_manager
                else None,
                "managers_initialized": {
                    "nfl_live": hasattr(self, "nfl_live"),
                    "nfl_recent": hasattr(self, "nfl_recent"),
                    "nfl_upcoming": hasattr(self, "nfl_upcoming"),
                    "ncaa_fb_live": hasattr(self, "ncaa_fb_live"),
                    "ncaa_fb_recent": hasattr(self, "ncaa_fb_recent"),
                    "ncaa_fb_upcoming": hasattr(self, "ncaa_fb_upcoming"),
                },
            }

            # Add manager-specific info if available
            if current_manager and hasattr(current_manager, "get_info"):
                try:
                    manager_info = current_manager.get_info()
                    info["current_manager_info"] = manager_info
                except Exception as e:
                    info["current_manager_info"] = f"Error getting manager info: {e}"

            return info

        except Exception as e:
            self.logger.error(f"Error getting plugin info: {e}")
            return {
                "plugin_id": self.plugin_id,
                "name": "Football Scoreboard",
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # Dynamic duration hooks
    # ------------------------------------------------------------------
    def reset_cycle_state(self) -> None:
        """Reset dynamic cycle tracking."""
        super().reset_cycle_state()
        self._dynamic_cycle_seen_modes.clear()
        self._dynamic_mode_to_manager_key.clear()
        self._dynamic_manager_progress.clear()
        self._dynamic_managers_completed.clear()
        self._dynamic_cycle_complete = False

    def is_cycle_complete(self) -> bool:
        """Report whether the plugin has shown a full cycle of content."""
        if not self._dynamic_feature_enabled():
            return True
        self._evaluate_dynamic_cycle_completion()
        return self._dynamic_cycle_complete

    def _dynamic_feature_enabled(self) -> bool:
        """Return True when dynamic duration should be active."""
        if not self.is_enabled:
            return False
        return self.supports_dynamic_duration()
    
    def supports_dynamic_duration(self) -> bool:
        """
        Check if dynamic duration is enabled for the current display context.
        Checks granular settings: per-league/per-mode > per-mode > per-league > global.
        """
        if not self.is_enabled:
            return False
        
        # If no current display context, return False (no global fallback)
        if not self._current_display_league or not self._current_display_mode_type:
            return False
        
        league = self._current_display_league
        mode_type = self._current_display_mode_type
        
        # Check per-league/per-mode setting first (most specific)
        league_config = self.config.get(league, {})
        league_dynamic = league_config.get("dynamic_duration", {})
        league_modes = league_dynamic.get("modes", {})
        mode_config = league_modes.get(mode_type, {})
        if "enabled" in mode_config:
            return bool(mode_config.get("enabled", False))
        
        # Check per-league setting
        if "enabled" in league_dynamic:
            return bool(league_dynamic.get("enabled", False))
        
        # No global fallback - return False
        return False
    
    def get_dynamic_duration_cap(self) -> Optional[float]:
        """
        Get dynamic duration cap for the current display context.
        Checks granular settings: per-league/per-mode > per-mode > per-league > global.
        """
        if not self.is_enabled:
            return None
        
        # If no current display context, return None (no global fallback)
        if not self._current_display_league or not self._current_display_mode_type:
            return None
        
        league = self._current_display_league
        mode_type = self._current_display_mode_type
        
        # Check per-league/per-mode setting first (most specific)
        league_config = self.config.get(league, {})
        league_dynamic = league_config.get("dynamic_duration", {})
        league_modes = league_dynamic.get("modes", {})
        mode_config = league_modes.get(mode_type, {})
        if "max_duration_seconds" in mode_config:
            try:
                cap = float(mode_config.get("max_duration_seconds"))
                if cap > 0:
                    return cap
            except (TypeError, ValueError):
                pass
        
        # Check per-league setting
        if "max_duration_seconds" in league_dynamic:
            try:
                cap = float(league_dynamic.get("max_duration_seconds"))
                if cap > 0:
                    return cap
            except (TypeError, ValueError):
                pass
        
        # No global fallback - return None
        return None

    def _get_manager_for_mode(self, mode_name: str):
        """Resolve manager instance for a given display mode."""
        if mode_name.startswith("nfl_"):
            if not self.nfl_enabled:
                return None
            suffix = mode_name.split("_", 1)[1]
            if suffix == "live":
                return getattr(self, "nfl_live", None)
            if suffix == "recent":
                return getattr(self, "nfl_recent", None)
            if suffix == "upcoming":
                return getattr(self, "nfl_upcoming", None)
        elif mode_name.startswith("ncaa_fb_"):
            if not self.ncaa_fb_enabled:
                return None
            suffix = mode_name[len("ncaa_fb_") :]
            if suffix == "live":
                return getattr(self, "ncaa_fb_live", None)
            if suffix == "recent":
                return getattr(self, "ncaa_fb_recent", None)
            if suffix == "upcoming":
                return getattr(self, "ncaa_fb_upcoming", None)
        return None

    def _record_dynamic_progress(self, current_manager) -> None:
        """Track progress through managers/games for dynamic duration."""
        if not self._dynamic_feature_enabled() or not self.modes:
            self._dynamic_cycle_complete = True
            return

        current_mode = self.modes[self.current_mode_index]
        self._dynamic_cycle_seen_modes.add(current_mode)

        manager_key = self._build_manager_key(current_mode, current_manager)
        self._dynamic_mode_to_manager_key[current_mode] = manager_key

        total_games = self._get_total_games_for_manager(current_manager)
        if total_games <= 1:
            # Single (or no) game - treat as complete once visited
            self._dynamic_managers_completed.add(manager_key)
            return

        current_index = getattr(current_manager, "current_game_index", None)
        if current_index is None:
            # Fall back to zero if the manager does not expose an index
            current_index = 0
        identifier = f"index-{current_index}"

        progress_set = self._dynamic_manager_progress.setdefault(manager_key, set())
        progress_set.add(identifier)

        # Drop identifiers that no longer exist if game list shrinks
        valid_identifiers = {f"index-{idx}" for idx in range(total_games)}
        progress_set.intersection_update(valid_identifiers)

        if len(progress_set) >= total_games:
            self._dynamic_managers_completed.add(manager_key)

    def _evaluate_dynamic_cycle_completion(self) -> None:
        """Determine whether all enabled modes have completed their cycles."""
        if not self._dynamic_feature_enabled():
            self._dynamic_cycle_complete = True
            return

        if not self.modes:
            self._dynamic_cycle_complete = True
            return

        required_modes = [mode for mode in self.modes if mode]
        if not required_modes:
            self._dynamic_cycle_complete = True
            return

        for mode_name in required_modes:
            if mode_name not in self._dynamic_cycle_seen_modes:
                self._dynamic_cycle_complete = False
                return

            manager_key = self._dynamic_mode_to_manager_key.get(mode_name)
            if not manager_key:
                self._dynamic_cycle_complete = False
                return

            if manager_key not in self._dynamic_managers_completed:
                manager = self._get_manager_for_mode(mode_name)
                total_games = self._get_total_games_for_manager(manager)
                if total_games <= 1:
                    self._dynamic_managers_completed.add(manager_key)
                else:
                    self._dynamic_cycle_complete = False
                    return

        self._dynamic_cycle_complete = True

    @staticmethod
    def _build_manager_key(mode_name: str, manager) -> str:
        manager_name = manager.__class__.__name__ if manager else "None"
        return f"{mode_name}:{manager_name}"

    @staticmethod
    def _get_total_games_for_manager(manager) -> int:
        if manager is None:
            return 0
        for attr in ("live_games", "games_list", "recent_games", "upcoming_games"):
            value = getattr(manager, attr, None)
            if isinstance(value, list):
                return len(value)
        return 0

    def cleanup(self) -> None:
        """Clean up resources."""
        try:
            if hasattr(self, "background_service") and self.background_service:
                # Clean up background service if needed
                pass
            self.logger.info("Football scoreboard plugin cleanup completed")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
