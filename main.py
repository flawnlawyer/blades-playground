#!/usr/bin/env python3
"""
The Blade's Playground
───────────────────────────────────────────────────────────────────────────────
A dark, glitchy roguelike where you navigate corrupted space, hack broken
objects, absorb poetic fragments, and survive long enough to unleash chaos.

Run:
    python main.py

Options:
    --stress N          Keep ~N enemies alive (engine stress test, F3 = debug overlay)
    --gpu               Experimental: SDL2 GPU scaling/presentation (falls back if unsupported)

Controls:
    WASD / Arrow keys   Move
    SHIFT               Dash
    SPACE               Hack nearby objects / stun enemies
    1-5                 Select weapon
    LMB                 Fire
    M                   Toggle mute
    ESC                 Pause / Back
    F11                 Toggle fullscreen
    F3                  Toggle debug overlay
"""

import sys
from pathlib import Path
import pygame

from game.constants import LOGICAL_W, LOGICAL_H
from game.state_manager import StateManager
from game.states.loading_state import LoadingState


def _arg_int(flag: str, default: int = 0) -> int:
    """Tiny CLI helper:  --flag 500"""
    if flag in sys.argv:
        try:
            return int(sys.argv[sys.argv.index(flag) + 1])
        except (IndexError, ValueError):
            print(f"{flag} needs an integer, e.g. {flag} 500")
    return default


def main() -> None:
    pygame.init()

    presenter = None
    if "--gpu" in sys.argv:                       # experimental: GPU scaling/present
        try:
            from utils.gpu import GpuPresenter
            presenter = GpuPresenter("The Blade's Playground",
                                     (LOGICAL_W, LOGICAL_H), (LOGICAL_W, LOGICAL_H))
            print("[gpu] SDL2 accelerated renderer active")
        except Exception as exc:
            print(f"[gpu] unavailable ({exc}); using the normal display")
    if presenter is None:
        # Start windowed at the logical resolution, resizable
        screen = pygame.display.set_mode(
            (LOGICAL_W, LOGICAL_H), pygame.RESIZABLE)
        pygame.display.set_caption("The Blade's Playground")
    else:
        screen = None

    # Window icon
    logo_surface = None
    logo_path = Path(__file__).parent / "assets" / "logo.png"
    if logo_path.exists():
        try:
            logo_surface = pygame.image.load(str(logo_path))
            if pygame.display.get_surface() is not None:
                logo_surface = logo_surface.convert_alpha()
            # Use a small version as window icon
            icon = pygame.transform.smoothscale(logo_surface, (64, 64))
            if presenter is not None:
                presenter.set_icon(icon)
            else:
                pygame.display.set_icon(icon)
        except Exception:
            pass

    # Create the state manager
    manager = StateManager(screen, presenter)
    manager.logo = logo_surface
    setattr(manager, "stress", _arg_int("--stress", 0))

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
