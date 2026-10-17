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
    PRISM_HP, MAX_ENEMY_BULLETS,
    DEATH_SLOW_FACTOR, DEATH_SLOW_DURATION,
    SHIELD_COL, BERSERKER_RAGE_COL, TELEPORTER_COL, SPLITTER_COL,
)
from game.player       import Player
from game.entities     import (MehBlock, Fragment, Enemy, Hunter, SwarmNode, Phantom, Boss,
                               Projectile, Berserker, Teleporter, ShieldDrone, Splitter,
                               Prism, EnemyBullet)
from game.perks        import PERKS, roll_choices
from game.music        import MusicEngine
from utils.helpers     import fade_ring
from utils             import helpers as _helpers
from utils.spatial     import SpatialHash
from game.dust         import DustField
from game.particles    import Particle, DashTrail, Ring, TextPopup
from game.renderer     import Renderer
from game.audio        import SoundManager
from game.ui           import UI
from game.wave_manager import WaveManager, boss_kind, BOSS_NAMES

_PARTICLE_CAP = 200
_MAX_ENEMY_R   = 32      # broad-phase query padding (largest non-boss enemy radius + margin)
_LOD_ENEMIES   = 120     # above this many enemies, skip glows / HP bars


class Game:
    """
    Core gameplay logic.  Owns all entities, physics, and rendering.
    Used by PlayState — does NOT own the main loop or the display surface.
    """

    def __init__(self, manager=None, seed: int | None = None) -> None:
        self.manager  = manager
        self.seed     = seed                       # not None => daily run
        self.daily    = seed is not None
        self.daily_date: str | None = None
        self.rng      = random.Random(seed)        # arena layout / replenishment
        self._spawn_rng = random if seed is None else random.Random(f"{seed}:w0")
        self.clock    = pygame.time.Clock()
        self.audio    = SoundManager()
        self.music    = MusicEngine(self.audio)      # layered, state-reactive music
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
                x = self.rng.randint(60, W - 100)
                y = self.rng.randint(60, H - 100)
                if pygame.Vector2(x + 19, y + 19).distance_to(self.player.pos) > 90:
                    self.meh_blocks.append(MehBlock(x, y))
                    break

    def _spawn_frags(self, n: int) -> None:
        used = {f.text for f in self.fragments}
        pool = [t for t in FRAGMENTS if t not in used]
        self.rng.shuffle(pool)
        for i in range(min(n, len(pool))):
            x = self.rng.randint(80, W - 80)
            y = self.rng.randint(80, H - 80)
            self.fragments.append(Fragment(x, y, pool[i]))

    def _spawn_entity(self, etype: str, x: float | None = None, y: float | None = None) -> None:
        if x is None or y is None:
            for _ in range(50):
                x = float(self._spawn_rng.randint(60, W - 60))
                y = float(self._spawn_rng.randint(60, H - 60))
                if pygame.Vector2(x, y).distance_to(self.player.pos) > 180:
                    break
        # Ensure x and y are floats (type-checkers may still consider them Optional)
        if x is None:
            x = float(self._spawn_rng.randint(60, W - 60))
        if y is None:
            y = float(self._spawn_rng.randint(60, H - 60))
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
            wave = self.wave_mgr.wave
            tier = max(0, (wave - 5) // 5)
            if boss_kind(wave) == "prism":
                self.boss = Prism(W // 2, 130, hp=PRISM_HP + 10 * tier)
            else:
                self.boss = Boss(W // 2, 80, hp=BOSS_HP + 8 * tier)
            self.enemy_bullets.clear()
            self.audio.boss_spawn()

    # ── State ─────────────────────────────────────────────────────────────────

    def _reset(self) -> None:
        self.perks       : dict             = {}
        self.dust        = DustField()                  # NumPy-vectorised spark field
        self._eh         = SpatialHash(64)              # enemy broad-phase
        self.stress_target = getattr(self, "stress_target", 0)
        self.show_debug  = getattr(self, "show_debug", False)
        self.debug_info  : list = []
        self.player      = Player(W // 2, H // 2)
        self.player.perks = self.perks
        self.meh_blocks  : list[MehBlock]   = []
        self.fragments   : list[Fragment]   = []
        self.enemies     : list             = []
        self.projectiles : list[Projectile] = []
        self.particles   : list             = []
        self.enemy_bullets : list           = []
        self._hitstop_t  = 0.0
        self._boss_state_prev = None
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
        # Plus a vectorised spray of fine sparks (px/frame -> px/s)
        self.dust.emit(x, y, n * 4, color, speed=(spd[0] * 55.0, spd[1] * 70.0))

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
        for b in self.enemy_bullets:                 # HACK also scrubs hostile bullets in range
            if b.alive and b.pos.distance_to(self.player.pos) < rng:
                b.alive = False
                self.dust.emit(b.pos.x, b.pos.y, 6, (80, 220, 120), speed=(40.0, 160.0))
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
        if self._hitstop_t > 0:                         # hit-stop: freeze the world for a few frames
            self._hitstop_t -= real_dt
            self.renderer.update(real_dt, self.player.chaos_mode)
            return
        self.run_time    += dt
        self._last_dt     = real_dt
        keys              = pygame.key.get_pressed()
        mouse_pos         = self._logical_mouse
        mouse_buttons     = ((False, False, False) if self.dying
                             else pygame.mouse.get_pressed())
        if self.stress_target:                      # hands-free stress test: hold fire
            mouse_buttons = (True, False, False)
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

        if self.projectiles:                       # broad-phase only needed when something can hit
            self._eh.rebuild(self.enemies)
        self.dust.update(dt)
        dead_projs = set()
        for i, proj in enumerate(self.projectiles):
            if not proj.alive:
                if proj.weapon_type == Projectile.TYPE_BOMB and proj.detonated:
                    self._handle_bomb_explosion(proj)
                dead_projs.add(i)
                continue
            # Broad-phase: only enemies in nearby grid cells; hit the NEAREST one
            best, best_d = None, 1e9
            for e in self._eh.nearby(proj.pos.x, proj.pos.y, proj.radius + _MAX_ENEMY_R):
                if e._dead or id(e) in proj.hit_ids:
                    continue
                d = e.pos.distance_to(proj.pos)
                if d < e.radius + proj.radius and d < best_d:
                    best, best_d = e, d
            if best is not None:
                e         = best
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
            st = getattr(self.boss, "_state", None)
            if st == "warn" and self._boss_state_prev != "warn":
                self.audio.play("telegraph")
            self._boss_state_prev = st
            bq = getattr(self.boss, "bullet_queue", None)
            if bq:
                room = MAX_ENEMY_BULLETS - len(self.enemy_bullets)
                for (bx, by, vx, vy) in bq[:max(0, room)]:
                    self.enemy_bullets.append(EnemyBullet(bx, by, vx, vy))
                bq.clear()
            if getattr(self.boss, "just_phase2", False):
                self.boss.just_phase2 = False
                bx, by = int(self.boss.pos.x), int(self.boss.pos.y)
                self._ring(bx, by, (255, 60, 60), 20, 260, 0.7)
                self.dust.emit(bx, by, 400, (255, 80, 80), speed=(80.0, 420.0), life=(0.4, 1.0))
                self.shake = 16
                self._freeze(0.14)
                self.renderer.trigger_flash((255, 60, 60), 0.18)
                self.audio.boss_spawn()
        self._update_bullets(dt)

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

        self.music.update(real_dt, enemies=len(self.enemies), boss=self.boss is not None,
                          chaos=p.chaos_mode, streak=self.streak,
                          wave=self.wave_mgr.wave, dying=self.dying)
        if self.stress_target:
            self._stress_tick()
            return
        # Wave system
        self.wave_mgr.update(dt, len(self.enemies), self.boss is not None)
        if self.wave_mgr.wave_just_started and self.seed is not None:
            self._spawn_rng = random.Random(f"{self.seed}:w{self.wave_mgr.wave}")
        for spawn in self.wave_mgr.spawn_queue:
            self._spawn_entity(spawn[0])
        if self.wave_mgr.wave_just_started:
            self.ui.show_wave_banner(self.wave_mgr.wave, self.wave_mgr.is_boss_wave,
                                     BOSS_NAMES[boss_kind(self.wave_mgr.wave)])
            if self.wave_mgr.is_boss_wave:
                self.audio.boss_spawn()
            else:
                self.audio.wave_start()
        if self.wave_mgr.wave_just_cleared and not self.dying:
            prng = (random.Random(f"{self.seed}:perk:{self.wave_mgr.wave}")
                    if self.seed is not None else None)
            choices = roll_choices(self.perks, rng=prng)
            if choices:
                self.perk_choices = choices
                self.perk_pending = True

    def _update_bullets(self, dt: float) -> None:
        """Move enemy bullets and resolve hits on the player.
        Dash i-frames dodge them, Chaos Mode erases them, otherwise 1 damage."""
        p = self.player
        for b in self.enemy_bullets:
            b.update(dt)
            if not b.alive:
                continue
            if b.pos.distance_to(p.pos) < p.radius + b.radius - 2:
                if p.chaos_mode:
                    b.alive = False
                    self.dust.emit(b.pos.x, b.pos.y, 10, b.color, speed=(60.0, 220.0))
                elif not p.invulnerable and not self.dying:
                    b.alive = False
                    self._hurt_player(b.pos, 10, 14, 40)
        self.enemy_bullets = [b for b in self.enemy_bullets if b.alive]

    def _clear_bullets(self) -> None:
        for b in self.enemy_bullets:
            self.dust.emit(b.pos.x, b.pos.y, 4, b.color, speed=(30.0, 140.0))
        self.enemy_bullets.clear()

    def _shake_offset(self, t: float) -> tuple:
        """Screen-shake offset at time *t* (s): smooth layered sines, |offset| <= shake.
        (Was a fresh random jump every frame, which reads as jitter, not impact.)"""
        sh = self.shake
        if sh < 1:
            return 0, 0
        return (int(sh * (0.7 * math.sin(t * 47.0) + 0.3 * math.sin(t * 91.3 + 1.7))),
                int(sh * (0.7 * math.sin(t * 53.0 + 2.1) + 0.3 * math.sin(t * 83.7 + 0.4))))

    def _freeze(self, seconds: float) -> None:
        """Hit-stop: briefly freeze the simulation on impactful moments."""
        if not self.stress_target:
            self._hitstop_t = min(0.3, max(self._hitstop_t, seconds))

    def _stress_tick(self) -> None:
        """--stress N: keep ~N enemies alive, make the player unkillable."""
        self.hp = max(self.hp, 3)
        self.perk_pending = False
        kinds = ("standard", "hunter", "swarm", "phantom", "splitter", "berserker")
        for _ in range(min(self.stress_target - len(self.enemies), 40)):
            self._spawn_entity(random.choice(kinds))

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
        self.dust.emit(cx, cy, 500, proj.color, speed=(80.0, 520.0), life=(0.4, 1.1))
        self._freeze(0.06)
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
            self.audio.play("streak_up")
            self._freeze(0.05)
        return new

    def _text_popup(self, x: float, y: float, text: str, color: tuple) -> None:
        if len(self.particles) < _PARTICLE_CAP:
            self.particles.append(TextPopup(x, y, text, color, self.ui.font_m, 1.6))

    # ── Enemy helpers ─────────────────────────────────────────────────────────

    def _update_shields(self) -> None:
        """Shield Drones orbit a host enemy and make it immune while they live."""
        for e in self.enemies:
            e.shield = 0
        hosts = None
        for d in self.enemies:
            if not isinstance(d, ShieldDrone):
                continue
            if d.host is None or d.host._dead:
                if hosts is None:
                    hosts = [h for h in self.enemies if not isinstance(h, ShieldDrone)]
                best, best_d = None, 1e9
                for h in hosts:
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
                self.audio.play("enrage")
                self._freeze(0.08)
                self.shake = max(self.shake, 7)
            elif isinstance(e, Teleporter) and e.blink_event:
                e.blink_event = False
                self._ring(int(e.blink_from.x), int(e.blink_from.y), TELEPORTER_COL, 14, 40, 0.25)
                self._ring(int(e.pos.x), int(e.pos.y), TELEPORTER_COL, 6, 46, 0.3)
                self.audio.play("teleport")

    def _on_enemy_killed(self, e) -> None:
        if e not in self.enemies:          # already dead (beam + chain on same frame, etc.)
            return
        self.enemies.remove(e)
        e._dead = True
        if isinstance(e, ShieldDrone):
            self.audio.play("shield_break")
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
        self._freeze(0.3)
        self._clear_bullets()
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
        self._freeze(0.07)
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
            self._clear_bullets()
            self.renderer.trigger_flash((255, 255, 255), 0.2)
            self._freeze(0.2)
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
        ox, oy = self._shake_offset(pygame.time.get_ticks() / 1000.0)

        self.renderer.draw_background(surf, self.player.chaos_mode)
        self.renderer.draw_glitch_lines(surf)

        world = self._world
        world.fill((0, 0, 0, 0))
        for b    in self.meh_blocks:  b.draw(world, self.ui.font_s)
        for f    in self.fragments:   f.draw(world)
        _helpers.LOD = len(self.enemies) > _LOD_ENEMIES      # crowd level-of-detail
        for e    in self.enemies:
            e.draw(world)
            if e.shield > 0:
                fade_ring(world, SHIELD_COL, e.pos, e.radius + 9, 150)
        _helpers.LOD = False
        for pt   in self.particles:   pt.draw(world)
        for proj in self.projectiles: proj.draw(world)
        for b    in self.enemy_bullets: b.draw(world)
        if self.boss:
            self.boss.draw(world)
        self.player.draw(world)
        surf.blit(world, (ox, oy))
        self.dust.draw(surf, ox, oy)

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

        if self.daily:
            tag = self.ui.font_s.render(f"DAILY RUN  {self.daily_date or ''}", True, (255, 190, 0))
            surf.blit(tag, (W // 2 - tag.get_width() // 2, 2))
        if self.show_debug or self.stress_target:
            self._draw_debug(surf)

        # Game-over overlay is handled by GameOverState;
        # only show it if we're NOT using the state manager
        if self.game_over and self.manager is None:
            self.ui.draw_game_over(surf, self.score)

    def _draw_debug(self, surf: pygame.Surface) -> None:
        lines = list(self.debug_info) + [
            f"enemies {len(self.enemies):4d}   projectiles {len(self.projectiles):3d}   bullets {len(self.enemy_bullets):3d}",
            f"particles {len(self.particles):3d}   dust {len(self.dust):5d}"
            + ("   [LOD]" if len(self.enemies) > _LOD_ENEMIES else ""),
        ]
        y = 110
        for ln in lines:
            surf.blit(self.ui.font_s.render(ln, True, (0, 255, 160)), (W - 330, y))
            y += 14
