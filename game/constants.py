# ── Window & timing ───────────────────────────────────────────────────────────
LOGICAL_W, LOGICAL_H = 1280, 720   # fixed internal rendering resolution
W, H   = LOGICAL_W, LOGICAL_H      # aliases used everywhere
MIN_W, MIN_H = 960, 540            # minimum window size
FPS    = 60
TILE   = 40

# ── Color palette ─────────────────────────────────────────────────────────────
BG           = (4,   4,  14)
GRID_DIM     = (15,  15, 30)
GRID_BRIGHT  = (28,  28, 50)
PLAYER_COL   = (160,  80, 255)
CHAOS_COL    = (255, 190,   0)
MEH_COL      = (70,  70,  95)
MEH_HACKED   = (0,  220, 110)
FRAG_COL     = (0,  200, 180)
ENEMY_COL    = (210,  45,  75)
HUNTER_COL   = (255, 120,  20)
SWARM_COL    = (220,  40, 200)
PHANTOM_COL  = (140,  80, 220)
BOSS_COL     = (0,  220, 255)
ENERGY_COL   = (80, 180, 255)
WHITE        = (255, 255, 255)
DIM          = (100, 100, 130)
ACCENT       = (0,  200, 160)
DARK_PANEL   = (8,    8,  22)

# Weapon colors
PLASMA_COL  = (100, 200, 255)
SPREAD_COL  = (180, 100, 255)
CHAIN_COL   = (100, 255, 180)
BEAM_COL    = (255,  60, 120)
BOMB_COL    = (255, 180,   0)

# ── Fragment pool ─────────────────────────────────────────────────────────────
FRAGMENTS = [
    "// error: meaning not found",
    "while alive: drift()",
    "null.identity",
    "ghost in the signal",
    "absorb the void",
    "undefined self",
    "execute silence",
    "the loop never breaks",
    "chaos.mode = True",
    "fragments remain",
    "del sorrow",
    "import purpose  # failed",
    "self.resolve()",
    "run blade.py --no-fear",
    "assert hope  # AssertionError",
    "return None  # as always",
    "try: exist() except: pass",
    "// she was a fragment too",
    "memory.leak() since forever",
    "break  # but gently",
    "kernel.panic() # not found",
    "rm -rf /feelings",
    "git commit -m 'survive'",
    "void main() { bleed(); }",
    "print('I am still here')",
    "catch(Exception e) { live(); }",
    "stack overflow: self",
    "sudo make me feel something",
    "404: peace not found",
    "segfault in the soul",
]

# ── Gameplay tuning ───────────────────────────────────────────────────────────
PLAYER_SPEED        = 4.5
PLAYER_RADIUS       = 14
PLAYER_HACK_CD      = 2.0
PLAYER_INV_DURATION = 1.5
PLAYER_TRAIL_LEN    = 18
PLAYER_MAX_ENERGY   = 100
CHAOS_DURATION      = 10.0
CHAOS_SPEED_MULT    = 1.9
HACK_RANGE_NORMAL   = 90
HACK_RANGE_CHAOS    = 150

# Dash
PLAYER_DASH_SPEED   = 22.0
PLAYER_DASH_FRAMES  = 8      # frames the dash lasts
PLAYER_DASH_CD      = 1.2

# Blocks
MEH_DEFAULT_HP      = 2

# Rewards
FRAG_ENERGY_REWARD   = 22
FRAG_SCORE_REWARD    = 50
MEH_ENERGY_REWARD    = 14
MEH_SCORE_REWARD     = 20
MEH_CHAOS_ENERGY     = 6
MEH_CHAOS_SCORE      = 10
ENEMY_SCORE_REWARD   = 35
HUNTER_SCORE_REWARD  = 55
SWARM_SCORE_REWARD   = 20
PHANTOM_SCORE_REWARD = 60
BOSS_SCORE_REWARD    = 500

# Standard enemy
ENEMY_SPEED_MIN     = 1.3
ENEMY_SPEED_MAX     = 2.4
ENEMY_CHASE_DIST    = 220
ENEMY_RADIUS        = 13
ENEMY_STUN_DURATION = 2.5

# Hunter enemy
HUNTER_RADIUS       = 11
HUNTER_SPEED        = 3.0

# Swarm enemy
SWARM_RADIUS        = 8
SWARM_SPEED         = 2.4

# Phantom enemy
PHANTOM_RADIUS      = 12
PHANTOM_SPEED       = 1.9

# Boss — The Architect
BOSS_RADIUS         = 32
BOSS_HP             = 15
BOSS_PHASE2_HP      = 7

# Spawn thresholds
MEH_SPAWN_MIN       = 12
MEH_SPAWN_BATCH     = 6
FRAG_SPAWN_MIN      = 3
FRAG_SPAWN_BATCH    = 3
ENEMY_SPAWN_MIN     = 4

FRAG_POPUP_DURATION = 2.8
CONTROLS_FADE_TIME  = 12.0

# ── Weapons ───────────────────────────────────────────────────────────────────
WEAPON_NAMES   = ["PLASMA BOLT", "VOID SPREAD", "CHAIN ZAP", "NULL BEAM", "CHAOS BOMB"]
WEAPON_COLORS  = [PLASMA_COL, SPREAD_COL, CHAIN_COL, BEAM_COL, BOMB_COL]

PLASMA_CD       = 0.22
PLASMA_SPEED    = 14
PLASMA_DAMAGE   = 1
PLASMA_RANGE    = 650

SPREAD_CD       = 0.65
SPREAD_SPEED    = 11
SPREAD_DAMAGE   = 1
SPREAD_COUNT    = 5
SPREAD_ANGLE    = 28   # total cone in degrees

CHAIN_CD        = 1.3
CHAIN_DAMAGE    = 2
CHAIN_LINKS     = 3
CHAIN_RANGE     = 190

BEAM_DAMAGE_PS    = 5    # damage per second
BEAM_ENERGY_DRAIN = 10   # energy per second (drains energy!)

BOMB_MAX        = 3
BOMB_RECHARGE   = 12.0   # seconds per bomb
BOMB_RADIUS     = 130
BOMB_DAMAGE     = 6
BOMB_FUSE       = 1.4    # seconds to detonate

# ── Wave config ───────────────────────────────────────────────────────────────
WAVE_BREAK_DURATION = 4.0

# ── Audio ─────────────────────────────────────────────────────────────────────
MASTER_VOLUME   = 0.55
