"""
Simplified BaseOddsManager for plugin use
"""

import time
import logging
import requests
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
import pytz

class BaseOddsManager:
    """
    Simplified base class for odds data fetching and management.
    
    Provides core functionality for:
    - ESPN API odds fetching
    - Caching and data processing
    - Error handling and timeouts
    - League mapping and data extraction
    """
    
    def __init__(self, cache_manager, config_manager=None):
        """
        Initialize the base odds manager.
        
        Args:
            cache_manager: Cache manager instance for data persistence
            config_manager: Configuration manager (optional)
        """
        self.cache_manager = cache_manager
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.base_url = "https://sports.core.api.espn.com/v2/sports"
        
        # Configuration with defaults
        self.update_interval = 3600  # 1 hour default
        self.request_timeout = 30    # 30 seconds default
        self.cache_ttl = 1800       # 30 minutes default
        
        # Load configuration if available
        if config_manager:
            self._load_configuration()
    
    def _load_configuration(self):
        """Load configuration from config manager."""
        if not self.config_manager:
            return
            
        try:
            config = self.config_manager.get_config()
            odds_config = config.get('base_odds_manager', {})
            
            self.update_interval = odds_config.get('update_interval', self.update_interval)
            self.request_timeout = odds_config.get('timeout', self.request_timeout)
            self.cache_ttl = odds_config.get('cache_ttl', self.cache_ttl)
            
            self.logger.debug(f"BaseOddsManager configuration loaded: "
                            f"update_interval={self.update_interval}s, "
                            f"timeout={self.request_timeout}s, "
                            f"cache_ttl={self.cache_ttl}s")
                            
        except Exception as e:
            self.logger.warning(f"Failed to load BaseOddsManager configuration: {e}")
    
    def get_odds(self, sport: str | None, league: str | None, event_id: str, 
                 update_interval_seconds: int = None) -> Optional[Dict[str, Any]]:
        """
        Fetch odds data for a specific game.
        
        Args:
            sport: Sport name (e.g., 'football', 'basketball')
            league: League name (e.g., 'nfl', 'nba')
            event_id: ESPN event ID
            update_interval_seconds: Override default update interval
            
        Returns:
            Dictionary containing odds data or None if unavailable
        """
        try:
            # Use provided interval or default
            interval = update_interval_seconds or self.update_interval
            
            # Create cache key
            cache_key = f"odds_{sport}_{league}_{event_id}"
            
            # Check cache first
            cached_data = self.cache_manager.get(cache_key)
            if cached_data:
                cache_time = cached_data.get('cache_time', 0)
                if time.time() - cache_time < interval:
                    self.logger.debug(f"Using cached odds for {event_id}")
                    return cached_data.get('odds_data')
            
            # Fetch fresh data
            odds_data = self._fetch_odds_from_api(sport, league, event_id)
            
            if odds_data:
                # Cache the result
                cache_data = {
                    'odds_data': odds_data,
                    'cache_time': time.time()
                }
                self.cache_manager.set(cache_key, cache_data, ttl=self.cache_ttl)
                self.logger.debug(f"Fetched and cached odds for {event_id}")
                return odds_data
            else:
                self.logger.warning(f"No odds data available for {event_id}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error fetching odds for {event_id}: {e}")
            return None
    
    def _fetch_odds_from_api(self, sport: str, league: str, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch odds data from ESPN API.
        
        Args:
            sport: Sport name
            league: League name  
            event_id: ESPN event ID
            
        Returns:
            Dictionary containing odds data or None
        """
        try:
            # Map sport/league to ESPN API format
            sport_mapping = {
                'football': 'football',
                'basketball': 'basketball',
                'baseball': 'baseball',
                'hockey': 'hockey'
            }
            
            league_mapping = {
                'nfl': 'nfl',
                'ncaa_fb': 'college-football',
                'nba': 'nba',
                'ncaam_basketball': 'mens-college-basketball',
                'mlb': 'mlb',
                'nhl': 'nhl'
            }
            
            espn_sport = sport_mapping.get(sport, sport)
            espn_league = league_mapping.get(league, league)
            
            # Construct API URL
            url = f"{self.base_url}/{espn_sport}/{espn_league}/events/{event_id}/odds"
            
            # Make request
            headers = {
                'User-Agent': 'LEDMatrix/1.0',
                'Accept': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=self.request_timeout)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract relevant odds data
            odds_data = self._extract_odds_data(data)
            
            if odds_data:
                self.logger.debug(f"Successfully fetched odds for {event_id}")
                return odds_data
            else:
                self.logger.debug(f"No odds data found for {event_id}")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed for odds {event_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error processing odds data for {event_id}: {e}")
            return None
    
    def _extract_odds_data(self, api_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract relevant odds data from ESPN API response.
        
        Args:
            api_data: Raw API response data
            
        Returns:
            Processed odds data dictionary
        """
        try:
            odds_data = {}
            
            # Extract spread data
            if 'items' in api_data:
                for item in api_data['items']:
                    if item.get('provider', {}).get('name') == 'Caesars Sportsbook':
                        details = item.get('details', '')
                        if 'SPREAD' in details:
                            # Parse spread from details string
                            # This is a simplified parser - real implementation would be more robust
                            odds_data['spread'] = 0.0  # Placeholder
                        elif 'TOTAL' in details:
                            # Parse over/under from details string
                            odds_data['over_under'] = 0.0  # Placeholder
            
            # Return data if we found anything useful
            if odds_data:
                return odds_data
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Error extracting odds data: {e}")
            return None
