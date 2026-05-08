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
    CHAIN_DAMAGE,
    FRAGMENTS,
    WEAPON_COLORS,
)
from game.player       import Player
from game.entities     import MehBlock, Fragment, Enemy, Hunter, SwarmNode, Phantom, Boss, Projectile
from game.particles    import Particle, DashTrail, Ring, TextPopup
from game.renderer     import Renderer
from game.audio        import SoundManager
from game.ui           import UI
from game.wave_manager import WaveManager

_PARTICLE_CAP = 200


class Game:
    def __init__(self) -> None:
        self.screen   = pygame.display.get_surface()
        self.clock    = pygame.time.Clock()
        self.audio    = SoundManager()
        self.ui       = UI()
        self.renderer = Renderer()
        self.wave_mgr = WaveManager()
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

    def _spawn_entity(self, etype: str, x: float = None, y: float = None) -> None:
        if x is None or y is None:
            for _ in range(50):
                x = random.randint(60, W - 60)
                y = random.randint(60, H - 60)
                if pygame.Vector2(x, y).distance_to(self.player.pos) > 180:
                    break
        if etype == "standard":
            self.enemies.append(Enemy(x, y))
        elif etype == "hunter":
            self.enemies.append(Hunter(x, y))
        elif etype == "swarm":
            self.enemies.append(SwarmNode(x, y))
        elif etype == "phantom":
            self.enemies.append(Phantom(x, y))
        elif etype == "boss":
            self.boss = Boss(W // 2, 80)
            self.audio.boss_spawn()

    # ── State ─────────────────────────────────────────────────────────────────

    def _reset(self) -> None:
        self.player      = Player(W // 2, H // 2)
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
        self.run_time    = 0.0
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
        self.run_time    += dt
        keys              = pygame.key.get_pressed()
        mouse_pos         = pygame.mouse.get_pos()
        mouse_buttons     = pygame.mouse.get_pressed()
        p                 = self.player

        # FIX B-01: correct 5-argument call
        p.update(keys, dt, mouse_pos, mouse_buttons, self.enemies)

        if p._chaos_just_ended:
            self.audio.chaos_end()

        # FIX C-08: live drone pitch update
        self.audio.update_drone(p.energy / p.max_energy, p.chaos_mode)

        # FIX B-03: consume new projectiles
        if p.new_projectiles:
            self.projectiles.extend(p.new_projectiles)
            wi = p.weapon_index
            if wi == 0:   self.audio.plasma_shoot()
            elif wi == 1: self.audio.spread_shoot()
            elif wi == 4: self.audio.bomb_launch()
            p.new_projectiles.clear()

        # FIX C-10: DashTrail particles while dashing
        if p.is_dashing:
            col = CHAOS_COL if p.chaos_mode else PLAYER_COL
            if len(self.particles) < _PARTICLE_CAP:
                self.particles.append(DashTrail(p.pos.x, p.pos.y, col, p.radius))

        # Update all projectiles
        for proj in self.projectiles:
            proj.update(dt)

        # FIX B-03 (collision): projectiles vs enemies and boss
        dead_projs = set()
        for i, proj in enumerate(self.projectiles):
            if not proj.alive:
                if proj.weapon_type == Projectile.TYPE_BOMB and proj.detonated:
                    self._handle_bomb_explosion(proj)
                dead_projs.add(i)
                continue
            for e in self.enemies[:]:
                if e.pos.distance_to(proj.pos) < e.radius + proj.radius:
                    killed = e.take_damage(proj.damage)
                    self._burst(int(proj.pos.x), int(proj.pos.y), proj.color, 6, (1, 4))
                    if killed:
                        self._on_enemy_killed(e)
                    proj.alive = False
                    dead_projs.add(i)
                    break
            if self.boss and i not in dead_projs:
                if self.boss.pos.distance_to(proj.pos) < self.boss.radius + proj.radius:
                    killed = self.boss.take_damage(proj.damage)
                    self._burst(int(proj.pos.x), int(proj.pos.y), proj.color, 8, (1, 5))
                    self.audio.boss_hit()
                    if killed:
                        self._on_boss_killed()
                    proj.alive = False
                    dead_projs.add(i)

        # FIX B-04: chain zap targets
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

        # Null beam hits boss too
        if p.beam_active:
            self.audio.beam_hum()
            if self.boss:
                from game.constants import BEAM_DAMAGE_PS
                ex   = self.boss.pos.x - p.pos.x
                ey   = self.boss.pos.y - p.pos.y
                dist = math.hypot(ex, ey)
                if dist < 500:
                    e_angle  = math.atan2(ey, ex)
                    diff     = abs(math.atan2(
                        math.sin(e_angle - p._angle),
                        math.cos(e_angle - p._angle)))
                    if diff < 0.18:
                        if self.boss.take_damage(BEAM_DAMAGE_PS * dt):
                            self._on_boss_killed()
                        else:
                            self.audio.boss_hit()

        self.projectiles = [proj for i, proj in enumerate(self.projectiles)
                            if i not in dead_projs]

        for b in self.meh_blocks: b.update(dt)
        for f in self.fragments:  f.update(dt)
        for e in self.enemies:    e.update(dt, p.pos)

        if self.boss:
            self.boss.update(dt, p.pos)
            # FIX B-13: consume boss spawn_queue
            for item in self.boss.spawn_queue:
                self._spawn_entity(item[0], item[1], item[2])
            self.boss.spawn_queue.clear()

        self.particles = [pt for pt in self.particles if pt.alive]
        if len(self.particles) > _PARTICLE_CAP:
            self.particles = self.particles[-_PARTICLE_CAP:]
        for pt in self.particles:
            pt.update(dt)

        if self.frag_timer > 0: self.frag_timer -= dt
        if self.shake      > 0: self.shake      -= 1

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
        if self.boss and self.boss.pos.distance_to(proj.pos) < BOMB_RADIUS:
            if self.boss.take_damage(BOMB_DAMAGE):
                self._on_boss_killed()
            else:
                self.audio.boss_hit()

    def _on_enemy_killed(self, e) -> None:
        ex, ey = int(e.pos.x), int(e.pos.y)
        self._burst(ex, ey, ENEMY_COL, 20, (2, 7))
        self._score_popup(ex, ey, e.score_val, ENEMY_COL)
        self.score += e.score_val
        self.shake  = 6
        if e in self.enemies:
            self.enemies.remove(e)

    def _on_boss_killed(self) -> None:
        if self.boss is None:
            return
        bx, by = int(self.boss.pos.x), int(self.boss.pos.y)
        self._burst(bx, by, (0, 220, 255), 50, (3, 12))
        self._ring(bx, by, (0, 220, 255), 20, 200, 0.8)
        self.score += BOSS_SCORE_REWARD
        self._score_popup(bx, by, BOSS_SCORE_REWARD, (0, 220, 255))
        self.audio.level_up()
        self.shake = 20
        self.boss  = None

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
                triggered = p.add_energy(FRAG_ENERGY_REWARD)
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
                elif p.inv_timer <= 0:
                    self.hp        -= 1
                    p.inv_timer     = PLAYER_INV_DURATION
                    self.shake      = 12
                    self.audio.player_hit()
                    self._burst(int(p.pos.x), int(p.pos.y), ENEMY_COL, 18)
                    self.renderer.trigger_flash((210, 45, 75))   # FIX B-07
                    push = (p.pos - e.pos)
                    if push.length_squared() > 0:
                        p.pos += push.normalize() * 70
                        # FIX B-12: clamp after push
                        p.pos.x = max(p.radius, min(W - p.radius, p.pos.x))
                        p.pos.y = max(p.radius, min(H - p.radius, p.pos.y))
                    if self.hp <= 0:
                        self.game_over = True
                        self.audio.game_over()

        if self.boss and not self.boss.stunned:
            if self.boss.pos.distance_to(p.pos) < self.boss.radius + p.radius:
                if p.chaos_mode:
                    self._on_boss_killed()
                elif p.inv_timer <= 0:
                    self.hp        -= 1
                    p.inv_timer     = PLAYER_INV_DURATION
                    self.shake      = 16
                    self.audio.player_hit()
                    self._burst(int(p.pos.x), int(p.pos.y), ENEMY_COL, 22)
                    self.renderer.trigger_flash((210, 45, 75))
                    push = (p.pos - self.boss.pos)
                    if push.length_squared() > 0:
                        p.pos += push.normalize() * 90
                        p.pos.x = max(p.radius, min(W - p.radius, p.pos.x))
                        p.pos.y = max(p.radius, min(H - p.radius, p.pos.y))
                    if self.hp <= 0:
                        self.game_over = True
                        self.audio.game_over()

    def _replenish(self) -> None:
        if len(self.meh_blocks) < MEH_SPAWN_MIN:
            self._spawn_mehs(MEH_SPAWN_BATCH)
        if len(self.fragments) < FRAG_SPAWN_MIN:
            self._spawn_frags(FRAG_SPAWN_BATCH)

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self) -> None:
        ox, oy = 0, 0
        if self.shake:
            ox = random.randint(-self.shake, self.shake)
            oy = random.randint(-self.shake, self.shake)

        self.renderer.draw_background(self.screen, self.player.chaos_mode)
        self.renderer.draw_glitch_lines(self.screen)

        world = pygame.Surface((W, H), pygame.SRCALPHA)
        for b    in self.meh_blocks:  b.draw(world, self.ui.font_s)
        for f    in self.fragments:   f.draw(world)
        for e    in self.enemies:     e.draw(world)
        for pt   in self.particles:   pt.draw(world)
        for proj in self.projectiles: proj.draw(world)
        if self.boss:
            self.boss.draw(world)
        self.player.draw(world)
        self.screen.blit(world, (ox, oy))

        if self.player.chaos_mode:
            self.renderer.draw_chromatic(self.screen)

        # FIX B-06: vignette + scanlines (pre-baked, free)
        self.renderer.draw_vignette(self.screen)
        self.renderer.draw_scanlines(self.screen)

        # FIX B-07: screen flash on hit
        self.renderer.draw_flash(self.screen)

        # FIX B-10: wave argument
        self.ui.draw_hud(self.screen, self.player, self.hp,
                         self.score, self.run_time, self.wave_mgr.wave)

        if self.boss:
            self.ui.draw_boss_bar(self.screen, self.boss)

        self.ui.draw_wave_banner(self.screen, self.clock.get_time() / 1000.0)
        self.ui.draw_fragment_popup(self.screen, self.frag_text,
                                    self.frag_timer, FRAG_POPUP_DURATION)
        self.ui.draw_controls_hint(self.screen, self.run_time)
        self.ui.draw_mute_indicator(self.screen, self.audio.muted)

        # FIX B-18: crosshair
        mx, my = pygame.mouse.get_pos()
        self.ui.draw_crosshair(self.screen, (mx, my),
                               WEAPON_COLORS[self.player.weapon_index])

        if self.game_over:
            self.ui.draw_game_over(self.screen, self.score)

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        pygame.mouse.set_visible(False)
        while True:
            dt = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.mouse.set_visible(True)
                    return
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        pygame.mouse.set_visible(True)
                        return
                    if event.key == pygame.K_SPACE and not self.game_over:
                        self._do_hack()
                    if event.key == pygame.K_r and self.game_over:
                        self._reset()
                    if event.key == pygame.K_m:
                        self.audio.toggle_mute()
                    # FIX B-05: dash on SHIFT
                    if event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                        if not self.game_over:
                            if self.player.trigger_dash(pygame.key.get_pressed()):
                                self.audio.dash()

            if not self.game_over:
                self.update(dt)

            self.draw()
            pygame.display.flip()
