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
    ESC                 Pause / Back
    F11                 Toggle fullscreen
"""

import sys
from pathlib import Path
import pygame

from game.constants import LOGICAL_W, LOGICAL_H
from game.state_manager import StateManager
from game.states.loading_state import LoadingState


def main() -> None:
    pygame.init()

    # Start windowed at the logical resolution, resizable
    screen = pygame.display.set_mode(
        (LOGICAL_W, LOGICAL_H), pygame.RESIZABLE)
    pygame.display.set_caption("The Blade's Playground")

    # Window icon
    logo_surface = None
    logo_path = Path(__file__).parent / "assets" / "logo.png"
    if logo_path.exists():
        try:
            logo_surface = pygame.image.load(str(logo_path)).convert_alpha()
            # Use a small version as window icon
            icon = pygame.transform.smoothscale(logo_surface, (64, 64))
            pygame.display.set_icon(icon)
        except Exception:
            pass

    # Create the state manager
    manager = StateManager(screen)
    manager.logo = logo_surface

    # Push the loading state to begin
    manager.push(LoadingState(manager))

    try:
        manager.run()
    except KeyboardInterrupt:
        pass
    finally:
        pygame.quit()
        sys.exit(0)


if __name__ == "__main__":
    main()
