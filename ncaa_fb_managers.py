import os
import time
import logging
import requests
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import pytz
from sports import SportsRecent, SportsUpcoming
from football import Football, FootballLive
from pathlib import Path

# Constants
ESPN_NCAAFB_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"  # Changed URL for NCAA FB


class BaseNCAAFBManager(Football):  # Renamed class
    """Base class for NCAA FB managers with common functionality."""  # Updated docstring

    # Class variables for warning tracking
    _no_data_warning_logged = False
    _last_warning_time = 0
    _warning_cooldown = 60  # Only log warnings once per minute
    _shared_data = None
    _last_shared_update = 0
    _processed_games_cache = {}  # Cache for processed game data
    _processed_games_timestamp = 0

    def __init__(self, config: Dict[str, Any], display_manager, cache_manager):
        self.logger = logging.getLogger("NCAAFB")  # Changed logger name
        super().__init__(
            config=config,
            display_manager=display_manager,
            cache_manager=cache_manager,
            logger=self.logger,
            sport_key="ncaa_fb",
        )

        # Configuration is already set in base class
        # self.logo_dir and self.update_interval are already configured

        # Check display modes to determine what data to fetch
        display_modes = self.mode_config.get("display_modes", {})
        self.recent_enabled = display_modes.get("ncaa_fb_recent", False)
        self.upcoming_enabled = display_modes.get("ncaa_fb_upcoming", False)
        self.live_enabled = display_modes.get("ncaa_fb_live", False)
        self.league = "college-football"

        self.logger.info(
            f"Initialized NCAAFB manager with display dimensions: {self.display_width}x{self.display_height}"
        )
        self.logger.info(f"Logo directory: {self.logo_dir}")
        self.logger.info(
            f"Display modes - Recent: {self.recent_enabled}, Upcoming: {self.upcoming_enabled}, Live: {self.live_enabled}"
        )

    def _fetch_ncaa_fb_api_data(self, use_cache: bool = True) -> Optional[Dict]:
        """
        Fetches the full season schedule for NCAAFB using week-by-week approach to ensure
        we get all games, then caches the complete dataset.

        This method now uses background threading to prevent blocking the display.
        """
        now = datetime.now(pytz.utc)
        season_year = now.year
        if now.month < 8:
            season_year = now.year - 1
        datestring = f"{season_year}0801-{season_year+1}0201"
        cache_key = f"ncaafb_schedule_{season_year}"

        if use_cache:
            cached_data = self.cache_manager.get(cache_key)
            if cached_data:
                # Validate cached data structure
                if isinstance(cached_data, dict) and "events" in cached_data:
                    self.logger.info(f"Using cached schedule for {season_year}")
                    return cached_data
                elif isinstance(cached_data, list):
                    # Handle old cache format (list of events)
                    self.logger.info(
                        f"Using cached schedule for {season_year} (legacy format)"
                    )
                    return {"events": cached_data}
                else:
                    self.logger.warning(
                        f"Invalid cached data format for {season_year}: {type(cached_data)}"
                    )
                    # Clear invalid cache
                    self.cache_manager.clear_cache(cache_key)

        self.logger.info(
            f"Fetching full {season_year} season schedule from ESPN API..."
        )

        # Start background fetch
        self.logger.info(
            f"Starting background fetch for {season_year} season schedule..."
        )

        def fetch_callback(result):
            """Callback when background fetch completes."""
            if result.success:
                self.logger.info(
                    f"Background fetch completed for {season_year}: {len(result.data.get('events'))} events"
                )
            else:
                self.logger.error(
                    f"Background fetch failed for {season_year}: {result.error}"
                )

            # Clean up request tracking
            if season_year in self.background_fetch_requests:
                del self.background_fetch_requests[season_year]

        # Get background service configuration
        background_config = self.mode_config.get("background_service", {})
        timeout = background_config.get("request_timeout", 30)
        max_retries = background_config.get("max_retries", 3)
        priority = background_config.get("priority", 2)

        # Start background fetch if service is available
        if self.background_service and self.background_enabled:
            self.logger.info(
                f"Starting background fetch for {season_year} season schedule..."
            )

            def fetch_callback(result):
                """Callback when background fetch completes."""
                if result.success:
                    self.logger.info(
                        f"Background fetch completed for {season_year}: {len(result.data.get('events'))} events"
                    )
                else:
                    self.logger.error(
                        f"Background fetch failed for {season_year}: {result.error}"
                    )

                # Clean up request tracking
                if season_year in self.background_fetch_requests:
                    del self.background_fetch_requests[season_year]

            # Submit background fetch request
            request_id = self.background_service.submit_fetch_request(
                sport="ncaa_fb",
                year=season_year,
                url=ESPN_NCAAFB_SCOREBOARD_URL,
                cache_key=cache_key,
                params={"dates": datestring, "limit": 1000},
                headers=self.headers,
                timeout=timeout,
                max_retries=max_retries,
                priority=priority,
                callback=fetch_callback,
            )

            # Track the request
            self.background_fetch_requests[season_year] = request_id

            # For immediate response, try to get partial data
            partial_data = self._get_weeks_data()
            if partial_data:
                return partial_data
        else:
            # Fallback to synchronous fetch if background service not available
            self.logger.warning(
                "Background service not available, using synchronous fetch"
            )
            try:
                response = self.session.get(
                    ESPN_NCAAFB_SCOREBOARD_URL,
                    params={"dates": datestring, "limit": 1000},
                    headers=self.headers,
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()

                # Cache the data
                self.cache_manager.set(cache_key, data)
                self.logger.info(f"Synchronously fetched {season_year} season schedule")
                return data

            except Exception as e:
                self.logger.error(f"Failed to fetch {season_year} season schedule: {e}")
                return None

    def _fetch_data(self) -> Optional[Dict]:
        """Fetch data using shared data mechanism or direct fetch for live."""
        if isinstance(self, NCAAFBLiveManager):
            return self._fetch_todays_games()
        else:
            return self._fetch_ncaa_fb_api_data(use_cache=True)


class NCAAFBLiveManager(BaseNCAAFBManager, FootballLive):  # Renamed class
    """Manager for live NCAA FB games."""  # Updated docstring

    def __init__(self, config: Dict[str, Any], display_manager, cache_manager):
        super().__init__(
            config=config, display_manager=display_manager, cache_manager=cache_manager
        )
        self.logger = logging.getLogger("NCAAFBLiveManager")  # Changed logger name

        if self.test_mode:
            # More detailed test game for NCAA FB
            self.current_game = {
                "id": "testNCAAFB001",
                "home_id": "343",
                "away_id": "567",
                "home_abbr": "UGA",
                "away_abbr": "AUB",  # NCAA Examples
                "home_score": "28",
                "away_score": "21",
                "period": 4,
                "period_text": "Q4",
                "clock": "01:15",
                "down_distance_text": "2nd & 5",
                "possession": "UGA",  # Placeholder ID for home team
                "possession_indicator": "home",  # Explicitly set for test
                "home_timeouts": 1,
                "away_timeouts": 2,
                "home_logo_path": Path(self.logo_dir, "UGA.png"),
                "away_logo_path": Path(self.logo_dir, "AUB.png"),
                "is_live": True,
                "is_final": False,
                "is_upcoming": False,
                "is_halftime": False,
                "status_text": "Q4 01:15",
            }
            self.live_games = [self.current_game]
            logging.info(
                "Initialized NCAAFBLiveManager with test game: AUB vs UGA"
            )  # Updated log message
        else:
            logging.info(
                "Initialized NCAAFBLiveManager in live mode"
            )  # Updated log message


class NCAAFBRecentManager(BaseNCAAFBManager, SportsRecent):  # Renamed class
    """Manager for recently completed NCAA FB games."""  # Updated docstring

    def __init__(self, config: Dict[str, Any], display_manager, cache_manager):
        super().__init__(config, display_manager, cache_manager)
        self.logger = logging.getLogger("NCAAFBRecentManager")  # Changed log prefix
        self.logger.info(
            f"Initialized NCAAFBRecentManager with {len(self.favorite_teams)} favorite teams"
        )  # Changed log prefix


class NCAAFBUpcomingManager(BaseNCAAFBManager, SportsUpcoming):  # Renamed class
    """Manager for upcoming NCAA FB games."""  # Updated docstring

    def __init__(self, config: Dict[str, Any], display_manager, cache_manager):
        super().__init__(config, display_manager, cache_manager)
        self.logger = logging.getLogger("NCAAFBUpcomingManager")  # Changed log prefix
        self.logger.info(
            f"Initialized NCAAFBUpcomingManager with {len(self.favorite_teams)} favorite teams"
        )  # Changed log prefix
