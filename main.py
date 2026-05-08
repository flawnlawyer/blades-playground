#!/usr/bin/env python3
"""
The Blade's Playground
───────────────────────────────────────────────────────────────────────────────
A dark, glitchy roguelike where you navigate corrupted space, hack broken
objects, absorb poetic fragments, and survive long enough to unleash chaos.

Run:
    python main.py

Controls:
    WASD / Arrow keys   Move
    SHIFT               Dash
    SPACE               Hack nearby objects / stun enemies
    1-5                 Select weapon
    LMB                 Fire
    M                   Toggle mute
    R                   Reboot (after game over)
    ESC                 Quit
"""

import sys
from pathlib import Path
import pygame

from game.constants import W, H
from game.game      import Game


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("The Blade's Playground")

    # Window icon
    logo_path = Path(__file__).parent / "assets" / "logo.png"
    if logo_path.exists():
        try:
            icon = pygame.image.load(str(logo_path))
            pygame.display.set_icon(icon)
        except Exception:
            pass

    try:
        game = Game()
        game.run()
    except KeyboardInterrupt:
        pass
    finally:
        pygame.quit()
        sys.exit(0)


if __name__ == "__main__":
    main()
