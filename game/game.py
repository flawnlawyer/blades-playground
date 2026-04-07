from __future__ import annotations
import random
import pygame

from game.constants import (
    W, H, FPS,
    PLAYER_COL, CHAOS_COL, MEH_HACKED, MEH_COL, FRAG_COL, ENEMY_COL, WHITE,
    PLAYER_INV_DURATION,
    HACK_RANGE_NORMAL, HACK_RANGE_CHAOS,
    MEH_ENERGY_REWARD, MEH_SCORE_REWARD, MEH_CHAOS_ENERGY, MEH_CHAOS_SCORE,
    FRAG_ENERGY_REWARD, FRAG_SCORE_REWARD, FRAG_POPUP_DURATION,
    ENEMY_SCORE_REWARD,
    MEH_SPAWN_MIN, MEH_SPAWN_BATCH, FRAG_SPAWN_MIN, FRAG_SPAWN_BATCH,
    ENEMY_SPAWN_MIN,
    FRAGMENTS,
)
from game.player    import Player
from game.entities  import MehBlock, Fragment, Enemy
from game.particles import Particle
from game.renderer  import Renderer
from game.audio     import SoundManager
from game.ui        import UI


class Game:
    def __init__(self) -> None:
        self.screen  = pygame.display.get_surface()
        self.clock   = pygame.time.Clock()
        self.audio   = SoundManager()
        self.ui      = UI()
        self.renderer= Renderer()
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

    def _spawn_enemies(self, n: int) -> None:
        for _ in range(n):
            for _ in range(50):
                x = random.randint(60, W - 60)
                y = random.randint(60, H - 60)
                if pygame.Vector2(x, y).distance_to(self.player.pos) > 160:
                    self.enemies.append(Enemy(x, y))
                    break

    # ── State ─────────────────────────────────────────────────────────────────

    def _reset(self) -> None:
        self.player     = Player(W // 2, H // 2)
        self.meh_blocks : list[MehBlock]  = []
        self.fragments  : list[Fragment]  = []
        self.enemies    : list[Enemy]     = []
        self.particles  : list[Particle]  = []
        self.hp         = 3
        self.score      = 0
        self.shake      = 0
        self.frag_text  = ""
        self.frag_timer = 0.0
        self.game_over  = False
        self.run_time   = 0.0
        self._spawn_mehs(22)
        self._spawn_frags(5)
        self._spawn_enemies(4)

    # ── Particle helper ───────────────────────────────────────────────────────

    def _burst(self, x: float, y: float, color: tuple,
               n: int = 12, spd: tuple = (1, 5)) -> None:
        for _ in range(n):
            self.particles.append(Particle(x, y, color, spd))

    # ── Hack ─────────────────────────────────────────────────────────────────

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
        self.run_time += dt
        keys = pygame.key.get_pressed()
        p    = self.player

        p.update(keys, dt)
        if p._chaos_just_ended:
            self.audio.chaos_end()

        for b in self.meh_blocks: b.update(dt)
        for f in self.fragments:  f.update(dt)
        for e in self.enemies:    e.update(dt, p.pos)

        self.particles = [pt for pt in self.particles if pt.alive]
        for pt in self.particles: pt.update(dt)

        if self.frag_timer > 0: self.frag_timer -= dt
        if self.shake      > 0: self.shake      -= 1

        self.renderer.update(dt, p.chaos_mode)
        self._handle_collisions()
        self._replenish()

    def _handle_collisions(self) -> None:
        p = self.player

        # Player ↔ meh blocks
        for b in self.meh_blocks[:]:
            if b.center.distance_to(p.pos) < p.radius + MehBlock.SIZE // 2:
                if p.chaos_mode:
                    self._burst(b.rect.centerx, b.rect.centery, MEH_COL, 16)
                    self.audio.meh_destroy()
                    self.meh_blocks.remove(b)
                    triggered = p.add_energy(MEH_CHAOS_ENERGY)
                    if triggered: self.audio.chaos_activate()
                    self.score += MEH_CHAOS_SCORE
                    self.shake  = 3
                elif b.hacked:
                    b.hp -= 1
                    self._burst(b.rect.centerx, b.rect.centery, MEH_HACKED, 10)
                    if b.hp <= 0:
                        self.meh_blocks.remove(b)
                        self.audio.meh_destroy()
                        triggered = p.add_energy(MEH_ENERGY_REWARD)
                        if triggered: self.audio.chaos_activate()
                        self.score += MEH_SCORE_REWARD
                        self.shake  = 4

        # Player ↔ fragments
        for f in self.fragments[:]:
            if f.pos.distance_to(p.pos) < p.radius + f.radius:
                self.frag_text  = f.text
                self.frag_timer = FRAG_POPUP_DURATION
                self._burst(int(f.pos.x), int(f.pos.y), FRAG_COL, 24, (1, 6))
                self.audio.fragment_collect()
                self.fragments.remove(f)
                triggered = p.add_energy(FRAG_ENERGY_REWARD)
                if triggered: self.audio.chaos_activate()
                self.score += FRAG_SCORE_REWARD
                self.shake  = 5

        # Player ↔ enemies
        for e in self.enemies[:]:
            if not e.stunned and e.pos.distance_to(p.pos) < e.radius + p.radius:
                if p.chaos_mode:
                    self._burst(int(e.pos.x), int(e.pos.y), ENEMY_COL, 22, (2, 7))
                    self.enemies.remove(e)
                    self.audio.meh_destroy()
                    self.score += ENEMY_SCORE_REWARD
                    self.shake  = 8
                elif p.inv_timer <= 0:
                    self.hp        -= 1
                    p.inv_timer     = PLAYER_INV_DURATION
                    self.shake      = 12
                    self.audio.player_hit()
                    self._burst(int(p.pos.x), int(p.pos.y), ENEMY_COL, 18)
                    push   = (p.pos - e.pos)
                    if push.length_squared() > 0:
                        p.pos += push.normalize() * 70
                    if self.hp <= 0:
                        self.game_over = True
                        self.audio.game_over()

    def _replenish(self) -> None:
        if len(self.meh_blocks) < MEH_SPAWN_MIN:
            self._spawn_mehs(MEH_SPAWN_BATCH)
        if len(self.fragments) < FRAG_SPAWN_MIN:
            self._spawn_frags(FRAG_SPAWN_BATCH)
        if len(self.enemies) < ENEMY_SPAWN_MIN and random.random() < 0.004:
            self._spawn_enemies(1)

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self) -> None:
        ox = 0
        oy = 0
        if self.shake:
            import random as _r
            ox = _r.randint(-self.shake, self.shake)
            oy = _r.randint(-self.shake, self.shake)

        self.renderer.draw_background(self.screen, self.player.chaos_mode)
        self.renderer.draw_glitch_lines(self.screen)

        # World layer (shake-offset)
        world = pygame.Surface((W, H), pygame.SRCALPHA)
        for b  in self.meh_blocks: b.draw(world, self.ui.font_s)
        for f  in self.fragments:  f.draw(world)
        for e  in self.enemies:    e.draw(world)
        for pt in self.particles:  pt.draw(world)
        self.player.draw(world)
        self.screen.blit(world, (ox, oy))

        if self.player.chaos_mode:
            self.renderer.draw_chromatic(self.screen)

        self.ui.draw_hud(self.screen, self.player, self.hp, self.score, self.run_time)
        self.ui.draw_fragment_popup(self.screen, self.frag_text,
                                    self.frag_timer, FRAG_POPUP_DURATION)
        self.ui.draw_controls_hint(self.screen, self.run_time)
        self.ui.draw_mute_indicator(self.screen, self.audio.muted)

        if self.game_over:
            self.ui.draw_game_over(self.screen, self.score)

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        while True:
            dt = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return
                    if event.key == pygame.K_SPACE and not self.game_over:
                        self._do_hack()
                    if event.key == pygame.K_r and self.game_over:
                        self._reset()
                    if event.key == pygame.K_m:
                        muted = self.audio.toggle_mute()

            if not self.game_over:
                self.update(dt)

            self.draw()
            pygame.display.flip()
