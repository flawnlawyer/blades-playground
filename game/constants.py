# ── Window & timing ───────────────────────────────────────────────────────────
W, H   = 960, 620
FPS    = 60
TILE   = 40

# ── Color palette ─────────────────────────────────────────────────────────────
BG          = (6,   6,  16)
GRID_DIM    = (18,  18, 35)
GRID_BRIGHT = (32,  32, 55)
PLAYER_COL  = (160, 80, 255)
CHAOS_COL   = (255, 190,  0)
MEH_COL     = (70,  70,  95)
MEH_HACKED  = (0,  220, 110)
FRAG_COL    = (0,  200, 180)
ENEMY_COL   = (210,  45,  75)
ENERGY_COL  = (80, 180, 255)
WHITE       = (255, 255, 255)
DIM         = (100, 100, 130)

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
]

# ── Gameplay tuning ───────────────────────────────────────────────────────────
PLAYER_SPEED        = 4.2
PLAYER_RADIUS       = 14
PLAYER_HACK_CD      = 2.0
PLAYER_INV_DURATION = 1.5
PLAYER_TRAIL_LEN    = 14
PLAYER_MAX_ENERGY   = 100
CHAOS_DURATION      = 9.0
CHAOS_SPEED_MULT    = 1.9
HACK_RANGE_NORMAL   = 85
HACK_RANGE_CHAOS    = 130

MEH_DEFAULT_HP      = 2
FRAG_ENERGY_REWARD  = 22
FRAG_SCORE_REWARD   = 50
MEH_ENERGY_REWARD   = 14
MEH_SCORE_REWARD    = 20
MEH_CHAOS_ENERGY    = 6
MEH_CHAOS_SCORE     = 10
ENEMY_SCORE_REWARD  = 35

ENEMY_SPEED_MIN     = 1.3
ENEMY_SPEED_MAX     = 2.4
ENEMY_CHASE_DIST    = 220
ENEMY_RADIUS        = 13
ENEMY_STUN_DURATION = 2.5

MEH_SPAWN_MIN       = 10   # replenish threshold
MEH_SPAWN_BATCH     = 6
FRAG_SPAWN_MIN      = 3
FRAG_SPAWN_BATCH    = 3
ENEMY_SPAWN_MIN     = 4

FRAG_POPUP_DURATION = 2.8
CONTROLS_FADE_TIME  = 10.0

# ── Audio ─────────────────────────────────────────────────────────────────────
MASTER_VOLUME       = 0.55
