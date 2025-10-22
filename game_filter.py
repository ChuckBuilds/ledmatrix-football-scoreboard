"""
Game Filter Module for Football Scoreboard Plugin

This module handles game filtering, favorite team logic, and game sorting
for both NFL and NCAA FB games.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class GameFilter:
    """Handles game filtering and sorting operations."""
    
    def __init__(self, ap_rankings_manager=None):
        """Initialize the game filter."""
        self.ap_rankings_manager = ap_rankings_manager
        self.logger = logger
    
    def filter_games_by_mode(self, games: List[Dict], mode: str, leagues_config: Dict) -> List[Dict]:
        """
        Filter games based on display mode (NFL and NCAA FB modes).
        
        Args:
            games: List of all games
            mode: Display mode (e.g., "nfl_live", "ncaa_fb_recent")
            leagues_config: League configuration dictionary
            
        Returns:
            Filtered list of games for the specified mode
        """
        if not games:
            return []

        filtered_games = []

        for game in games:
            league = game.get("league", "nfl")
            league_config = game.get("league_config", {})
            display_modes = league_config.get("display_modes", {})

            # Determine if this is an NFL or NCAA FB mode
            if mode.startswith("nfl_"):
                target_league = "nfl"
            elif mode.startswith("ncaa_fb_"):
                target_league = "ncaa_fb"
            else:
                continue

            # Only process games for the correct league
            if league != target_league:
                continue

            # Check if this mode is enabled
            mode_enabled = False
            if mode == "nfl_live" or mode == "ncaa_fb_live":
                mode_enabled = display_modes.get("show_live", True)
                game_matches = game.get("is_live", False)
            elif mode == "nfl_recent" or mode == "ncaa_fb_recent":
                mode_enabled = display_modes.get("show_recent", True)
                # Check if game is final
                if game.get("is_final", False):
                    if mode == "nfl_recent":
                        # NFL: Check if game is within recent date range (last 21 days like SportsRecent class)
                        game_time = game.get("start_time_utc")
                        if game_time:
                            now = datetime.now(timezone.utc)
                            recent_cutoff = now - timedelta(days=21)
                            game_matches = game_time >= recent_cutoff
                        else:
                            game_matches = False
                    else:  # ncaa_fb_recent
                        # NCAA FB: Check the whole schedule for recent games (no date restriction)
                        game_matches = True
                else:
                    game_matches = False
            elif mode == "nfl_upcoming" or mode == "ncaa_fb_upcoming":
                mode_enabled = display_modes.get("show_upcoming", True)
                game_matches = game.get("is_upcoming", False)
            else:
                continue

            # Only include games if the mode is enabled and the game matches the criteria
            if mode_enabled and game_matches:
                filtered_games.append(game)
            

        # Apply favorite teams filtering if enabled - one game per favorite team
        if filtered_games:
            filtered_games = self._apply_favorite_team_filtering(
                filtered_games, mode, leagues_config
            )

        # Sort games appropriately for the mode
        filtered_games = self._sort_games(filtered_games, mode)

        return filtered_games
    
    def _apply_favorite_team_filtering(self, games: List[Dict], mode: str, leagues_config: Dict) -> List[Dict]:
        """Apply favorite team filtering with one game per favorite team logic."""
        # Determine which league config to use based on the mode
        if mode.startswith("nfl_"):
            league_key = "nfl"
        elif mode.startswith("ncaa_fb_"):
            league_key = "ncaa_fb"
        else:
            league_key = "nfl"  # Default fallback
            
        league_config = leagues_config.get(league_key, {})
        filtering = league_config.get("filtering", {})
        show_favorite_teams_only = filtering.get("show_favorite_teams_only", False)

        if not show_favorite_teams_only:
            return games

        favorite_teams = league_config.get("favorite_teams", [])
        if not favorite_teams:
            return games

        # Get all games involving favorite teams
        favorite_team_games = [game for game in games if self._is_favorite_game(game, favorite_teams)]
        
        # Select one game per favorite team (like NFL manager)
        team_games = []
        for team in favorite_teams:
            # Find games where this team is playing
            team_specific_games = [game for game in favorite_team_games 
                                 if game['home_abbr'] == team or game['away_abbr'] == team]
            
            if team_specific_games:
                # Sort by game time and take the appropriate game based on mode
                if "recent" in mode:
                    # For recent games, take the most recent
                    team_specific_games.sort(key=lambda g: g.get('start_time_utc') or datetime.max.replace(tzinfo=timezone.utc), reverse=True)
                else:
                    # For upcoming games, take the earliest
                    team_specific_games.sort(key=lambda g: g.get('start_time_utc') or datetime.max.replace(tzinfo=timezone.utc))
                
                team_games.append(team_specific_games[0])

        # Sort the final list appropriately
        if "recent" in mode:
            # Most recent first
            team_games.sort(key=lambda g: g.get('start_time_utc') or datetime.max.replace(tzinfo=timezone.utc), reverse=True)
        else:
            # Earliest first
            team_games.sort(key=lambda g: g.get('start_time_utc') or datetime.max.replace(tzinfo=timezone.utc))

        return team_games
    
    def _is_favorite_game(self, game: Dict, favorite_teams: List[str]) -> bool:
        """
        Check if game involves a favorite team.
        
        Args:
            game: Game dictionary
            favorite_teams: List of favorite team abbreviations
            
        Returns:
            True if game involves a favorite team
        """
        if not favorite_teams:
            return False

        home_abbr = game.get("home_abbr", "").upper()
        away_abbr = game.get("away_abbr", "").upper()

        # Check for dynamic team patterns (AP_TOP_25, AP_TOP_10, AP_TOP_5)
        if self.ap_rankings_manager:
            try:
                # Resolve dynamic teams to actual team abbreviations
                resolved_favorites = self.ap_rankings_manager.resolve_teams(favorite_teams)
                return home_abbr in resolved_favorites or away_abbr in resolved_favorites
            except Exception as e:
                self.logger.warning(f"Error resolving dynamic teams: {e}")
                # Fallback to direct matching
                return home_abbr in favorite_teams or away_abbr in favorite_teams
        else:
            # Fallback to direct matching if resolver not available
            return home_abbr in favorite_teams or away_abbr in favorite_teams
    
    def _sort_games(self, games: List[Dict], mode: str) -> List[Dict]:
        """
        Sort games appropriately for the display mode.
        
        Args:
            games: List of games to sort
            mode: Display mode
            
        Returns:
            Sorted list of games
        """
        if not games:
            return games

        # Define sorting key based on mode
        def sort_key(game):
            # Priority order: live games first, then by game state and time
            live_score = 0 if game.get("is_live", False) else 1
            favorite_score = 0 if self._is_favorite_game(game, []) else 1  # This will be overridden by actual favorite checking
            state_score = 0 if game.get("is_live", False) else 1
            
            return (
                live_score,
                favorite_score,
                state_score,
                game.get("start_time_utc", datetime.max.replace(tzinfo=timezone.utc))
            )

        games.sort(key=sort_key)
        return games
    
    def get_live_games(self, games: List[Dict], leagues_config: Dict) -> List[Dict]:
        """
        Extract live games from all games, applying favorite team filtering.
        
        Args:
            games: List of all games
            leagues_config: League configuration dictionary
            
        Returns:
            List of live games
        """
        live_games = []
        
        for game in games:
            if game.get("is_live", False) or game.get("is_halftime", False):
                league = game.get("league", "nfl")
                league_config = leagues_config.get(league, {})
                filtering = league_config.get("filtering", {})
                show_favorite_teams_only = filtering.get("show_favorite_teams_only", False)
                
                if not show_favorite_teams_only or self._is_favorite_game(game, league_config.get("favorite_teams", [])):
                    live_games.append(game)
        
        return live_games
