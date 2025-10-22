"""
Data Fetcher Module for Football Scoreboard Plugin

This module handles all API data fetching, processing, and caching
for both NFL and NCAA FB games.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import pytz
import requests
from pathlib import Path

try:
    from src.background_data_service import get_background_service
except ImportError:
    get_background_service = None

logger = logging.getLogger(__name__)


class FootballDataFetcher:
    """Handles all data fetching operations for football games."""
    
    def __init__(self, cache_manager, background_service=None):
        """Initialize the data fetcher."""
        self.cache_manager = cache_manager
        self.background_service = background_service
        self.logger = logger
        
        # API endpoints
        self.NFL_API_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
        self.NCAA_FB_API_URL = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
        
        # Request settings
        self.headers = {
            'User-Agent': 'LEDMatrix/1.0 (Educational Project)',
            'Accept': 'application/json'
        }
        
        # Background fetch tracking
        self.background_fetch_requests = {}
        
    def fetch_nfl_data(self, use_cache: bool = True) -> Optional[Dict]:
        """Fetches the full season schedule for NFL using background threading."""
        now = datetime.now(pytz.utc)
        season_year = now.year
        if now.month < 8:
            season_year = now.year - 1
        datestring = f"{season_year}0801-{season_year+1}0301"
        cache_key = f"nfl_schedule_{season_year}"

        # Check cache first
        if use_cache and self.cache_manager:
            cached_data = self.cache_manager.get(cache_key)
            if cached_data:
                # Validate cached data structure
                if isinstance(cached_data, dict) and "events" in cached_data:
                    self.logger.info(f"Using cached NFL schedule for {season_year}")
                    return cached_data
                elif isinstance(cached_data, list):
                    # Handle old cache format (list of events)
                    self.logger.info(f"Using cached NFL schedule for {season_year} (legacy format)")
                    return {"events": cached_data}

        # Start background fetch if background service is available
        if self.background_service:
            self._start_background_fetch("nfl", season_year, datestring, cache_key)

        # For immediate response, try to get extended games
        return self._fetch_extended_games("nfl")
    
    def fetch_ncaa_fb_data(self, use_cache: bool = True) -> Optional[Dict]:
        """Fetches the full season schedule for NCAA FB using background threading."""
        now = datetime.now(pytz.utc)
        season_year = now.year
        if now.month < 8:
            season_year = now.year - 1
        datestring = f"{season_year}0801-{season_year+1}0301"
        cache_key = f"ncaa_fb_schedule_{season_year}"

        # Check cache first
        if use_cache and self.cache_manager:
            cached_data = self.cache_manager.get(cache_key)
            if cached_data:
                # Validate cached data structure
                if isinstance(cached_data, dict) and "events" in cached_data:
                    self.logger.info(f"Using cached NCAA FB schedule for {season_year}")
                    return cached_data
                elif isinstance(cached_data, list):
                    # Handle old cache format (list of events)
                    self.logger.info(f"Using cached NCAA FB schedule for {season_year} (legacy format)")
                    return {"events": cached_data}

        # Start background fetch if background service is available
        if self.background_service:
            self._start_background_fetch("ncaa_fb", season_year, datestring, cache_key)

        # For NCAA FB, try to get the full season data first, then fall back to today's games
        # This matches the original NCAA FB manager behavior
        full_season_data = self._fetch_full_season_games("ncaa_fb", season_year, datestring)
        if full_season_data:
            return full_season_data
        
        # Fallback to today's games if full season fetch fails
        return self._fetch_todays_games("ncaa_fb")
    
    def _fetch_extended_games(self, league: str) -> Optional[Dict]:
        """Fetch games for an extended period to cover upcoming games beyond the next few days."""
        try:
            now = datetime.now()
            all_events = []
            
            # Fetch games from the past 7 days to today + 14 days to cover more upcoming games
            for days_offset in range(-7, 15):  # -7 days to +14 days
                target_date = now + timedelta(days=days_offset)
                formatted_date = target_date.strftime("%Y%m%d")

                if league == "nfl":
                    url = self.NFL_API_URL
                elif league == "ncaa_fb":
                    url = self.NCAA_FB_API_URL
                else:
                    continue

                try:
                    response = requests.get(
                        url,
                        params={"dates": formatted_date, "limit": 1000},
                        headers=self.headers,
                        timeout=30
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    if "events" in data:
                        all_events.extend(data["events"])
                        
                except Exception as e:
                    self.logger.warning(f"Error fetching {league} games for {formatted_date}: {e}")
                    continue

            self.logger.info(f"Fetched {len(all_events)} total games for {league} across extended date range")
            return {"events": all_events}
            
        except Exception as e:
            self.logger.error(f"Error fetching extended games for {league}: {e}")
            return None
    
    def _fetch_todays_games(self, league: str) -> Optional[Dict]:
        """Fetch today's games for immediate display."""
        try:
            today = datetime.now().strftime("%Y%m%d")
            
            if league == "nfl":
                url = self.NFL_API_URL
            elif league == "ncaa_fb":
                url = self.NCAA_FB_API_URL
            else:
                return None

            response = requests.get(
                url,
                params={"dates": today, "limit": 1000},
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error fetching today's {league} games: {e}")
            return None
    
    def _fetch_full_season_games(self, league: str, season_year: int, datestring: str) -> Optional[Dict]:
        """Fetch full season games for NCAA FB (matches original NCAA FB manager behavior)."""
        try:
            if league == "ncaa_fb":
                url = self.NCAA_FB_API_URL
            else:
                return None

            response = requests.get(
                url,
                params={"dates": datestring, "limit": 1000},
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            self.logger.info(f"Fetched full season {league} data: {len(data.get('events', []))} events")
            return data
            
        except Exception as e:
            self.logger.error(f"Error fetching full season {league} games: {e}")
            return None
    
    def _start_background_fetch(self, sport: str, season_year: int, datestring: str, cache_key: str):
        """Start background fetch for full season data."""
        try:
            def fetch_callback(result):
                """Callback when background fetch completes."""
                if result.success:
                    self.logger.info(f"Background fetch completed for {sport} {season_year}: {len(result.data.get('events', []))} events")
                else:
                    self.logger.error(f"Background fetch failed for {sport} {season_year}: {result.error}")
                
                # Clean up request tracking
                if season_year in self.background_fetch_requests:
                    del self.background_fetch_requests[season_year]
            
            # Get background service configuration
            timeout = 30
            max_retries = 3
            priority = 2
            
            # Choose the correct URL based on sport
            if sport == "nfl":
                url = self.NFL_API_URL
            elif sport == "ncaa_fb":
                url = self.NCAA_FB_API_URL
            else:
                return
            
            # Submit background fetch request
            request_id = self.background_service.submit_fetch_request(
                sport=sport,
                year=season_year,
                url=url,
                cache_key=cache_key,
                params={"dates": datestring, "limit": 1000},
                headers=self.headers,
                timeout=timeout,
                max_retries=max_retries,
                priority=priority,
                callback=fetch_callback
            )
            
            # Track the request
            self.background_fetch_requests[season_year] = request_id
            self.logger.info(f"Started background fetch for {sport} {season_year}")
            
        except Exception as e:
            self.logger.error(f"Error starting background fetch for {sport}: {e}")
    
    def process_api_response(self, data: Dict, league_key: str, league_config: Dict) -> List[Dict]:
        """Process API response data into standardized game format."""
        if not data or "events" not in data:
            return []

        games = []
        for event in data["events"]:
            try:
                game = self._extract_game_details(event, league_key, league_config)
                if game:
                    games.append(game)
            except Exception as e:
                self.logger.warning(f"Error processing game event: {e}")
                continue

        return games
    
    def _extract_game_details(self, event: Dict, league_key: str, league_config: Dict) -> Optional[Dict]:
        """Extract game details from ESPN API event data."""
        try:
            # Extract basic game info
            game_id = event.get("id", "")
            date_str = event.get("date", "")
            
            # Parse date
            try:
                game_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except:
                game_date = datetime.now(pytz.utc)
            
            # Extract teams
            competitions = event.get("competitions", [])
            if not competitions:
                return None
                
            competition = competitions[0]
            competitors = competition.get("competitors", [])
            
            if len(competitors) < 2:
                return None
            
            # Home and away teams
            home_competitor = None
            away_competitor = None
            
            for competitor in competitors:
                if competitor.get("homeAway") == "home":
                    home_competitor = competitor
                elif competitor.get("homeAway") == "away":
                    away_competitor = competitor
            
            if not home_competitor or not away_competitor:
                return None
            
            # Extract team info
            home_team = home_competitor.get("team", {})
            away_team = away_competitor.get("team", {})
            
            home_abbr = home_team.get("abbreviation", "HOME")
            away_abbr = away_team.get("abbreviation", "AWAY")
            home_score = home_competitor.get("score", "0")
            away_score = away_competitor.get("score", "0")
            
            # Extract game status
            status = competition.get("status", {})
            period = status.get("period", 0)
            clock = status.get("displayClock", "")
            type_code = status.get("type", {}).get("name", "")
            
            # Determine game state
            is_live = type_code in ["STATUS_IN_PROGRESS", "STATUS_HALFTIME"]
            is_final = type_code == "STATUS_FINAL"
            is_upcoming = type_code in ["STATUS_SCHEDULED", "STATUS_PRE"]
            
            # Create period text
            if is_live:
                if period <= 4:
                    period_text = f"Q{period}"
                else:
                    period_text = f"OT{period-4}"
                if clock:
                    period_text += f" {clock}"
            elif is_final:
                if period <= 4:
                    period_text = "Final"
                else:
                    period_text = f"Final OT{period-4}"
            else:
                # Upcoming game - format time
                try:
                    game_time = game_date.strftime("%I:%M%p").lower()
                    period_text = game_time
                except:
                    period_text = "TBD"
            
            # Format date and time for display
            formatted_date = ""
            formatted_time = ""
            if is_upcoming:
                try:
                    # Format date (e.g., "Oct 27" or "10/27")
                    formatted_date = game_date.strftime("%b %d")  # "Oct 27"
                    # Format time (e.g., "1:00pm")
                    formatted_time = game_date.strftime("%I:%M%p").lower().lstrip('0')  # "1:00pm"
                except:
                    formatted_date = "TBD"
                    formatted_time = "TBD"
            
            # Create game object
            game = {
                "id": game_id,
                "league": league_key,
                "league_config": league_config,
                "home_abbr": home_abbr,
                "away_abbr": away_abbr,
                "home_score": home_score,
                "away_score": away_score,
                "period": period,
                "period_text": period_text,
                "clock": clock,
                "is_live": is_live,
                "is_final": is_final,
                "is_upcoming": is_upcoming,
                "start_time_utc": game_date,
                "status_text": period_text,
                "game_date": formatted_date,  # For upcoming games display
                "game_time": formatted_time   # For upcoming games display
            }
            
            return game
            
        except Exception as e:
            self.logger.error(f"Error extracting game details: {e}")
            return None
