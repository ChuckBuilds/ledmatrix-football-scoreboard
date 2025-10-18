"""
Football Scoreboard Plugin for LEDMatrix

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

API Version: 1.0.0
"""

import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pathlib import Path

import pytz
import requests
from PIL import Image, ImageDraw

try:
    # Try importing from LEDMatrix src directory
    from src.plugin_system.base_plugin import BasePlugin
except ImportError:
    try:
        # Try importing from plugin_system directly
        from plugin_system.base_plugin import BasePlugin
    except ImportError:
        BasePlugin = None

logger = logging.getLogger(__name__)


class FootballScoreboardPlugin(BasePlugin if BasePlugin else object):
    """
    Football scoreboard plugin for displaying games across multiple leagues.

    Supports NFL and NCAA Football with live, recent, and upcoming game modes.

    Configuration options:
        leagues: Enable/disable NFL, NCAA FB
        display_modes: Enable live, recent, upcoming modes
        favorite_teams: Team abbreviations per league
        show_records: Display team records
        show_ranking: Display team rankings
        background_service: Data fetching configuration
    """

    # ESPN API endpoints for each league
    ESPN_API_URLS = {
        'nfl': 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard',
        'ncaa_fb': 'https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard'
    }

    def __init__(self, plugin_id: str, config: Dict[str, Any],
                 display_manager, cache_manager, plugin_manager):
        """Initialize the football scoreboard plugin."""
        if BasePlugin:
            super().__init__(plugin_id, config, display_manager, cache_manager, plugin_manager)
        else:
            # Fallback initialization if BasePlugin is not available
            self.plugin_id = plugin_id
            self.config = config
            self.display_manager = display_manager
            self.cache_manager = cache_manager
            self.plugin_manager = plugin_manager
            self.logger = logging.getLogger(f"plugin.{plugin_id}")
            self.enabled = config.get('enabled', True)

        # Plugin is self-contained and doesn't depend on base classes

        # Configuration - per-league structure like original managers
        self.leagues = {
            'nfl': config.get('nfl', {}),
            'ncaa_fb': config.get('ncaa_fb', {})
        }

        # Global settings
        self.global_config = config
        self.display_duration = config.get('display_duration', 15)
        self.show_records = config.get('show_records', False)
        self.show_ranking = config.get('show_ranking', False)

        # Background service configuration (internal only)
        self.background_config = {
            'enabled': True,
            'request_timeout': 30,
            'max_retries': 3,
            'priority': 2
        }

        # State
        self.current_games = []
        self.current_league = None
        self.current_display_mode = None
        self.last_update = 0
        self.initialized = True

        # Register fonts
        self._register_fonts()

        # Log enabled leagues and their settings
        enabled_leagues = []
        for league_key, league_config in self.leagues.items():
            if league_config.get('enabled', False):
                enabled_leagues.append(league_key)

        self.logger.info("Football scoreboard plugin initialized")
        self.logger.info(f"Enabled leagues: {enabled_leagues}")

    def _register_fonts(self):
        """Register fonts with the font manager."""
        try:
            if not hasattr(self.plugin_manager, 'font_manager'):
                return

            font_manager = self.plugin_manager.font_manager

            # Team name font
            font_manager.register_manager_font(
                manager_id=self.plugin_id,
                element_key=f"{self.plugin_id}.team_name",
                family="press_start",
                size_px=10,
                color=(255, 255, 255)
            )

            # Score font
            font_manager.register_manager_font(
                manager_id=self.plugin_id,
                element_key=f"{self.plugin_id}.score",
                family="press_start",
                size_px=12,
                color=(255, 200, 0)
            )

            # Status font (quarter, time)
            font_manager.register_manager_font(
                manager_id=self.plugin_id,
                element_key=f"{self.plugin_id}.status",
                family="four_by_six",
                size_px=6,
                color=(0, 255, 0)
            )

            # Detail font (down/distance, possession)
            font_manager.register_manager_font(
                manager_id=self.plugin_id,
                element_key=f"{self.plugin_id}.detail",
                family="four_by_six",
                size_px=6,
                color=(200, 200, 0)
            )

            self.logger.info("Football scoreboard fonts registered")
        except Exception as e:
            self.logger.warning(f"Error registering fonts: {e}")

    def update(self) -> None:
        """Update football game data for all enabled leagues."""
        if not self.initialized:
            return

        try:
            self.current_games = []

            # Fetch data for each enabled league
            for league_key, league_config in self.leagues.items():
                if league_config.get('enabled', False):
                    games = self._fetch_league_data(league_key, league_config)
                    if games:
                        # Add league info to each game
                        for game in games:
                            game['league_config'] = league_config
                        self.current_games.extend(games)

            # Sort games - prioritize live games and favorites
            self._sort_games()

            self.last_update = time.time()
            self.logger.debug(f"Updated football data: {len(self.current_games)} games")

        except Exception as e:
            self.logger.error(f"Error updating football data: {e}")

    def _sort_games(self):
        """Sort games by priority and favorites."""
        def sort_key(game):
            league_key = game.get('league')
            league_config = game.get('league_config', {})
            status = game.get('status', {})

            # Priority 1: Live games
            is_live = status.get('state') == 'in'
            live_score = 0 if is_live else 1

            # Priority 2: Favorite teams
            favorite_score = 0 if self._is_favorite_game(game) else 1

            # Priority 3: Start time (earlier games first for upcoming, later for recent)
            start_time = game.get('start_time', '')

            return (live_score, favorite_score, start_time)

        self.current_games.sort(key=sort_key)

    def _fetch_league_data(self, league_key: str, league_config: Dict) -> List[Dict]:
        """Fetch game data for a specific league."""
        cache_key = f"football_{league_key}_{datetime.now().strftime('%Y%m%d')}"
        update_interval = league_config.get('update_interval_seconds', 60)

        # Check cache first (use league-specific interval)
        cached_data = self.cache_manager.get(cache_key)
        if cached_data and (time.time() - self.last_update) < update_interval:
            self.logger.debug(f"Using cached data for {league_key}")
            return cached_data

        # Fetch from API
        try:
            url = self.ESPN_API_URLS.get(league_key)
            if not url:
                self.logger.error(f"Unknown league key: {league_key}")
                return []

            self.logger.info(f"Fetching {league_key} data from ESPN API...")
            response = requests.get(url, timeout=self.background_config.get('request_timeout', 30))
            response.raise_for_status()

            data = response.json()
            games = self._process_api_response(data, league_key, league_config)

            # Cache for league-specific interval
            self.cache_manager.set(cache_key, games, ttl=update_interval * 2)

            return games

        except requests.RequestException as e:
            self.logger.error(f"Error fetching {league_key} data: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Error processing {league_key} data: {e}")
            return []

    def _process_api_response(self, data: Dict, league_key: str, league_config: Dict) -> List[Dict]:
        """Process ESPN API response into standardized game format."""
        games = []

        try:
            events = data.get('events', [])

            for event in events:
                try:
                    game = self._extract_game_info(event, league_key, league_config)
                    if game:
                        games.append(game)
                except Exception as e:
                    self.logger.error(f"Error extracting game info: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error processing API response: {e}")

        return games

    def _extract_game_info(self, event: Dict, league_key: str, league_config: Dict) -> Optional[Dict]:
        """Extract game information from ESPN event with football-specific details."""
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

            # Extract basic game details
            game = {
                'league': league_key,
                'league_config': league_config,
                'game_id': event.get('id'),
                'home_team': {
                    'name': home_team.get('team', {}).get('displayName', 'Unknown'),
                    'abbrev': home_team.get('team', {}).get('abbreviation', 'UNK'),
                    'score': int(home_team.get('score', 0)),
                    'logo': home_team.get('team', {}).get('logo')
                },
                'away_team': {
                    'name': away_team.get('team', {}).get('displayName', 'Unknown'),
                    'abbrev': away_team.get('team', {}).get('abbreviation', 'UNK'),
                    'score': int(away_team.get('score', 0)),
                    'logo': away_team.get('team', {}).get('logo')
                },
                'status': {
                    'state': status.get('type', {}).get('state', 'unknown'),
                    'detail': status.get('type', {}).get('detail', ''),
                    'short_detail': status.get('type', {}).get('shortDetail', ''),
                    'period': status.get('period', 0),
                    'display_clock': status.get('displayClock', '')
                },
                'start_time': event.get('date', ''),
                'venue': competition.get('venue', {}).get('fullName', 'Unknown Venue')
            }

            # Add football-specific details
            situation = competition.get('situation', {})
            if situation:
                game['down_distance'] = situation.get('shortDownDistanceText', '')
                game['possession'] = situation.get('possession')
                game['is_redzone'] = situation.get('isRedZone', False)
                
                # Add more detailed football info
                game['down'] = situation.get('down')
                game['distance'] = situation.get('distance')
                game['yard_line'] = situation.get('yardLine')
                game['possession_text'] = situation.get('possessionText', '')
                
                # Timeouts
                game['home_timeouts'] = situation.get('homeTimeouts', 0)
                game['away_timeouts'] = situation.get('awayTimeouts', 0)
            
            # Add scoring events detection
            game['scoring_event'] = self._detect_scoring_event(status)
            
            # Add game phase info
            game['game_phase'] = self._determine_game_phase(status, league_key)
            
            return game

        except Exception as e:
            self.logger.error(f"Error extracting game info: {e}")
            return None

    def _detect_scoring_event(self, status: Dict) -> str:
        """Detect if there's a scoring event happening."""
        try:
            status_detail = status.get('type', {}).get('detail', '').lower()
            status_short = status.get('type', {}).get('shortDetail', '').lower()
            
            scoring_keywords = ['touchdown', 'field goal', 'safety', 'extra point', 'two-point', 'conversion']
            
            for keyword in scoring_keywords:
                if keyword in status_detail or keyword in status_short:
                    return keyword
            
            return ""
        except:
            return ""

    def _determine_game_phase(self, status: Dict, league: str) -> str:
        """Determine the current phase of the game."""
        try:
            state = status.get('type', {}).get('state', '')
            period = status.get('period', 0)
            
            if state == 'pre':
                return 'pregame'
            elif state == 'in':
                if league == 'nfl':
                    if period <= 4:
                        return f'Q{period}'
                    else:
                        return 'OT'
                else:  # ncaa_fb
                    if period <= 4:
                        return f'Q{period}'
                    else:
                        return 'OT'
            elif state == 'post':
                return 'final'
            else:
                return 'unknown'
        except:
            return 'unknown'

    def _is_favorite_game(self, game: Dict) -> bool:
        """Check if game involves a favorite team."""
        league = game.get('league')
        league_config = game.get('league_config', {})
        favorites = league_config.get('favorite_teams', [])

        if not favorites:
            return False

        home_abbrev = game.get('home_team', {}).get('abbrev')
        away_abbrev = game.get('away_team', {}).get('abbrev')

        return home_abbrev in favorites or away_abbrev in favorites

    def display(self, display_mode: str = None, force_clear: bool = False) -> None:
        """
        Display football games.

        Args:
            display_mode: Which mode to display (football_live, football_recent, football_upcoming)
            force_clear: If True, clear display before rendering
        """
        if not self.initialized:
            self._display_error("Football plugin not initialized")
            return

        # Determine which display mode to use - prioritize live games if enabled
        if not display_mode:
            # Auto-select mode based on available games and priorities
            if self._has_live_games():
                display_mode = 'football_live'
            else:
                # Fall back to recent or upcoming
                display_mode = 'football_recent' if self._has_recent_games() else 'football_upcoming'

        self.current_display_mode = display_mode

        # Filter games by display mode
        filtered_games = self._filter_games_by_mode(display_mode)

        if not filtered_games:
            self._display_no_games(display_mode)
            return

        # Display the first game (rotation handled by LEDMatrix)
        game = filtered_games[0]
        self._display_game(game, display_mode)

    def _filter_games_by_mode(self, mode: str) -> List[Dict]:
        """Filter games based on display mode and per-league settings."""
        filtered = []

        for game in self.current_games:
            league_key = game.get('league')
            league_config = game.get('league_config', {})
            status = game.get('status', {})
            state = status.get('state')

            # Check if this mode is enabled for this league
            display_modes = league_config.get('display_modes', {})
            mode_enabled = display_modes.get(mode.replace('football_', ''), False)
            if not mode_enabled:
                continue

            # Filter by game state and per-league limits
            if mode == 'football_live' and state == 'in':
                filtered.append(game)

            elif mode == 'football_recent' and state == 'post':
                # Check recent games limit for this league
                recent_limit = league_config.get('recent_games_to_show', 5)
                recent_count = len([g for g in filtered if g.get('league') == league_key and g.get('status', {}).get('state') == 'post'])
                if recent_count >= recent_limit:
                    continue
                filtered.append(game)

            elif mode == 'football_upcoming' and state == 'pre':
                # Check upcoming games limit for this league
                upcoming_limit = league_config.get('upcoming_games_to_show', 10)
                upcoming_count = len([g for g in filtered if g.get('league') == league_key and g.get('status', {}).get('state') == 'pre'])
                if upcoming_count >= upcoming_limit:
                    continue
                filtered.append(game)

        return filtered

    def _has_live_games(self) -> bool:
        """Check if there are any live games available."""
        return any(game.get('status', {}).get('state') == 'in' for game in self.current_games)

    def _has_recent_games(self) -> bool:
        """Check if there are any recent games available."""
        return any(game.get('status', {}).get('state') == 'post' for game in self.current_games)

    def _display_game(self, game: Dict, mode: str):
        """Display a single game with professional scorebug layout matching old managers."""
        try:
            matrix_width = self.display_manager.matrix.width
            matrix_height = self.display_manager.matrix.height

            # Create image with transparency support
            main_img = Image.new('RGBA', (matrix_width, matrix_height), (0, 0, 0, 255))
            overlay = Image.new('RGBA', (matrix_width, matrix_height), (0, 0, 0, 0))
            draw_overlay = ImageDraw.Draw(overlay)

            # Get team info
            home_team = game.get('home_team', {})
            away_team = game.get('away_team', {})
            status = game.get('status', {})
            
            # Get football-specific info
            down_distance = game.get('down_distance', '')
            possession = game.get('possession', '')
            game_phase = game.get('game_phase', '')
            scoring_event = self._detect_scoring_event(status)
            is_redzone = game.get('is_redzone', False)

            # Team info
            home_abbrev = home_team.get('abbrev', 'HOME')
            away_abbrev = away_team.get('abbrev', 'AWAY')
            home_score = home_team.get('score', 0)
            away_score = away_team.get('score', 0)

            # Load team logos
            home_logo = self._load_team_logo(home_team, game.get('league', ''))
            away_logo = self._load_team_logo(away_team, game.get('league', ''))

            # If logos failed to load, show text fallback
            if not home_logo or not away_logo:
                self.logger.warning("Failed to load team logos, using text fallback")
                self._draw_text_fallback(draw_overlay, home_team, away_team, status, game, matrix_width, matrix_height)
            else:
                # Professional scorebug layout with logos
                self._draw_scorebug_layout(draw_overlay, main_img, home_logo, away_logo, 
                                         home_team, away_team, status, game, 
                                         matrix_width, matrix_height)

            # Composite the overlay onto main image
            final_img = Image.alpha_composite(main_img, overlay)
            
            self.display_manager.image = final_img.convert('RGB').copy()
            self.display_manager.update_display()

        except Exception as e:
            self.logger.error(f"Error displaying game: {e}")
            self._display_error("Display error")

    def _load_team_logo(self, team: Dict, league: str) -> Optional[Image.Image]:
        """Load and resize team logo."""
        try:
            # Determine logo directory based on league
            if league == 'nfl':
                logo_dir = "assets/sports/nfl_logos"
            elif league == 'ncaa_fb':
                logo_dir = "assets/sports/ncaa_logos"
            else:
                return None
            
            team_abbrev = team.get('abbrev', '').lower()
            if not team_abbrev:
                return None
            
            # Try different logo file extensions
            logo_extensions = ['.png', '.jpg', '.jpeg']
            logo_path = None
            
            for ext in logo_extensions:
                potential_path = f"{logo_dir}/{team_abbrev}{ext}"
                if os.path.exists(potential_path):
                    logo_path = potential_path
                    break
            
            if not logo_path:
                # Try with team name instead of abbreviation
                team_name = team.get('name', '').lower().replace(' ', '_')
                for ext in logo_extensions:
                    potential_path = f"{logo_dir}/{team_name}{ext}"
                    if os.path.exists(potential_path):
                        logo_path = potential_path
                        break
            
            if not logo_path:
                return None
            
            # Load and resize logo
            logo = Image.open(logo_path).convert('RGBA')
            # Resize to appropriate size for matrix (typically 16x16 or 20x20)
            max_size = min(self.display_manager.matrix.height // 2, 20)
            logo.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            return logo
            
        except Exception as e:
            self.logger.debug(f"Could not load logo for {team.get('abbrev', 'unknown')}: {e}")
            return None

    def _draw_scorebug_layout(self, draw_overlay: ImageDraw.Draw, main_img: Image.Image,
                            home_logo: Image.Image, away_logo: Image.Image,
                            home_team: Dict, away_team: Dict, status: Dict, game: Dict,
                            matrix_width: int, matrix_height: int):
        """Draw professional scorebug layout matching old managers."""
        try:
            center_y = matrix_height // 2
            
            # Draw team logos
            home_x = matrix_width - home_logo.width + 10
            home_y = center_y - (home_logo.height // 2)
            main_img.paste(home_logo, (home_x, home_y), home_logo)
            
            away_x = -10
            away_y = center_y - (away_logo.height // 2)
            main_img.paste(away_logo, (away_x, away_y), away_logo)
            
            # Draw scores (centered)
            home_score = str(home_team.get('score', 0))
            away_score = str(away_team.get('score', 0))
            score_text = f"{away_score}-{home_score}"
            
            # Use default font for scores
            score_width = len(score_text) * 6  # Approximate width
            score_x = (matrix_width - score_width) // 2
            score_y = (matrix_height // 2) - 3
            self._draw_text_with_outline(draw_overlay, score_text, (score_x, score_y), fill=(255, 200, 0))
            
            # Period/Quarter and Clock (Top center)
            period_clock_text = f"{game.get('game_phase', '')} {status.get('display_clock', '')}".strip()
            if status.get('state') == 'post':
                period_clock_text = "FINAL"
            elif status.get('state') == 'pre':
                period_clock_text = "UPCOMING"
            
            status_width = len(period_clock_text) * 4  # Approximate width
            status_x = (matrix_width - status_width) // 2
            status_y = 1
            self._draw_text_with_outline(draw_overlay, period_clock_text, (status_x, status_y), fill=(0, 255, 0))
            
            # Down & Distance or Scoring Event (Below scores)
            scoring_event = self._detect_scoring_event(status)
            down_distance = game.get('down_distance', '')
            
            # Show scoring event if detected, otherwise show down & distance
            if scoring_event and status.get('state') == 'in':
                # Display scoring event with special formatting
                event_width = len(scoring_event) * 4
                event_x = (matrix_width - event_width) // 2
                event_y = matrix_height - 7
                
                # Color coding for different scoring events
                if 'touchdown' in scoring_event.lower():
                    event_color = (255, 215, 0)  # Gold
                elif 'field goal' in scoring_event.lower():
                    event_color = (0, 255, 0)    # Green
                elif 'extra point' in scoring_event.lower() or 'pat' in scoring_event.lower():
                    event_color = (255, 165, 0)  # Orange
                else:
                    event_color = (255, 255, 255)  # White
                
                self._draw_text_with_outline(draw_overlay, scoring_event.upper(), (event_x, event_y), fill=event_color)
                
            elif down_distance and status.get('state') == 'in':
                # Show down & distance
                dd_width = len(down_distance) * 4
                dd_x = (matrix_width - dd_width) // 2
                dd_y = matrix_height - 7
                down_color = (200, 200, 0) if not game.get('is_redzone', False) else (255, 0, 0)
                self._draw_text_with_outline(draw_overlay, down_distance, (dd_x, dd_y), fill=down_color)
                
                # Possession Indicator (small football icon)
                possession = game.get('possession', '')
                if possession:
                    self._draw_possession_indicator(draw_overlay, possession, dd_x, dd_width, dd_y)
            
            # Timeouts (Bottom corners)
            self._draw_timeouts(draw_overlay, game, matrix_width, matrix_height)
            
        except Exception as e:
            self.logger.error(f"Error drawing scorebug layout: {e}")

    def _draw_text_fallback(self, draw_overlay: ImageDraw.Draw, home_team: Dict, away_team: Dict, 
                          status: Dict, game: Dict, matrix_width: int, matrix_height: int):
        """Draw text-only fallback when logos are not available."""
        try:
            home_abbrev = home_team.get('abbrev', 'HOME')
            away_abbrev = away_team.get('abbrev', 'AWAY')
            home_score = home_team.get('score', 0)
            away_score = away_team.get('score', 0)
            
            # Team matchup
            matchup_text = f"{away_abbrev} @ {home_abbrev}"
            draw_overlay.text((2, 2), matchup_text, fill=(255, 255, 255))
            
            # Scores
            score_text = f"{away_score} - {home_score}"
            draw_overlay.text((2, 12), score_text, fill=(255, 200, 0))
            
            # Game status
            if status.get('state') == 'in':
                period_clock_text = f"{game.get('game_phase', '')} {status.get('display_clock', '')}"
                draw_overlay.text((2, 22), period_clock_text, fill=(0, 255, 0))
                
                # Down & distance
                down_distance = game.get('down_distance', '')
                if down_distance:
                    draw_overlay.text((2, 32), down_distance, fill=(200, 200, 0))
            elif status.get('state') == 'post':
                draw_overlay.text((2, 22), "FINAL", fill=(200, 200, 200))
            else:
                draw_overlay.text((2, 22), "UPCOMING", fill=(255, 255, 0))
                
        except Exception as e:
            self.logger.error(f"Error drawing text fallback: {e}")

    def _draw_text_with_outline(self, draw: ImageDraw.Draw, text: str, position: tuple, fill: tuple):
        """Draw text with outline for better visibility."""
        try:
            x, y = position
            # Draw outline
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx != 0 or dy != 0:
                        draw.text((x + dx, y + dy), text, fill=(0, 0, 0))
            # Draw main text
            draw.text((x, y), text, fill=fill)
        except Exception as e:
            self.logger.error(f"Error drawing text with outline: {e}")

    def _draw_possession_indicator(self, draw: ImageDraw.Draw, possession: str, dd_x: int, dd_width: int, dd_y: int):
        """Draw possession indicator (football icon)."""
        try:
            ball_radius_x = 3
            ball_radius_y = 2
            ball_color = (139, 69, 19)  # Brown
            lace_color = (255, 255, 255)  # White
            
            ball_y_center = dd_y + 3  # Center with text
            possession_ball_padding = 3
            
            if possession == "away":
                ball_x_center = dd_x - possession_ball_padding - ball_radius_x
            elif possession == "home":
                ball_x_center = dd_x + dd_width + possession_ball_padding + ball_radius_x
            else:
                return
            
            if ball_x_center > 0:
                # Draw football shape
                draw.ellipse(
                    (ball_x_center - ball_radius_x, ball_y_center - ball_radius_y,
                     ball_x_center + ball_radius_x, ball_y_center + ball_radius_y),
                    fill=ball_color, outline=(0, 0, 0)
                )
                # Draw lace
                draw.line(
                    (ball_x_center - 1, ball_y_center, ball_x_center + 1, ball_y_center),
                    fill=lace_color, width=1
                )
        except Exception as e:
            self.logger.error(f"Error drawing possession indicator: {e}")

    def _draw_timeouts(self, draw: ImageDraw.Draw, game: Dict, matrix_width: int, matrix_height: int):
        """Draw timeout indicators in bottom corners."""
        try:
            timeout_bar_width = 4
            timeout_bar_height = 2
            timeout_spacing = 1
            timeout_y = matrix_height - timeout_bar_height - 1
            
            # Away timeouts (bottom left)
            away_timeouts = game.get('away_timeouts', 0)
            for i in range(3):
                to_x = 2 + i * (timeout_bar_width + timeout_spacing)
                color = (255, 255, 255) if i < away_timeouts else (80, 80, 80)
                draw.rectangle([to_x, timeout_y, to_x + timeout_bar_width, timeout_y + timeout_bar_height], 
                             fill=color, outline=(0, 0, 0))
            
            # Home timeouts (bottom right)
            home_timeouts = game.get('home_timeouts', 0)
            for i in range(3):
                to_x = matrix_width - 2 - (3 - i) * (timeout_bar_width + timeout_spacing)
                color = (255, 255, 255) if i < home_timeouts else (80, 80, 80)
                draw.rectangle([to_x, timeout_y, to_x + timeout_bar_width, timeout_y + timeout_bar_height], 
                             fill=color, outline=(0, 0, 0))
        except Exception as e:
            self.logger.error(f"Error drawing timeouts: {e}")

    def _display_no_games(self, mode: str):
        """Display message when no games are available."""
        img = Image.new('RGB', (self.display_manager.matrix.width,
                               self.display_manager.matrix.height),
                       (0, 0, 0))
        draw = ImageDraw.Draw(img)

        message = {
            'football_live': "No Live Games",
            'football_recent': "No Recent Games",
            'football_upcoming': "No Upcoming Games"
        }.get(mode, "No Games")

        draw.text((5, 12), message, fill=(150, 150, 150))

        self.display_manager.image = img.copy()
        self.display_manager.update_display()

    def _display_error(self, message: str):
        """Display error message."""
        img = Image.new('RGB', (self.display_manager.matrix.width,
                               self.display_manager.matrix.height),
                       (0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.text((5, 12), message, fill=(255, 0, 0))

        self.display_manager.image = img.copy()
        self.display_manager.update_display()

    def get_display_duration(self) -> float:
        """Get display duration from config."""
        return self.display_duration

    def get_info(self) -> Dict[str, Any]:
        """Return plugin info for web UI."""
        if BasePlugin:
            info = super().get_info()
        else:
            # Fallback info structure
            info = {
                'plugin_id': self.plugin_id,
                'enabled': self.enabled,
                'version': '1.0.1'
            }

        # Get league-specific configurations
        leagues_config = {}
        for league_key, league_config in self.leagues.items():
            leagues_config[league_key] = {
                'enabled': league_config.get('enabled', False),
                'favorite_teams': league_config.get('favorite_teams', []),
                'display_modes': league_config.get('display_modes', {}),
                'recent_games_to_show': league_config.get('recent_games_to_show', 5),
                'upcoming_games_to_show': league_config.get('upcoming_games_to_show', 10),
                'update_interval_seconds': league_config.get('update_interval_seconds', 60)
            }

        info.update({
            'total_games': len(self.current_games),
            'enabled_leagues': [k for k, v in self.leagues.items() if v.get('enabled', False)],
            'current_mode': self.current_display_mode,
            'last_update': self.last_update,
            'display_duration': self.display_duration,
            'show_records': self.show_records,
            'show_ranking': self.show_ranking,
            'live_games': len([g for g in self.current_games if g.get('status', {}).get('state') == 'in']),
            'recent_games': len([g for g in self.current_games if g.get('status', {}).get('state') == 'post']),
            'upcoming_games': len([g for g in self.current_games if g.get('status', {}).get('state') == 'pre']),
            'leagues_config': leagues_config,
            'global_config': self.global_config
        })
        return info

    def cleanup(self) -> None:
        """Cleanup resources."""
        self.current_games = []
        self.logger.info("Football scoreboard plugin cleaned up")
