"""
player.py — Player entity: movement, dash, 5-weapon system, mouse aim.
"""
from __future__ import annotations
import math
import pygame

from game.constants import (
    W, H,
    PLAYER_COL, CHAOS_COL, WHITE,
    PLAYER_SPEED, PLAYER_RADIUS, PLAYER_TRAIL_LEN,
    PLAYER_HACK_CD, PLAYER_INV_DURATION,
    PLAYER_MAX_ENERGY, CHAOS_DURATION, CHAOS_SPEED_MULT,
    PLAYER_DASH_SPEED, PLAYER_DASH_FRAMES, PLAYER_DASH_CD,
    WEAPON_NAMES, WEAPON_COLORS,
    PLASMA_CD, PLASMA_SPEED, PLASMA_DAMAGE, PLASMA_RANGE,
    SPREAD_CD, SPREAD_SPEED, SPREAD_DAMAGE, SPREAD_COUNT, SPREAD_ANGLE,
    CHAIN_CD, CHAIN_DAMAGE, CHAIN_LINKS, CHAIN_RANGE,
    BEAM_DAMAGE_PS, BEAM_ENERGY_DRAIN,
    BOMB_MAX, BOMB_RECHARGE, BOMB_RADIUS, BOMB_DAMAGE, BOMB_FUSE,
)
from game.entities import Projectile
from utils.helpers import glow_circle, glow_circle_multi, rotate_points, lerp_color


class Player:
    def __init__(self, x: float, y: float) -> None:
        self.pos          = pygame.Vector2(x, y)
        self.radius       = PLAYER_RADIUS
        self.energy       = 0.0
        self.max_energy   = PLAYER_MAX_ENERGY
        self.chaos_mode   = False
        self.chaos_timer  = 0.0
        self.hack_cd      = 0.0
        self.inv_timer    = 0.0
        self.trail: list[pygame.Vector2] = []

        # Dash
        self._dash_cd          = 0.0
        self._dash_frames_left = 0
        self._dash_vel         = pygame.Vector2(0, 0)
        self.is_dashing        = False

        # Facing angle (radians, updated from mouse)
        self._angle = 0.0

        # Weapons
        self.weapon_index    = 0          # 0–4
        self._weapon_cds     = [0.0] * 5
        self.bomb_count      = BOMB_MAX
        self._bomb_recharge  = 0.0
        self._beam_firing    = False

        self._chaos_just_ended = False

        # Fired projectiles (returned to game.py for collision)
        self.new_projectiles: list[Projectile] = []

        # Chain zap targets (returned to game.py)
        self.chain_targets: list = []

        # Beam active flag
        self.beam_active   = False
        self._beam_timer   = 0.0

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, keys: pygame.key.ScancodeWrapper, dt: float,
               mouse_pos: tuple, mouse_buttons: tuple,
               enemies: list) -> None:
        # Mouse facing angle
        dx = mouse_pos[0] - self.pos.x
        dy = mouse_pos[1] - self.pos.y
        if abs(dx) > 1 or abs(dy) > 1:
            self._angle = math.atan2(dy, dx)

        # Movement
        vel = pygame.Vector2(0, 0)
        spd = PLAYER_SPEED * (CHAOS_SPEED_MULT if self.chaos_mode else 1.0)

        if keys[pygame.K_w] or keys[pygame.K_UP]:    vel.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  vel.y += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  vel.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: vel.x += 1

        if vel.length_squared() > 0:
            vel = vel.normalize() * spd

        # Dash
        if self._dash_frames_left > 0:
            self.pos += self._dash_vel
            self._dash_frames_left -= 1
            if self._dash_frames_left == 0:
                self.is_dashing = False
        else:
            self.pos += vel

        self.pos.x = max(self.radius, min(W - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(H - self.radius, self.pos.y))

        # Trail
        self.trail.append(pygame.Vector2(self.pos))
        if len(self.trail) > PLAYER_TRAIL_LEN:
            self.trail.pop(0)

        # Timers
        if self.hack_cd   > 0: self.hack_cd   -= dt
        if self.inv_timer > 0: self.inv_timer -= dt
        if self._dash_cd  > 0: self._dash_cd  -= dt
        for i in range(5):
            if self._weapon_cds[i] > 0:
                self._weapon_cds[i] -= dt

        # Bomb recharge
        if self.bomb_count < BOMB_MAX:
            self._bomb_recharge -= dt
            if self._bomb_recharge <= 0:
                self.bomb_count     += 1
                self._bomb_recharge  = BOMB_RECHARGE

        # Chaos countdown
        self._chaos_just_ended = False
        if self.chaos_mode:
            self.chaos_timer -= dt
            if self.chaos_timer <= 0:
                self.chaos_mode        = False
                self.energy            = 0.0
                self._chaos_just_ended = True

        # Weapon switching (keys 1–5)
        for i, key in enumerate([pygame.K_1, pygame.K_2, pygame.K_3,
                                  pygame.K_4, pygame.K_5]):
            if keys[key]:
                self.weapon_index = i

        # Weapon fire
        self.beam_active  = False
        lmb = mouse_buttons[0]
        if lmb:
            self._fire(mouse_pos, enemies, dt)

    # ── Dash ──────────────────────────────────────────────────────────────────

    def trigger_dash(self, keys) -> bool:
        if self._dash_cd > 0 or self.is_dashing:
            return False
        vel = pygame.Vector2(0, 0)
        if keys[pygame.K_w] or keys[pygame.K_UP]:    vel.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  vel.y += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  vel.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: vel.x += 1
        if vel.length_squared() == 0:
            vel = pygame.Vector2(math.cos(self._angle), math.sin(self._angle))
        self._dash_vel         = vel.normalize() * PLAYER_DASH_SPEED
        self._dash_frames_left = PLAYER_DASH_FRAMES
        self._dash_cd          = PLAYER_DASH_CD
        self.is_dashing        = True
        return True

    # ── Weapon fire ───────────────────────────────────────────────────────────

    def _fire(self, mouse_pos: tuple, enemies: list, dt: float) -> None:
        wi  = self.weapon_index
        cdl = self._weapon_cds

        dx = mouse_pos[0] - self.pos.x
        dy = mouse_pos[1] - self.pos.y

        if wi == 0 and cdl[0] <= 0:          # Plasma Bolt
            self._fire_plasma(dx, dy)
            cdl[0] = PLASMA_CD

        elif wi == 1 and cdl[1] <= 0:        # Void Spread
            self._fire_spread(dx, dy)
            cdl[1] = SPREAD_CD

        elif wi == 2 and cdl[2] <= 0:        # Chain Zap
            self._fire_chain(enemies)
            cdl[2] = CHAIN_CD

        elif wi == 3:                          # Null Beam (hold)
            self._fire_beam(dx, dy, enemies, dt)

        elif wi == 4 and cdl[4] <= 0:        # Chaos Bomb
            if self.bomb_count > 0:
                self._fire_bomb(dx, dy)
                self.bomb_count    -= 1
                self._bomb_recharge = BOMB_RECHARGE
                cdl[4] = 0.5

    def _fire_plasma(self, dx: float, dy: float) -> None:
        self.new_projectiles.append(
            Projectile(self.pos.x, self.pos.y, dx, dy,
                       PLASMA_SPEED, PLASMA_DAMAGE, PLASMA_RANGE,
                       Projectile.TYPE_PLASMA))

    def _fire_spread(self, dx: float, dy: float) -> None:
        base_angle = math.atan2(dy, dx)
        spread_rad = math.radians(SPREAD_ANGLE)
        for i in range(SPREAD_COUNT):
            t = i / (SPREAD_COUNT - 1) - 0.5 if SPREAD_COUNT > 1 else 0
            a = base_angle + t * spread_rad
            self.new_projectiles.append(
                Projectile(self.pos.x, self.pos.y,
                           math.cos(a), math.sin(a),
                           SPREAD_SPEED, SPREAD_DAMAGE, 400,
                           Projectile.TYPE_SPREAD))

    def _fire_chain(self, enemies: list) -> None:
        """Chain zap — finds nearest enemies within range, chains."""
        remaining = list(enemies)
        origin    = pygame.Vector2(self.pos)
        targets   = []
        for _ in range(CHAIN_LINKS):
            best, best_d = None, CHAIN_RANGE
            for e in remaining:
                d = origin.distance_to(e.pos)
                if d < best_d:
                    best, best_d = e, d
            if best is None:
                break
            targets.append(best)
            remaining.remove(best)
            origin = pygame.Vector2(best.pos)
        self.chain_targets = targets

    def _fire_beam(self, dx: float, dy: float, enemies: list, dt: float) -> None:
        """Null Beam — continuous, drains energy."""
        self.beam_active = True
        # Damage enemies along beam
        angle = math.atan2(dy, dx)
        for e in enemies:
            ex = e.pos.x - self.pos.x
            ey = e.pos.y - self.pos.y
            dist   = math.hypot(ex, ey)
            if dist > 500:
                continue
            e_angle = math.atan2(ey, ex)
            diff    = abs(math.atan2(math.sin(e_angle - angle),
                                     math.cos(e_angle - angle)))
            if diff < 0.18 and dist < 500:
                e.take_damage(BEAM_DAMAGE_PS * dt)
        # Drain energy
        drain = BEAM_ENERGY_DRAIN * dt
        self.energy = max(0.0, self.energy - drain)
        if self.chaos_mode and self.energy <= 0:
            self.chaos_mode = False

    def _fire_bomb(self, dx: float, dy: float) -> None:
        self.new_projectiles.append(
            Projectile(self.pos.x, self.pos.y, dx, dy,
                       6, BOMB_DAMAGE, 9999,
                       Projectile.TYPE_BOMB))

    # ── Energy / chaos ────────────────────────────────────────────────────────

    def add_energy(self, amt: float) -> bool:
        self.energy = min(self.max_energy, self.energy + amt)
        if self.energy >= self.max_energy and not self.chaos_mode:
            self.chaos_mode  = True
            self.chaos_timer = CHAOS_DURATION
            return True
        return False

    # ── Hack ──────────────────────────────────────────────────────────────────

    @property
    def can_hack(self) -> bool:
        return self.hack_cd <= 0

    def trigger_hack(self) -> None:
        self.hack_cd = PLAYER_HACK_CD

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surf: pygame.Surface) -> None:
        # Color shifts: purple → teal → gold based on energy
        t   = self.energy / self.max_energy
        col = CHAOS_COL if self.chaos_mode else lerp_color(PLAYER_COL, (0, 220, 180), t)

        # Trail
        n = len(self.trail)
        for i, tp in enumerate(self.trail):
            tt = i / max(n, 1)
            r  = max(1, int(self.radius * 0.55 * tt))
            a  = int(170 * tt)
            s  = pygame.Surface((r * 2 + 1, r * 2 + 1), pygame.SRCALPHA)
            pygame.draw.circle(s, (*col, a), (r, r), r)
            surf.blit(s, (int(tp.x) - r, int(tp.y) - r))

        cx, cy = int(self.pos.x), int(self.pos.y)

        # Glow
        if self.chaos_mode:
            glow_circle_multi(surf, col, (cx, cy), self.radius + 8, 3)
        else:
            glow_circle(surf, col, (cx, cy), self.radius + 8, 45)

        # Body — arrowhead polygon pointing toward mouse
        r  = self.radius
        a  = self._angle
        pts = rotate_points([
            (cx + r,      cy),
            (cx - r + 4,  cy - r + 4),
            (cx - r // 2, cy),
            (cx - r + 4,  cy + r - 4),
        ], a, cx, cy)
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, WHITE, pts, 1)

        # Specular highlight
        pygame.draw.circle(surf, (*WHITE, 80), (cx - 4, cy - 4), 4)

        # Dash afterburner
        if self.is_dashing:
            s = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*CHAOS_COL, 90), (r * 2, r * 2), r + 6)
            surf.blit(s, (cx - r * 2, cy - r * 2))

        # Invincibility flash ring
        if self.inv_timer > 0 and int(self.inv_timer * 10) % 2 == 0:
            pygame.draw.circle(surf, WHITE, (cx, cy), self.radius + 4, 2)

        # Beam draw
        if self.beam_active:
            bx = int(self.pos.x + math.cos(self._angle) * 500)
            by = int(self.pos.y + math.sin(self._angle) * 500)
            s  = pygame.Surface((W, H), pygame.SRCALPHA)
            pygame.draw.line(s, (*WEAPON_COLORS[3], 180), (cx, cy), (bx, by), 3)
            pygame.draw.line(s, (*WEAPON_COLORS[3], 80),  (cx, cy), (bx, by), 7)
            surf.blit(s, (0, 0))
