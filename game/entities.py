"""
entities.py — MehBlock, Fragment, and all enemy types + Projectile.
Enemies: Standard, Hunter, Swarm, Phantom, Boss (The Architect)
"""
from __future__ import annotations
import math, random, colorsys
from functools import lru_cache
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
    BERSERKER_RADIUS, BERSERKER_HP, BERSERKER_SPEED, BERSERKER_RAGE_SPEED,
    BERSERKER_SCORE, BERSERKER_RAGE_HP_THRESH, BERSERKER_COL, BERSERKER_RAGE_COL,
    TELEPORTER_RADIUS, TELEPORTER_HP, TELEPORTER_BLINK_CD, TELEPORTER_BLINK_RANGE,
    TELEPORTER_VULN_TIME, TELEPORTER_SCORE, TELEPORTER_COL,
    SHIELD_DRONE_RADIUS, SHIELD_DRONE_HP, SHIELD_DRONE_ORBIT_R, SHIELD_DRONE_ORBIT_SPD,
    SHIELD_DRONE_SCORE, SHIELD_COL,
    SPLITTER_RADIUS, SPLITTER_HP, SPLITTER_SCORE, SPLITTER_SPEED, SPLITTER_COL,
    PRISM_HP, PRISM_RADIUS, PRISM_SCORE, PRISM_COL,
    ENEMY_BULLET_RADIUS, ENEMY_BULLET_COL,
    SNIPER_RADIUS, SNIPER_HP, SNIPER_SCORE, SNIPER_COL, SNIPER_KEEP_DIST, SNIPER_CD,
    SNIPER_TELEGRAPH, SNIPER_BULLET_SPEED,
)
from utils import helpers as _helpers
from utils.helpers import glow_circle, glow_circle_multi, rotate_points, _q, _qa


# ── Meh Block ─────────────────────────────────────────────────────────────────

class MehBlock:
    SIZE = 38
    _stripe: "pygame.Surface | None" = None      # shared, built once
    _labels: dict = {}                            # (font id, hacked) -> Surface

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
        if MehBlock._stripe is None:
            MehBlock._stripe = pygame.Surface((self.SIZE, 3), pygame.SRCALPHA)
            MehBlock._stripe.fill((*WHITE, 16))
        surf.blit(MehBlock._stripe, (r.x, self._stripe_y))
        pygame.draw.rect(surf, (*WHITE, 28), r, 1, border_radius=5)
        key = (id(font), self.hacked)
        label = MehBlock._labels.get(key)
        if label is None:
            label = font.render(">>" if self.hacked else "meh", True, (20, 20, 35))
            MehBlock._labels[key] = label
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

        # Piercing (PIERCE perk): how many extra enemies it may pass through
        self.pierce      = 0
        self.homing      = False      # HOMING BOLTS evolution
        self.hit_ids: set = set()

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
            self.pos += self.vel * (dt * 60.0)
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
        self._k         = 1.0   # dt*60, refreshed every update
        self.shield     = 0     # >0 while a Shield Drone protects this enemy
        self._dead      = False # set by Game on kill; lets stale spatial-hash entries be skipped
        self.spawn_grace = 0.0  # >0 right after spawning: harmless to touch (spawn-in telegraph)

    def take_damage(self, dmg: float) -> bool:
        if self.shield > 0:
            return False
        self.hp -= dmg
        return self.hp <= 0

    def stun(self) -> None:
        self.stunned    = True
        self.stun_timer = 2.5

    def _tick_stun(self, dt: float) -> bool:
        self._k = dt * 60.0
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
        if _helpers.LOD:
            return
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
        if 0.001 < dist < ENEMY_CHASE_DIST:
            self.pos += (player_pos - self.pos).normalize() * self.speed * 1.6 * self._k
        else:
            self._wander_cd -= dt
            if self._wander_cd <= 0:
                self._wander_cd = random.uniform(1.0, 2.5)
                self._wander = pygame.Vector2(
                    random.uniform(-1, 1), random.uniform(-1, 1)).normalize()
            self.pos += self._wander * self.speed * self._k
        self.pos.x = max(self.radius, min(W - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(H - self.radius, self.pos.y))

    def draw(self, surf: pygame.Surface) -> None:
        col = (80, 80, 100) if self.stunned else ENEMY_COL
        cx  = int(self.pos[0]) + self._glitch[0]
        cy  = int(self.pos[1]) + self._glitch[1]
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
            self.pos += direction.normalize() * self.speed * 1.8 * self._k
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
        if 0.001 < dist < 300:
            self.pos += (player_pos - self.pos).normalize() * self.speed * 1.9 * self._k
        else:
            self._wander_cd -= dt
            if self._wander_cd <= 0:
                self._wander_cd = random.uniform(0.5, 1.5)
                self._wander = pygame.Vector2(
                    random.uniform(-1, 1), random.uniform(-1, 1)).normalize()
            self.pos += self._wander * self.speed * self._k
        self.pos.x = max(self.radius, min(W - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(H - self.radius, self.pos.y))

    def draw(self, surf: pygame.Surface) -> None:
        col = (80, 80, 100) if self.stunned else SWARM_COL
        cx  = int(self.pos[0]) + self._glitch[0]
        cy  = int(self.pos[1]) + self._glitch[1]
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

@lru_cache(maxsize=64)
def _phantom_sprite(r: int, alpha: int) -> pygame.Surface:
    s = pygame.Surface((r * 2 + 20, r * 2 + 20), pygame.SRCALPHA)
    pts = [(r + 10 + int(r * math.cos(math.tau * i / 8)),
            r + 10 + int(r * math.sin(math.tau * i / 8))) for i in range(8)]
    pygame.draw.polygon(s, (*PHANTOM_COL, alpha), pts)
    pygame.draw.polygon(s, (*WHITE, 100), pts, 1)
    return s


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
        if 0.001 < dist < 280:
            self.pos += (player_pos - self.pos).normalize() * self.speed * 1.5 * self._k
        else:
            self._wander_cd -= dt
            if self._wander_cd <= 0:
                self._wander_cd = random.uniform(1.2, 2.8)
                self._wander = pygame.Vector2(
                    random.uniform(-1, 1), random.uniform(-1, 1)).normalize()
            self.pos += self._wander * self.speed * self._k
        self.pos.x = max(self.radius, min(W - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(H - self.radius, self.pos.y))

    def draw(self, surf: pygame.Surface) -> None:
        pulse_a = _qa(120 + 50 * abs(math.sin(self._phase * 0.7)))
        cx  = int(self.pos[0]) + self._glitch[0]
        cy  = int(self.pos[1]) + self._glitch[1]
        r   = self.radius
        surf.blit(_phantom_sprite(r, pulse_a), (cx - r - 10, cy - r - 10))
        if not self.stunned:
            glow_circle(surf, PHANTOM_COL, (cx, cy), r + 10, 20)
        self._draw_hp_bar(surf, cx, cy, r)


# ── Berserker ─────────────────────────────────────────────────────────────────

class Berserker(_BaseEnemy):
    """Slow tank. Below 50% HP it enrages and charges at full sprint."""
    def __init__(self, x: float, y: float) -> None:
        super().__init__(x, y, hp=BERSERKER_HP)
        self.radius    = BERSERKER_RADIUS
        self.score_val = BERSERKER_SCORE
        self.enraged   = False
        self.just_enraged = False      # consumed by Game for the rage effect

    def take_damage(self, dmg: float) -> bool:
        killed = super().take_damage(dmg)
        if (not killed and not self.enraged
                and self.hp / self.max_hp <= BERSERKER_RAGE_HP_THRESH):
            self.enraged = True
            self.just_enraged = True
        return killed

    def update(self, dt: float, player_pos: pygame.Vector2) -> None:
        if self._tick_stun(dt):
            return
        d    = player_pos - self.pos
        dist = d.length()
        if dist > 0.001:
            spd = BERSERKER_RAGE_SPEED if self.enraged else BERSERKER_SPEED * 1.4
            self.pos += d / dist * spd * self._k
        self.pos.x = max(self.radius, min(W - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(H - self.radius, self.pos.y))

    def draw(self, surf: pygame.Surface) -> None:
        base = BERSERKER_RAGE_COL if self.enraged else BERSERKER_COL
        col  = (80, 80, 100) if self.stunned else base
        cx   = int(self.pos[0]) + self._glitch[0]
        cy   = int(self.pos[1]) + self._glitch[1]
        r    = self.radius
        if not self.stunned:
            pulse = abs(math.sin(self._phase * (2.5 if self.enraged else 1.0)))
            glow_circle(surf, base, (cx, cy), r + 5 + int(pulse * (9 if self.enraged else 4)), 36)
        # Spiked star: alternating outer/inner points
        spin = self._phase * (0.9 if self.enraged else 0.25)
        pts = []
        for i in range(12):
            rad = r + 5 if i % 2 == 0 else r - 4
            a = spin + math.tau * i / 12
            pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, WHITE, pts, 1)
        self._draw_hp_bar(surf, cx, cy, r + 5)


# ── Teleporter ────────────────────────────────────────────────────────────────

class Teleporter(_BaseEnemy):
    """Blinks around the player. Only vulnerable right after a blink — or while
    stunned, so the HACK is the counter."""
    def __init__(self, x: float, y: float) -> None:
        super().__init__(x, y, hp=TELEPORTER_HP)
        self.radius      = TELEPORTER_RADIUS
        self.score_val   = TELEPORTER_SCORE
        self._blink_cd   = random.uniform(1.0, TELEPORTER_BLINK_CD)
        self._vuln       = 0.0
        self.blink_event = False         # consumed by Game for the blink effect
        self.blink_from  = pygame.Vector2(x, y)

    @property
    def vulnerable(self) -> bool:
        return self._vuln > 0 or self.stunned

    def take_damage(self, dmg: float) -> bool:
        if not self.vulnerable:
            return False
        return super().take_damage(dmg)

    def update(self, dt: float, player_pos: pygame.Vector2) -> None:
        if self._tick_stun(dt):
            return
        self._vuln -= dt
        self._blink_cd -= dt
        d = player_pos - self.pos
        if d.length() > 0.001:                       # slow drift between blinks
            self.pos += d.normalize() * 1.0 * self._k
        if self._blink_cd <= 0:
            self._blink_cd  = TELEPORTER_BLINK_CD
            self.blink_from = pygame.Vector2(self.pos)
            ang  = random.uniform(0, math.tau)
            dist = random.uniform(TELEPORTER_BLINK_RANGE * 0.55, TELEPORTER_BLINK_RANGE)
            self.pos = pygame.Vector2(player_pos.x + math.cos(ang) * dist,
                                      player_pos.y + math.sin(ang) * dist)
            self._vuln       = TELEPORTER_VULN_TIME
            self.blink_event = True
        self.pos.x = max(self.radius, min(W - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(H - self.radius, self.pos.y))

    def draw(self, surf: pygame.Surface) -> None:
        cx = int(self.pos[0]) + self._glitch[0]
        cy = int(self.pos[1]) + self._glitch[1]
        r  = self.radius
        if self.stunned:
            col = (80, 80, 100)
        else:
            col = TELEPORTER_COL
        if self.vulnerable:
            glow_circle(surf, (255, 255, 255), (cx, cy), r + 4, 40)   # "hit me now"
        elif self._blink_cd < 0.45:                                   # telegraph the blink
            if int(self._blink_cd * 24) % 2 == 0:
                glow_circle(surf, col, (cx, cy), r + 10, 45)
        else:
            glow_circle(surf, col, (cx, cy), r + 3, 22)
        # Hollow when invulnerable, solid when vulnerable
        pts = [(cx, cy - r - 2), (cx + r, cy), (cx, cy + r + 2), (cx - r, cy)]
        if self.vulnerable:
            pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, col if not self.vulnerable else WHITE, pts, 2)
        self._draw_hp_bar(surf, cx, cy, r)


# ── Shield Drone ──────────────────────────────────────────────────────────────

class ShieldDrone(_BaseEnemy):
    """Orbits another enemy and makes it immune. Kill the drone first."""
    def __init__(self, x: float, y: float) -> None:
        super().__init__(x, y, hp=SHIELD_DRONE_HP)
        self.radius    = SHIELD_DRONE_RADIUS
        self.score_val = SHIELD_DRONE_SCORE
        self.host      = None            # assigned by Game each frame
        self._orbit    = random.uniform(0, math.tau)

    def update(self, dt: float, player_pos: pygame.Vector2) -> None:
        if self._tick_stun(dt):
            return
        if self.host is not None:
            self._orbit += SHIELD_DRONE_ORBIT_SPD * dt
            target = self.host.pos + pygame.Vector2(
                math.cos(self._orbit), math.sin(self._orbit)) * (SHIELD_DRONE_ORBIT_R + self.host.radius * 0.4)
            self.pos += (target - self.pos) * min(1.0, 0.18 * self._k)
        else:                                  # orphaned: harass the player
            d = player_pos - self.pos
            if d.length() > 0.001:
                self.pos += d.normalize() * 2.0 * self._k
        self.pos.x = max(self.radius, min(W - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(H - self.radius, self.pos.y))

    def draw(self, surf: pygame.Surface) -> None:
        col = (80, 80, 100) if self.stunned else SHIELD_COL
        cx  = int(self.pos[0]) + self._glitch[0]
        cy  = int(self.pos[1]) + self._glitch[1]
        r   = self.radius
        if self.host is not None and not self.stunned:      # tether to the protected enemy
            pygame.draw.line(surf, (*SHIELD_COL, 70), (cx, cy),
                             (int(self.host.pos.x), int(self.host.pos.y)), 1)
        if not self.stunned:
            glow_circle(surf, SHIELD_COL, (cx, cy), r + 5, 32)
        pts = [(cx + int(r * math.cos(self._phase + math.tau * i / 3)),
                cy + int(r * math.sin(self._phase + math.tau * i / 3))) for i in range(3)]
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, WHITE, pts, 1)


# ── Splitter ──────────────────────────────────────────────────────────────────

class Splitter(_BaseEnemy):
    """Chases the player; bursts into two Swarm Nodes when killed (see Game)."""
    def __init__(self, x: float, y: float) -> None:
        super().__init__(x, y, hp=SPLITTER_HP)
        self.radius    = SPLITTER_RADIUS
        self.score_val = SPLITTER_SCORE
        self.speed     = SPLITTER_SPEED

    def update(self, dt: float, player_pos: pygame.Vector2) -> None:
        if self._tick_stun(dt):
            return
        d    = player_pos - self.pos
        dist = d.length()
        if dist > 0.001:
            self.pos += d / dist * self.speed * 1.3 * self._k
        self.pos.x = max(self.radius, min(W - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(H - self.radius, self.pos.y))

    def draw(self, surf: pygame.Surface) -> None:
        col = (80, 80, 100) if self.stunned else SPLITTER_COL
        cx  = int(self.pos[0]) + self._glitch[0]
        cy  = int(self.pos[1]) + self._glitch[1]
        r   = self.radius
        if not self.stunned:
            glow_circle(surf, SPLITTER_COL, (cx, cy), r + 6 + int(abs(math.sin(self._phase)) * 3), 30)
        pts = [(cx + int(r * math.cos(-math.pi / 2 + math.tau * i / 5)),
                cy + int(r * math.sin(-math.pi / 2 + math.tau * i / 5))) for i in range(5)]
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, WHITE, pts, 1)
        # the seam it will split along
        pygame.draw.line(surf, WHITE, (cx, cy - r + 3), (cx, cy + r - 3), 1)
        self._draw_hp_bar(surf, cx, cy, r)


# ── Sniper ────────────────────────────────────────────────────────────────────

class Sniper(_BaseEnemy):
    """Ranged enemy.  Keeps its distance, then telegraphs with a laser line for
    ~0.9 s (the aim locks for the last 0.25 s) and fires one fast bullet.
    Counters: dash through the shot, HACK (stun / scrub the bullet), or break line of fire."""
    def __init__(self, x: float, y: float) -> None:
        super().__init__(x, y, hp=SNIPER_HP)
        self.radius       = SNIPER_RADIUS
        self.score_val    = SNIPER_SCORE
        self.speed        = 1.6
        self._cd          = random.uniform(1.0, SNIPER_CD)
        self._aim_t       = 0.0                    # >0 while telegraphing
        self.aim          = pygame.Vector2(x, y)   # where the shot is going
        self.bullet_queue: list = []               # (x, y, vx, vy, colour, radius) consumed by Game
        self.just_aimed   = False                  # consumed by Game for the warning sound
        self._strafe      = random.choice((-1, 1))

    @property
    def aiming(self) -> bool:
        return self._aim_t > 0

    def stun(self) -> None:
        super().stun()
        self._aim_t = 0.0                          # a hacked sniper loses its shot
        self._cd    = SNIPER_CD

    def update(self, dt: float, player_pos: pygame.Vector2) -> None:
        if self._tick_stun(dt):
            return
        d    = player_pos - self.pos
        dist = d.length()
        if dist > 0.001 and not self.aiming:       # hold position while lining up the shot
            dirv = d / dist
            if dist < SNIPER_KEEP_DIST - 70:
                self.pos -= dirv * self.speed * 1.2 * self._k          # too close: back off
            elif dist > SNIPER_KEEP_DIST + 90:
                self.pos += dirv * self.speed * self._k                # too far: close in
            else:
                perp = pygame.Vector2(-dirv.y, dirv.x) * self._strafe
                self.pos += perp * self.speed * 0.6 * self._k          # circle-strafe
        if self.aiming:
            self._aim_t -= dt
            if self._aim_t > 0.25:                 # track the player, then lock for the last 0.25 s
                self.aim = pygame.Vector2(player_pos)
            if self._aim_t <= 0:
                v = self.aim - self.pos
                if v.length_squared() > 0:
                    v = v.normalize() * SNIPER_BULLET_SPEED
                    self.bullet_queue.append((self.pos.x, self.pos.y, v.x, v.y, SNIPER_COL, 5))
                self._cd = SNIPER_CD
        else:
            self._cd -= dt
            if self._cd <= 0:
                self._aim_t, self.aim, self.just_aimed = SNIPER_TELEGRAPH, pygame.Vector2(player_pos), True
        self.pos.x = max(self.radius, min(W - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(H - self.radius, self.pos.y))

    def draw(self, surf: pygame.Surface) -> None:
        col = (80, 80, 100) if self.stunned else SNIPER_COL
        cx  = int(self.pos[0]) + self._glitch[0]
        cy  = int(self.pos[1]) + self._glitch[1]
        r   = self.radius
        if self.aiming and not self.stunned:       # laser telegraph: thin -> bright as the shot nears
            t = 1.0 - max(0.0, self._aim_t) / SNIPER_TELEGRAPH
            a = int(40 + 200 * t * t)
            end = (int(self.aim.x), int(self.aim.y))
            pygame.draw.line(surf, (*SNIPER_COL, a), (cx, cy), end, 1 + (1 if self._aim_t < 0.25 else 0))
            glow_circle(surf, SNIPER_COL, (cx, cy), r + 6 + int(6 * t), 30 + int(60 * t))
        elif not self.stunned:
            glow_circle(surf, SNIPER_COL, (cx, cy), r + 4, 24)
        pts = [(cx, cy - r - 3), (cx + r, cy), (cx, cy + r + 3), (cx - r, cy)]
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, WHITE, pts, 1)
        pygame.draw.line(surf, WHITE, (cx - r - 4, cy), (cx + r + 4, cy), 1)     # crosshair
        pygame.draw.line(surf, WHITE, (cx, cy - r - 6), (cx, cy + r + 6), 1)
        self._draw_hp_bar(surf, cx, cy, r)


# ── Boss — The Architect ───────────────────────────────────────────────────────

@lru_cache(maxsize=8)
def _phase2_overlay(r: int) -> pygame.Surface:
    s = pygame.Surface((r * 2 + 1, r * 2 + 1), pygame.SRCALPHA)
    pts = [(r, 0), (r * 2, r), (r, r * 2), (0, r)]
    pygame.draw.polygon(s, (255, 60, 60, 40), pts)
    return s


class Boss(_BaseEnemy):
    """
    The Architect. Phase 1: mirrors player X. Phase 2: mirrors both axes.
    Spawns Swarm Nodes and Hunters.
    """
    SPAWN_CD_P1 = 8.0
    SPAWN_CD_P2 = 5.0
    name        = "THE ARCHITECT"
    bar_color   = BOSS_COL

    def __init__(self, x: float, y: float, hp: float = BOSS_HP) -> None:
        super().__init__(x, y, hp=hp)
        self._p2_hp     = max(1, int(hp) // 2)   # 15 -> 7, matching the old constant
        self.radius     = BOSS_RADIUS
        self.score_val  = 500
        self.phase      = 1
        self._spawn_cd  = self.SPAWN_CD_P1
        self._ring_angle= 0.0
        self.spawn_queue: list = []   # entities to spawn this tick

    @property
    def is_phase2(self) -> bool:
        return self.hp <= self._p2_hp

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
            self.pos += direction.normalize() * speed * self._k

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
        px, py = self.pos
        cx = int(px) + self._glitch[0]
        cy = int(py) + self._glitch[1]
        r  = self.radius
        col = BOSS_COL

        # Outer rotating ring
        ring_pts = [
            (cx + int((r + 18) * math.cos(self._ring_angle + math.tau * i / 8)),
             cy + int((r + 18) * math.sin(self._ring_angle + math.tau * i / 8)))
            for i in range(8)
        ]
        pygame.draw.polygon(surf, (*col, 60), ring_pts, 2)

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
            surf.blit(_phase2_overlay(r), (cx - r, cy - r))


# ── Enemy bullet ──────────────────────────────────────────────────────────────

class EnemyBullet:
    """Hostile projectile.  Velocity is in px/second.  Dash i-frames dodge it,
    Chaos Mode destroys it on contact, and HACK clears bullets in range."""
    __slots__ = ("pos", "vel", "radius", "color", "life", "alive")

    def __init__(self, x: float, y: float, vx: float, vy: float,
                 color: tuple = ENEMY_BULLET_COL, radius: int = ENEMY_BULLET_RADIUS) -> None:
        self.pos    = pygame.Vector2(x, y)
        self.vel    = pygame.Vector2(vx, vy)
        self.radius = radius
        self.color  = color
        self.life   = 8.0
        self.alive  = True

    def update(self, dt: float) -> None:
        self.pos  += self.vel * dt
        self.life -= dt
        if self.life <= 0 or not (-30 < self.pos.x < W + 30 and -30 < self.pos.y < H + 30):
            self.alive = False

    def draw(self, surf: pygame.Surface) -> None:
        x, y = int(self.pos.x), int(self.pos.y)
        glow_circle(surf, self.color, (x, y), self.radius + 3, 38)
        pygame.draw.circle(surf, self.color, (x, y), self.radius)
        pygame.draw.circle(surf, WHITE, (x, y), max(1, self.radius - 3))


# ── Boss — The Prism ──────────────────────────────────────────────────────────

_PRISM_PALETTE = [tuple(int(c * 255) for c in colorsys.hsv_to_rgb(i / 6, 0.62, 1.0))
                  for i in range(6)]
# Each attack telegraphs in its own colour for 0.65 s before it fires.
_ATTACK_COL = {"spiral": (170, 100, 255), "ring": (80, 230, 255),
               "aimed": (255, 70, 70),    "bloom": (120, 255, 150)}


class Prism(_BaseEnemy):
    """
    The Prism — a bullet-hell boss.  It drifts across the top of the arena and
    cycles through telegraphed attacks:

      SPIRAL  rotating arms of bullets        RING   a ring with one gap to find
      AIMED   fan of shots at you             BLOOM  (phase 2) slow dense rings

    Below half HP (phase 2) it moves wider, fires faster, adds BLOOM and calls
    in Swarm Nodes once.  Dash i-frames dodge bullets, Chaos Mode erases them,
    HACK clears the ones near you.  Stunning it (HACK range / Second Wind) pauses
    its attacks.
    """
    name      = "THE PRISM"
    bar_color = PRISM_COL
    ATTACKS_P1 = ("spiral", "ring", "aimed")
    ATTACKS_P2 = ("spiral", "ring", "aimed", "bloom")

    def __init__(self, x: float, y: float, hp: float = PRISM_HP) -> None:
        super().__init__(x, y, hp=hp)
        self._p2_hp       = max(1, int(hp) // 2)
        self.radius       = PRISM_RADIUS
        self.score_val    = PRISM_SCORE
        self.phase        = 1
        self.just_phase2  = False                 # consumed by Game for the transition effect
        self.spawn_queue: list  = []
        self.bullet_queue: list = []              # (x, y, vx, vy) in px/s, consumed by Game
        self._t           = 0.0
        self._state       = "rest"                # rest -> warn -> fire -> rest ...
        self._state_t     = 1.5
        self._attack      = "spiral"
        self._attack_i    = 0
        self._shot_cd     = 0.0
        self._spin        = 0.0
        self._ring_cd     = 0.0
        self._rings_left  = 0

    @property
    def is_phase2(self) -> bool:
        return self.hp <= self._p2_hp

    # ── behaviour ────────────────────────────────────────────────────────────

    def update(self, dt: float, player_pos: pygame.Vector2) -> None:
        self._tick_stun(dt)
        if self.stunned:
            return
        self._t += dt
        if self.is_phase2 and self.phase == 1:
            self.phase       = 2
            self.just_phase2 = True
            self._state, self._state_t = "rest", 1.2
            for i in range(3):                    # call in reinforcements once
                a = math.tau * i / 3
                self.spawn_queue.append(("swarm", self.pos.x + math.cos(a) * 70,
                                         self.pos.y + math.sin(a) * 70))

        p2 = self.phase == 2
        tx = W / 2 + math.cos(self._t * (0.7 if p2 else 0.45)) * (430 if p2 else 380)
        ty = 150 + math.sin(self._t * 0.9) * (90 if p2 else 40)
        self.pos += (pygame.Vector2(tx, ty) - self.pos) * min(1.0, 0.06 * self._k)

        self._state_t -= dt
        if self._state == "rest":
            if self._state_t <= 0:
                attacks      = self.ATTACKS_P2 if p2 else self.ATTACKS_P1
                self._attack = attacks[self._attack_i % len(attacks)]
                self._attack_i += 1
                self._state, self._state_t = "warn", 0.65
        elif self._state == "warn":
            if self._state_t <= 0:
                self._state = "fire"
                self._begin_fire(player_pos)
        else:
            self._fire(dt, player_pos)
            if self._state_t <= 0:
                self._state, self._state_t = "rest", (0.6 if p2 else 0.9)

    def _emit(self, angle: float, speed: float) -> None:
        self.bullet_queue.append((self.pos.x, self.pos.y,
                                  math.cos(angle) * speed, math.sin(angle) * speed))

    def _begin_fire(self, player_pos: pygame.Vector2) -> None:
        p2 = self.phase == 2
        self._shot_cd = 0.0
        if self._attack == "spiral":
            self._state_t = 3.6 if p2 else 3.2
        elif self._attack == "ring":
            self._rings_left = 2 if p2 else 1
            self._ring_cd    = 0.0
            self._state_t    = 0.1 + (0.55 if p2 else 0.0)
        elif self._attack == "aimed":
            self._state_t = 1.6 if p2 else 1.3
        else:                                      # bloom
            self._state_t = 2.0

    def _fire(self, dt: float, player_pos: pygame.Vector2) -> None:
        p2 = self.phase == 2
        if self._attack == "spiral":
            interval, arms, speed = (0.055, 4, 215) if p2 else (0.085, 3, 190)
            self._shot_cd -= dt
            while self._shot_cd <= 0:
                self._shot_cd += interval
                self._spin   += 0.31
                for k in range(arms):
                    self._emit(self._spin + math.tau * k / arms, speed)
        elif self._attack == "ring":
            self._ring_cd -= dt
            if self._rings_left > 0 and self._ring_cd <= 0:
                self._rings_left -= 1
                self._ring_cd     = 0.55
                n, gap_w, speed   = (34, 0.36, 185) if p2 else (26, 0.42, 160)
                gap = random.uniform(0, math.tau)
                for i in range(n):
                    a = math.tau * i / n
                    d = abs((a - gap + math.pi) % math.tau - math.pi)
                    if d > gap_w:                  # leave a gap to slip through
                        self._emit(a, speed)
        elif self._attack == "aimed":
            interval, shots, spread = (0.34, 5, 0.22) if p2 else (0.42, 3, 0.20)
            self._shot_cd -= dt
            while self._shot_cd <= 0:
                self._shot_cd += interval
                base = math.atan2(player_pos.y - self.pos.y, player_pos.x - self.pos.x)
                for k in range(shots):
                    self._emit(base + (k - (shots - 1) / 2) * spread, 270)
        else:                                      # bloom
            self._shot_cd -= dt
            while self._shot_cd <= 0:
                self._shot_cd += 0.5
                self._spin    += 0.2
                for k in range(14):
                    self._emit(self._spin + math.tau * k / 14, 120)

    # ── drawing ──────────────────────────────────────────────────────────────

    def draw(self, surf: pygame.Surface) -> None:
        cx, cy = int(self.pos[0]), int(self.pos[1])
        r      = self.radius
        col    = (80, 80, 100) if self.stunned else PRISM_COL
        if not self.stunned:
            glow_circle_multi(surf, col, (cx, cy), r, 3)
            if self._state == "warn":              # telegraph: attack-coloured halo
                wc = _ATTACK_COL[self._attack]
                glow_circle(surf, wc, (cx, cy), r + 16 + int(abs(math.sin(self._t * 14)) * 8), 55)
        rot = self._t * 0.6
        pts = [(cx + r * math.cos(rot + math.tau * i / 6),
                cy + r * math.sin(rot + math.tau * i / 6)) for i in range(6)]
        shift = int(self._t * 2)
        for i in range(6):                         # rainbow facets
            tri = [(cx, cy), pts[i], pts[(i + 1) % 6]]
            pygame.draw.polygon(surf, (70, 70, 90) if self.stunned
                                else _PRISM_PALETTE[(i + shift) % 6], tri)
        pygame.draw.polygon(surf, WHITE, pts, 2)
        pygame.draw.circle(surf, WHITE, (cx, cy), 6)
