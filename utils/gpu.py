"""
gpu.py — Optional GPU presentation via SDL2's accelerated Renderer.

Normal mode composes the 1280x720 logical surface on the CPU and, for any window
size other than 1:1, runs `smoothscale` on it every frame (≈4 ms at 1600x900,
more at 1080p/4K).  With --gpu the finished frame is uploaded once as a texture
and the GPU does the scaling, letterboxing and presentation (with vsync).

Honest scope: only the *final present/scale* moves to the GPU — the game world
itself is still composed by pygame's CPU blitter.  Uses pygame's `_sdl2.video`
API (underscore-prefixed = experimental), so it is strictly opt-in and main.py
falls back to the normal display if anything here fails.
"""
from __future__ import annotations
import os
import pygame


class GpuPresenter:
    def __init__(self, title: str, size: tuple, logical_size: tuple,
                 vsync: bool = True) -> None:
        # Bilinear filtering for the upscale (must be set before the texture exists)
        os.environ.setdefault("SDL_RENDER_SCALE_QUALITY", "1")
        from pygame._sdl2 import video                     # raises ImportError if unsupported
        self.window     = video.Window(title, size=size, resizable=True)
        self.renderer   = video.Renderer(self.window, vsync=vsync)
        self.texture    = video.Texture(self.renderer, logical_size, streaming=True)
        self._fullscreen = False

    @property
    def size(self) -> tuple:
        return tuple(self.window.size)

    def present(self, logical: pygame.Surface, dst_rect: pygame.Rect) -> None:
        r = self.renderer
        r.draw_color = (0, 0, 0, 255)
        r.clear()                                          # letterbox bars
        self.texture.update(logical)                       # one upload per frame
        self.texture.draw(dstrect=dst_rect)                # GPU scales it
        r.present()

    def toggle_fullscreen(self) -> None:
        if self._fullscreen:
            self.window.set_windowed()
        else:
            self.window.set_fullscreen(desktop=True)
        self._fullscreen = not self._fullscreen

    def set_icon(self, surface: pygame.Surface) -> None:
        self.window.set_icon(surface)
