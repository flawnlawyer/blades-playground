from __future__ import annotations
import pygame

from game.constants import (
    W, H,
    PLAYER_COL, CHAOS_COL, ENERGY_COL, ENEMY_COL,
    FRAG_COL, WHITE, DIM,
    CONTROLS_FADE_TIME,
)


class UI:
    def __init__(self) -> None:
        self.font_m = pygame.font.SysFont("monospace", 13, bold=False)
        self.font_b = pygame.font.SysFont("monospace", 20, bold=True)
        self.font_s = pygame.font.SysFont("monospace", 11)

    # ── Main HUD ─────────────────────────────────────────────────────────────

    def draw_hud(self, surf: pygame.Surface, player, hp: int, score: int,
                 run_time: float) -> None:
        p = player
        self._draw_energy_bar(surf, p)
        self._draw_hp_pips(surf, hp)
        self._draw_score_time(surf, score, run_time)
        self._draw_hack_prompt(surf, p)
        if p.chaos_mode:
            self._draw_chaos_banner(surf, p)

    def _draw_energy_bar(self, surf: pygame.Surface, player) -> None:
        bx, by, bw, bh = 20, H - 38, 210, 11
        col = CHAOS_COL if player.chaos_mode else ENERGY_COL
        pygame.draw.rect(surf, (25, 25, 45), (bx, by, bw, bh), border_radius=4)
        fill = int(bw * (player.energy / player.max_energy))
        if fill:
            pygame.draw.rect(surf, col, (bx, by, fill, bh), border_radius=4)
        pygame.draw.rect(surf, (70, 70, 110), (bx, by, bw, bh), 1, border_radius=4)
        lbl = "CHAOS ACTIVE" if player.chaos_mode else "ENERGY"
        surf.blit(self.font_s.render(lbl, True, col), (bx, by - 14))

    def _draw_hp_pips(self, surf: pygame.Surface, hp: int) -> None:
        for i in range(max(0, hp)):
            cx = W - 25 - i * 22
            pygame.draw.circle(surf, ENEMY_COL, (cx, 22), 7)
            pygame.draw.circle(surf, WHITE,     (cx, 22), 7, 1)

    def _draw_score_time(self, surf: pygame.Surface, score: int,
                         run_time: float) -> None:
        surf.blit(self.font_m.render(f"score: {score}", True, DIM), (20, 18))
        t = int(run_time)
        surf.blit(
            self.font_s.render(f"t+{t // 60:02d}:{t % 60:02d}", True, DIM),
            (20, 36),
        )

    def _draw_hack_prompt(self, surf: pygame.Surface, player) -> None:
        if player.hack_cd > 0:
            txt = f"[SPACE] hack: {player.hack_cd:.1f}s"
            col = (60, 160, 80)
        else:
            txt = "[SPACE] hack: ready"
            col = (80, 220, 100)
        surf.blit(self.font_s.render(txt, True, col), (20, 52))

    def _draw_chaos_banner(self, surf: pygame.Surface, player) -> None:
        txt = self.font_b.render(
            f"// CHAOS MODE  {player.chaos_timer:.1f}s", True, CHAOS_COL
        )
        surf.blit(txt, (W // 2 - txt.get_width() // 2, 14))

    # ── Fragment popup ────────────────────────────────────────────────────────

    def draw_fragment_popup(self, surf: pygame.Surface,
                            text: str, timer: float, max_timer: float) -> None:
        if timer <= 0:
            return
        a   = min(1.0, timer / (max_timer * 0.35))
        ft  = self.font_m.render(f'"{text}"', True, FRAG_COL)
        s   = pygame.Surface(ft.get_size(), pygame.SRCALPHA)
        s.blit(ft, (0, 0))
        s.set_alpha(int(a * 255))
        surf.blit(s, (W // 2 - s.get_width() // 2, H // 2 - 70))

    # ── Controls hint (fades) ─────────────────────────────────────────────────

    def draw_controls_hint(self, surf: pygame.Surface, run_time: float) -> None:
        if run_time >= CONTROLS_FADE_TIME:
            return
        a = max(0.0, 1.0 - run_time / CONTROLS_FADE_TIME)
        hints = [
            "WASD / arrows : move",
            "SPACE         : hack nearby",
            "destroy meh blocks → fill energy → CHAOS",
            "M             : toggle mute",
        ]
        for i, h in enumerate(hints):
            ht = self.font_s.render(h, True, (90, 90, 130))
            ht.set_alpha(int(a * 200))
            surf.blit(ht, (W // 2 - ht.get_width() // 2, H - 96 + i * 16))

    # ── Mute indicator ────────────────────────────────────────────────────────

    def draw_mute_indicator(self, surf: pygame.Surface, muted: bool) -> None:
        txt = "[M] muted" if muted else "[M] sound on"
        col = (80, 80, 110) if muted else (60, 100, 60)
        surf.blit(self.font_s.render(txt, True, col), (W - 110, H - 20))

    # ── Game over overlay ─────────────────────────────────────────────────────

    def draw_game_over(self, surf: pygame.Surface, score: int) -> None:
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 175))
        surf.blit(ov, (0, 0))

        go = self.font_b.render("// system.collapse()", True, ENEMY_COL)
        sc = self.font_m.render(f"final score : {score}", True, WHITE)
        rt = self.font_m.render("[R] reboot   [ESC] quit", True, DIM)

        surf.blit(go, (W // 2 - go.get_width() // 2, H // 2 - 45))
        surf.blit(sc, (W // 2 - sc.get_width() // 2, H // 2 +  2))
        surf.blit(rt, (W // 2 - rt.get_width() // 2, H // 2 + 30))
