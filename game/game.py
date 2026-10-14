from __future__ import annotations
import math
import random
import pygame

from game.constants import (
    W, H, FPS,
    PLAYER_COL, CHAOS_COL, MEH_HACKED, MEH_COL, FRAG_COL, ENEMY_COL, WHITE,
    PLAYER_INV_DURATION,
    HACK_RANGE_NORMAL, HACK_RANGE_CHAOS,
    MEH_ENERGY_REWARD, MEH_SCORE_REWARD, MEH_CHAOS_ENERGY, MEH_CHAOS_SCORE,
    FRAG_ENERGY_REWARD, FRAG_SCORE_REWARD, FRAG_POPUP_DURATION,
    ENEMY_SCORE_REWARD, BOSS_SCORE_REWARD,
    MEH_SPAWN_MIN, MEH_SPAWN_BATCH, FRAG_SPAWN_MIN, FRAG_SPAWN_BATCH,
    BOMB_RADIUS, BOMB_DAMAGE,
    CHAIN_DAMAGE, BEAM_DAMAGE_PS, BOSS_HP,
    FRAGMENTS,
    WEAPON_COLORS,
    STREAK_RESET_TIME, STREAK_THRESHOLDS, STREAK_MULTIPLIERS,
    DEATH_SLOW_FACTOR, DEATH_SLOW_DURATION,
    SHIELD_COL, BERSERKER_RAGE_COL, TELEPORTER_COL, SPLITTER_COL,
)
from game.player       import Player
from game.entities     import (MehBlock, Fragment, Enemy, Hunter, SwarmNode, Phantom, Boss,
                               Projectile, Berserker, Teleporter, ShieldDrone, Splitter)
from game.perks        import PERKS, roll_choices
from utils.helpers     import fade_ring
from game.particles    import Particle, DashTrail, Ring, TextPopup
from game.renderer     import Renderer
from game.audio        import SoundManager
from game.ui           import UI
from game.wave_manager import WaveManager

_PARTICLE_CAP = 200


class Game:
    """
    Core gameplay logic.  Owns all entities, physics, and rendering.
    Used by PlayState — does NOT own the main loop or the display surface.
    """

    def __init__(self, manager=None) -> None:
        self.manager  = manager
        self.clock    = pygame.time.Clock()
        self.audio    = SoundManager()
        self.ui       = UI()
        self.renderer = Renderer()
        self.wave_mgr = WaveManager()

        # Logical mouse position (set by PlayState each frame)
        self._logical_mouse = (W // 2, H // 2)

        # Flag so PlayState pushes GameOverState only once
        self._gameover_handled = False

        # Reused every frame instead of allocating a 1280x720 surface per draw
        self._world = pygame.Surface((W, H), pygame.SRCALPHA)
        self._beam_sfx_cd = 0.0

        # Track dt for wave banner (since we don't tick our own clock)
        self._last_dt = 0.016

        self._reset()

    # ── Spawn helpers ─────────────────────────────────────────────────────────

    def _spawn_mehs(self, n: int) -> None:
        for _ in range(n):
            for _ in range(30):
                x = random.randint(60, W - 100)
                y = random.randint(60, H - 100)
                if pygame.Vector2(x + 19, y + 19).distance_to(self.player.pos) > 90:
                    self.meh_blocks.append(MehBlock(x, y))
                    break

    def _spawn_frags(self, n: int) -> None:
        used = {f.text for f in self.fragments}
        pool = [t for t in FRAGMENTS if t not in used]
        random.shuffle(pool)
        for i in range(min(n, len(pool))):
            x = random.randint(80, W - 80)
            y = random.randint(80, H - 80)
            self.fragments.append(Fragment(x, y, pool[i]))

    def _spawn_entity(self, etype: str, x: float | None = None, y: float | None = None) -> None:
        if x is None or y is None:
            for _ in range(50):
                x = float(random.randint(60, W - 60))
                y = float(random.randint(60, H - 60))
                if pygame.Vector2(x, y).distance_to(self.player.pos) > 180:
                    break
        # Ensure x and y are floats (type-checkers may still consider them Optional)
        if x is None:
            x = float(random.randint(60, W - 60))
        if y is None:
            y = float(random.randint(60, H - 60))
        if etype == "standard":
            self.enemies.append(Enemy(x, y))
        elif etype == "hunter":
            self.enemies.append(Hunter(x, y))
        elif etype == "swarm":
            self.enemies.append(SwarmNode(x, y))
        elif etype == "phantom":
            self.enemies.append(Phantom(x, y))
        elif etype == "berserker":
            self.enemies.append(Berserker(x, y))
        elif etype == "teleporter":
            self.enemies.append(Teleporter(x, y))
        elif etype == "shield_drone":
            self.enemies.append(ShieldDrone(x, y))
        elif etype == "splitter":
            self.enemies.append(Splitter(x, y))
        elif etype == "boss":
            tier = max(0, (self.wave_mgr.wave - 5) // 5)
            self.boss = Boss(W // 2, 80, hp=BOSS_HP + 8 * tier)
            self.audio.boss_spawn()

    # ── State ─────────────────────────────────────────────────────────────────

    def _reset(self) -> None:
        self.perks       : dict             = {}
        self.player      = Player(W // 2, H // 2)
        self.player.perks = self.perks
        self.meh_blocks  : list[MehBlock]   = []
        self.fragments   : list[Fragment]   = []
        self.enemies     : list             = []
        self.projectiles : list[Projectile] = []
        self.particles   : list             = []
        self.boss        : Boss | None      = None
        self.hp          = 3
        self.score       = 0
        self.shake       = 0
        self.frag_text   = ""
        self.frag_timer  = 0.0
        self.game_over   = False
        self._gameover_handled = False
        self.run_time    = 0.0
        # Kill streak
        self.streak       = 0
        self.streak_timer = 0.0
        # Death slow-motion
        self.dying        = False
        self._death_timer = 0.0
        # Perks
        self.perk_pending = False
        self.perk_choices : list = []
        self._second_wind_used = False
        self._volatile_depth   = 0
        self.wave_mgr    = WaveManager()
        self.wave_mgr.start()
        self._spawn_mehs(22)
        self._spawn_frags(5)

    # ── Particle helpers ──────────────────────────────────────────────────────

    def _burst(self, x: float, y: float, color: tuple,
               n: int = 12, spd: tuple = (1, 5)) -> None:
        space = _PARTICLE_CAP - len(self.particles)
        for _ in range(min(n, space)):
            self.particles.append(Particle(x, y, color, spd))

    def _ring(self, x: float, y: float, color: tuple,
              start_r: int = 10, end_r: int = 90, dur: float = 0.45) -> None:
        self.particles.append(Ring(x, y, color, start_r, end_r, dur))

    def _score_popup(self, x: float, y: float, val: int, color: tuple) -> None:
        if len(self.particles) < _PARTICLE_CAP:
            self.particles.append(TextPopup(x, y - 20, f"+{val}", color, self.ui.font_s))

    # ── Hack ──────────────────────────────────────────────────────────────────

    def _do_hack(self) -> None:
        if not self.player.can_hack:
            return
        rng = HACK_RANGE_CHAOS if self.player.chaos_mode else HACK_RANGE_NORMAL
        hit = False
        for b in self.meh_blocks:
            if b.center.distance_to(self.player.pos) < rng:
                b.hack()
                self._burst(b.rect.centerx, b.rect.centery, MEH_HACKED, 8)
                self.audio.meh_hack()
                hit = True
        for e in self.enemies:
            if e.pos.distance_to(self.player.pos) < rng:
                e.stun()
                self._burst(int(e.pos.x), int(e.pos.y), (80, 220, 120), 14)
                self.audio.enemy_stun()
                hit = True
        if hit:
            self.player.trigger_hack()
            self.shake = 5
            self.audio.hack()

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt: float) -> None:
        real_dt = dt
        if self.dying:                                   # death slow-motion
            self._death_timer -= real_dt
            dt = real_dt * DEATH_SLOW_FACTOR
            if self._death_timer <= 0 and not self.game_over:
                self.game_over = True
                self.audio.game_over()
        self.run_time    += dt
        self._last_dt     = real_dt
        keys              = pygame.key.get_pressed()
        mouse_pos         = self._logical_mouse
        mouse_buttons     = ((False, False, False) if self.dying
                             else pygame.mouse.get_pressed())
        p                 = self.player

        p.update(keys, dt, mouse_pos, mouse_buttons, self.enemies)

        if p._chaos_just_ended:
            self.audio.chaos_end()

        self.audio.update_drone(p.energy / p.max_energy, p.chaos_mode)

        if p.new_projectiles:
            self.projectiles.extend(p.new_projectiles)
            wi = p.weapon_index
            if wi == 0:   self.audio.plasma_shoot()
            elif wi == 1: self.audio.spread_shoot()
            elif wi == 4: self.audio.bomb_launch()
            p.new_projectiles.clear()

        if p.is_dashing:
            col = CHAOS_COL if p.chaos_mode else PLAYER_COL
            if len(self.particles) < _PARTICLE_CAP:
                self.particles.append(DashTrail(p.pos.x, p.pos.y, col, p.radius))

        # Kill-streak decay
        if self.streak > 0:
            self.streak_timer -= dt
            if self.streak_timer <= 0:
                self.streak = 0

        for proj in self.projectiles:
            proj.update(dt)

        dead_projs = set()
        for i, proj in enumerate(self.projectiles):
            if not proj.alive:
                if proj.weapon_type == Projectile.TYPE_BOMB and proj.detonated:
                    self._handle_bomb_explosion(proj)
                dead_projs.add(i)
                continue
            for e in self.enemies[:]:
                if id(e) in proj.hit_ids:
                    continue
                if e.pos.distance_to(proj.pos) < e.radius + proj.radius:
                    hp_before = e.hp
                    killed    = e.take_damage(proj.damage)
                    dealt     = killed or e.hp != hp_before
                    if dealt:
                        self._burst(int(proj.pos.x), int(proj.pos.y), proj.color, 6, (1, 4))
                    else:                                    # shielded / invulnerable: deflected
                        self._burst(int(proj.pos.x), int(proj.pos.y), (200, 210, 255), 4, (2, 5))
                    if killed:
                        self._on_enemy_killed(e)
                    if dealt and proj.pierce > 0:            # PIERCE: keep flying
                        proj.pierce -= 1
                        proj.hit_ids.add(id(e))
                    else:
                        proj.alive = False
                        dead_projs.add(i)
                    break
            if self.boss and i not in dead_projs:
                # Use vector math directly to avoid attribute access issues
                if (self.boss.pos - proj.pos).length() < self.boss.radius + proj.radius:
                    killed = self.boss.take_damage(proj.damage)
                    self._burst(int(proj.pos.x), int(proj.pos.y), proj.color, 8, (1, 5))
                    self.audio.boss_hit()
                    if killed:
                        self._on_boss_killed()
                    proj.alive = False
                    dead_projs.add(i)

        if p.chain_targets:
            prev_pos = pygame.Vector2(p.pos)
            for target in p.chain_targets:
                killed = target.take_damage(CHAIN_DAMAGE)
                mid    = (prev_pos + target.pos) / 2
                self._burst(int(mid.x), int(mid.y), (100, 255, 180), 5, (2, 6))
                if killed:
                    self._on_enemy_killed(target)
                prev_pos = pygame.Vector2(target.pos)
            self.audio.chain_zap()
            p.chain_targets.clear()

        if self._beam_sfx_cd > 0:
            self._beam_sfx_cd -= dt
        if p.beam_active:
            self._apply_beam(dt)

        self.projectiles = [proj for i, proj in enumerate(self.projectiles)
                            if i not in dead_projs]

        for b in self.meh_blocks: b.update(dt)
        for f in self.fragments:  f.update(dt)
        self._update_shields()
        for e in self.enemies:    e.update(dt, p.pos)
        self._enemy_effects()

        if self.boss:
            self.boss.update(dt, p.pos)
            for item in self.boss.spawn_queue:
                self._spawn_entity(item[0], item[1], item[2])
            self.boss.spawn_queue.clear()

        self.particles = [pt for pt in self.particles if pt.alive]
        if len(self.particles) > _PARTICLE_CAP:
            self.particles = self.particles[-_PARTICLE_CAP:]
        for pt in self.particles:
            pt.update(dt)

        if self.frag_timer > 0: self.frag_timer -= dt
        if self.shake      > 0: self.shake      = max(0.0, self.shake - 60.0 * dt)

        self.renderer.update(dt, p.chaos_mode)
        self._handle_collisions()
        self._replenish()

        # Wave system
        self.wave_mgr.update(dt, len(self.enemies), self.boss is not None)
        for spawn in self.wave_mgr.spawn_queue:
            self._spawn_entity(spawn[0])
        if self.wave_mgr.wave_just_started:
            self.ui.show_wave_banner(self.wave_mgr.wave, self.wave_mgr.is_boss_wave)
            if self.wave_mgr.is_boss_wave:
                self.audio.boss_spawn()
            else:
                self.audio.wave_start()
        if self.wave_mgr.wave_just_cleared and not self.dying:
            choices = roll_choices(self.perks)
            if choices:
                self.perk_choices = choices
                self.perk_pending = True

    def _beam_hits(self, ent, cx: float, cy: float) -> bool:
        """Perpendicular-distance test against the beam ray (500px long)."""
        ex = ent.pos.x - self.player.pos.x
        ey = ent.pos.y - self.player.pos.y
        along = ex * cx + ey * cy
        if along < 0 or along > 500:
            return False
        return abs(ex * cy - ey * cx) < ent.radius + 6

    def _apply_beam(self, dt: float) -> None:
        p   = self.player
        cx, cy = math.cos(p._angle), math.sin(p._angle)
        dmg = BEAM_DAMAGE_PS * dt          # float damage — no int truncation to 0
        sfx = self._beam_sfx_cd <= 0
        if sfx:                            # throttled: was fired every frame
            self.audio.beam_hum()
            self._beam_sfx_cd = 0.12
        for e in self.enemies[:]:
            if self._beam_hits(e, cx, cy):
                if e.take_damage(dmg):
                    self._on_enemy_killed(e)   # scores, bursts, REMOVES the enemy
        if self.boss and self._beam_hits(self.boss, cx, cy):
            if self.boss.take_damage(dmg):
                self._on_boss_killed()
            elif sfx:
                self.audio.boss_hit()

    def _handle_bomb_explosion(self, proj: Projectile) -> None:
        cx, cy = int(proj.pos.x), int(proj.pos.y)
        self._burst(cx, cy, proj.color, 28, (2, 9))
        self._ring(cx, cy, proj.color, 10, BOMB_RADIUS, 0.5)
        self.audio.bomb_explode()
        self.shake = 14
        for e in self.enemies[:]:
            if e.pos.distance_to(proj.pos) < BOMB_RADIUS:
                if e.take_damage(BOMB_DAMAGE):
                    self._on_enemy_killed(e)
        if self.boss and (self.boss.pos - proj.pos).length() < BOMB_RADIUS:
            if self.boss.take_damage(BOMB_DAMAGE):
                self._on_boss_killed()
            else:
                self.audio.boss_hit()

    # ── Kill streak ───────────────────────────────────────────────────────────

    def _streak_mult(self) -> float:
        tier = sum(1 for t in STREAK_THRESHOLDS if self.streak >= t)
        return STREAK_MULTIPLIERS[tier]

    def _register_kill(self) -> float:
        """Count a kill toward the streak; returns the multiplier to score it at."""
        old = self._streak_mult()
        self.streak      += 1
        self.streak_timer = STREAK_RESET_TIME
        new = self._streak_mult()
        if new > old:
            self._text_popup(self.player.pos.x, self.player.pos.y - 34,
                             f"STREAK x{new:g}", CHAOS_COL)
            self.audio.level_up()
        return new

    def _text_popup(self, x: float, y: float, text: str, color: tuple) -> None:
        if len(self.particles) < _PARTICLE_CAP:
            self.particles.append(TextPopup(x, y, text, color, self.ui.font_m, 1.6))

    # ── Enemy helpers ─────────────────────────────────────────────────────────

    def _update_shields(self) -> None:
        """Shield Drones orbit a host enemy and make it immune while they live."""
        for e in self.enemies:
            e.shield = 0
        for d in self.enemies:
            if not isinstance(d, ShieldDrone):
                continue
            if d.host is None or d.host not in self.enemies:
                best, best_d = None, 1e9
                for h in self.enemies:
                    if isinstance(h, ShieldDrone):
                        continue
                    dist = h.pos.distance_to(d.pos)
                    if dist < best_d:
                        best, best_d = h, dist
                d.host = best
            if d.host is not None and not d.stunned:
                d.host.shield += 1

    def _enemy_effects(self) -> None:
        """Visual/audio reactions to enemy events raised during update."""
        for e in self.enemies:
            if isinstance(e, Berserker) and e.just_enraged:
                e.just_enraged = False
                x, y = int(e.pos.x), int(e.pos.y)
                self._ring(x, y, BERSERKER_RAGE_COL, 10, 100, 0.45)
                self._burst(x, y, BERSERKER_RAGE_COL, 18, (2, 8))
                self.audio.boss_hit()
                self.shake = max(self.shake, 7)
            elif isinstance(e, Teleporter) and e.blink_event:
                e.blink_event = False
                self._ring(int(e.blink_from.x), int(e.blink_from.y), TELEPORTER_COL, 14, 40, 0.25)
                self._ring(int(e.pos.x), int(e.pos.y), TELEPORTER_COL, 6, 46, 0.3)
                self.audio.dash()

    def _on_enemy_killed(self, e) -> None:
        if e not in self.enemies:          # already dead (beam + chain on same frame, etc.)
            return
        self.enemies.remove(e)
        ex, ey = int(e.pos.x), int(e.pos.y)
        mult = self._register_kill()
        pts  = int(round(e.score_val * mult))
        self._burst(ex, ey, ENEMY_COL, 20, (2, 7))
        self._score_popup(ex, ey, pts, ENEMY_COL)
        self.score += pts
        self.shake  = max(self.shake, 6)
        if isinstance(e, Splitter):        # bursts into two Swarm Nodes
            self._ring(ex, ey, SPLITTER_COL, 8, 50, 0.3)
            for sx in (-1, 1):
                self.enemies.append(SwarmNode(ex + sx * 16, ey))
        self._volatile_blast(e)

    def _volatile_blast(self, src) -> None:
        """VOLATILE CORE: kills detonate, damaging nearby enemies (can chain)."""
        n = self.perks.get("volatile", 0)
        if not n or self._volatile_depth >= 3:
            return
        self._volatile_depth += 1
        pos = pygame.Vector2(src.pos)
        self._ring(int(pos.x), int(pos.y), (255, 140, 40), 8, 80, 0.35)
        self._burst(int(pos.x), int(pos.y), (255, 140, 40), 14, (2, 7))
        for other in self.enemies[:]:
            if other.pos.distance_to(pos) < 80 and other.take_damage(n + 1):
                self._on_enemy_killed(other)
        if self.boss and (self.boss.pos - pos).length() < 80 + self.boss.radius:
            if self.boss.take_damage(n + 1):
                self._on_boss_killed()
        self._volatile_depth -= 1

    def _on_boss_killed(self) -> None:
        boss = self.boss
        if boss is None:
            return
        pos = boss.pos
        bx, by = int(pos.x), int(pos.y)
        mult = self._register_kill()
        pts  = int(round(BOSS_SCORE_REWARD * mult))
        self._burst(bx, by, (0, 220, 255), 50, (3, 12))
        self._ring(bx, by, (0, 220, 255), 20, 200, 0.8)
        self.score += pts
        self._score_popup(bx, by, pts, (0, 220, 255))
        self.audio.level_up()
        self.shake = 20
        self.boss  = None

    # ── Perks ─────────────────────────────────────────────────────────────────

    def grant_perk(self, key: str) -> None:
        perk = PERKS.get(key)
        if perk is None or self.perks.get(key, 0) >= perk.max_stacks:
            return
        self.perks[key] = self.perks.get(key, 0) + 1
        if key == "repair":
            self.hp += 1
        elif key == "phase_drive":
            self.player.dash_charges += 1
        self.perk_pending = False
        self.perk_choices = []

    # ── Damage to the player ──────────────────────────────────────────────────

    def _hurt_player(self, src_pos, shake: int, burst_n: int, push_dist: float) -> None:
        if self.dying:
            return
        p = self.player
        self.hp        -= 1
        p.inv_timer     = PLAYER_INV_DURATION
        self.shake      = shake
        self.streak     = 0                           # getting hit breaks the streak
        self.audio.player_hit()
        self._burst(int(p.pos.x), int(p.pos.y), ENEMY_COL, burst_n)
        self.renderer.trigger_flash((210, 45, 75))
        push = p.pos - src_pos
        if push.length_squared() > 0:
            p.pos += push.normalize() * push_dist
            p.pos.x = max(p.radius, min(W - p.radius, p.pos.x))
            p.pos.y = max(p.radius, min(H - p.radius, p.pos.y))
        if self.hp <= 0:
            self._on_lethal()

    def _on_lethal(self) -> None:
        p = self.player
        if self.perks.get("second_wind") and not self._second_wind_used:
            self._second_wind_used = True              # SECOND WIND
            self.hp         = 1
            p.inv_timer     = 2.0
            for e in self.enemies:
                e.stun()
            if self.boss:
                self.boss.stun()
            self._ring(int(p.pos.x), int(p.pos.y), WHITE, 10, 260, 0.7)
            self._burst(int(p.pos.x), int(p.pos.y), WHITE, 30, (3, 10))
            self._text_popup(p.pos.x, p.pos.y - 40, "SECOND WIND", WHITE)
            self.renderer.trigger_flash((255, 255, 255), 0.2)
            self.audio.chaos_activate()
            return
        self.dying        = True                       # slow-motion, then game over
        self._death_timer = DEATH_SLOW_DURATION
        self.shake        = 18
        self.renderer.trigger_flash((255, 255, 255), 0.25)

    def _handle_collisions(self) -> None:
        p = self.player

        for b in self.meh_blocks[:]:
            if b.center.distance_to(p.pos) < p.radius + MehBlock.SIZE // 2:
                if p.chaos_mode:
                    self._burst(b.rect.centerx, b.rect.centery, MEH_COL, 16)
                    self.audio.meh_destroy()
                    self.meh_blocks.remove(b)
                    triggered = p.add_energy(MEH_CHAOS_ENERGY)
                    if triggered:
                        self._ring(int(p.pos.x), int(p.pos.y), CHAOS_COL, 10, 120, 0.55)
                        self.audio.chaos_activate()
                    self.score += MEH_CHAOS_SCORE
                    self.shake  = 3
                elif b.hacked:
                    b.hp -= 1
                    self._burst(b.rect.centerx, b.rect.centery, MEH_HACKED, 10)
                    if b.hp <= 0:
                        self.meh_blocks.remove(b)
                        self.audio.meh_destroy()
                        triggered = p.add_energy(MEH_ENERGY_REWARD)
                        if triggered:
                            self._ring(int(p.pos.x), int(p.pos.y), CHAOS_COL, 10, 120, 0.55)
                            self.audio.chaos_activate()
                        self.score += MEH_SCORE_REWARD
                        self.shake  = 4

        for f in self.fragments[:]:
            if f.pos.distance_to(p.pos) < p.radius + f.radius:
                self.frag_text  = f.text
                self.frag_timer = FRAG_POPUP_DURATION
                self._burst(int(f.pos.x), int(f.pos.y), FRAG_COL, 24, (1, 6))
                self.audio.fragment_collect()
                self.fragments.remove(f)
                triggered = p.add_energy(FRAG_ENERGY_REWARD * (1 + 0.4 * self.perks.get("salvage", 0)))
                if triggered:
                    self._ring(int(p.pos.x), int(p.pos.y), CHAOS_COL, 10, 120, 0.55)
                    self.audio.chaos_activate()
                self.score += FRAG_SCORE_REWARD
                self.shake  = 5

        for e in self.enemies[:]:
            if not e.stunned and e.pos.distance_to(p.pos) < e.radius + p.radius:
                if p.chaos_mode:
                    self._burst(int(e.pos.x), int(e.pos.y), ENEMY_COL, 22, (2, 7))
                    self._on_enemy_killed(e)
                    self.audio.meh_destroy()
                elif not p.invulnerable:
                    self._hurt_player(e.pos, 12, 18, 70)

        if self.boss and not self.boss.stunned and hasattr(self.boss, 'pos'):
            # use squared-length check to avoid relying on distance_to attribute
            push_vec = self.boss.pos - p.pos
            if push_vec.length_squared() < (self.boss.radius + p.radius) ** 2:
                if p.chaos_mode:
                    self._on_boss_killed()
                elif not p.invulnerable:
                    self._hurt_player(self.boss.pos, 16, 22, 90)

    def _replenish(self) -> None:
        if len(self.meh_blocks) < MEH_SPAWN_MIN:
            self._spawn_mehs(MEH_SPAWN_BATCH)
        if len(self.fragments) < FRAG_SPAWN_MIN:
            self._spawn_frags(FRAG_SPAWN_BATCH)

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surf: pygame.Surface | None = None) -> None:
        """Render the game world onto *surf* (the logical surface)."""
        if surf is None:
            surf = pygame.display.get_surface()

        ox, oy = 0, 0
        sh = int(self.shake)
        if sh:
            ox = random.randint(-sh, sh)
            oy = random.randint(-sh, sh)

        self.renderer.draw_background(surf, self.player.chaos_mode)
        self.renderer.draw_glitch_lines(surf)

        world = self._world
        world.fill((0, 0, 0, 0))
        for b    in self.meh_blocks:  b.draw(world, self.ui.font_s)
        for f    in self.fragments:   f.draw(world)
        for e    in self.enemies:
            e.draw(world)
            if e.shield > 0:
                fade_ring(world, SHIELD_COL, e.pos, e.radius + 9, 150)
        for pt   in self.particles:   pt.draw(world)
        for proj in self.projectiles: proj.draw(world)
        if self.boss:
            self.boss.draw(world)
        self.player.draw(world)
        surf.blit(world, (ox, oy))

        if self.player.chaos_mode:
            self.renderer.draw_chromatic(surf)

        self.renderer.draw_overlay(surf)
        self.renderer.draw_flash(surf)

        self.ui.draw_hud(surf, self.player, self.hp,
                         self.score, self.run_time, self.wave_mgr.wave,
                         wave_mgr=self.wave_mgr)

        self.ui.draw_streak(surf, self.streak, self._streak_mult(),
                            self.streak_timer / STREAK_RESET_TIME)
        self.ui.draw_perks(surf, [(PERKS[k].name, n, PERKS[k].color)
                                  for k, n in self.perks.items()])
        if self.boss:
            self.ui.draw_boss_bar(surf, self.boss)

        self.ui.draw_wave_banner(surf, self._last_dt)
        self.ui.draw_fragment_popup(surf, self.frag_text,
                                    self.frag_timer, FRAG_POPUP_DURATION)
        self.ui.draw_controls_hint(surf, self.run_time)
        self.ui.draw_mute_indicator(surf, self.audio.muted)

        # Crosshair at logical mouse position
        mx, my = self._logical_mouse
        self.ui.draw_crosshair(surf, (mx, my),
                               WEAPON_COLORS[self.player.weapon_index])

        # Game-over overlay is handled by GameOverState;
        # only show it if we're NOT using the state manager
        if self.game_over and self.manager is None:
            self.ui.draw_game_over(surf, self.score)
