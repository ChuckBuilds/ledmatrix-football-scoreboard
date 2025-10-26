"""
Data Fetcher Module for Football Scoreboard Plugin

This module handles all API data fetching, processing, and caching
for both NFL and NCAA FB games.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import pytz
import requests

try:
    from src.background_data_service import get_background_service  # noqa: F401
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
                    self.logger.info("Using cached NFL schedule for %s", season_year)
                    return cached_data
                elif isinstance(cached_data, list):
                    # Handle old cache format (list of events)
                    self.logger.info("Using cached NFL schedule for %s (legacy format)", season_year)
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
                    self.logger.info("Using cached NCAA FB schedule for %s", season_year)
                    return cached_data
                elif isinstance(cached_data, list):
                    # Handle old cache format (list of events)
                    self.logger.info("Using cached NCAA FB schedule for %s (legacy format)", season_year)
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
                    self.logger.warning("Error fetching %s games for %s: %s", league, formatted_date, e)
                    continue

            self.logger.info("Fetched %d total games for %s across extended date range", len(all_events), league)
            return {"events": all_events}
            
        except Exception as e:
            self.logger.error("Error fetching extended games for %s: %s", league, e)
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
            self.logger.error("Error fetching today's %s games: %s", league, e)
            return None
    
    def _fetch_full_season_games(self, league: str, season_year: int, datestring: str) -> Optional[Dict]:  # noqa: ARG002
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
            
            self.logger.info("Fetched full season %s data: %d events", league, len(data.get('events', [])))
            return data
            
        except Exception as e:
            self.logger.error("Error fetching full season %s games: %s", league, e)
            return None
    
    def _start_background_fetch(self, sport: str, season_year: int, datestring: str, cache_key: str):  # noqa: ARG002
        """Start background fetch for full season data."""
        try:
            def fetch_callback(result):
                """Callback when background fetch completes."""
                if result.success:
                    self.logger.info("Background fetch completed for %s %s: %d events", sport, season_year, len(result.data.get('events', [])))
                else:
                    self.logger.error("Background fetch failed for %s %s: %s", sport, season_year, result.error)
                
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
            self.logger.info("Started background fetch for %s %s", sport, season_year)
            
        except Exception as e:
            self.logger.error("Error starting background fetch for %s: %s", sport, e)
    
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
                self.logger.warning("Error processing game event: %s", e)
                continue

        return games
    
    def _extract_game_details(self, event: Dict, league_key: str, league_config: Dict) -> Optional[Dict]:
        """Extract game details from ESPN API event data - mirrors old football managers exactly."""
        try:
            # Extract basic game info
            game_id = event.get("id", "")
            date_str = event.get("date", "")
            
            # Parse date
            try:
                game_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except (ValueError, TypeError):
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
            home_id = home_team.get("id", "")
            away_id = away_team.get("id", "")
            home_score = home_competitor.get("score", "0")
            away_score = away_competitor.get("score", "0")
            
            # Get logo URLs from team data
            home_logo_url = home_team.get("logo")
            away_logo_url = away_team.get("logo")
            
            # Extract team records (Win-Loss-Tie) - matches old managers
            home_record = home_competitor.get('records', [{}])[0].get('summary', '') if home_competitor.get('records') else ''
            away_record = away_competitor.get('records', [{}])[0].get('summary', '') if away_competitor.get('records') else ''
            
            # Don't show "0-0" records - set to blank instead (matches old managers)
            if home_record in {"0-0", "0-0-0"}:
                home_record = ''
            if away_record in {"0-0", "0-0-0"}:
                away_record = ''
            
            # Determine logo directory based on league
            if league_key == "nfl":
                logo_dir = "assets/sports/nfl_logos"
            else:  # ncaa_fb
                logo_dir = "assets/sports/ncaa_logos"
            
            # Import LogoDownloader for normalization
            try:
                from src.logo_downloader import LogoDownloader
                from pathlib import Path
                
                # Normalize abbreviations and create logo paths
                home_logo_path = Path(logo_dir) / f"{LogoDownloader.normalize_abbreviation(home_abbr)}.png"
                away_logo_path = Path(logo_dir) / f"{LogoDownloader.normalize_abbreviation(away_abbr)}.png"
            except ImportError:
                # Fallback if LogoDownloader not available
                from pathlib import Path
                home_logo_path = Path(logo_dir) / f"{home_abbr}.png"
                away_logo_path = Path(logo_dir) / f"{away_abbr}.png"
            
            # Extract game status
            status = competition.get("status", {})
            period = status.get("period", 0)
            clock = status.get("displayClock", "")
            type_code = status.get("type", {}).get("name", "")
            status_state = status.get("type", {}).get("state", "")
            
            # Determine game state (matches old managers - uses status_state primarily)
            is_live = status_state == "in"
            is_final = status_state == "post"
            is_upcoming = (status_state == "pre" or 
                          type_code.lower() in ['scheduled', 'pre-game', 'status_scheduled'])
            is_halftime = status_state == "halftime" or type_code == "STATUS_HALFTIME"
            is_period_break = status.get("type", {}).get("detail", "").lower() in ["period break", "timeout"]
            
            # --- Football Specific Details (mirrors old football.py exactly) ---
            down_distance_text = ""
            down_distance_text_long = ""
            possession_indicator = None
            scoring_event = ""
            home_timeouts = 0  # Start at 0, only live games will have timeout data
            away_timeouts = 0  # Start at 0, only live games will have timeout data
            is_redzone = False
            possession = None
            
            # Extract situation data for live games
            situation = competition.get("situation", {})
            if situation and status_state == "in":
                down_distance_text = situation.get("shortDownDistanceText", "")
                down_distance_text_long = situation.get("downDistanceText", "")
                is_redzone = situation.get("isRedZone", False)
                possession = situation.get("possession")
                
                # Detect scoring events from status detail
                status_detail = status.get("type", {}).get("detail", "").lower()
                status_short = status.get("type", {}).get("shortDetail", "").lower()
                
                if any(keyword in status_detail for keyword in ["touchdown", "td"]):
                    scoring_event = "TOUCHDOWN"
                elif any(keyword in status_detail for keyword in ["field goal", "fg"]):
                    scoring_event = "FIELD GOAL"
                elif any(keyword in status_detail for keyword in ["extra point", "pat", "point after"]):
                    scoring_event = "PAT"
                elif any(keyword in status_short for keyword in ["touchdown", "td"]):
                    scoring_event = "TOUCHDOWN"
                elif any(keyword in status_short for keyword in ["field goal", "fg"]):
                    scoring_event = "FIELD GOAL"
                elif any(keyword in status_short for keyword in ["extra point", "pat"]):
                    scoring_event = "PAT"
                
                # Determine possession indicator
                possession_team_id = situation.get("possession")
                if possession_team_id:
                    if possession_team_id == home_id:
                        possession_indicator = "home"
                    elif possession_team_id == away_id:
                        possession_indicator = "away"
                
                # Get timeout data for live games (defaults to 3 if not available)
                home_timeouts = situation.get("homeTimeouts", 3)
                away_timeouts = situation.get("awayTimeouts", 3)
            
            # Format date and time for display (do this BEFORE period_text uses it)
            formatted_date = ""
            formatted_time = ""
            game_time = ""
            
            if is_upcoming:
                try:
                    formatted_date = game_date.strftime("%b %d")
                    formatted_time = game_date.strftime("%I:%M%p").lower().lstrip('0')
                except (ValueError, TypeError):
                    formatted_date = "TBD"
                    formatted_time = "TBD"
            
            # Format game_time for period_text (like old managers)
            if status_state == "pre":
                try:
                    game_time = game_date.strftime("%I:%M%p").lower().lstrip('0')
                except (ValueError, TypeError):
                    game_time = "TBD"
            
            # Format period/quarter (mirrors old football.py exactly)
            period_text = ""
            if status_state == "in":
                if period == 0:
                    period_text = "Start"
                elif period >= 1 and period <= 4:
                    period_text = f"Q{period}"
                elif period > 4:
                    period_text = f"OT{period - 4}"
            elif status_state == "halftime" or type_code == "STATUS_HALFTIME":
                period_text = "HALF"
            elif status_state == "post":
                if period > 4:
                    period_text = "Final/OT"
                else:
                    period_text = "Final"
            elif status_state == "pre":
                # Match old managers - use game_time variable
                period_text = game_time
            
            # Create status_text (period + clock for live games, just period for others)
            status_text = period_text
            if status_state == "in" and clock:
                status_text = f"{period_text} {clock}"
            
            # Create game object with all football-specific data
            game = {
                "id": game_id,
                "league": league_key,
                "league_config": league_config,
                "home_abbr": home_abbr,
                "away_abbr": away_abbr,
                "home_id": home_id,
                "away_id": away_id,
                "home_score": home_score,
                "away_score": away_score,
                "period": period,
                "period_text": period_text,
                "clock": clock,
                "is_live": is_live,
                "is_final": is_final,
                "is_upcoming": is_upcoming,
                "is_halftime": is_halftime,
                "is_period_break": is_period_break,
                "start_time_utc": game_date,
                "status_text": status_text,
                "game_date": formatted_date,
                "game_time": formatted_time,
                # Logo paths and URLs (matches old managers)
                "home_logo_path": home_logo_path,
                "away_logo_path": away_logo_path,
                "home_logo_url": home_logo_url,
                "away_logo_url": away_logo_url,
                # Team records (matches old managers)
                "home_record": home_record,
                "away_record": away_record,
                # Football-specific data
                "down_distance_text": down_distance_text,
                "down_distance_text_long": down_distance_text_long,
                "possession_indicator": possession_indicator,
                "scoring_event": scoring_event,
                "home_timeouts": home_timeouts,
                "away_timeouts": away_timeouts,
                "is_redzone": is_redzone,
                "possession": possession
            }
            
            return game
            
        except Exception as e:
            self.logger.error("Error extracting game details: %s", e)
            return None
