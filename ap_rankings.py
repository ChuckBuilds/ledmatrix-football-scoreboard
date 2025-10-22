"""
AP Rankings Module for Football Scoreboard Plugin

This module handles AP Top 25/10/5 team resolution and ranking management
for NCAA Football.
"""

import logging
import time
import requests
from typing import Dict, List, Set, Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class APRankingsManager:
    """
    Manages AP Top 25/10/5 team rankings for NCAA Football.
    
    This class handles fetching current rankings and resolving dynamic team names
    like AP_TOP_25 to actual team abbreviations.
    """
    
    # Cache for rankings data
    _rankings_cache: Dict[str, List[str]] = {}
    _cache_timestamp: float = 0
    _cache_duration: int = 3600  # 1 hour cache
    
    # Supported dynamic team patterns
    DYNAMIC_PATTERNS = {
        'AP_TOP_25': {'sport': 'ncaa_fb', 'limit': 25},
        'AP_TOP_10': {'sport': 'ncaa_fb', 'limit': 10}, 
        'AP_TOP_5': {'sport': 'ncaa_fb', 'limit': 5},
    }
    
    def __init__(self, request_timeout: int = 30):
        """Initialize the AP rankings manager."""
        self.request_timeout = request_timeout
        self.logger = logger
        
    def resolve_teams(self, team_list: List[str], sport: str = 'ncaa_fb') -> List[str]:
        """
        Resolve a list of teams, expanding dynamic team names to actual team abbreviations.
        
        Args:
            team_list: List of team names (may include dynamic patterns like AP_TOP_25)
            sport: Sport type for context
            
        Returns:
            List of resolved team abbreviations
        """
        resolved_teams = []
        seen_teams = set()
        
        for team in team_list:
            if team in self.DYNAMIC_PATTERNS:
                # Resolve dynamic team
                dynamic_teams = self._resolve_dynamic_team(team, sport)
                for dynamic_team in dynamic_teams:
                    if dynamic_team not in seen_teams:
                        resolved_teams.append(dynamic_team)
                        seen_teams.add(dynamic_team)
            else:
                # Regular team name
                if team not in seen_teams:
                    resolved_teams.append(team)
                    seen_teams.add(team)
        
        return resolved_teams
    
    def _resolve_dynamic_team(self, dynamic_team: str, sport: str) -> List[str]:
        """
        Resolve a dynamic team name to actual team abbreviations.
        
        Args:
            dynamic_team: Dynamic team name (e.g., "AP_TOP_25")
            sport: Sport type for context
            
        Returns:
            List of team abbreviations
        """
        if dynamic_team not in self.DYNAMIC_PATTERNS:
            self.logger.warning(f"Unknown dynamic team: {dynamic_team}")
            return []
            
        pattern_config = self.DYNAMIC_PATTERNS[dynamic_team]
        target_sport = pattern_config['sport']
        limit = pattern_config['limit']
        
        # Only support NCAA Football rankings for now
        if target_sport != 'ncaa_fb':
            self.logger.warning(f"Dynamic team {dynamic_team} not supported for sport {sport}")
            return []
            
        # Fetch current rankings
        rankings = self._fetch_ncaa_fb_rankings()
        if not rankings:
            self.logger.warning(f"Could not fetch rankings for {dynamic_team}")
            return []
            
        # Get top N teams
        top_teams = list(rankings.keys())[:limit]
        self.logger.info(f"Resolved {dynamic_team} to top {len(top_teams)} teams: {top_teams}")
        
        return top_teams
    
    def _fetch_ncaa_fb_rankings(self) -> Dict[str, int]:
        """
        Fetch current NCAA Football rankings from ESPN API.
        
        Returns:
            Dictionary mapping team abbreviations to their rankings
        """
        current_time = time.time()
        
        # Check if we have cached rankings that are still valid
        if (self._rankings_cache and 
            current_time - self._cache_timestamp < self._cache_duration):
            return self._rankings_cache
        
        try:
            rankings_url = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/rankings"
            response = requests.get(rankings_url, timeout=self.request_timeout)
            response.raise_for_status()
            data = response.json()
            
            rankings = {}
            rankings_data = data.get('rankings', [])
            
            if rankings_data:
                # Use the first ranking (usually AP Top 25)
                first_ranking = rankings_data[0]
                ranking_name = first_ranking.get('name', 'Unknown')
                teams = first_ranking.get('ranks', [])
                
                self.logger.info(f"Using ranking: {ranking_name}")
                self.logger.info(f"Found {len(teams)} teams in ranking")
                
                for team_data in teams:
                    team_info = team_data.get('team', {})
                    team_abbr = team_info.get('abbreviation', '')
                    current_rank = team_data.get('current', 0)
                    
                    if team_abbr and current_rank > 0:
                        rankings[team_abbr] = current_rank
            
            # Cache the results
            self._rankings_cache = rankings
            self._cache_timestamp = current_time
            
            self.logger.info(f"Fetched rankings for {len(rankings)} teams")
            return rankings
            
        except Exception as e:
            self.logger.error(f"Error fetching team rankings: {e}")
            return {}
    
    def get_team_rank(self, team_abbr: str) -> Optional[int]:
        """
        Get the current rank of a specific team.
        
        Args:
            team_abbr: Team abbreviation
            
        Returns:
            Team rank (1-25) or None if not ranked
        """
        rankings = self._fetch_ncaa_fb_rankings()
        return rankings.get(team_abbr.upper())
    
    def is_ranked_team(self, team_abbr: str) -> bool:
        """
        Check if a team is currently ranked in AP Top 25.
        
        Args:
            team_abbr: Team abbreviation
            
        Returns:
            True if team is ranked, False otherwise
        """
        return self.get_team_rank(team_abbr) is not None
    
    def get_top_teams(self, limit: int = 25) -> List[str]:
        """
        Get the top N ranked teams.
        
        Args:
            limit: Number of top teams to return (default 25)
            
        Returns:
            List of team abbreviations in ranking order
        """
        rankings = self._fetch_ncaa_fb_rankings()
        return list(rankings.keys())[:limit]
    
    def clear_cache(self):
        """Clear the rankings cache to force fresh data on next fetch."""
        self._rankings_cache = {}
        self._cache_timestamp = 0
        self.logger.info("AP rankings cache cleared")
