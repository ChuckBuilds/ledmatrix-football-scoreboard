import logging
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw
from pathlib import Path


class ScoreboardRenderer:
    def __init__(self, display_manager: Any, fonts: Dict, display_width: int, display_height: int, logger: logging.Logger):
        self.display_manager = display_manager
        self.fonts = fonts
        self.display_width = display_width
        self.display_height = display_height
        self.logger = logger
        
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

            # Load logos from the correct directory based on league
            league = game.get("league", "nfl")
            if league == "nfl":
                logo_dir = "/home/chuck/Github/LEDMatrix/assets/sports/nfl_logos"
            else:  # ncaa_fb
                logo_dir = "/home/chuck/Github/LEDMatrix/assets/sports/ncaa_logos"
            
            home_logo = self._load_team_logo(game.get("home_abbr", ""), logo_dir)
            away_logo = self._load_team_logo(game.get("away_abbr", ""), logo_dir)

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

            # Draw logos
            home_x = self.display_width - home_logo.width + 10
            home_y = center_y - (home_logo.height // 2)
            main_img.paste(home_logo, (home_x, home_y), home_logo)
            
            away_x = -10
            away_y = center_y - (away_logo.height // 2)
            main_img.paste(away_logo, (away_x, away_y), away_logo)
            
            # Scores (centered, slightly above bottom)
            if game.get("is_live"):
                # Show scores for live games
                home_score = str(game.get("home_score", "0"))
                away_score = str(game.get("away_score", "0"))
                score_text = f"{away_score}-{home_score}"
                score_width = draw_overlay.textlength(
                    score_text, font=self.fonts["score"]
                )
                score_x = (self.display_width - score_width) // 2
                score_y = (self.display_height // 2) - 3
                self._draw_text_with_outline(
                    draw_overlay, score_text, (score_x, score_y), self.fonts["score"]
                )
            elif game.get("is_final"):
                # Show scores for completed games (without FINAL since it's shown in period area)
                home_score = str(game.get("home_score", "0"))
                away_score = str(game.get("away_score", "0"))
                score_text = f"{away_score}-{home_score}"
                score_width = draw_overlay.textlength(
                    score_text, font=self.fonts["score"]
                )
                score_x = (self.display_width - score_width) // 2
                score_y = (self.display_height // 2) - 3
                self._draw_text_with_outline(
                    draw_overlay, score_text, (score_x, score_y), self.fonts["score"]
                )

            # Period/Quarter and Clock (Top center) - Only show clock for live games
            if game.get("is_live"):
                period_clock_text = (
                    f"{game.get('period_text', '')} {game.get('clock', '')}".strip()
                )
                if game.get("is_halftime"):
                    period_clock_text = "Halftime"
                elif game.get("is_period_break"):
                    period_clock_text = game.get("status_text", "Period Break")

                status_width = draw_overlay.textlength(
                    period_clock_text, font=self.fonts["time"]
                )
                status_x = (self.display_width - status_width) // 2
                status_y = 1
                self._draw_text_with_outline(
                    draw_overlay,
                    period_clock_text,
                    (status_x, status_y),
                    self.fonts["time"],
                )

            elif game.get("is_upcoming"):
                # Format upcoming games like the original football.py
                game_date = game.get("game_date", "")
                game_time = game.get("game_time", "")

                # "Next Game" at the top (use smaller status font for smaller displays)
                status_font = self.fonts["status"]
                if self.display_width > 128:
                    status_font = self.fonts["time"]
                status_text = "Next Game"
                status_width = draw_overlay.textlength(status_text, font=status_font)
                status_x = (self.display_width - status_width) // 2
                status_y = 1
                self._draw_text_with_outline(
                    draw_overlay, status_text, (status_x, status_y), status_font
                )
                
                # Date text (centered, below "Next Game")
                date_width = draw_overlay.textlength(game_date, font=self.fonts["time"])
                date_x = (self.display_width - date_width) // 2
                date_y = center_y - 7  # Position above vertical center
                self._draw_text_with_outline(
                    draw_overlay, game_date, (date_x, date_y), self.fonts["time"]
                )
                
                # Time text (centered, below Date)
                time_width = draw_overlay.textlength(game_time, font=self.fonts["time"])
                time_x = (self.display_width - time_width) // 2
                time_y = date_y + 9  # Position below date
                self._draw_text_with_outline(
                    draw_overlay, game_time, (time_x, time_y), self.fonts["time"]
                )

            else:
                # For final games, show "Final" status
                period_clock_text = game.get("period_text", "Final")
                status_width = draw_overlay.textlength(
                    period_clock_text, font=self.fonts["time"]
                )
                status_x = (self.display_width - status_width) // 2
                status_y = 1
                self._draw_text_with_outline(
                    draw_overlay,
                    period_clock_text,
                    (status_x, status_y),
                    self.fonts["time"],
                )

            # Down & Distance or Scoring Event (Below Period/Clock)
            scoring_event = game.get("scoring_event", "")
            down_distance = game.get("down_distance_text", "")
            if self.display_width > 128:
                down_distance = game.get("down_distance_text_long", "")

            # Show scoring event if detected, otherwise show down & distance
            if scoring_event and game.get("is_live"):
                # Display scoring event with special formatting
                event_width = draw_overlay.textlength(
                    scoring_event, font=self.fonts["detail"]
                )
                event_x = (self.display_width - event_width) // 2
                event_y = (self.display_height) - 7

                # Color coding for different scoring events
                if scoring_event == "TOUCHDOWN":
                    event_color = (255, 215, 0)  # Gold
                elif scoring_event == "FIELD GOAL":
                    event_color = (0, 255, 0)  # Green
                elif scoring_event == "PAT":
                    event_color = (255, 165, 0)  # Orange
                else:
                    event_color = (255, 255, 255)  # White

                self._draw_text_with_outline(
                    draw_overlay,
                    scoring_event,
                    (event_x, event_y),
                    self.fonts["detail"],
                    fill=event_color,
                )
            elif down_distance and game.get("is_live"):
                dd_width = draw_overlay.textlength(
                    down_distance, font=self.fonts["detail"]
                )
                dd_x = (self.display_width - dd_width) // 2
                dd_y = (self.display_height) - 7
                down_color = (
                    (200, 200, 0) if not game.get("is_redzone", False) else (255, 0, 0)
                )
                self._draw_text_with_outline(
                    draw_overlay,
                    down_distance,
                    (dd_x, dd_y),
                    self.fonts["detail"],
                    fill=down_color,
                )

                # Possession Indicator (small football icon)
                possession = game.get("possession_indicator")
                if possession:
                    ball_radius_x = 3
                    ball_radius_y = 2
                    ball_color = (139, 69, 19)
                    lace_color = (255, 255, 255)
            
                    detail_font_height_approx = 6
                    ball_y_center = dd_y + (detail_font_height_approx // 2)

                    possession_ball_padding = 3
            
                    if possession == "away":
                        ball_x_center = dd_x - possession_ball_padding - ball_radius_x
                    elif possession == "home":
                        ball_x_center = (
                            dd_x + dd_width + possession_ball_padding + ball_radius_x
                        )
                    else:
                        ball_x_center = 0
                    
                    if ball_x_center > 0:
                        # Draw the football shape (ellipse)
                        draw_overlay.ellipse(
                            (
                                ball_x_center - ball_radius_x,
                                ball_y_center - ball_radius_y,
                                ball_x_center + ball_radius_x,
                                ball_y_center + ball_radius_y,
                            ),
                            fill=ball_color,
                            outline=(0, 0, 0),
                        )
                        # Draw a simple horizontal lace
                        draw_overlay.line(
                            (
                                ball_x_center - 1,
                                ball_y_center,
                                ball_x_center + 1,
                                ball_y_center,
                            ),
                            fill=lace_color,
                            width=1,
                        )

            # Timeouts (Bottom corners) - Only show for live games
            if game.get("is_live"):
                timeout_bar_width = 4
                timeout_bar_height = 2
                timeout_spacing = 1
                timeout_y = self.display_height - timeout_bar_height - 1
            
                # Away Timeouts (Bottom Left)
                away_timeouts_remaining = game.get("away_timeouts", 0)
                for i in range(3):
                    to_x = 2 + i * (timeout_bar_width + timeout_spacing)
                    color = (
                        (255, 255, 255) if i < away_timeouts_remaining else (80, 80, 80)
                    )
                    draw_overlay.rectangle(
                        [
                            to_x,
                            timeout_y,
                            to_x + timeout_bar_width,
                            timeout_y + timeout_bar_height,
                        ],
                        fill=color,
                        outline=(0, 0, 0),
                    )

                # Home Timeouts (Bottom Right)
                home_timeouts_remaining = game.get("home_timeouts", 0)
                for i in range(3):
                    to_x = (
                        self.display_width
                        - 2
                        - timeout_bar_width
                        - (2 - i) * (timeout_bar_width + timeout_spacing)
                    )
                    color = (
                        (255, 255, 255) if i < home_timeouts_remaining else (80, 80, 80)
                    )
                    draw_overlay.rectangle(
                        [
                            to_x,
                            timeout_y,
                            to_x + timeout_bar_width,
                            timeout_y + timeout_bar_height,
                        ],
                        fill=color,
                        outline=(0, 0, 0),
                    )

            # Composite the text overlay onto the main image
            main_img = Image.alpha_composite(main_img, overlay)
            main_img = main_img.convert("RGB")

            # Display the final image
            self.display_manager.image.paste(main_img, (0, 0))
            self.display_manager.update_display()

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
        try:
            logo_path = Path(logo_dir) / f"{team_abbr}.png"
            if logo_path.exists():
                logo = Image.open(logo_path)
                if logo.mode != 'RGBA':
                    logo = logo.convert('RGBA')
                
                # Resize logo as percentage of display size like original football.py
                max_width = int(self.display_width * 1.5)
                max_height = int(self.display_height * 1.5)
                logo.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                return logo
            else:
                self.logger.warning(f"Logo not found for team: {team_abbr} at {logo_path}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error loading logo for {team_abbr}: {e}")
            return None