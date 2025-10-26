import logging
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path


class ScoreboardRenderer:
    def __init__(self, display_manager: Any, fonts: Dict, display_width: int, display_height: int, logger: logging.Logger):
        self.display_manager = display_manager
        self.fonts = fonts
        self.display_width = display_width
        self.display_height = display_height
        self.logger = logger
        
        # Initialize attributes that will be set by the manager
        self.show_records = False
        self.show_ranking = False
        self._team_rankings_cache = {}
        
        # Logo cache for performance (matches old managers)
        self._logo_cache = {}
        
        self.colors = {
            'white': (255, 255, 255),
            'red': (255, 0, 0),
            'green': (0, 255, 0),
            'blue': (0, 0, 255),
            'yellow': (255, 255, 0),
            'gold': (255, 215, 0),
            'orange': (255, 165, 0),
            'gray': (128, 128, 128),
            'black': (0, 0, 0)
        }
    
    def render_game(self, game: Dict, force_clear: bool = False) -> bool:
        """
        Render a single game to the display using the original football.py layout.
        
        Args:
            game: Game dictionary with all game information
            force_clear: Whether to force clear the display
            
        Returns:
            True if rendering was successful, False otherwise
        """
        try:
            if force_clear:
                self.display_manager.clear()
            
            # Use the exact same layout as the original football.py
            self._draw_scorebug_layout(game, force_clear)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error rendering game: {e}")
            return False
    
    def _draw_scorebug_layout(self, game: Dict, force_clear: bool = False) -> None:  # noqa: ARG002
        """Draw the detailed scorebug layout following football.py structure exactly."""
        try:
            main_img = Image.new(
                "RGBA", (self.display_width, self.display_height), (0, 0, 0, 255)
            )
            overlay = Image.new(
                "RGBA", (self.display_width, self.display_height), (0, 0, 0, 0)
            )
            draw_overlay = ImageDraw.Draw(overlay)

            # Load logos using paths from game data (matches old managers)
            home_logo_path = game.get("home_logo_path")
            away_logo_path = game.get("away_logo_path")
            
            # Fallback to team abbreviation lookup if paths not in game data
            if not home_logo_path or not away_logo_path:
                league = game.get("league", "nfl")
                if league == "nfl":
                    logo_dir = "assets/sports/nfl_logos"
                else:  # ncaa_fb
                    logo_dir = "assets/sports/ncaa_logos"
                
                home_logo = self._load_team_logo(game.get("home_abbr", ""), logo_dir)
                away_logo = self._load_team_logo(game.get("away_abbr", ""), logo_dir)
            else:
                # Use paths from game data
                home_logo = self._load_logo_from_path(home_logo_path, game.get("home_abbr", ""))
                away_logo = self._load_logo_from_path(away_logo_path, game.get("away_abbr", ""))

            if not home_logo or not away_logo:
                self.logger.error(f"Failed to load logos for game: {game.get('id')}")
                # Draw placeholder text if logos fail
                draw_final = ImageDraw.Draw(main_img.convert("RGB"))
                self._draw_text_with_outline(
                    draw_final, "Logo Error", (5, 5), self.fonts["status"]
                )
                self.display_manager.image.paste(main_img.convert("RGB"), (0, 0))
                self.display_manager.update_display()
                return

            center_y = self.display_height // 2

            # Draw logos (shifted slightly more inward than NHL perhaps)
            home_x = self.display_width - home_logo.width + 10  # adjusted from 18
            home_y = center_y - (home_logo.height // 2)
            main_img.paste(home_logo, (home_x, home_y), home_logo)
            
            away_x = -10  # adjusted from 18
            away_y = center_y - (away_logo.height // 2)
            main_img.paste(away_logo, (away_x, away_y), away_logo)
            
            # --- Draw Text Elements on Overlay ---
            # Note: Rankings are now handled in the records/rankings section below

            # Scores (centered, slightly above bottom)
            home_score = str(game.get("home_score", "0"))
            away_score = str(game.get("away_score", "0"))
            score_text = f"{away_score}-{home_score}"
            score_width = draw_overlay.textlength(score_text, font=self.fonts["score"])
            score_x = (self.display_width - score_width) // 2
            score_y = (self.display_height // 2) - 3  # centered from 14
            self._draw_text_with_outline(draw_overlay, score_text, (score_x, score_y), self.fonts["score"])

            # Period/Quarter and Clock (Top center) - Use status_text directly
            if game.get("is_halftime"):
                period_clock_text = "Halftime"  # Override for halftime
            elif game.get("is_period_break"):
                period_clock_text = game.get("status_text", "Period Break")
            else:
                # Use status_text which already has the correct format (mirrors old managers)
                period_clock_text = game.get("status_text", "")

            status_width = draw_overlay.textlength(period_clock_text, font=self.fonts["time"])
            status_x = (self.display_width - status_width) // 2
            status_y = 1  # Position at top
            self._draw_text_with_outline(draw_overlay, period_clock_text, (status_x, status_y), self.fonts["time"])

            # Down & Distance or Scoring Event (Below Period/Clock)
            scoring_event = game.get("scoring_event", "")
            down_distance = game.get("down_distance_text", "")
            if self.display_width > 128:
                down_distance = game.get("down_distance_text_long", "")
            
            # Show scoring event if detected, otherwise show down & distance
            if scoring_event and game.get("is_live"):
                # Display scoring event with special formatting
                event_width = draw_overlay.textlength(scoring_event, font=self.fonts["detail"])
                event_x = (self.display_width - event_width) // 2
                event_y = (self.display_height) - 7
                
                # Color coding for different scoring events
                if scoring_event == "TOUCHDOWN":
                    event_color = (255, 215, 0)  # Gold
                elif scoring_event == "FIELD GOAL":
                    event_color = (0, 255, 0)    # Green
                elif scoring_event == "PAT":
                    event_color = (255, 165, 0)  # Orange
                else:
                    event_color = (255, 255, 255)  # White
                
                self._draw_text_with_outline(draw_overlay, scoring_event, (event_x, event_y), self.fonts["detail"], fill=event_color)
            elif down_distance and game.get("is_live"):  # Only show if live and available
                dd_width = draw_overlay.textlength(down_distance, font=self.fonts["detail"])
                dd_x = (self.display_width - dd_width) // 2
                dd_y = (self.display_height) - 7  # Top of D&D text
                down_color = (200, 200, 0) if not game.get("is_redzone", False) else (255, 0, 0)  # Yellowish text
                self._draw_text_with_outline(draw_overlay, down_distance, (dd_x, dd_y), self.fonts["detail"], fill=down_color)

                # Possession Indicator (small football icon)
                possession = game.get("possession_indicator")
                if possession:  # Only draw if possession is known
                    ball_radius_x = 3  # Wider for football shape
                    ball_radius_y = 2  # Shorter for football shape
                    ball_color = (139, 69, 19)  # Brown color for the football
                    lace_color = (255, 255, 255)  # White for laces

                    # Approximate height of the detail font (4x6 font at size 6 is roughly 6px tall)
                    detail_font_height_approx = 6
                    ball_y_center = dd_y + (detail_font_height_approx // 2)  # Center ball vertically with D&D text

                    possession_ball_padding = 3  # Pixels between D&D text and ball

                    if possession == "away":
                        # Position ball to the left of D&D text
                        ball_x_center = dd_x - possession_ball_padding - ball_radius_x
                    elif possession == "home":
                        # Position ball to the right of D&D text
                        ball_x_center = dd_x + dd_width + possession_ball_padding + ball_radius_x
                    else:
                        ball_x_center = 0  # Should not happen / no indicator

                    if ball_x_center > 0:  # Draw if position is valid
                        # Draw the football shape (ellipse)
                        draw_overlay.ellipse(
                            (ball_x_center - ball_radius_x, ball_y_center - ball_radius_y,  # x0, y0
                             ball_x_center + ball_radius_x, ball_y_center + ball_radius_y),  # x1, y1
                            fill=ball_color, outline=(0, 0, 0)
                        )
                        # Draw a simple horizontal lace
                        draw_overlay.line(
                            (ball_x_center - 1, ball_y_center, ball_x_center + 1, ball_y_center),
                            fill=lace_color, width=1
                        )

            # Timeouts (Bottom corners) - 3 small bars per team
            timeout_bar_width = 4
            timeout_bar_height = 2
            timeout_spacing = 1
            timeout_y = self.display_height - timeout_bar_height - 1  # Bottom edge

            # Away Timeouts (Bottom Left)
            away_timeouts_remaining = game.get("away_timeouts", 0)
            for i in range(3):
                to_x = 2 + i * (timeout_bar_width + timeout_spacing)
                color = (255, 255, 255) if i < away_timeouts_remaining else (80, 80, 80)  # White if available, gray if used
                draw_overlay.rectangle([to_x, timeout_y, to_x + timeout_bar_width, timeout_y + timeout_bar_height], fill=color, outline=(0, 0, 0))

            # Home Timeouts (Bottom Right)
            home_timeouts_remaining = game.get("home_timeouts", 0)
            for i in range(3):
                to_x = self.display_width - 2 - timeout_bar_width - (2 - i) * (timeout_bar_width + timeout_spacing)
                color = (255, 255, 255) if i < home_timeouts_remaining else (80, 80, 80)  # White if available, gray if used
                draw_overlay.rectangle([to_x, timeout_y, to_x + timeout_bar_width, timeout_y + timeout_bar_height], fill=color, outline=(0, 0, 0))

            # Draw odds if available (matches old managers)
            if 'odds' in game and game['odds']:
                self._draw_dynamic_odds(draw_overlay, game['odds'], self.display_width, self.display_height)

            # Draw records or rankings if enabled (mirrors old football.py exactly)
            if hasattr(self, 'show_records') and (self.show_records or hasattr(self, 'show_ranking') and self.show_ranking):
                try:
                    record_font = ImageFont.truetype("assets/fonts/4x6-font.ttf", 6)  # Exact same font as old football.py
                    self.logger.debug("Loaded 6px record font successfully")
                except IOError:
                    record_font = ImageFont.load_default()
                    self.logger.warning(f"Failed to load 6px font, using default font (size: {record_font.size})")
                
                # Get team abbreviations
                away_abbr = game.get('away_abbr', '')
                home_abbr = game.get('home_abbr', '')
                
                record_bbox = draw_overlay.textbbox((0, 0), "0-0", font=record_font)
                record_height = record_bbox[3] - record_bbox[1]
                # Position records/rankings exactly like old football.py
                record_y = self.display_height - record_height - 4  # Exact same positioning as old football.py
                self.logger.debug(f"Record positioning: height={record_height}, record_y={record_y}, display_height={self.display_height}")

                # Display away team info
                if away_abbr:
                    if hasattr(self, 'show_ranking') and self.show_ranking and hasattr(self, 'show_records') and self.show_records:
                        # When both rankings and records are enabled, rankings replace records completely
                        away_rank = getattr(self, '_team_rankings_cache', {}).get(away_abbr, 0)
                        if away_rank > 0:
                            away_text = f"#{away_rank}"
                        else:
                            # Show nothing for unranked teams when rankings are prioritized
                            away_text = ''
                    elif hasattr(self, 'show_ranking') and self.show_ranking:
                        # Show ranking only if available
                        away_rank = getattr(self, '_team_rankings_cache', {}).get(away_abbr, 0)
                        if away_rank > 0:
                            away_text = f"#{away_rank}"
                        else:
                            away_text = ''
                    elif hasattr(self, 'show_records') and self.show_records:
                        # Show record only when rankings are disabled
                        away_text = game.get('away_record', '')
                    else:
                        away_text = ''
                    
                    if away_text:
                        away_record_x = 3
                        self.logger.debug(f"Drawing away ranking '{away_text}' at ({away_record_x}, {record_y})")
                        self._draw_text_with_outline(draw_overlay, away_text, (away_record_x, record_y), record_font)

                # Display home team info
                if home_abbr:
                    if hasattr(self, 'show_ranking') and self.show_ranking and hasattr(self, 'show_records') and self.show_records:
                        # When both rankings and records are enabled, rankings replace records completely
                        home_rank = getattr(self, '_team_rankings_cache', {}).get(home_abbr, 0)
                        if home_rank > 0:
                            home_text = f"#{home_rank}"
                        else:
                            # Show nothing for unranked teams when rankings are prioritized
                            home_text = ''
                    elif hasattr(self, 'show_ranking') and self.show_ranking:
                        # Show ranking only if available
                        home_rank = getattr(self, '_team_rankings_cache', {}).get(home_abbr, 0)
                        if home_rank > 0:
                            home_text = f"#{home_rank}"
                        else:
                            home_text = ''
                    elif hasattr(self, 'show_records') and self.show_records:
                        # Show record only when rankings are disabled
                        home_text = game.get('home_record', '')
                    else:
                        home_text = ''
                    
                    if home_text:
                        home_record_bbox = draw_overlay.textbbox((0, 0), home_text, font=record_font)
                        home_record_width = home_record_bbox[2] - home_record_bbox[0]
                        home_record_x = self.display_width - home_record_width - 3
                        self.logger.debug(f"Drawing home ranking '{home_text}' at ({home_record_x}, {record_y})")
                        self._draw_text_with_outline(draw_overlay, home_text, (home_record_x, record_y), record_font)

            # Composite the text overlay onto the main image
            main_img = Image.alpha_composite(main_img, overlay)
            main_img = main_img.convert("RGB")  # Convert for display

            # Display the final image
            self.display_manager.image.paste(main_img, (0, 0))
            self.display_manager.update_display()  # Update display here for live

        except Exception as e:
            self.logger.error(f"Error displaying Football game: {e}", exc_info=True)

    def _draw_text_with_outline(
        self,
        draw: ImageDraw.Draw,
        text: str,
        position: tuple,
        font,
        fill=(255, 255, 255),
        outline_color=(0, 0, 0),
    ):
        """Draw text with outline - following football.py structure."""
        try:
            x, y = position
            # Draw outline
            for dx, dy in [
                (-1, -1),
                (-1, 0),
                (-1, 1),
                (0, -1),
                (0, 1),
                (1, -1),
                (1, 0),
                (1, 1),
            ]:
                draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
            # Draw main text
            draw.text((x, y), text, font=font, fill=fill)
        except Exception as e:
            self.logger.error(f"Error drawing text with outline: {e}")

    def _load_team_logo(self, team_abbr: str, logo_dir: str) -> Optional[Image.Image]:
        """Load team logo image with proper sizing - percentage of display size like original."""
        # Check cache first (matches old managers)
        if team_abbr in self._logo_cache:
            self.logger.debug(f"Using cached logo for {team_abbr}")
            return self._logo_cache[team_abbr]
        
        try:
            # Import LogoDownloader for filename variations
            try:
                from src.logo_downloader import LogoDownloader
            except ImportError:
                # Fallback if LogoDownloader not available
                LogoDownloader = None
            
            # Try filename variations first (for cases like TA&M vs TAANDM)
            logo_path = Path(logo_dir) / f"{team_abbr}.png"
            actual_logo_path = None
            
            if LogoDownloader:
                filename_variations = LogoDownloader.get_logo_filename_variations(team_abbr)
                for filename in filename_variations:
                    test_path = Path(logo_dir) / filename
                    if test_path.exists():
                        actual_logo_path = test_path
                        self.logger.debug(f"Found logo at alternative path: {actual_logo_path}")
                        break
            
            # If no variation found, use original path
            if not actual_logo_path:
                actual_logo_path = logo_path
            
            # Load the logo
            if actual_logo_path.exists():
                logo = Image.open(actual_logo_path)
                if logo.mode != 'RGBA':
                    logo = logo.convert('RGBA')
                
                # Resize logo as percentage of display size like original football.py
                max_width = int(self.display_width * 1.5)
                max_height = int(self.display_height * 1.5)
                logo.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                
                # Cache the logo
                self._logo_cache[team_abbr] = logo
                return logo
            else:
                self.logger.warning(f"Logo not found for team: {team_abbr} at {actual_logo_path}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error loading logo for {team_abbr}: {e}")
            return None
    
    def _load_logo_from_path(self, logo_path: Path, team_abbr: str) -> Optional[Image.Image]:
        """Load logo from a specific path with caching (matches old managers)."""
        # Check cache first
        if team_abbr in self._logo_cache:
            self.logger.debug(f"Using cached logo for {team_abbr}")
            return self._logo_cache[team_abbr]
        
        try:
            # Import LogoDownloader for filename variations
            try:
                from src.logo_downloader import LogoDownloader
            except ImportError:
                LogoDownloader = None
            
            # Try filename variations first
            actual_logo_path = None
            if LogoDownloader:
                filename_variations = LogoDownloader.get_logo_filename_variations(team_abbr)
                for filename in filename_variations:
                    test_path = logo_path.parent / filename
                    if test_path.exists():
                        actual_logo_path = test_path
                        self.logger.debug(f"Found logo at alternative path: {actual_logo_path}")
                        break
            
            # If no variation found, use original path
            if not actual_logo_path:
                actual_logo_path = logo_path
            
            # Load the logo
            if actual_logo_path.exists():
                logo = Image.open(actual_logo_path)
                if logo.mode != 'RGBA':
                    logo = logo.convert('RGBA')
                
                # Resize logo as percentage of display size
                max_width = int(self.display_width * 1.5)
                max_height = int(self.display_height * 1.5)
                logo.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                
                # Cache the logo
                self._logo_cache[team_abbr] = logo
                return logo
            else:
                self.logger.warning(f"Logo not found at path: {actual_logo_path}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error loading logo from path {logo_path}: {e}")
            return None
    
    def _draw_dynamic_odds(self, draw: ImageDraw.Draw, odds: Dict[str, Any], width: int, height: int) -> None:
        """Draw odds with dynamic positioning - only show negative spread and position O/U based on favored team (matches old managers)."""
        try:
            home_team_odds = odds.get('home_team_odds', {})
            away_team_odds = odds.get('away_team_odds', {})
            home_spread = home_team_odds.get('spread_odds')
            away_spread = away_team_odds.get('spread_odds')

            # Get top-level spread as fallback
            top_level_spread = odds.get('spread')
            
            # If we have a top-level spread and the individual spreads are None or 0, use the top-level
            if top_level_spread is not None:
                if home_spread is None or home_spread == 0.0:
                    home_spread = top_level_spread
                if away_spread is None:
                    away_spread = -top_level_spread

            # Determine which team is favored (has negative spread)
            home_favored = home_spread is not None and home_spread < 0
            away_favored = away_spread is not None and away_spread < 0
            
            # Only show the negative spread (favored team)
            favored_spread = None
            favored_side = None
            
            if home_favored:
                favored_spread = home_spread
                favored_side = 'home'
            elif away_favored:
                favored_spread = away_spread
                favored_side = 'away'
            
            # Show the negative spread on the appropriate side
            if favored_spread is not None:
                spread_text = str(favored_spread)
                font = self.fonts['detail']  # Use detail font for odds
                
                if favored_side == 'home':
                    # Home team is favored, show spread on right side
                    spread_width = draw.textlength(spread_text, font=font)
                    spread_x = width - spread_width  # Top right
                    spread_y = 0
                    self._draw_text_with_outline(draw, spread_text, (spread_x, spread_y), font, fill=(0, 255, 0))
                else:
                    # Away team is favored, show spread on left side
                    spread_x = 0  # Top left
                    spread_y = 0
                    self._draw_text_with_outline(draw, spread_text, (spread_x, spread_y), font, fill=(0, 255, 0))
            
            # Show over/under on the opposite side of the favored team
            over_under = odds.get('over_under')
            if over_under is not None:
                ou_text = f"O/U: {over_under}"
                font = self.fonts['detail']  # Use detail font for odds
                ou_width = draw.textlength(ou_text, font=font)
                
                if favored_side == 'home':
                    # Home team is favored, show O/U on left side (opposite of spread)
                    ou_x = 0  # Top left
                    ou_y = 0
                elif favored_side == 'away':
                    # Away team is favored, show O/U on right side (opposite of spread)
                    ou_x = width - ou_width  # Top right
                    ou_y = 0
                else:
                    # No clear favorite, show O/U in center
                    ou_x = (width - ou_width) // 2
                    ou_y = 0
                
                self._draw_text_with_outline(draw, ou_text, (ou_x, ou_y), font, fill=(0, 255, 0))
                
        except Exception as e:
            self.logger.error(f"Error drawing odds: {e}")