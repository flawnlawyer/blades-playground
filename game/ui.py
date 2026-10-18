"""
ui.py — All HUD panels, overlays, and animated UI elements.
"""
from __future__ import annotations
import math, random
import pygame

from game.constants import (
    W, H,
    PLAYER_COL, CHAOS_COL, ENERGY_COL, ENEMY_COL,
    FRAG_COL, WHITE, DIM, ACCENT,
    WEAPON_NAMES, WEAPON_COLORS,
    BOSS_COL, BOSS_HP,
    CONTROLS_FADE_TIME,
)
from utils.helpers import alpha_rect, draw_panel, lerp_color, fade_circle


class UI:
    def __init__(self) -> None:
        self.font_xl = pygame.font.SysFont("monospace", 32, bold=True)
        self.font_l  = pygame.font.SysFont("monospace", 22, bold=True)
        self.font_m  = pygame.font.SysFont("monospace", 14)
        self.font_s  = pygame.font.SysFont("monospace", 11)
        self._wave_banner_timer = 0.0
        self._wave_banner_text  = ""
        self._wave_glitch       = []

    # ── Main HUD ─────────────────────────────────────────────────────────────

    def draw_hud(self, surf: pygame.Surface, player, hp: int, score: int,
                 run_time: float, wave: int, wave_mgr=None) -> None:
        self._draw_energy_bar(surf, player)
        self._draw_hp_pips(surf, hp)
        self._draw_score_time(surf, score, run_time, wave)
        self._draw_hack_prompt(surf, player)
        self._draw_weapon_bar(surf, player)
        if wave_mgr and wave_mgr.in_break and wave_mgr.wave > 0:
            self._draw_wave_break(surf, wave_mgr.break_countdown)
        if player.chaos_mode:
            self._draw_chaos_banner(surf, player)

    def _draw_energy_bar(self, surf: pygame.Surface, player) -> None:
        bx, by, bw, bh = 20, H - 46, 240, 14
        draw_panel(surf, (bx - 6, by - 18, bw + 12, bh + 24), alpha=160)
        col  = CHAOS_COL if player.chaos_mode else ENERGY_COL
        fill = int(bw * (player.energy / player.max_energy))
        pygame.draw.rect(surf, (18, 18, 38), (bx, by, bw, bh), border_radius=5)
        if fill:
            pygame.draw.rect(surf, col, (bx, by, fill, bh), border_radius=5)
            # Shimmer
            pygame.draw.rect(surf, (*WHITE, 30),
                             (bx, by, fill, bh // 2), border_radius=5)
        pygame.draw.rect(surf, (70, 70, 110), (bx, by, bw, bh), 1, border_radius=5)
        lbl = "// CHAOS ACTIVE //" if player.chaos_mode else "ENERGY"
        surf.blit(self.font_s.render(lbl, True, col), (bx, by - 14))

    def _draw_hp_pips(self, surf: pygame.Surface, hp: int) -> None:
        for i in range(max(0, hp)):
            cx = W - 28 - i * 26
            cy = 24
            fade_circle(surf, ENEMY_COL, (cx, cy), 12, 40)      # cached sprite
            pygame.draw.circle(surf, ENEMY_COL, (cx, cy), 8)
            pygame.draw.circle(surf, WHITE,     (cx, cy), 8, 1)

    def _draw_score_time(self, surf: pygame.Surface, score: int,
                         run_time: float, wave: int) -> None:
        draw_panel(surf, (14, 8, 200, 56), alpha=150)
        surf.blit(self.font_m.render(f"SCORE  {score:>7}", True, WHITE),   (20, 12))
        t = int(run_time)
        surf.blit(self.font_s.render(f"t+{t // 60:02d}:{t % 60:02d}", True, DIM), (20, 32))
        surf.blit(self.font_s.render(f"WAVE   {wave}", True, ACCENT), (100, 32))

    def draw_streak(self, surf: pygame.Surface, streak: int, mult: float,
                    frac: float) -> None:
        """Kill-streak counter + decay bar under the score panel."""
        if streak < 2:
            return
        hot = mult >= 3.0
        col = CHAOS_COL if mult > 1.0 else ACCENT
        draw_panel(surf, (14, 70, 200, 34), alpha=150,
                   border_color=col if mult > 1.0 else (50, 50, 90))
        label = f"STREAK {streak}"
        surf.blit(self.font_s.render(label, True, WHITE), (22, 75))
        mtxt = self.font_m.render(f"x{mult:g}", True, col)
        surf.blit(mtxt, (206 - mtxt.get_width(), 74 if not hot else 73 + int(math.sin(pygame.time.get_ticks() * 0.02) * 1.5)))
        pygame.draw.rect(surf, (18, 18, 38), (22, 94, 184, 4), border_radius=2)
        pygame.draw.rect(surf, col, (22, 94, int(184 * max(0.0, min(1.0, frac))), 4), border_radius=2)

    def draw_perks(self, surf: pygame.Surface, perks: list) -> None:
        """Owned perks, right-aligned under the HP pips: [(name, stacks, color), ...]."""
        y = 46
        for name, stacks, col in perks:
            txt = self.font_s.render(f"{name} x{stacks}" if stacks > 1 else name, True, col)
            surf.blit(txt, (W - 16 - txt.get_width(), y))
            y += 14

    def _draw_hack_prompt(self, surf: pygame.Surface, player) -> None:
        if player.hack_cd > 0:
            txt = f"[SPACE] hack: {player.hack_cd:.1f}s"
            col = (60, 160, 80)
        else:
            txt = "[SPACE] hack: READY"
            col = (80, 220, 100)
        surf.blit(self.font_s.render(txt, True, col), (20, H - 82))

        # Dash indicator
        pips = "".join("[#]" if i < player.dash_charges else "[ ]"
                       for i in range(player.max_dash_charges))
        if player.dash_charges <= 0:
            dtxt = f"[SHIFT] dash: {pips}  {max(0.0, player._dash_recharge):.1f}s"
            dcol = (80, 80, 160)
        else:
            dtxt = f"[SHIFT] dash: {pips}"
            dcol = (120, 120, 255)
        surf.blit(self.font_s.render(dtxt, True, dcol), (20, H - 96))

    def _draw_weapon_bar(self, surf: pygame.Surface, player) -> None:
        bw, bh = 44, 44
        total  = 5
        bar_w  = total * bw + (total - 1) * 4
        bx     = W // 2 - bar_w // 2
        by     = H - 58
        draw_panel(surf, (bx - 8, by - 8, bar_w + 16, bh + 16), alpha=170)

        for i in range(total):
            x   = bx + i * (bw + 4)
            col = WEAPON_COLORS[i]
            selected = (i == player.weapon_index)
            # Box
            pygame.draw.rect(surf, (16, 16, 32), (x, by, bw, bh), border_radius=4)
            if selected:
                pygame.draw.rect(surf, col, (x, by, bw, bh), 2, border_radius=4)
                glow = pygame.Surface((bw + 12, bh + 12), pygame.SRCALPHA)
                pygame.draw.rect(glow, (*col, 30), (0, 0, bw + 12, bh + 12),
                                 border_radius=6)
                surf.blit(glow, (x - 6, by - 6))
            else:
                pygame.draw.rect(surf, (40, 40, 65), (x, by, bw, bh), 1, border_radius=4)
            # Cooldown overlay
            cd  = player._weapon_cds[i]
            if cd > 0:
                max_cds = [0.22, 0.65, 1.3, 0, 0.5]
                frac = min(1.0, cd / max(max_cds[i], 0.01))
                alpha_rect(surf, (0, 0, 0), (x, by + int(bh * (1 - frac)),
                                              bw, int(bh * frac)), 140, 4)
            # Key number
            surf.blit(self.font_s.render(str(i + 1), True, DIM), (x + 3, by + 3))
            # Weapon abbreviated name
            abbr = WEAPON_NAMES[i].split()[0][:3]
            surf.blit(self.font_s.render(abbr, True,
                       col if selected else DIM), (x + 5, by + 28))
            # Bomb count
            if i == 4:
                bomb_txt = f"x{player.bomb_count}"
                surf.blit(self.font_s.render(bomb_txt, True,
                           WEAPON_COLORS[4]), (x + 24, by + 3))

    def _draw_chaos_banner(self, surf: pygame.Surface, player) -> None:
        txt = self.font_l.render(
            f"// CHAOS MODE  {player.chaos_timer:.1f}s", True, CHAOS_COL)
        sx = W // 2 - txt.get_width() // 2
        surf.blit(txt, (sx, 14))

    def _draw_wave_break(self, surf: pygame.Surface, countdown: float) -> None:
        """Pulsing countdown shown between waves."""
        import math
        pulse = 0.5 + 0.5 * math.sin(countdown * 6)
        col = tuple(int(c * (0.7 + 0.3 * pulse)) for c in (0, 200, 160))
        txt = self.font_l.render(
            f"NEXT WAVE IN: {max(0, countdown):.1f}s", True, col)
        s = pygame.Surface(txt.get_size(), pygame.SRCALPHA)
        s.blit(txt, (0, 0))
        s.set_alpha(int(180 + 75 * pulse))
        surf.blit(s, (W // 2 - s.get_width() // 2, 14))

    # ── Boss HP bar ───────────────────────────────────────────────────────────

    def draw_boss_bar(self, surf: pygame.Surface, boss) -> None:
        if boss is None:
            return
        bw, bh = 500, 18
        bx = W // 2 - bw // 2
        by = H - 90
        draw_panel(surf, (bx - 10, by - 20, bw + 20, bh + 30), alpha=200)
        bcol = getattr(boss, "bar_color", BOSS_COL)
        surf.blit(self.font_s.render(getattr(boss, "name", "BOSS"), True, bcol), (bx, by - 16))
        fill = int(bw * max(0, boss.hp / boss.max_hp))
        pygame.draw.rect(surf, (20, 20, 40), (bx, by, bw, bh), border_radius=6)
        if fill:
            col = (255, 80, 80) if boss.is_phase2 else bcol
            pygame.draw.rect(surf, col, (bx, by, fill, bh), border_radius=6)
            pygame.draw.rect(surf, (*WHITE, 30), (bx, by, fill, bh // 2), border_radius=6)
        pygame.draw.rect(surf, (80, 80, 130), (bx, by, bw, bh), 1, border_radius=6)
        # Phase 2 warning line
        p2x = bx + int(bw * (boss._p2_hp / boss.max_hp))
        pygame.draw.line(surf, (255, 60, 60), (p2x, by), (p2x, by + bh), 2)

    # ── Fragment popup ────────────────────────────────────────────────────────

    def draw_fragment_popup(self, surf: pygame.Surface, text: str,
                            timer: float, max_timer: float) -> None:
        if timer <= 0:
            return
        a  = min(1.0, timer / (max_timer * 0.35))
        ft = self.font_m.render(f'"{text}"', True, FRAG_COL)
        draw_panel(surf, (W // 2 - ft.get_width() // 2 - 10,
                          H // 2 - 80, ft.get_width() + 20, 28), alpha=180)
        ft.set_alpha(int(a * 255))
        surf.blit(ft, (W // 2 - ft.get_width() // 2, H // 2 - 74))

    # ── Wave banner ───────────────────────────────────────────────────────────

    def show_wave_banner(self, wave: int, is_boss: bool = False,
                         boss_name: str = "THE ARCHITECT") -> None:
        if is_boss:
            self._wave_banner_text = f"// {boss_name} INCOMING //"
        else:
            self._wave_banner_text = f"// WAVE {wave} //"
        self._wave_banner_timer = 3.0

    def draw_wave_banner(self, surf: pygame.Surface, dt: float) -> None:
        if self._wave_banner_timer <= 0:
            return
        self._wave_banner_timer -= dt
        a   = min(1.0, self._wave_banner_timer / 2.5)
        # Glitch the text occasionally
        text = self._wave_banner_text
        if random.random() < 0.08:
            i = random.randint(0, len(text) - 1)
            text = text[:i] + random.choice("!@#$%^&*<>") + text[i + 1:]
        txt = self.font_xl.render(text, True, CHAOS_COL)
        s   = pygame.Surface(txt.get_size(), pygame.SRCALPHA)
        s.blit(txt, (0, 0))
        s.set_alpha(int(a * 255))
        surf.blit(s, (W // 2 - s.get_width() // 2, H // 2 - 30))

    # ── Controls hint ─────────────────────────────────────────────────────────

    def draw_controls_hint(self, surf: pygame.Surface, run_time: float) -> None:
        if run_time >= CONTROLS_FADE_TIME:
            return
        a = max(0.0, 1.0 - run_time / CONTROLS_FADE_TIME)
        hints = [
            "WASD: move   SHIFT: dash   SPACE: hack",
            "1-5: select weapon   LMB: fire   M: mute",
            "destroy meh blocks → fill energy → CHAOS",
        ]
        for i, h in enumerate(hints):
            ht = self.font_s.render(h, True, (90, 90, 130))
            ht.set_alpha(int(a * 200))
            surf.blit(ht, (W // 2 - ht.get_width() // 2, H - 100 + i * 16))

    # ── Mute indicator ────────────────────────────────────────────────────────

    def draw_mute_indicator(self, surf: pygame.Surface, muted: bool) -> None:
        txt = "[M] MUTED" if muted else "[M] SFX ON"
        col = (70, 70, 90) if muted else (80, 200, 80)
        surf.blit(self.font_s.render(txt, True, col), (W - 120, H - 20))

    # ── Game Over overlay ─────────────────────────────────────────────────────

    def draw_game_over(self, surf: pygame.Surface, score: int) -> None:
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surf.blit(overlay, (0, 0))

        title = self.font_xl.render("// PROCESS TERMINATED //", True, ENEMY_COL)
        surf.blit(title, (W // 2 - title.get_width() // 2, H // 2 - 70))

        score_txt = self.font_l.render(f"FINAL SCORE:  {score}", True, WHITE)
        surf.blit(score_txt, (W // 2 - score_txt.get_width() // 2, H // 2 - 20))

        hint = self.font_m.render("[R] restart   [ESC] quit", True, DIM)
        surf.blit(hint, (W // 2 - hint.get_width() // 2, H // 2 + 30))

    # ── Crosshair ────────────────────────────────────────────────────────────

    def draw_crosshair(self, surf: pygame.Surface, pos: tuple,
                       weapon_col: tuple) -> None:
        mx, my = int(pos[0]), int(pos[1])
        size, gap = 10, 4
        s = pygame.Surface((size * 4, size * 4), pygame.SRCALPHA)
        cx, cy = size * 2, size * 2
        lines = [
            ((cx - size, cy), (cx - gap, cy)),
            ((cx + gap,  cy), (cx + size, cy)),
            ((cx, cy - size), (cx, cy - gap)),
            ((cx, cy + gap),  (cx, cy + size)),
        ]
        for p1, p2 in lines:
            pygame.draw.line(s, (*weapon_col, 200), p1, p2, 1)
        pygame.draw.circle(s, (*weapon_col, 120), (cx, cy), 2)
        surf.blit(s, (mx - size * 2, my - size * 2))


# Local import to avoid circular issues
def glow_circle(surf, color, pos, radius, alpha=50):
    r2 = radius * 2
    s = pygame.Surface((r2 * 2, r2 * 2), pygame.SRCALPHA)
    pygame.draw.circle(s, (*color[:3], alpha), (r2, r2), r2)
    surf.blit(s, (int(pos[0]) - r2, int(pos[1]) - r2))
