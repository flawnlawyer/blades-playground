"""
entities.py — MehBlock, Fragment, and all enemy types + Projectile.
Enemies: Standard, Hunter, Swarm, Phantom, Boss (The Architect)
"""
from __future__ import annotations
import math, random
import pygame

from game.constants import (
    W, H,
    MEH_COL, MEH_HACKED, FRAG_COL, ENEMY_COL, WHITE, DIM,
    HUNTER_COL, SWARM_COL, PHANTOM_COL, BOSS_COL,
    MEH_DEFAULT_HP,
    ENEMY_SPEED_MIN, ENEMY_SPEED_MAX, ENEMY_CHASE_DIST,
    ENEMY_RADIUS, ENEMY_STUN_DURATION,
    HUNTER_RADIUS, HUNTER_SPEED,
    SWARM_RADIUS, SWARM_SPEED,
    PHANTOM_RADIUS, PHANTOM_SPEED,
    BOSS_RADIUS, BOSS_HP, BOSS_PHASE2_HP,
    BOMB_FUSE,
    PLASMA_COL, SPREAD_COL, CHAIN_COL, BEAM_COL, BOMB_COL,
)
from utils.helpers import glow_circle, glow_circle_multi, rotate_points


# ── Meh Block ─────────────────────────────────────────────────────────────────

class MehBlock:
    SIZE = 38

    def __init__(self, x: float, y: float) -> None:
        self.rect       = pygame.Rect(int(x), int(y), self.SIZE, self.SIZE)
        self.hp         = MEH_DEFAULT_HP
        self.hacked     = False
        self.hack_timer = 0.0
        self._glitch    = [0, 0]
        self._glitch_cd = random.uniform(0.5, 2.0)
        self._stripe_y  = int(y) + self.SIZE // 2

    def update(self, dt: float) -> None:
        self._glitch_cd -= dt
        if self._glitch_cd <= 0:
            self._glitch_cd = random.uniform(0.8, 3.0)
            self._glitch    = [random.randint(-2, 2), random.randint(-2, 2)]
            self._stripe_y  = self.rect.y + random.randint(0, self.SIZE - 3)
        if self.hacked:
            self.hack_timer -= dt
            if self.hack_timer <= 0:
                self.hacked = False

    def hack(self, duration: float = 3.5) -> None:
        self.hacked     = True
        self.hack_timer = duration

    @property
    def center(self) -> pygame.Vector2:
        return pygame.Vector2(self.rect.centerx, self.rect.centery)

    def draw(self, surf: pygame.Surface, font: pygame.font.Font) -> None:
        col = MEH_HACKED if self.hacked else MEH_COL
        r   = self.rect.move(self._glitch)
        pygame.draw.rect(surf, col, r, border_radius=5)
        stripe = pygame.Surface((r.width, 3), pygame.SRCALPHA)
        stripe.fill((*WHITE, 16))
        surf.blit(stripe, (r.x, self._stripe_y))
        pygame.draw.rect(surf, (*WHITE, 28), r, 1, border_radius=5)
        label = font.render(">>" if self.hacked else "meh", True, (20, 20, 35))
        surf.blit(label, (r.x + 7, r.y + 13))


# ── Fragment ──────────────────────────────────────────────────────────────────

class Fragment:
    RADIUS = 9

    def __init__(self, x: float, y: float, text: str) -> None:
        self.pos    = pygame.Vector2(x, y)
        self.text   = text
        self.radius = self.RADIUS
        self._float = random.uniform(0, math.tau)
        self._pulse = 0.0

    def update(self, dt: float) -> None:
        self._float += dt * 2.2
        self._pulse += dt * 3.5

    def draw(self, surf: pygame.Surface) -> None:
        oy = math.sin(self._float) * 5
        cx = int(self.pos.x)
        cy = int(self.pos.y + oy)
        pr = self.radius + abs(math.sin(self._pulse)) * 4
        glow_circle(surf, FRAG_COL, (cx, cy), int(pr) + 8, 35)
        pygame.draw.circle(surf, FRAG_COL, (cx, cy), self.radius)
        pygame.draw.circle(surf, WHITE,    (cx, cy), self.radius, 1)


# ── Projectile ────────────────────────────────────────────────────────────────

class Projectile:
    """Mouse-aimed player projectile. weapon_type selects visuals/behaviour."""

    TYPE_PLASMA = 0
    TYPE_SPREAD = 1
    TYPE_CHAIN  = 2   # handled specially — not a normal projectile
    TYPE_BEAM   = 3   # handled specially — not a normal projectile
    TYPE_BOMB   = 4

    def __init__(self, x: float, y: float, dx: float, dy: float,
                 speed: float, damage: int, max_range: float,
                 weapon_type: int = 0) -> None:
        self.pos         = pygame.Vector2(x, y)
        self.origin      = pygame.Vector2(x, y)
        mag = math.hypot(dx, dy) or 1
        self.vel         = pygame.Vector2(dx / mag * speed, dy / mag * speed)
        self.damage      = damage
        self.max_range   = max_range
        self.weapon_type = weapon_type
        self._phase      = random.uniform(0, math.tau)
        self.alive       = True
        self.radius      = 5

        # Bomb-specific
        self.fuse        = BOMB_FUSE   # seconds until detonation
        self.detonated   = False

        _COLS = [PLASMA_COL, SPREAD_COL, CHAIN_COL, BEAM_COL, BOMB_COL]
        self.color = _COLS[weapon_type % len(_COLS)]

    def update(self, dt: float) -> None:
        self._phase += dt * 8
        if self.weapon_type == self.TYPE_BOMB:
            self.pos += self.vel * dt * 60
            self.vel *= 0.93
            self.fuse -= dt
            if self.fuse <= 0 and not self.detonated:
                self.detonated = True
                self.alive     = False
        else:
            self.pos += self.vel
            if self.origin.distance_to(self.pos) > self.max_range:
                self.alive = False

    def draw(self, surf: pygame.Surface) -> None:
        if not self.alive:
            return
        cx, cy = int(self.pos.x), int(self.pos.y)
        pulse = 1 + abs(math.sin(self._phase)) * 0.4

        if self.weapon_type == self.TYPE_PLASMA:
            glow_circle(surf, self.color, (cx, cy), int(10 * pulse), 40)
            pygame.draw.circle(surf, self.color, (cx, cy), 4)

        elif self.weapon_type == self.TYPE_SPREAD:
            glow_circle(surf, self.color, (cx, cy), 8, 35)
            pygame.draw.circle(surf, self.color, (cx, cy), 3)

        elif self.weapon_type == self.TYPE_BOMB:
            t  = max(0, self.fuse / BOMB_FUSE)
            r  = int(6 + (1 - t) * 4)
            glow_circle(surf, self.color, (cx, cy), r + 6, 50)
            pygame.draw.circle(surf, self.color, (cx, cy), r)
            pygame.draw.circle(surf, WHITE,       (cx, cy), r, 1)


# ── Base Enemy ────────────────────────────────────────────────────────────────

class _BaseEnemy:
    def __init__(self, x: float, y: float, hp: int) -> None:
        self.pos        = pygame.Vector2(x, y)
        self.radius     = 13
        self.hp         = hp
        self.max_hp     = hp
        self.stunned    = False
        self.stun_timer = 0.0
        self._phase     = random.uniform(0, math.tau)
        self._glitch    = [0, 0]
        self.score_val  = 35

    def take_damage(self, dmg: int) -> bool:
        self.hp -= dmg
        return self.hp <= 0

    def stun(self) -> None:
        self.stunned    = True
        self.stun_timer = 2.5

    def _tick_stun(self, dt: float) -> bool:
        self._phase += dt * 4
        if random.random() < 0.04:
            self._glitch = [random.randint(-3, 3), random.randint(-3, 3)]
        else:
            self._glitch = [0, 0]
        if self.stunned:
            self.stun_timer -= dt
            if self.stun_timer <= 0:
                self.stunned = False
            return True
        return False

    def update(self, dt: float, player_pos: pygame.Vector2) -> None:
        self._tick_stun(dt)

    def draw(self, surf: pygame.Surface) -> None:
        pass

    def _draw_hp_bar(self, surf: pygame.Surface, cx: int, cy: int, r: int) -> None:
        if self.hp >= self.max_hp:
            return
        bw = r * 2 + 4
        bh = 3
        bx = cx - bw // 2
        by = cy - r - 10
        pygame.draw.rect(surf, (40, 10, 10), (bx, by, bw, bh))
        fill = int(bw * self.hp / self.max_hp)
        if fill > 0:
            pygame.draw.rect(surf, ENEMY_COL, (bx, by, fill, bh))


# ── Standard Enemy ────────────────────────────────────────────────────────────

class Enemy(_BaseEnemy):
    def __init__(self, x: float, y: float) -> None:
        super().__init__(x, y, hp=2)
        self.speed    = random.uniform(ENEMY_SPEED_MIN, ENEMY_SPEED_MAX)
        self.radius   = ENEMY_RADIUS
        self._wander  = pygame.Vector2(random.uniform(-1, 1),
                                       random.uniform(-1, 1)).normalize()
        self._wander_cd = 0.0
        self.score_val  = 35

    def update(self, dt: float, player_pos: pygame.Vector2) -> None:
        if self._tick_stun(dt):
            return
        dist = (player_pos - self.pos).length()
        if dist < ENEMY_CHASE_DIST:
            self.pos += (player_pos - self.pos).normalize() * self.speed * 1.6
        else:
            self._wander_cd -= dt
            if self._wander_cd <= 0:
                self._wander_cd = random.uniform(1.0, 2.5)
                self._wander = pygame.Vector2(
                    random.uniform(-1, 1), random.uniform(-1, 1)).normalize()
            self.pos += self._wander * self.speed
        self.pos.x = max(self.radius, min(W - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(H - self.radius, self.pos.y))

    def draw(self, surf: pygame.Surface) -> None:
        col = (80, 80, 100) if self.stunned else ENEMY_COL
        cx  = int(self.pos[0]) + self._glitch[0]
        cy  = int(self.pos.y) + self._glitch[1]
        r   = self.radius
        if not self.stunned:
            gr = r + int(abs(math.sin(self._phase)) * 5)
            glow_circle(surf, ENEMY_COL, (cx, cy), gr, 30)
        pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, WHITE, pts, 1)
        self._draw_hp_bar(surf, cx, cy, r)


# ── Hunter Enemy ──────────────────────────────────────────────────────────────

class Hunter(_BaseEnemy):
    """Always chasing. Fast, small, aggressive."""
    def __init__(self, x: float, y: float) -> None:
        super().__init__(x, y, hp=2)
        self.speed      = HUNTER_SPEED + random.uniform(-0.2, 0.4)
        self.radius     = HUNTER_RADIUS
        self.score_val  = 55
        self._face_angle = -math.pi / 2  # radians, starts pointing up

    def update(self, dt: float, player_pos: pygame.Vector2) -> None:
        if self._tick_stun(dt):
            return
        direction = player_pos - self.pos
        if direction.length() > 0:
            self._face_angle = math.atan2(direction.y, direction.x)
            self.pos += direction.normalize() * self.speed * 1.8
        self.pos.x = max(self.radius, min(W - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(H - self.radius, self.pos.y))

    def draw(self, surf: pygame.Surface) -> None:
        col = (80, 80, 100) if self.stunned else HUNTER_COL
        cx  = int(self.pos[0]) + self._glitch[0]
        cy  = int(self.pos[1]) + self._glitch[1]
        r   = self.radius
        if not self.stunned:
            glow_circle(surf, HUNTER_COL, (cx, cy), r + 8, 35)
        # Triangle tip points toward player using actual facing angle
        tip_angle = self._face_angle
        pts = rotate_points(
            [(cx + r, cy),
             (cx - r + 3, cy - r + 3),
             (cx - r + 3, cy + r - 3)],
            tip_angle - 0, cx, cy)
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, WHITE, pts, 1)
        self._draw_hp_bar(surf, cx, cy, r)


# ── Swarm Enemy ───────────────────────────────────────────────────────────────

class SwarmNode(_BaseEnemy):
    """Weak, small, fast — always spawns in packs."""
    def __init__(self, x: float, y: float) -> None:
        super().__init__(x, y, hp=1)
        self.speed     = SWARM_SPEED + random.uniform(-0.3, 0.5)
        self.radius    = SWARM_RADIUS
        self.score_val = 20
        self._wander   = pygame.Vector2(
            random.uniform(-1, 1), random.uniform(-1, 1)).normalize()
        self._wander_cd= 0.0

    def update(self, dt: float, player_pos: pygame.Vector2) -> None:
        if self._tick_stun(dt):
            return
        dist = (player_pos - self.pos).length()
        if dist < 300:
            self.pos += (player_pos - self.pos).normalize() * self.speed * 1.9
        else:
            self._wander_cd -= dt
            if self._wander_cd <= 0:
                self._wander_cd = random.uniform(0.5, 1.5)
                self._wander = pygame.Vector2(
                    random.uniform(-1, 1), random.uniform(-1, 1)).normalize()
            self.pos += self._wander * self.speed
        self.pos.x = max(self.radius, min(W - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(H - self.radius, self.pos.y))

    def draw(self, surf: pygame.Surface) -> None:
        col = (80, 80, 100) if self.stunned else SWARM_COL
        cx  = int(self.pos.x) + self._glitch[0]
        cy  = int(self.pos.y) + self._glitch[1]
        r   = self.radius
        if not self.stunned:
            glow_circle(surf, SWARM_COL, (cx, cy), r + 6, 28)
        # Hexagon
        pts = [(cx + int(r * math.cos(math.tau * i / 6 + self._phase * 0.3)),
                cy + int(r * math.sin(math.tau * i / 6 + self._phase * 0.3)))
               for i in range(6)]
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, WHITE, pts, 1)


# ── Phantom Enemy ─────────────────────────────────────────────────────────────

class Phantom(_BaseEnemy):
    """Translucent. Passes through MehBlocks. Medium speed."""
    def __init__(self, x: float, y: float) -> None:
        super().__init__(x, y, hp=3)
        self.speed     = PHANTOM_SPEED + random.uniform(-0.2, 0.3)
        self.radius    = PHANTOM_RADIUS
        self.score_val = 60
        self._wander   = pygame.Vector2(
            random.uniform(-1, 1), random.uniform(-1, 1)).normalize()
        self._wander_cd= 0.0

    def update(self, dt: float, player_pos: pygame.Vector2) -> None:
        if self._tick_stun(dt):
            return
        dist = (player_pos - self.pos).length()
        if dist < 280:
            self.pos += (player_pos - self.pos).normalize() * self.speed * 1.5
        else:
            self._wander_cd -= dt
            if self._wander_cd <= 0:
                self._wander_cd = random.uniform(1.2, 2.8)
                self._wander = pygame.Vector2(
                    random.uniform(-1, 1), random.uniform(-1, 1)).normalize()
            self.pos += self._wander * self.speed
        self.pos.x = max(self.radius, min(W - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(H - self.radius, self.pos.y))

    def draw(self, surf: pygame.Surface) -> None:
        pulse_a = int(120 + 50 * abs(math.sin(self._phase * 0.7)))
        col     = (*PHANTOM_COL, pulse_a)
        cx  = int(self.pos.x) + self._glitch[0]
        cy  = int(self.pos.y) + self._glitch[1]
        r   = self.radius
        s   = pygame.Surface((r * 2 + 20, r * 2 + 20), pygame.SRCALPHA)
        # Octagon
        pts_local = [
            (r + 10 + int(r * math.cos(math.tau * i / 8)),
             r + 10 + int(r * math.sin(math.tau * i / 8)))
            for i in range(8)
        ]
        pygame.draw.polygon(s, col, pts_local)
        pygame.draw.polygon(s, (*WHITE, 100), pts_local, 1)
        surf.blit(s, (cx - r - 10, cy - r - 10))
        if not self.stunned:
            glow_circle(surf, PHANTOM_COL, (cx, cy), r + 10, 20)
        self._draw_hp_bar(surf, cx, cy, r)


# ── Boss — The Architect ───────────────────────────────────────────────────────

class Boss(_BaseEnemy):
    """
    The Architect. Phase 1: mirrors player X. Phase 2: mirrors both axes.
    Spawns Swarm Nodes and Hunters.
    """
    SPAWN_CD_P1 = 8.0
    SPAWN_CD_P2 = 5.0

    def __init__(self, x: float, y: float) -> None:
        super().__init__(x, y, hp=BOSS_HP)
        self.radius     = BOSS_RADIUS
        self.score_val  = 500
        self.phase      = 1
        self._spawn_cd  = self.SPAWN_CD_P1
        self._ring_angle= 0.0
        self.spawn_queue: list = []   # entities to spawn this tick

    @property
    def is_phase2(self) -> bool:
        return self.hp <= BOSS_PHASE2_HP

    def update(self, dt: float, player_pos: pygame.Vector2) -> None:
        self._tick_stun(dt)
        if self.stunned:
            return

        # Phase transition
        if self.is_phase2 and self.phase == 1:
            self.phase     = 2
            self._spawn_cd = self.SPAWN_CD_P2

        self._ring_angle += dt * (2.5 if self.is_phase2 else 1.5)

        # Mirror movement
        target_x = W - player_pos.x
        target_y = (H - player_pos.y) if self.is_phase2 else self.pos.y
        target   = pygame.Vector2(target_x, target_y)
        direction = target - self.pos
        speed = 2.0 if self.is_phase2 else 1.4
        if direction.length() > 2:
            self.pos += direction.normalize() * speed

        self.pos.x = max(self.radius + 20, min(W - self.radius - 20, self.pos.x))
        self.pos.y = max(self.radius + 20, min(H - self.radius - 20, self.pos.y))

        # Spawn enemies
        self._spawn_cd -= dt
        if self._spawn_cd <= 0:
            self._spawn_cd = self.SPAWN_CD_P2 if self.is_phase2 else self.SPAWN_CD_P1
            if self.is_phase2:
                self.spawn_queue.append(("hunter", self.pos.x, self.pos.y))
            else:
                for i in range(4):
                    angle = math.tau * i / 4
                    sx = self.pos.x + math.cos(angle) * 80
                    sy = self.pos.y + math.sin(angle) * 80
                    self.spawn_queue.append(("swarm", sx, sy))

    def draw(self, surf: pygame.Surface) -> None:
        cx = int(self.pos.x) + self._glitch[0]
        cy = int(self.pos.y) + self._glitch[1]
        r  = self.radius
        col = BOSS_COL

        # Outer rotating ring
        ring_pts = [
            (cx + int((r + 18) * math.cos(self._ring_angle + math.tau * i / 8)),
             cy + int((r + 18) * math.sin(self._ring_angle + math.tau * i / 8)))
            for i in range(8)
        ]
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        pygame.draw.polygon(s, (*col, 60), ring_pts, 2)
        surf.blit(s, (0, 0))

        # Multi-layer glow
        glow_circle_multi(surf, col, (cx, cy), r, 3)

        # Core body — large diamond
        pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, WHITE, pts, 2)

        # Inner cross detail
        inner = r // 2
        pygame.draw.line(surf, (*WHITE, 120), (cx - inner, cy), (cx + inner, cy), 1)
        pygame.draw.line(surf, (*WHITE, 120), (cx, cy - inner), (cx, cy + inner), 1)

        # Phase 2 indicator
        if self.is_phase2:
            s2 = pygame.Surface((W, H), pygame.SRCALPHA)
            pygame.draw.polygon(s2, (255, 60, 60, 40), pts)
            surf.blit(s2, (0, 0))
