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
    SPACE               Hack nearby objects / stun enemies
    M                   Toggle mute
    R                   Reboot (after game over)
    ESC                 Quit
"""

import sys
import pygame

from game.constants import W, H
from game.game      import Game


def main() -> None:
    pygame.init()
    pygame.display.set_mode((W, H))
    pygame.display.set_caption("The Blade's Playground")

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
