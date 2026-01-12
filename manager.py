"""
Football Scoreboard Plugin for LEDMatrix - Using Existing Managers

This plugin provides NFL and NCAA FB scoreboard functionality by reusing
the proven, working manager classes from the LEDMatrix core project.

Supports two display modes:
- Switch Mode: Display one game at a time with timed transitions
- Scroll Mode: High-FPS horizontal scrolling of all games with league separators
"""

import logging
import time
from typing import Dict, Any, Set, Optional, Tuple, List

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

# Import scroll display components
try:
    from scroll_display import ScrollDisplayManager
    SCROLL_AVAILABLE = True
except ImportError:
    ScrollDisplayManager = None
    SCROLL_AVAILABLE = False

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
        
        # Display mode settings per league and game type
        self._display_mode_settings = self._parse_display_mode_settings()

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
        
        # Initialize scroll display manager if available
        self._scroll_manager: Optional[ScrollDisplayManager] = None
        if SCROLL_AVAILABLE and ScrollDisplayManager:
            try:
                self._scroll_manager = ScrollDisplayManager(
                    self.display_manager,
                    self.config,
                    self.logger
                )
                self.logger.info("Scroll display manager initialized")
            except Exception as e:
                self.logger.warning(f"Could not initialize scroll display manager: {e}")
                self._scroll_manager = None
        else:
            self.logger.debug("Scroll mode not available - ScrollDisplayManager not imported")
        
        # Track current scroll state
        self._scroll_active: Dict[str, bool] = {}  # {game_type: is_active}
        self._scroll_prepared: Dict[str, bool] = {}  # {game_type: is_prepared}

        # Enable high-FPS mode for scroll display (allows 100+ FPS scrolling)
        # This signals to the display controller to use high-FPS loop (8ms = 125 FPS)
        self.enable_scrolling = self._scroll_manager is not None
        if self.enable_scrolling:
            self.logger.info("High-FPS scrolling enabled for football scoreboard")

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
        # Track when single-game managers were first seen to ensure full duration
        self._single_game_manager_start_times: Dict[str, float] = {}
        # Track when each game ID was first seen to ensure full per-game duration
        # Using game IDs instead of indices prevents start time resets when game order changes
        self._game_id_start_times: Dict[str, Dict[str, float]] = {}  # {manager_key: {game_id: start_time}}
        # Track which managers were actually used for each display mode
        self._display_mode_to_managers: Dict[str, Set[str]] = {}  # {display_mode: {manager_key, ...}}
        
        # Track current display context for granular dynamic duration
        self._current_display_league: Optional[str] = None  # 'nfl' or 'ncaa_fb'
        self._current_display_mode_type: Optional[str] = None  # 'live', 'recent', 'upcoming'
        
        # Throttle logging for has_live_content() when returning False
        self._last_live_content_false_log: float = 0.0  # Timestamp of last False log
        self._live_content_log_interval: float = 60.0  # Log False results every 60 seconds
        
        # Track last display mode to detect when we return after being away
        self._last_display_mode: Optional[str] = None  # Track previous display mode
        self._last_display_mode_time: float = 0.0  # When we last saw this mode
        self._current_active_display_mode: Optional[str] = None  # Currently active external display mode
        
        # Sticky manager tracking - ensures we complete all games from one league before switching
        self._sticky_manager_per_mode: Dict[str, Any] = {}  # {display_mode: manager_instance}
        self._sticky_manager_start_time: Dict[str, float] = {}  # {display_mode: timestamp}

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
                "recent_game_duration": league_config.get(
                    "recent_game_duration",
                    self.config.get("game_display_duration", 15)
                ),
                "upcoming_game_duration": league_config.get(
                    "upcoming_game_duration",
                    self.config.get("game_display_duration", 15)
                ),
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
    
    def _parse_display_mode_settings(self) -> Dict[str, Dict[str, str]]:
        """
        Parse display mode settings from config.
        
        Returns:
            Dict mapping league -> game_type -> display_mode ('switch' or 'scroll')
            e.g., {'nfl': {'live': 'switch', 'recent': 'scroll', 'upcoming': 'scroll'}}
        """
        settings = {}
        
        for league in ['nfl', 'ncaa_fb']:
            league_config = self.config.get(league, {})
            display_modes_config = league_config.get("display_modes", {})
            
            settings[league] = {
                'live': display_modes_config.get('live_display_mode', 'switch'),
                'recent': display_modes_config.get('recent_display_mode', 'switch'),
                'upcoming': display_modes_config.get('upcoming_display_mode', 'switch'),
            }
            
            self.logger.debug(f"Display mode settings for {league}: {settings[league]}")
        
        return settings
    
    def _get_display_mode(self, league: str, game_type: str) -> str:
        """
        Get the display mode for a specific league and game type.
        
        Args:
            league: 'nfl' or 'ncaa_fb'
            game_type: 'live', 'recent', or 'upcoming'
            
        Returns:
            'switch' or 'scroll'
        """
        return self._display_mode_settings.get(league, {}).get(game_type, 'switch')
    
    def _should_use_scroll_mode(self, mode_type: str) -> bool:
        """
        Check if ANY enabled league should use scroll mode for this game type.
        
        This determines if we should collect games for scrolling or use switch mode.
        
        Args:
            mode_type: 'live', 'recent', or 'upcoming'
            
        Returns:
            True if at least one enabled league uses scroll mode for this game type
        """
        if self.nfl_enabled and self._get_display_mode('nfl', mode_type) == 'scroll':
            return True
        if self.ncaa_fb_enabled and self._get_display_mode('ncaa_fb', mode_type) == 'scroll':
            return True
        return False
    
    def _collect_games_for_scroll(
        self, 
        mode_type: str, 
        live_priority_active: bool = False
    ) -> Tuple[List[Dict], List[str]]:
        """
        Collect all games from enabled leagues for scroll mode.
        
        Args:
            mode_type: 'live', 'recent', or 'upcoming'
            live_priority_active: If True, only include live games
            
        Returns:
            Tuple of (games list with league info, list of leagues included)
        """
        games = []
        leagues = []
        
        # Collect NFL games if enabled and using scroll mode
        if self.nfl_enabled and self._get_display_mode('nfl', mode_type) == 'scroll':
            nfl_manager = self._get_manager_for_league_mode('nfl', mode_type)
            if nfl_manager:
                nfl_games = self._get_games_from_manager(nfl_manager, mode_type)
                if nfl_games:
                    # Add league info to each game
                    for game in nfl_games:
                        game['league'] = 'nfl'
                    games.extend(nfl_games)
                    if 'nfl' not in leagues:
                        leagues.append('nfl')
                    self.logger.debug(f"Collected {len(nfl_games)} NFL {mode_type} games for scroll")
        
        # Collect NCAA FB games if enabled and using scroll mode
        if self.ncaa_fb_enabled and self._get_display_mode('ncaa_fb', mode_type) == 'scroll':
            ncaa_manager = self._get_manager_for_league_mode('ncaa_fb', mode_type)
            if ncaa_manager:
                ncaa_games = self._get_games_from_manager(ncaa_manager, mode_type)
                if ncaa_games:
                    # Add league info to each game
                    for game in ncaa_games:
                        game['league'] = 'ncaa_fb'
                    games.extend(ncaa_games)
                    if 'ncaa_fb' not in leagues:
                        leagues.append('ncaa_fb')
                    self.logger.debug(f"Collected {len(ncaa_games)} NCAA FB {mode_type} games for scroll")
        
        # If live priority is active, filter to only live games
        if live_priority_active and mode_type == 'live':
            games = [g for g in games if g.get('is_live', False) and not g.get('is_final', False)]
            self.logger.debug(f"Live priority active: filtered to {len(games)} live games")
        
        return games, leagues
    
    def _get_games_from_manager(self, manager, mode_type: str) -> List[Dict]:
        """Get games list from a manager based on mode type."""
        if mode_type == 'live':
            return list(getattr(manager, 'live_games', []) or [])
        elif mode_type == 'recent':
            # Try games_list first (used by recent managers), then recent_games
            games = getattr(manager, 'games_list', None)
            if games is None:
                games = getattr(manager, 'recent_games', [])
            return list(games or [])
        elif mode_type == 'upcoming':
            # Try games_list first (used by upcoming managers), then upcoming_games
            games = getattr(manager, 'games_list', None)
            if games is None:
                games = getattr(manager, 'upcoming_games', [])
            return list(games or [])
        return []
    
    def _get_rankings_cache(self) -> Dict[str, int]:
        """Get combined team rankings cache from all managers."""
        rankings = {}
        
        # Try to get rankings from each manager
        for manager_attr in ['nfl_live', 'nfl_recent', 'nfl_upcoming', 
                            'ncaa_fb_live', 'ncaa_fb_recent', 'ncaa_fb_upcoming']:
            manager = getattr(self, manager_attr, None)
            if manager:
                manager_rankings = getattr(manager, '_team_rankings_cache', {})
                if manager_rankings:
                    rankings.update(manager_rankings)
        
        return rankings

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

    def _ensure_manager_updated(self, manager) -> None:
        """Trigger an update when the delegated manager is stale."""
        last_update = getattr(manager, "last_update", None)
        update_interval = getattr(manager, "update_interval", None)
        if last_update is None or update_interval is None:
            return

        interval = update_interval
        no_data_interval = getattr(manager, "no_data_interval", None)
        live_games = getattr(manager, "live_games", None)
        if no_data_interval and not live_games:
            interval = no_data_interval

        try:
            if interval and time.time() - last_update >= interval:
                manager.update()
        except Exception as exc:
            self.logger.debug(f"Auto-refresh failed for manager {manager}: {exc}")

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

    def _apply_sticky_manager_logic(self, display_mode: str, managers_to_try: list) -> list:
        """Apply sticky manager logic to filter managers list.
        
        Args:
            display_mode: External display mode name
            managers_to_try: List of managers to try
            
        Returns:
            Filtered list of managers (only sticky manager if exists and available)
        """
        sticky_manager = self._sticky_manager_per_mode.get(display_mode)
        
        self.logger.info(
            f"Sticky manager check for {display_mode}: "
            f"sticky={sticky_manager.__class__.__name__ if sticky_manager else None}, "
            f"available_managers={[m.__class__.__name__ for m in managers_to_try if m]}"
        )
        
        if sticky_manager and sticky_manager in managers_to_try:
            self.logger.info(
                f"Using sticky manager {sticky_manager.__class__.__name__} for {display_mode} - "
                "RESTRICTING to this manager only"
            )
            return [sticky_manager]
        
        # No sticky manager or not in list - clean up if needed
        if sticky_manager:
            self.logger.info(
                f"Sticky manager {sticky_manager.__class__.__name__} no longer available for {display_mode}, "
                f"selecting new one from {len(managers_to_try)} options"
            )
            self._sticky_manager_per_mode.pop(display_mode, None)
            self._sticky_manager_start_time.pop(display_mode, None)
        else:
            self.logger.info(
                f"No sticky manager yet for {display_mode}, will select from {len(managers_to_try)} available managers"
            )
        
        return managers_to_try

    def _try_manager_display(
        self, 
        manager, 
        force_clear: bool, 
        display_mode: str, 
        mode_type: str, 
        sticky_manager
    ) -> Tuple[bool, Optional[str]]:
        """Try to display content from a single manager.
        
        Args:
            manager: Manager instance to try
            force_clear: Whether to force clear display
            display_mode: External display mode name
            mode_type: Mode type ('live', 'recent', 'upcoming')
            sticky_manager: Current sticky manager (if any)
            
        Returns:
            Tuple of (success: bool, actual_mode: Optional[str])
        """
        if not manager:
            return False, None
        
        # Track which league we're displaying for granular dynamic duration
        self._set_display_context_from_manager(manager, mode_type)
        
        # Ensure manager is updated before displaying
        self._ensure_manager_updated(manager)
        
        result = manager.display(force_clear)
        
        # Debug logging
        manager_class_name = manager.__class__.__name__
        has_current_game = hasattr(manager, 'current_game') and manager.current_game is not None
        self.logger.info(
            f"Manager {manager_class_name} display() returned {result}, "
            f"has_current_game={has_current_game}"
        )
        
        # Build the actual mode name from league and mode_type for accurate tracking
        actual_mode = (
            f"{self._current_display_league}_{mode_type}" 
            if self._current_display_league and mode_type 
            else display_mode
        )
        
        if result is True:
            # Success - track progress and set sticky manager
            manager_key = self._build_manager_key(actual_mode, manager)
            
            try:
                self._record_dynamic_progress(manager, actual_mode=actual_mode, display_mode=display_mode)
            except Exception as progress_err:  # pylint: disable=broad-except
                self.logger.debug(f"Dynamic progress tracking failed: {progress_err}")
            
            # Set as sticky manager AFTER progress tracking (which may clear it on new cycle)
            if display_mode not in self._sticky_manager_per_mode:
                self._sticky_manager_per_mode[display_mode] = manager
                self._sticky_manager_start_time[display_mode] = time.time()
                self.logger.info(f"Set sticky manager {manager_class_name} for {display_mode}")
            
            # Track which managers were used for this display mode
            if display_mode:
                self._display_mode_to_managers.setdefault(display_mode, set()).add(manager_key)
            
            self._evaluate_dynamic_cycle_completion(display_mode=display_mode)
            return True, actual_mode
        
        elif result is False and manager == sticky_manager:
            # Sticky manager returned False - check if completed
            manager_key = self._build_manager_key(actual_mode, manager)
            
            if manager_key in self._dynamic_managers_completed:
                self.logger.info(
                    f"Sticky manager {manager_class_name} completed all games, switching to next manager"
                )
                self._sticky_manager_per_mode.pop(display_mode, None)
                self._sticky_manager_start_time.pop(display_mode, None)
                # Signal to break out of loop and try next manager
                return False, None
            else:
                # Manager not done yet, just returning False temporarily (between game switches)
                self.logger.debug(
                    f"Sticky manager {manager_class_name} returned False (between games), continuing"
                )
                return False, None
        
        elif result is False:
            # Non-sticky manager returned False - try next
            return False, None
        
        else:
            # Result is None or other - assume success
            manager_key = self._build_manager_key(actual_mode, manager)
            
            try:
                self._record_dynamic_progress(manager, actual_mode=actual_mode, display_mode=display_mode)
            except Exception as progress_err:  # pylint: disable=broad-except
                self.logger.debug(f"Dynamic progress tracking failed: {progress_err}")
            
            # Track which managers were used for this display mode
            if display_mode:
                self._display_mode_to_managers.setdefault(display_mode, set()).add(manager_key)
            
            self._evaluate_dynamic_cycle_completion(display_mode=display_mode)
            return True, actual_mode

    def _display_external_mode(self, display_mode: str, force_clear: bool) -> bool:
        """Handle display for external display_mode calls (from display controller).
        
        Handles both combined modes (football_live) and granular modes (nfl_live, ncaa_fb_recent).
        
        Args:
            display_mode: External mode name (e.g., 'football_live', 'nfl_recent', 'ncaa_fb_upcoming')
            force_clear: Whether to force clear display
            
        Returns:
            True if content was displayed, False otherwise
        """
        self.logger.debug(f"Display called with mode: {display_mode}")
        
        # Extract the mode type (live, recent, upcoming)
        mode_type = self._extract_mode_type(display_mode)
        if not mode_type:
            self.logger.warning(f"Unknown display_mode: {display_mode}")
            return False
        
        # Check if this is a granular mode (league-specific) or combined mode
        # Granular modes: nfl_live, ncaa_fb_recent, etc.
        # Combined modes: football_live, football_recent, etc.
        league = None
        if display_mode.startswith('nfl_'):
            league = 'nfl'
        elif display_mode.startswith('ncaa_fb_'):
            league = 'ncaa_fb'
        # If no league prefix, it's a combined mode - keep league=None
        
        self.logger.debug(
            f"Mode: {display_mode}, League: {league}, Mode type: {mode_type}, "
            f"NFL enabled: {self.nfl_enabled}, NCAA FB enabled: {self.ncaa_fb_enabled}"
        )
        
        # If granular mode (league-specific), display only that league
        if league:
            return self._display_league_mode(league, mode_type, force_clear)
        
        # Combined mode - display across all enabled leagues
        
        # Check if we should use scroll mode for this game type
        if self._should_use_scroll_mode(mode_type):
            return self._display_scroll_mode(display_mode, mode_type, force_clear)
        
        # Otherwise, use switch mode (existing behavior)
        
        # Resolve managers to try for this mode type
        managers_to_try = self._resolve_managers_for_mode(mode_type)
        
        # Apply sticky manager logic
        sticky_manager = self._sticky_manager_per_mode.get(display_mode)
        managers_to_try = self._apply_sticky_manager_logic(display_mode, managers_to_try)
        
        # Try each manager until one returns True (has content)
        for current_manager in managers_to_try:
            success, _ = self._try_manager_display(
                current_manager, force_clear, display_mode, mode_type, sticky_manager
            )
            
            if success:
                self.logger.info(f"Plugin display() returning True for {display_mode}")
                return True
            
            # If sticky manager completed, it's been removed from sticky dict
            # Continue to try next manager (if any) or exit loop
            # Note: When sticky manager is active, managers_to_try contains only that manager,
            # so loop will exit naturally if it returns False
        
        # No manager had content - log why
        if not managers_to_try:
            nfl_has_manager = self._get_manager_for_league_mode('nfl', mode_type) is not None
            ncaa_fb_has_manager = self._get_manager_for_league_mode('ncaa_fb', mode_type) is not None
            self.logger.warning(
                f"No managers to try for {display_mode}: nfl_enabled={self.nfl_enabled}, "
                f"nfl_has_manager={nfl_has_manager}, ncaa_fb_enabled={self.ncaa_fb_enabled}, "
                f"ncaa_fb_has_manager={ncaa_fb_has_manager}"
            )
        else:
            # Managers were tried but all returned False - log details for live mode
            if mode_type == 'live':
                nfl_live_manager = self._get_manager_for_league_mode('nfl', 'live')
                if nfl_live_manager:
                    nfl_live_games = getattr(nfl_live_manager, 'live_games', [])
                    self.logger.warning(
                        f"football_live: All managers returned False. "
                        f"NFL live_games count: {len(nfl_live_games) if nfl_live_games else 0}"
                    )
                    if nfl_live_games:
                        self.logger.warning(
                            f"football_live: NFL has {len(nfl_live_games)} live game(s) "
                            "but display() returned False"
                        )
                ncaa_fb_live_manager = self._get_manager_for_league_mode('ncaa_fb', 'live')
                if ncaa_fb_live_manager:
                    ncaa_live_games = getattr(ncaa_fb_live_manager, 'live_games', [])
                    self.logger.warning(
                        f"football_live: All managers returned False. "
                        f"NCAA FB live_games count: {len(ncaa_live_games) if ncaa_live_games else 0}"
                    )
                    if ncaa_live_games:
                        self.logger.warning(
                            f"football_live: NCAA FB has {len(ncaa_live_games)} live game(s) "
                            "but display() returned False"
                        )
            else:
                self.logger.debug(
                    f"No content available for mode: {display_mode} after trying "
                    f"{len(managers_to_try)} manager(s)"
                )
        
        # Clear display when no content available (safety measure)
        if force_clear:
            try:
                self.display_manager.clear()
                self.display_manager.update_display()
            except Exception as clear_err:
                self.logger.debug(f"Error clearing display when no content: {clear_err}")
        
        self.logger.info(f"Plugin display() returning False for {display_mode} - no content from any manager")
        return False
    
    def _display_scroll_mode(self, display_mode: str, mode_type: str, force_clear: bool) -> bool:
        """Handle display for scroll mode.
        
        Args:
            display_mode: External mode name (e.g., 'football_live')
            mode_type: Game type ('live', 'recent', 'upcoming')
            force_clear: Whether to force clear display
            
        Returns:
            True if content was displayed, False otherwise
        """
        if not self._scroll_manager:
            self.logger.warning("Scroll mode requested but scroll manager not available")
            # Fall back to switch mode
            return self._display_switch_mode_fallback(display_mode, mode_type, force_clear)
        
        # Check if we need to prepare new scroll content
        scroll_key = f"{display_mode}_{mode_type}"
        
        if not self._scroll_prepared.get(scroll_key, False):
            # Update managers first to get latest game data
            if self.nfl_enabled:
                nfl_manager = self._get_manager_for_league_mode('nfl', mode_type)
                if nfl_manager:
                    self._ensure_manager_updated(nfl_manager)
            if self.ncaa_fb_enabled:
                ncaa_manager = self._get_manager_for_league_mode('ncaa_fb', mode_type)
                if ncaa_manager:
                    self._ensure_manager_updated(ncaa_manager)
            
            # Check if live priority should filter to only live games
            live_priority_active = (
                mode_type == 'live' and 
                (self.nfl_live_priority or self.ncaa_fb_live_priority) and
                self.has_live_content()
            )
            
            # Collect games from all leagues using scroll mode
            games, leagues = self._collect_games_for_scroll(mode_type, live_priority_active)
            
            if not games:
                self.logger.debug(f"No games to scroll for {display_mode}")
                self._scroll_prepared[scroll_key] = False
                self._scroll_active[scroll_key] = False
                return False
            
            # Get rankings cache for display
            rankings = self._get_rankings_cache()
            
            # Prepare scroll content
            success = self._scroll_manager.prepare_and_display(
                games, mode_type, leagues, rankings
            )
            
            if success:
                self._scroll_prepared[scroll_key] = True
                self._scroll_active[scroll_key] = True
                self.logger.info(
                    f"[Football Scroll] Started scrolling {len(games)} {mode_type} games "
                    f"from {', '.join(leagues)}"
                )
            else:
                self._scroll_prepared[scroll_key] = False
                self._scroll_active[scroll_key] = False
                return False
        
        # Display the next scroll frame
        if self._scroll_active.get(scroll_key, False):
            displayed = self._scroll_manager.display_frame(mode_type)
            
            if displayed:
                # Check if scroll is complete
                if self._scroll_manager.is_complete(mode_type):
                    self.logger.info(f"[Football Scroll] Cycle complete for {display_mode}")
                    # Reset for next cycle
                    self._scroll_prepared[scroll_key] = False
                    self._scroll_active[scroll_key] = False
                    # Mark cycle as complete for dynamic duration
                    self._dynamic_cycle_complete = True
                
                return True
            else:
                # Scroll display failed
                self._scroll_active[scroll_key] = False
                return False
        
        return False
    
    def _display_switch_mode_fallback(self, display_mode: str, mode_type: str, force_clear: bool) -> bool:
        """Fallback to switch mode when scroll is not available.
        
        This is essentially the same logic as the switch mode portion of _display_external_mode.
        """
        # Resolve managers to try for this mode type
        managers_to_try = self._resolve_managers_for_mode(mode_type)
        
        # Apply sticky manager logic
        sticky_manager = self._sticky_manager_per_mode.get(display_mode)
        managers_to_try = self._apply_sticky_manager_logic(display_mode, managers_to_try)
        
        # Try each manager until one returns True (has content)
        for current_manager in managers_to_try:
            success, _ = self._try_manager_display(
                current_manager, force_clear, display_mode, mode_type, sticky_manager
            )
            
            if success:
                return True
        
        return False

    def _display_internal_cycling(self, force_clear: bool) -> bool:
        """Handle display for internal mode cycling (when no display_mode provided).
        
        Args:
            force_clear: Whether to force clear display
            
        Returns:
            True if content was displayed, False otherwise
        """
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
            self.current_mode_index = (self.current_mode_index + 1) % len(self.modes)
            self.last_mode_switch = current_time
            force_clear = True
            
            current_mode = self.modes[self.current_mode_index]
            self.logger.info(f"Switching to display mode: {current_mode}")
        
        # Get current manager and display
        current_manager = self._get_current_manager()
        if not current_manager:
            self.logger.warning("No manager available for current mode")
            return False
        
        # Track which league/mode we're displaying for granular dynamic duration
        current_mode = self.modes[self.current_mode_index] if self.modes else None
        if current_mode:
            # Extract mode type from mode name
            mode_type = self._extract_mode_type(current_mode)
            if mode_type:
                self._set_display_context_from_manager(current_manager, mode_type)
        
        result = current_manager.display(force_clear)
        if result is not False:
            try:
                # Build the actual mode name from league and mode_type for accurate tracking
                current_mode = self.modes[self.current_mode_index] if self.modes else None
                if current_mode:
                    manager_key = self._build_manager_key(current_mode, current_manager)
                    # Track which managers were used for internal mode cycling
                    # For internal cycling, the mode itself is the display_mode
                    self._display_mode_to_managers.setdefault(current_mode, set()).add(manager_key)
                self._record_dynamic_progress(
                    current_manager, actual_mode=current_mode, display_mode=current_mode
                )
            except Exception as progress_err:  # pylint: disable=broad-except
                self.logger.debug(f"Dynamic progress tracking failed: {progress_err}")
        else:
            # Manager returned False (no content) - ensure display is cleared
            # This is a safety measure in case the manager didn't clear it
            if force_clear:
                try:
                    self.display_manager.clear()
                    self.display_manager.update_display()
                except Exception as clear_err:
                    self.logger.debug(f"Error clearing display when manager returned False: {clear_err}")
        
        current_mode = self.modes[self.current_mode_index] if self.modes else None
        self._evaluate_dynamic_cycle_completion(display_mode=current_mode)
        return result

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
            # Track the current active display mode for use in is_cycle_complete()
            if display_mode:
                # Early exit: Skip if this mode is not in our available modes (disabled league)
                if display_mode not in self.modes:
                    self.logger.debug(f"Skipping disabled mode: {display_mode} (not in available modes: {self.modes})")
                    return False
                self._current_active_display_mode = display_mode
            
            # Route to appropriate display handler
            if display_mode:
                return self._display_external_mode(display_mode, force_clear)
            else:
                return self._display_internal_cycling(force_clear)

        except Exception as e:
            self.logger.error(f"Error in display method: {e}")
            return False

    def has_live_priority(self) -> bool:
        if not self.is_enabled:
            return False
        result = (
            (self.nfl_enabled and self.nfl_live_priority)
            or (self.ncaa_fb_enabled and self.ncaa_fb_live_priority)
        )
        self.logger.info(f"has_live_priority() called: nfl_enabled={self.nfl_enabled}, nfl_live_priority={self.nfl_live_priority}, ncaa_fb_enabled={self.ncaa_fb_enabled}, ncaa_fb_live_priority={self.ncaa_fb_live_priority}, result={result}")
        return result

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
                    
                    self.logger.info(f"has_live_content: NFL live_games={len(live_games)}, filtered_live_games={len(live_games)}, nfl_live={nfl_live}")

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
                    
                    self.logger.info(f"has_live_content: NCAA FB live_games={len(live_games)}, filtered_live_games={len(live_games)}, ncaa_live={ncaa_live}")

        result = nfl_live or ncaa_live
        
        # Throttle logging when returning False to reduce log noise
        # Always log True immediately (important), but only log False every 60 seconds
        current_time = time.time()
        should_log = result or (current_time - self._last_live_content_false_log >= self._live_content_log_interval)
        
        if should_log:
            if result:
                # Always log True results immediately
                self.logger.info(f"has_live_content() returning {result}: nfl_live={nfl_live}, ncaa_live={ncaa_live}")
            else:
                # Log False results only every 60 seconds
                self.logger.info(f"has_live_content() returning {result}: nfl_live={nfl_live}, ncaa_live={ncaa_live}")
                self._last_live_content_false_log = current_time
        
        return result

    def get_live_modes(self) -> list:
        """
        Return the registered plugin mode name(s) that have live content.
        
        Returns granular live modes (nfl_live, ncaa_fb_live) that actually have live content.
        The plugin is now registered with granular modes in manifest.json.
        """
        if not self.is_enabled:
            return []

        live_modes = []
        
        # Check NFL live content
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
                    # If favorite teams are configured, only return if there are live games for favorite teams
                    favorite_teams = getattr(self.nfl_live, "favorite_teams", [])
                    if favorite_teams:
                        if any(
                            game.get("home_abbr") in favorite_teams
                            or game.get("away_abbr") in favorite_teams
                            for game in live_games
                        ):
                            live_modes.append("nfl_live")
                    else:
                        # No favorite teams configured, include if any live games exist
                        live_modes.append("nfl_live")
        
        # Check NCAA FB live content
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
                    # If favorite teams are configured, only return if there are live games for favorite teams
                    favorite_teams = getattr(self.ncaa_fb_live, "favorite_teams", [])
                    if favorite_teams:
                        if any(
                            game.get("home_abbr") in favorite_teams
                            or game.get("away_abbr") in favorite_teams
                            for game in live_games
                        ):
                            live_modes.append("ncaa_fb_live")
                    else:
                        # No favorite teams configured, include if any live games exist
                        live_modes.append("ncaa_fb_live")
        
        return live_modes

    def _get_game_duration(self, league: str, mode_type: str, manager=None) -> float:
        """Get game duration for a league and mode type combination.
        
        Resolves duration using the following hierarchy:
        1. Manager's game_display_duration attribute (if manager provided)
        2. League-specific mode duration (e.g., nfl.live_game_duration)
        3. Global game_display_duration fallback
        
        Args:
            league: League name ('nfl' or 'ncaa_fb')
            mode_type: Mode type ('live', 'recent', or 'upcoming')
            manager: Optional manager instance (if provided, checks manager's game_display_duration)
            
        Returns:
            Game duration in seconds (float)
        """
        # First, try manager's game_display_duration if available
        if manager:
            manager_duration = getattr(manager, 'game_display_duration', None)
            if manager_duration is not None:
                return float(manager_duration)
        
        # Next, try league-specific mode duration
        league_config = self.config.get(league, {})
        mode_duration_key = f"{mode_type}_game_duration"  # e.g., 'live_game_duration'
        mode_duration = league_config.get(mode_duration_key)
        if mode_duration is not None:
            return float(mode_duration)
        
        # Fallback to global game_display_duration
        return float(self.game_display_duration)

    def get_cycle_duration(self, display_mode: str = None) -> Optional[float]:
        """
        Calculate the expected cycle duration for a display mode based on the number of games.
        
        This implements dynamic duration scaling where:
        - For switch mode: Total duration = num_games × per_game_duration
        - For scroll mode: Duration is calculated by ScrollHelper based on content width
        
        Args:
            display_mode: The display mode to calculate duration for (e.g., 'football_live', 'football_recent')
        
        Returns:
            Total expected duration in seconds, or None if not applicable
        """
        self.logger.info(f"get_cycle_duration() called with display_mode={display_mode}, is_enabled={self.is_enabled}")
        if not self.is_enabled or not display_mode:
            self.logger.info(f"get_cycle_duration() returning None: is_enabled={self.is_enabled}, display_mode={display_mode}")
            return None
        
        # Extract mode type
        mode_type = self._extract_mode_type(display_mode)
        if not mode_type:
            return None
        
        # Check if scroll mode is active for this mode type
        if self._should_use_scroll_mode(mode_type) and self._scroll_manager:
            # Get dynamic duration from scroll manager
            scroll_duration = self._scroll_manager.get_dynamic_duration(mode_type)
            if scroll_duration > 0:
                self.logger.info(f"get_cycle_duration: scroll mode duration for {display_mode} = {scroll_duration}s")
                return float(scroll_duration)
        
        # Fall through to switch mode duration calculation
        
        try:
            # Extract the mode type (live, recent, upcoming)
            mode_type = None
            if display_mode.endswith('_live'):
                mode_type = 'live'
            elif display_mode.endswith('_recent'):
                mode_type = 'recent'
            elif display_mode.endswith('_upcoming'):
                mode_type = 'upcoming'
            
            self.logger.info(f"get_cycle_duration: extracted mode_type={mode_type} from display_mode={display_mode}")
            
            if not mode_type:
                self.logger.info(f"get_cycle_duration: mode_type is None, returning None")
                return None
            
            total_games = 0
            per_game_duration = self.game_display_duration  # Default fallback (will be overridden per league)
            
            # Collect all managers for this mode and count their games
            managers_to_check = []
            
            if mode_type == 'live':
                if self.nfl_enabled:
                    nfl_manager = self._get_manager_for_league_mode('nfl', 'live')
                    if nfl_manager:
                        managers_to_check.append(('nfl', nfl_manager))
                if self.ncaa_fb_enabled:
                    ncaa_fb_manager = self._get_manager_for_league_mode('ncaa_fb', 'live')
                    if ncaa_fb_manager:
                        managers_to_check.append(('ncaa_fb', ncaa_fb_manager))
            elif mode_type == 'recent':
                if self.nfl_enabled:
                    nfl_manager = self._get_manager_for_league_mode('nfl', 'recent')
                    if nfl_manager:
                        managers_to_check.append(('nfl', nfl_manager))
                if self.ncaa_fb_enabled:
                    ncaa_fb_manager = self._get_manager_for_league_mode('ncaa_fb', 'recent')
                    if ncaa_fb_manager:
                        managers_to_check.append(('ncaa_fb', ncaa_fb_manager))
            elif mode_type == 'upcoming':
                if self.nfl_enabled:
                    nfl_manager = self._get_manager_for_league_mode('nfl', 'upcoming')
                    if nfl_manager:
                        managers_to_check.append(('nfl', nfl_manager))
                if self.ncaa_fb_enabled:
                    ncaa_fb_manager = self._get_manager_for_league_mode('ncaa_fb', 'upcoming')
                    if ncaa_fb_manager:
                        managers_to_check.append(('ncaa_fb', ncaa_fb_manager))
            
            # CRITICAL: Update managers BEFORE checking game counts!
            self.logger.info(f"get_cycle_duration: updating {len(managers_to_check)} manager(s) before counting games")
            for league_name, manager in managers_to_check:
                if manager:
                    self._ensure_manager_updated(manager)
            
            # Count games from all applicable managers and get duration
            for league_name, manager in managers_to_check:
                if not manager:
                    continue
                
                # Get the appropriate game list based on mode type
                if mode_type == 'live':
                    games = getattr(manager, 'live_games', [])
                elif mode_type == 'recent':
                    games = getattr(manager, 'recent_games', [])
                elif mode_type == 'upcoming':
                    games = getattr(manager, 'upcoming_games', [])
                else:
                    games = []
                
                # Get duration for this league/mode combination
                per_game_duration = self._get_game_duration(league_name, mode_type, manager)
                
                # Filter out invalid games
                if games:
                    # For live games, filter out final games
                    if mode_type == 'live':
                        games = [g for g in games if not g.get('is_final', False)]
                        if hasattr(manager, '_is_game_really_over'):
                            games = [g for g in games if not manager._is_game_really_over(g)]
                    
                    game_count = len(games)
                    total_games += game_count
                    
                    self.logger.debug(
                        f"get_cycle_duration: {league_name} {mode_type} has {game_count} games, "
                        f"per_game_duration={per_game_duration}s"
                    )
            
            self.logger.info(f"get_cycle_duration: found {total_games} total games for {display_mode}")
            
            if total_games == 0:
                # If no games found yet (managers still fetching data), return a default duration
                # This allows the display to start while data is loading
                default_duration = 45.0  # 3 games × 15s per game (reasonable default)
                self.logger.info(f"get_cycle_duration: {display_mode} has no games yet, returning default {default_duration}s")
                return default_duration
            
            # Calculate total duration: num_games × per_game_duration
            total_duration = total_games * per_game_duration
            self.logger.info(
                f"get_cycle_duration({display_mode}): {total_games} games × {per_game_duration}s = {total_duration}s"
            )
            
            self.logger.info(
                f"get_cycle_duration: {display_mode} = {total_games} games × {per_game_duration}s = {total_duration}s"
            )
            
            return total_duration
            
        except Exception as e:
            self.logger.error(f"Error calculating cycle duration for {display_mode}: {e}")
            return None

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
        """Reset dynamic cycle tracking.
        
        Note: We do NOT clear start times, progress, or display_mode_to_managers
        because these need to persist across quick mode switches within the same plugin.
        The 10-second threshold in _record_dynamic_progress handles true new cycles.
        """
        super().reset_cycle_state()
        self._dynamic_cycle_seen_modes.clear()
        self._dynamic_mode_to_manager_key.clear()
        # DO NOT clear these - let the 10-second threshold in _record_dynamic_progress handle it
        # self._dynamic_manager_progress.clear()
        # self._dynamic_managers_completed.clear()
        self._dynamic_cycle_complete = False
        # DO NOT clear start times - they need to persist until full duration elapsed
        # self._single_game_manager_start_times.clear()  # Keep for duration tracking
        # self._game_id_start_times.clear()  # Keep for duration tracking
        # DO NOT clear display_mode_to_managers - the 10s threshold handles new cycles
        # self._display_mode_to_managers.clear()
        self.logger.debug("Dynamic cycle state reset - flags cleared, tracking preserved for multi-mode plugin cycle")

    def is_cycle_complete(self) -> bool:
        """Report whether the plugin has shown a full cycle of content."""
        if not self._dynamic_feature_enabled():
            return True
        
        # Check if scroll mode is active for the current display mode
        if self._current_active_display_mode:
            mode_type = self._extract_mode_type(self._current_active_display_mode)
            if mode_type and self._should_use_scroll_mode(mode_type) and self._scroll_manager:
                # For scroll mode, check ScrollHelper's completion status
                is_complete = self._scroll_manager.is_complete(mode_type)
                self.logger.info(f"is_cycle_complete() [scroll mode]: display_mode={self._current_active_display_mode}, returning {is_complete}")
                return is_complete
        
        # Pass the current active display mode to evaluate completion for the right mode
        self._evaluate_dynamic_cycle_completion(display_mode=self._current_active_display_mode)
        self.logger.info(f"is_cycle_complete() called: display_mode={self._current_active_display_mode}, returning {self._dynamic_cycle_complete}")
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

    def _get_manager_for_league_mode(self, league: str, mode_type: str):
        """Get manager instance for a league and mode type combination.
        
        Args:
            league: 'nfl' or 'ncaa_fb'
            mode_type: 'live', 'recent', or 'upcoming'
            
        Returns:
            Manager instance or None if not available/enabled
        """
        if league == 'nfl' and not self.nfl_enabled:
            return None
        if league == 'ncaa_fb' and not self.ncaa_fb_enabled:
            return None
        
        attr_name = f"{league}_{mode_type}"
        return getattr(self, attr_name, None) if hasattr(self, attr_name) else None

    def _has_live_games_for_manager(self, manager) -> bool:
        """Check if a manager has valid live games (for favorite teams if configured).
        
        Args:
            manager: Manager instance to check
            
        Returns:
            True if manager has live games that should be displayed
        """
        if not manager:
            return False
        
        live_games = getattr(manager, 'live_games', [])
        if not live_games:
            return False
        
        # Filter out games that are final or appear over
        live_games = [g for g in live_games if not g.get('is_final', False)]
        if hasattr(manager, '_is_game_really_over'):
            live_games = [g for g in live_games if not manager._is_game_really_over(g)]
        
        if not live_games:
            return False
        
        # If favorite teams are configured, only return True if there are live games for favorite teams
        favorite_teams = getattr(manager, 'favorite_teams', [])
        if favorite_teams:
            has_favorite_live = any(
                game.get('home_abbr') in favorite_teams
                or game.get('away_abbr') in favorite_teams
                for game in live_games
            )
            return has_favorite_live
        
        # No favorite teams configured, any live game counts
        return True

    def _filter_managers_by_live_content(self, managers: list, mode_type: str) -> list:
        """Filter managers based on live content when in live mode.
        
        Args:
            managers: List of manager instances
            mode_type: 'live', 'recent', or 'upcoming'
            
        Returns:
            Filtered list of managers with live content (for live mode) or original list
        """
        if mode_type != 'live':
            return managers
        
        # For live mode, only include managers with actual live games
        filtered = []
        for manager in managers:
            if self._has_live_games_for_manager(manager):
                filtered.append(manager)
        
        return filtered

    def _resolve_managers_for_mode(self, mode_type: str) -> list:
        """Resolve ordered list of managers to try for a given mode type.
        
        Args:
            mode_type: 'live', 'recent', or 'upcoming'
            
        Returns:
            Ordered list of manager instances to try
        """
        managers_to_try = []
        
        if mode_type == 'live':
            # For live mode, update managers first to get current live games
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
            if self.nfl_enabled and self.nfl_live_priority:
                nfl_live_manager = self._get_manager_for_league_mode('nfl', 'live')
                if nfl_live_manager and self._has_live_games_for_manager(nfl_live_manager):
                    managers_to_try.append(nfl_live_manager)
                    self.logger.debug("NFL has live games - prioritizing NFL")
            
            # Check NCAA FB
            if self.ncaa_fb_enabled and self.ncaa_fb_live_priority:
                ncaa_fb_live_manager = self._get_manager_for_league_mode('ncaa_fb', 'live')
                if ncaa_fb_live_manager and self._has_live_games_for_manager(ncaa_fb_live_manager):
                    managers_to_try.append(ncaa_fb_live_manager)
                    self.logger.debug("NCAA FB has live games")
            
            # Fallback: if no live content found, show any enabled live manager (NFL first)
            if not managers_to_try:
                nfl_live_manager = self._get_manager_for_league_mode('nfl', 'live')
                if nfl_live_manager:
                    managers_to_try.append(nfl_live_manager)
                    self.logger.debug("No live content found, falling back to NFL live manager")
                ncaa_fb_live_manager = self._get_manager_for_league_mode('ncaa_fb', 'live')
                if ncaa_fb_live_manager:
                    managers_to_try.append(ncaa_fb_live_manager)
                    self.logger.debug("No live content found, falling back to NCAA FB live manager")
        else:
            # For recent and upcoming modes, use standard priority order: NFL > NCAA FB
            nfl_manager = self._get_manager_for_league_mode('nfl', mode_type)
            if nfl_manager:
                managers_to_try.append(nfl_manager)
            
            ncaa_fb_manager = self._get_manager_for_league_mode('ncaa_fb', mode_type)
            if ncaa_fb_manager:
                managers_to_try.append(ncaa_fb_manager)
        
        return managers_to_try

    def _extract_mode_type(self, display_mode: str) -> Optional[str]:
        """Extract mode type (live, recent, upcoming) from display mode string.
        
        Args:
            display_mode: Display mode string (e.g., 'football_live', 'nfl_recent')
            
        Returns:
            Mode type string ('live', 'recent', 'upcoming') or None
        """
        if display_mode.endswith('_live'):
            return 'live'
        elif display_mode.endswith('_recent'):
            return 'recent'
        elif display_mode.endswith('_upcoming'):
            return 'upcoming'
        return None

    def _set_display_context_from_manager(self, manager, mode_type: str) -> None:
        """Set current display league and mode type based on manager instance.
        
        Args:
            manager: Manager instance
            mode_type: 'live', 'recent', or 'upcoming'
        """
        self._current_display_mode_type = mode_type
        
        if manager in (getattr(self, 'nfl_live', None), 
                      getattr(self, 'nfl_recent', None), 
                      getattr(self, 'nfl_upcoming', None)):
            self._current_display_league = 'nfl'
        elif manager in (getattr(self, 'ncaa_fb_live', None), 
                        getattr(self, 'ncaa_fb_recent', None), 
                        getattr(self, 'ncaa_fb_upcoming', None)):
            self._current_display_league = 'ncaa_fb'

    def _track_single_game_progress(self, manager_key: str, manager, league: str, mode_type: str) -> None:
        """Track progress for a manager with a single game (or no games).
        
        Args:
            manager_key: Unique key identifying this manager
            manager: Manager instance
            league: League name ('nfl' or 'ncaa_fb')
            mode_type: Mode type ('live', 'recent', or 'upcoming')
        """
        current_time = time.time()
        
        if manager_key not in self._single_game_manager_start_times:
            # First time seeing this single-game manager (in this cycle) - record start time
            self._single_game_manager_start_times[manager_key] = current_time
            game_duration = self._get_game_duration(league, mode_type, manager) if league and mode_type else getattr(manager, 'game_display_duration', 15)
            self.logger.info(f"Single-game manager {manager_key} first seen at {current_time:.2f}, will complete after {game_duration}s")
        else:
            # Check if enough time has passed
            start_time = self._single_game_manager_start_times[manager_key]
            game_duration = self._get_game_duration(league, mode_type, manager) if league and mode_type else getattr(manager, 'game_display_duration', 15)
            elapsed = current_time - start_time
            if elapsed >= game_duration:
                # Enough time has passed - mark as complete
                if manager_key not in self._dynamic_managers_completed:
                    self._dynamic_managers_completed.add(manager_key)
                    self.logger.info(f"Single-game manager {manager_key} completed after {elapsed:.2f}s (required: {game_duration}s)")
                    # Clean up start time now that manager has completed
                    if manager_key in self._single_game_manager_start_times:
                        del self._single_game_manager_start_times[manager_key]
            else:
                # Still waiting
                self.logger.debug(f"Single-game manager {manager_key} waiting: {elapsed:.2f}s/{game_duration}s (start_time={start_time:.2f}, current_time={current_time:.2f})")

    def _record_dynamic_progress(self, current_manager, actual_mode: str = None, display_mode: str = None) -> None:
        """Track progress through managers/games for dynamic duration."""
        if not self._dynamic_feature_enabled() or not self.modes:
            self._dynamic_cycle_complete = True
            return

        # Use actual_mode if provided (when display_mode is specified), otherwise use internal mode cycling
        if actual_mode:
            current_mode = actual_mode
        else:
            current_mode = self.modes[self.current_mode_index]
        
        # Track both the internal mode and the external display mode if provided
        self._dynamic_cycle_seen_modes.add(current_mode)
        if display_mode and display_mode != current_mode:
            # Also track the external display mode for proper completion checking
            self._dynamic_cycle_seen_modes.add(display_mode)

        manager_key = self._build_manager_key(current_mode, current_manager)
        self._dynamic_mode_to_manager_key[current_mode] = manager_key
        
        # Extract league and mode_type from current_mode for duration lookups
        league = None
        mode_type = None
        if current_mode:
            if current_mode.startswith('nfl_'):
                league = 'nfl'
                mode_type = current_mode.split('_', 1)[1]
            elif current_mode.startswith('ncaa_fb_'):
                league = 'ncaa_fb'
                mode_type = current_mode.split('_', 2)[2]
        
        # Log for debugging
        self.logger.debug(f"_record_dynamic_progress: current_mode={current_mode}, display_mode={display_mode}, manager={current_manager.__class__.__name__}, manager_key={manager_key}, _last_display_mode={self._last_display_mode}")

        total_games = self._get_total_games_for_manager(current_manager)
        
        # Check if this is a new cycle for this display mode BEFORE adding to tracking
        # A "new cycle" means we're returning to a mode after having been away (different mode)
        # Only track external display_mode (from display controller), not internal mode cycling
        is_new_cycle = False
        current_time = time.time()
        
        # Only track mode changes for external calls (where display_mode differs from actual_mode)
        # This prevents internal mode cycling from triggering new cycle detection
        is_external_call = (display_mode and actual_mode and display_mode != actual_mode)
        
        if is_external_call:
            # External call from display controller - check for mode switches
            # Only treat as "new cycle" if we've been away for a while (> 10s)
            # This allows cycling through recent→upcoming→live→recent without clearing state
            NEW_CYCLE_THRESHOLD = 10.0  # seconds
            
            if display_mode != self._last_display_mode:
                # Switched to a different external mode
                time_since_last = current_time - self._last_display_mode_time if self._last_display_mode_time > 0 else 999
                
                # Only treat as new cycle if we've been away for a while OR this is the first time
                if time_since_last >= NEW_CYCLE_THRESHOLD:
                    is_new_cycle = True
                    self.logger.info(f"New cycle detected for {display_mode}: switched from {self._last_display_mode} (last seen {time_since_last:.1f}s ago)")
                else:
                    # Quick mode switch within same overall cycle - don't reset
                    self.logger.debug(f"Quick mode switch to {display_mode} from {self._last_display_mode} ({time_since_last:.1f}s ago) - continuing cycle")
            elif manager_key not in self._display_mode_to_managers.get(display_mode, set()):
                # Same external mode but manager not tracked yet - could be multi-league setup
                self.logger.debug(f"Manager {manager_key} not yet tracked for current mode {display_mode}")
            else:
                # Same mode and manager already tracked - continue within current cycle
                self.logger.debug(f"Continuing cycle for {display_mode}: manager {manager_key} already tracked")
            
            # Update last display mode tracking (only for external calls)
            self._last_display_mode = display_mode
            self._last_display_mode_time = current_time
            
            # ONLY reset state if this is truly a new cycle (after threshold)
            if is_new_cycle:
                # New cycle starting - reset ALL state for this manager to start completely fresh
                if manager_key in self._single_game_manager_start_times:
                    old_start = self._single_game_manager_start_times[manager_key]
                    self.logger.info(f"New cycle for {display_mode}: resetting start time for {manager_key} (old: {old_start:.2f})")
                    del self._single_game_manager_start_times[manager_key]
                # Also remove from completed set so it can be tracked fresh in this cycle
                if manager_key in self._dynamic_managers_completed:
                    self.logger.info(f"New cycle for {display_mode}: removing {manager_key} from completed set")
                    self._dynamic_managers_completed.discard(manager_key)
                # Also clear any game ID start times for this manager
                if manager_key in self._game_id_start_times:
                    self.logger.info(f"New cycle for {display_mode}: clearing game ID start times for {manager_key}")
                    del self._game_id_start_times[manager_key]
                # Clear progress tracking for this manager
                if manager_key in self._dynamic_manager_progress:
                    self.logger.info(f"New cycle for {display_mode}: clearing progress for {manager_key}")
                    self._dynamic_manager_progress[manager_key].clear()
                
                # Clear sticky manager for this mode since we're starting fresh
                if display_mode in self._sticky_manager_per_mode:
                    self.logger.info(f"New cycle for {display_mode}: clearing sticky manager")
                    self._sticky_manager_per_mode.pop(display_mode, None)
                    self._sticky_manager_start_time.pop(display_mode, None)
        
        # Now add to tracking AFTER checking for new cycle
        if display_mode and display_mode != current_mode:
            # Store mapping from display_mode to manager_key for completion checking
            self._display_mode_to_managers.setdefault(display_mode, set()).add(manager_key)
        
        if total_games <= 1:
            # Single (or no) game - wait for full game display duration before marking complete
            self._track_single_game_progress(manager_key, current_manager, league, mode_type)
            return

        # Get current game to extract its ID for tracking
        current_game = getattr(current_manager, "current_game", None)
        if not current_game:
            # No current game - can't track progress, but this is valid (empty game list)
            self.logger.debug(f"No current_game in manager {manager_key}, skipping progress tracking")
            # Still mark the mode as seen even if no content
            return
        
        # Use game ID for tracking instead of index to persist across game order changes
        game_id = current_game.get('id')
        if not game_id:
            # Fallback to index if game ID not available (shouldn't happen, but safety first)
            current_index = getattr(current_manager, "current_game_index", 0)
            # Also try to get a unique identifier from game data
            away_abbr = current_game.get('away_abbr', '')
            home_abbr = current_game.get('home_abbr', '')
            if away_abbr and home_abbr:
                game_id = f"{away_abbr}@{home_abbr}-{current_index}"
            else:
                game_id = f"index-{current_index}"
            self.logger.warning(f"Game ID not found for manager {manager_key}, using fallback: {game_id}")
        
        # Ensure game_id is a string for consistent tracking
        game_id = str(game_id)
        
        progress_set = self._dynamic_manager_progress.setdefault(manager_key, set())
        
        # Track when this game ID was first seen
        game_times = self._game_id_start_times.setdefault(manager_key, {})
        if game_id not in game_times:
            # First time seeing this game - record start time
            game_times[game_id] = time.time()
            game_duration = self._get_game_duration(league, mode_type, current_manager) if league and mode_type else getattr(current_manager, 'game_display_duration', 15)
            game_display = f"{current_game.get('away_abbr', '?')}@{current_game.get('home_abbr', '?')}"
            self.logger.info(f"Game {game_display} (ID: {game_id}) in manager {manager_key} first seen, will complete after {game_duration}s")
        
        # Check if this game has been shown for full duration
        start_time = game_times[game_id]
        game_duration = self._get_game_duration(league, mode_type, current_manager) if league and mode_type else getattr(current_manager, 'game_display_duration', 15)
        elapsed = time.time() - start_time
        
        if elapsed >= game_duration:
            # This game has been shown for full duration - add to progress set
            if game_id not in progress_set:
                progress_set.add(game_id)
                game_display = f"{current_game.get('away_abbr', '?')}@{current_game.get('home_abbr', '?')}"
                self.logger.info(f"Game {game_display} (ID: {game_id}) in manager {manager_key} completed after {elapsed:.2f}s (required: {game_duration}s)")
        else:
            # Still waiting for this game to complete its duration
            self.logger.debug(f"Game ID {game_id} in manager {manager_key} waiting: {elapsed:.2f}s/{game_duration}s")

        # Get all valid game IDs from current game list to clean up stale entries
        valid_game_ids = self._get_all_game_ids_for_manager(current_manager)
        
        # Clean up progress set and start times for games that no longer exist
        if valid_game_ids:
            # Remove game IDs from progress set that are no longer in the game list
            progress_set.intersection_update(valid_game_ids)
            # Also clean up start times for games that no longer exist
            game_times = {k: v for k, v in game_times.items() if k in valid_game_ids}
            self._game_id_start_times[manager_key] = game_times
        elif total_games == 0:
            # No games in list - clear all tracking for this manager
            progress_set.clear()
            game_times.clear()
            self._game_id_start_times[manager_key] = {}

        # Only mark manager complete when all current games have been shown for their full duration
        # Use the actual current game IDs, not just the count, to handle dynamic game lists
        current_game_ids = self._get_all_game_ids_for_manager(current_manager)
        
        if current_game_ids:
            # Check if all current games have been shown for full duration
            if current_game_ids.issubset(progress_set):
                if manager_key not in self._dynamic_managers_completed:
                    self._dynamic_managers_completed.add(manager_key)
                    self.logger.info(f"Manager {manager_key} completed - all {len(current_game_ids)} games shown for full duration (progress: {len(progress_set)} game IDs)")
            else:
                missing_count = len(current_game_ids - progress_set)
                self.logger.debug(f"Manager {manager_key} incomplete - {missing_count} of {len(current_game_ids)} games not yet shown for full duration")
        elif total_games == 0:
            # Empty game list - mark as complete immediately
            if manager_key not in self._dynamic_managers_completed:
                self._dynamic_managers_completed.add(manager_key)
                self.logger.debug(f"Manager {manager_key} completed - no games to display")

    def _evaluate_dynamic_cycle_completion(self, display_mode: str = None) -> None:
        """Determine whether all enabled modes have completed their cycles."""
        if not self._dynamic_feature_enabled():
            self._dynamic_cycle_complete = True
            return

        if not self.modes:
            self._dynamic_cycle_complete = True
            return

        # If display_mode is provided, check all managers used for that display mode
        if display_mode and display_mode in self._display_mode_to_managers:
            used_manager_keys = self._display_mode_to_managers[display_mode]
            if not used_manager_keys:
                # No managers were used for this display mode yet - cycle not complete
                self._dynamic_cycle_complete = False
                self.logger.debug(f"Display mode {display_mode} has no managers tracked yet - cycle incomplete")
                return
            
            self.logger.info(f"_evaluate_dynamic_cycle_completion for {display_mode}: checking {len(used_manager_keys)} manager(s): {used_manager_keys}")
            
            # Check if all managers used for this display mode have completed
            incomplete_managers = []
            for manager_key in used_manager_keys:
                if manager_key not in self._dynamic_managers_completed:
                    incomplete_managers.append(manager_key)
                    # Get the manager to check its state for logging and potential completion
                    # Extract mode and manager class from manager_key (format: "mode:ManagerClass")
                    parts = manager_key.split(':', 1)
                    if len(parts) == 2:
                        mode_name, manager_class_name = parts
                        manager = self._get_manager_for_mode(mode_name)
                        if manager and manager.__class__.__name__ == manager_class_name:
                            total_games = self._get_total_games_for_manager(manager)
                            if total_games <= 1:
                                # Single-game manager - check time
                                if manager_key in self._single_game_manager_start_times:
                                    start_time = self._single_game_manager_start_times[manager_key]
                                    # Extract league and mode_type from mode_name
                                    league = 'nfl' if mode_name.startswith('nfl_') else ('ncaa_fb' if mode_name.startswith('ncaa_fb_') else None)
                                    mode_type = mode_name.split('_')[-1] if mode_name else None
                                    game_duration = self._get_game_duration(league, mode_type, manager) if league and mode_type else getattr(manager, 'game_display_duration', 15)
                                    current_time = time.time()
                                    elapsed = current_time - start_time
                                    if elapsed >= game_duration:
                                        self._dynamic_managers_completed.add(manager_key)
                                        incomplete_managers.remove(manager_key)
                                        self.logger.info(f"Manager {manager_key} marked complete in completion check: {elapsed:.2f}s >= {game_duration}s")
                                        # Clean up start time now that manager has completed
                                        if manager_key in self._single_game_manager_start_times:
                                            del self._single_game_manager_start_times[manager_key]
                                    else:
                                        self.logger.debug(f"Manager {manager_key} waiting in completion check: {elapsed:.2f}s/{game_duration}s (start_time={start_time:.2f}, current_time={current_time:.2f})")
                                else:
                                    # Manager not yet seen - keep it incomplete
                                    # This means _record_dynamic_progress hasn't been called yet for this manager
                                    # or the state was reset, so we can't determine completion
                                    self.logger.debug(f"Manager {manager_key} not yet seen in completion check (not in start_times) - keeping incomplete")
                                    # Don't remove from incomplete_managers - it stays incomplete
                            else:
                                # Multi-game manager - check if all current games have been shown for full duration
                                progress_set = self._dynamic_manager_progress.get(manager_key, set())
                                current_game_ids = self._get_all_game_ids_for_manager(manager)
                                
                                # Check if all current games are in the progress set (shown for full duration)
                                if current_game_ids and current_game_ids.issubset(progress_set):
                                    self._dynamic_managers_completed.add(manager_key)
                                    incomplete_managers.remove(manager_key)
                                else:
                                    missing_games = current_game_ids - progress_set
                                    self.logger.debug(f"Manager {manager_key} progress: {len(progress_set)}/{len(current_game_ids)} games completed, missing: {len(missing_games)}")
            
            self.logger.info(f"_evaluate_dynamic_cycle_completion for {display_mode}: incomplete_managers={incomplete_managers}, completed={[k for k in used_manager_keys if k in self._dynamic_managers_completed]}")
            
            if not incomplete_managers:
                # All managers have completed - but verify they actually completed in THIS cycle
                # Check that all managers either:
                # 1. Are in _dynamic_managers_completed AND have no start time (truly completed)
                # 2. Or have a start time that has elapsed (completed in this check)
                all_truly_completed = True
                for manager_key in used_manager_keys:
                    # If manager has a start time, it hasn't completed yet (or just completed)
                    if manager_key in self._single_game_manager_start_times:
                        # Still has start time - check if it should be completed
                        parts = manager_key.split(':', 1)
                        if len(parts) == 2:
                            mode_name, manager_class_name = parts
                            manager = self._get_manager_for_mode(mode_name)
                            if manager and manager.__class__.__name__ == manager_class_name:
                                start_time = self._single_game_manager_start_times[manager_key]
                                # Extract league and mode_type from mode_name
                                league = 'nfl' if mode_name.startswith('nfl_') else ('ncaa_fb' if mode_name.startswith('ncaa_fb_') else None)
                                mode_type = mode_name.split('_')[-1] if mode_name else None
                                game_duration = self._get_game_duration(league, mode_type, manager) if league and mode_type else getattr(manager, 'game_display_duration', 15)
                                elapsed = time.time() - start_time
                                if elapsed < game_duration:
                                    # Not enough time has passed - not truly completed
                                    all_truly_completed = False
                                    self.logger.debug(f"Manager {manager_key} in completed set but still has start time with {elapsed:.2f}s < {game_duration}s")
                                    break
                
                if all_truly_completed:
                    self._dynamic_cycle_complete = True
                    self.logger.info(f"Display mode {display_mode} cycle complete - all {len(used_manager_keys)} manager(s) completed")
                else:
                    # Some managers aren't truly completed - keep cycle incomplete
                    self._dynamic_cycle_complete = False
                    self.logger.debug(f"Display mode {display_mode} cycle incomplete - some managers not truly completed yet")
            else:
                self._dynamic_cycle_complete = False
                self.logger.debug(f"Display mode {display_mode} cycle incomplete - {len(incomplete_managers)} manager(s) still in progress: {incomplete_managers}")
            return

        # Standard mode checking (for internal mode cycling)
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
                    # For single-game managers, check if enough time has passed
                    if manager_key in self._single_game_manager_start_times:
                        start_time = self._single_game_manager_start_times[manager_key]
                        # Extract league and mode_type from mode_name
                        league = 'nfl' if mode_name.startswith('nfl_') else ('ncaa_fb' if mode_name.startswith('ncaa_fb_') else None)
                        mode_type = mode_name.split('_')[-1] if mode_name else None
                        game_duration = self._get_game_duration(league, mode_type, manager) if (league and mode_type and manager) else (getattr(manager, 'game_display_duration', 15) if manager else 15)
                        elapsed = time.time() - start_time
                        if elapsed >= game_duration:
                            self._dynamic_managers_completed.add(manager_key)
                        else:
                            # Not enough time yet
                            self._dynamic_cycle_complete = False
                            return
                    else:
                        # Haven't seen this manager yet in _record_dynamic_progress
                        self._dynamic_cycle_complete = False
                        return
                else:
                    # Multi-game manager - check if all current games have been shown for full duration
                    progress_set = self._dynamic_manager_progress.get(manager_key, set())
                    current_game_ids = self._get_all_game_ids_for_manager(manager)
                    
                    # Check if all current games are in the progress set (shown for full duration)
                    if current_game_ids and current_game_ids.issubset(progress_set):
                        self._dynamic_managers_completed.add(manager_key)
                        # Continue to check other modes
                    else:
                        missing_games = current_game_ids - progress_set if current_game_ids else set()
                        self.logger.debug(f"Manager {manager_key} progress: {len(progress_set)}/{len(current_game_ids)} games completed, missing: {len(missing_games)}")
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
    
    @staticmethod
    def _get_all_game_ids_for_manager(manager) -> set:
        """Get all game IDs from a manager's game list."""
        if manager is None:
            return set()
        game_ids = set()
        for attr in ("live_games", "games_list", "recent_games", "upcoming_games"):
            game_list = getattr(manager, attr, None)
            if isinstance(game_list, list) and game_list:
                for i, game in enumerate(game_list):
                    game_id = game.get('id')
                    if game_id:
                        game_ids.add(str(game_id))
                    else:
                        # Fallback to index-based identifier if ID missing
                        away_abbr = game.get('away_abbr', '')
                        home_abbr = game.get('home_abbr', '')
                        if away_abbr and home_abbr:
                            game_ids.add(f"{away_abbr}@{home_abbr}-{i}")
                        else:
                            game_ids.add(f"index-{i}")
                break
        return game_ids

    def cleanup(self) -> None:
        """Clean up resources."""
        try:
            if hasattr(self, "background_service") and self.background_service:
                # Clean up background service if needed
                pass
            self.logger.info("Football scoreboard plugin cleanup completed")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
