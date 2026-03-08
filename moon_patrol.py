#!/usr/bin/env python3
"""Moon Patrol - 1990s style sideways scrolling arcade game"""

import pygame
import sys
import math
import random
import array
import os
import subprocess
import tempfile
from collections import deque

pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

# --- Constants ---
SCREEN_W, SCREEN_H = 1040, 780
FPS = 60
TILE = 8  # 8-bit pixel size

# Colors (limited palette, CGA/NES style)
BLACK   = (0, 0, 0)
WHITE   = (255, 255, 255)
GRAY    = (128, 128, 128)
DKGRAY  = (64, 64, 64)
RED     = (220, 40, 40)
ORANGE  = (220, 140, 40)
YELLOW  = (240, 220, 40)
GREEN   = (40, 200, 40)
DKGREEN = (20, 100, 20)
CYAN    = (40, 220, 220)
BLUE    = (40, 80, 220)
LTBLUE  = (100, 160, 255)
PURPLE  = (160, 40, 220)
MAGENTA = (220, 40, 180)
BROWN   = (140, 80, 40)
TAN     = (180, 140, 80)
LASER_BLUE   = (20, 80, 180)
MOON_SURFACE = (50, 50, 50)
MOON_DARK    = (35, 35, 35)
MOON_SHADOW  = (14, 14, 14)
SKY_TOP      = (5, 10, 30)
SKY_BOT      = (1, 5, 5)

# Game settings
GRAVITY       = 0.4
SCROLL_SPEED  = 2.2
PLAYER_SPEED  = 3.2
JUMP_VEL      = -10
BULLET_SPEED  = 8
LASER_SPEED   = BULLET_SPEED * 1.7
ALIEN_BULLET_SPEED = 3
LEVEL_LENGTH  = 12000   # pixels of terrain to generate

screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("MOON PATROL")
clock = pygame.time.Clock()

# ─────────────────────────────────────────────
# FONTS  (PressStart2P — 1980s arcade style)
# ─────────────────────────────────────────────
_FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'PressStart2P-Regular.ttf')
try:
    FONT_LG   = pygame.font.Font(_FONT_PATH, 22)
    FONT_MD   = pygame.font.Font(_FONT_PATH, 13)
    FONT_SM   = pygame.font.Font(_FONT_PATH, 10)
    FONT_TINY = pygame.font.Font(_FONT_PATH, 7)
    FONT_POPUP = pygame.font.Font(_FONT_PATH, 22)
    FONT_POPUP.set_italic(True)
except Exception:
    FONT_LG   = pygame.font.SysFont("monospace", 48, bold=True)
    FONT_MD   = pygame.font.SysFont("monospace", 24, bold=True)
    FONT_SM   = pygame.font.SysFont("monospace", 16, bold=True)
    FONT_TINY = pygame.font.SysFont("monospace", 11, bold=True)
    FONT_POPUP = pygame.font.SysFont("monospace", 36, bold=True, italic=True)

# ─────────────────────────────────────────────
# SOUND SYNTHESIS (modern sounds, programmatic)
# ─────────────────────────────────────────────
SAMPLE_RATE = 44100

def make_sound(samples):
    """Convert a list of float samples [-1,1] to a pygame Sound (stereo)."""
    mono = [int(s * 32767) for s in samples]
    stereo = []
    for v in mono:
        stereo.append(v)
        stereo.append(v)
    buf = array.array('h', stereo)
    return pygame.mixer.Sound(buffer=bytes(buf))

def sine(t, freq):
    return math.sin(2 * math.pi * freq * t)

def square(t, freq, duty=0.5):
    phase = (freq * t) % 1.0
    return 1.0 if phase < duty else -1.0

def noise():
    return random.uniform(-1, 1)

def adsr(t, dur, a=0.01, d=0.05, s=0.7, r=0.1):
    """ADSR envelope 0..1"""
    if t < a:
        return t / a
    elif t < a + d:
        return 1.0 - (1.0 - s) * (t - a) / d
    elif t < dur - r:
        return s
    elif t < dur:
        return s * (1.0 - (t - (dur - r)) / r)
    return 0.0

def gen_shoot_sound():
    dur = 0.18
    n = int(SAMPLE_RATE * dur)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        freq = 800 - 500 * (t / dur)
        env = adsr(t, dur, 0.005, 0.03, 0.4, 0.08)
        s = square(t, freq, 0.3) * 0.5 + sine(t, freq * 1.5) * 0.3
        samples.append(s * env * 0.7)
    return make_sound(samples)

def gen_explosion_sound():
    dur = 0.5
    n = int(SAMPLE_RATE * dur)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = adsr(t, dur, 0.002, 0.05, 0.3, 0.25)
        freq = 120 - 80 * (t / dur)
        s = noise() * 0.6 + sine(t, freq) * 0.3 + sine(t, freq * 2.1) * 0.1
        samples.append(s * env)
    return make_sound(samples)

def gen_alien_shoot_sound():
    dur = 0.22
    n = int(SAMPLE_RATE * dur)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        freq = 300 + 400 * (t / dur)
        env = adsr(t, dur, 0.005, 0.04, 0.5, 0.1)
        s = sine(t, freq) * 0.5 + square(t, freq * 0.5, 0.4) * 0.3
        samples.append(s * env * 0.6)
    return make_sound(samples)

def gen_jump_sound():
    dur = 0.15
    n = int(SAMPLE_RATE * dur)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        freq = 200 + 600 * (t / dur)
        env = adsr(t, dur, 0.005, 0.02, 0.6, 0.07)
        s = sine(t, freq) * 0.6 + sine(t, freq * 2) * 0.2
        samples.append(s * env)
    return make_sound(samples)

def gen_hit_sound():
    dur = 0.12
    n = int(SAMPLE_RATE * dur)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = adsr(t, dur, 0.002, 0.02, 0.4, 0.06)
        s = noise() * 0.5 + sine(t, 80) * 0.4
        samples.append(s * env)
    return make_sound(samples)

def gen_powerup_sound():
    dur = 0.4
    n = int(SAMPLE_RATE * dur)
    samples = []
    freqs = [440, 550, 660, 880]
    for i in range(n):
        t = i / SAMPLE_RATE
        fi = int(t / dur * len(freqs))
        fi = min(fi, len(freqs)-1)
        env = adsr(t, dur, 0.01, 0.05, 0.7, 0.1)
        s = sine(t, freqs[fi]) * 0.5 + sine(t, freqs[fi]*2) * 0.2
        samples.append(s * env * 0.8)
    return make_sound(samples)

def gen_win_sound():
    dur = 1.2
    n = int(SAMPLE_RATE * dur)
    samples = []
    melody = [523, 659, 784, 1047]
    seg = dur / len(melody)
    for i in range(n):
        t = i / SAMPLE_RATE
        mi = int(t / seg)
        mi = min(mi, len(melody)-1)
        lt = t - mi * seg
        env = adsr(lt, seg, 0.01, 0.03, 0.7, 0.1)
        f = melody[mi]
        s = sine(t, f) * 0.5 + sine(t, f*2) * 0.2 + sine(t, f*0.5) * 0.15
        samples.append(s * env * 0.8)
    return make_sound(samples)

def gen_robot_powerup_sound():
    """R2D2-style ascending triple chirp with ring modulation."""
    dur = 0.48
    n = int(SAMPLE_RATE * dur)
    samples = [0.0] * n
    chirps = [(0.00, 0.14, 380,  900),
              (0.16, 0.30, 620, 1300),
              (0.32, 0.48, 950, 2000)]
    carrier_freq = 75
    for t0, t1, f0, f1 in chirps:
        for i in range(int(t0 * SAMPLE_RATE), min(n, int(t1 * SAMPLE_RATE))):
            t  = i / SAMPLE_RATE
            lt = (t - t0) / (t1 - t0)
            freq = f0 + (f1 - f0) * lt
            env  = adsr(t - t0, t1 - t0, 0.005, 0.02, 0.75, 0.04)
            buzz = square(t, freq, 0.3) * 0.5 + sine(t, freq) * 0.5
            samples[i] = buzz * sine(t, carrier_freq) * env * 0.75
    return make_sound(samples)

def gen_robot_start_sound():
    """Robotic rising sweep + harmonic sting for level start."""
    dur = 0.9
    n = int(SAMPLE_RATE * dur)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        p   = t / dur
        freq    = 130 + 720 * (p ** 0.6)      # sweep 130→850 Hz
        carrier = 55 + 35 * p                  # carrier rises slightly
        env     = adsr(t, dur, 0.01, 0.05, 0.65, 0.25)
        buzz    = square(t, freq, 0.35) * 0.55 + sine(t, freq * 2) * 0.2
        s = buzz * sine(t, carrier) * env
        # Final chord sting in the last 25 %
        if p > 0.75:
            k = (p - 0.75) / 0.25
            s += (sine(t, 880) + sine(t, 1108) + sine(t, 1320)) * k * 0.18
        samples.append(s * 0.7)
    return make_sound(samples)

def gen_robot_gameover_sound():
    """Robotic descending wail with wobbling carrier for game over."""
    dur = 1.6
    n = int(SAMPLE_RATE * dur)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        p    = t / dur
        freq    = 580 * ((1 - p) ** 0.7) + 70  # sweep 650→70 Hz
        carrier = 48 + 28 * math.sin(t * 9)    # slow wobble
        env     = adsr(t, dur, 0.01, 0.12, 0.55, 0.45)
        buzz    = square(t, freq, 0.5) * 0.5 + sine(t, freq * 0.5) * 0.3
        samples.append(buzz * sine(t, carrier) * env * 0.8)
    return make_sound(samples)

def gen_wave_sound():
    """Low swooping pulse for wave fire."""
    dur = 0.5
    n = int(SAMPLE_RATE * dur)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        freq = 180 + 320 * (t / dur)          # sweep 180→500 Hz
        env = adsr(t, dur, 0.01, 0.1, 0.5, 0.3)
        s = sine(t, freq) * 0.6 + sine(t, freq * 1.5) * 0.25
        samples.append(s * env * 0.7)
    return make_sound(samples)

# Pre-generate sounds
SND_SHOOT    = pygame.mixer.Sound('/Users/nickhobson/Claude/gridrunner/data/spo.wav')
SND_EXPLODE  = gen_explosion_sound()
SND_ALIEN_SHOOT = gen_alien_shoot_sound()
SND_JUMP     = gen_jump_sound()
SND_HIT              = gen_hit_sound()
SND_WIN              = gen_win_sound()
SND_WAVE             = gen_wave_sound()
SND_ROBOT_POWERUP    = gen_robot_powerup_sound()
SND_ROBOT_START      = gen_robot_start_sound()
SND_ROBOT_GAMEOVER   = gen_robot_gameover_sound()

# ─────────────────────────────────────────────
# VOICE SYNTHESISER  (macOS 'say' + Zarvox)
# ─────────────────────────────────────────────
def _voice(text, voice='Zarvox', rate=105):
    """Generate a pygame Sound via macOS say/afconvert. Returns None on failure."""
    try:
        with tempfile.NamedTemporaryFile(suffix='.aiff', delete=False) as f:
            aiff = f.name
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            wav = f.name
        subprocess.run(
            ['say', '-v', voice, '-r', str(rate), '-o', aiff, text],
            check=True, capture_output=True)
        subprocess.run(
            ['afconvert', '-f', 'WAVE', '-d', 'LEI16@22050', aiff, wav],
            check=True, capture_output=True)
        snd = pygame.mixer.Sound(wav)
        os.unlink(aiff)
        os.unlink(wav)
        return snd
    except Exception:
        return None

VOX_TITLE      = _voice('Moon Patrol',  rate=90)
VOX_READY      = _voice('Get ready',    rate=100)
VOX_GAMEOVER   = _voice('Game over',    rate=85)
VOX_RAPIDFIRE  = _voice('Rapid fire')
VOX_SPREAD     = _voice('Spread shot')
VOX_WAVE       = _voice('Wave fire')
VOX_SPEED      = _voice('Speed boost')

def _vplay(snd):
    """Play a VOX sound if it was generated successfully."""
    if snd:
        snd.play()

# ─────────────────────────────────────────────
# TERRAIN GENERATION
# ─────────────────────────────────────────────
TERRAIN_GROUND_Y = 640  # baseline y on screen
TERRAIN_RESOLUTION = 4  # pixels per terrain sample

def generate_terrain(length):
    """Generate undulating moon surface heights (y positions, screen coords)."""
    points = length // TERRAIN_RESOLUTION + 10
    heights = []
    for i in range(points):
        x = i * TERRAIN_RESOLUTION
        y = (TERRAIN_GROUND_Y
             + 30 * math.sin(x * 0.003)
             + 20 * math.sin(x * 0.007 + 1.2)
             + 10 * math.sin(x * 0.015 + 0.5)
             + 8  * math.sin(x * 0.031 + 2.1))
        heights.append(y)
    # Add craters (dips)
    num_craters = length // 400
    for _ in range(num_craters):
        cx = random.randint(200, points - 200)
        cw = random.randint(15, 40)
        cd = random.randint(15, 35)
        for j in range(max(0, cx-cw), min(points, cx+cw)):
            dist = abs(j - cx) / cw
            heights[j] += cd * (1 - dist**2)
    # Add some rocks/bumps
    num_bumps = length // 200
    for _ in range(num_bumps):
        bx = random.randint(100, points - 100)
        bw = random.randint(5, 12)
        bd = random.randint(-20, -5)
        for j in range(max(0, bx-bw), min(points, bx+bw)):
            dist = abs(j - bx) / bw
            heights[j] += bd * (1 - dist)
    return heights

# ─────────────────────────────────────────────
# TANK DIMENSIONS & COLOURS
# ─────────────────────────────────────────────
TANK_HULL     = (48, 105, 36)
TANK_DARK     = (24,  56, 18)
TANK_LIGHT    = (62, 138, 48)
TURRET_COL    = (60, 128, 45)
GUN_COL       = (28,  62, 20)
TURRET_RADIUS = 9
GUN_LENGTH    = 32
GUN_WIDTH     = 5

VEHICLE_W  = 48
VEHICLE_H  = 30
_TRACK_H   = 13   # caterpillar track height (bottom of tank)
_HULL_H    = VEHICLE_H - _TRACK_H   # hull body height
_SPUR_R    = 6    # sprocket radius at each end
_ROAD_R    = 4    # road wheel radius
_LINK_W    = 6    # one track-link segment width

# ─────────────────────────────────────────────
# ALIEN SPRITE (8-bit pixel art)
# ─────────────────────────────────────────────
ALIEN_PIXELS = [
    "..RRRR..",
    ".RRRRRR.",
    "RRGRRGRR",
    "RRRRRRRR",
    ".RRRRRR.",
    "..R..R..",
    ".RR..RR.",
]
def build_alien_surf(color=RED):
    pw = 3
    surf = pygame.Surface((8*pw, 7*pw), pygame.SRCALPHA)
    cmap = {'R': color, 'G': GREEN, '.': None}
    for row, line in enumerate(ALIEN_PIXELS):
        for col, ch in enumerate(line):
            c = cmap.get(ch)
            if c:
                pygame.draw.rect(surf, c, (col*pw, row*pw, pw, pw))
    return surf

ALIEN_SURF_R = build_alien_surf(RED)
ALIEN_SURF_P = build_alien_surf(PURPLE)
ALIEN_SURF_C = build_alien_surf(CYAN)
ALIEN_SURF_O = build_alien_surf(ORANGE)
ALIEN_SURFS = [ALIEN_SURF_R, ALIEN_SURF_P, ALIEN_SURF_C, ALIEN_SURF_O]

# ─────────────────────────────────────────────
# EXPLOSION PARTICLE
# ─────────────────────────────────────────────
class Particle:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        angle = random.uniform(0, 2*math.pi)
        speed = random.uniform(2, 8)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed - 2
        self.life = random.randint(20, 40)
        self.max_life = self.life
        colors = [RED, ORANGE, YELLOW, WHITE]
        self.color = random.choice(colors)
        self.size = random.randint(2, 6)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.3
        self.life -= 1

    def draw(self, surf):
        if self.life > 0:
            t = self.life / self.max_life
            c = (int(self.color[0] * t), int(self.color[1] * t), int(self.color[2] * t))
            pygame.draw.rect(surf, c, (int(self.x), int(self.y), self.size, self.size))

# ─────────────────────────────────────────────
# STAR FIELD
# ─────────────────────────────────────────────
STARS = [(random.randint(0, SCREEN_W), random.randint(0, TERRAIN_GROUND_Y - 50),
          random.choice([1, 1, 1, 2]), random.uniform(0.2, 1.0))
         for _ in range(150)]

# Pre-built sky gradient surface (replaces 640 draw.line calls per frame)
_SKY_SURF = pygame.Surface((SCREEN_W, TERRAIN_GROUND_Y))
for _y in range(TERRAIN_GROUND_Y):
    _t = _y / TERRAIN_GROUND_Y
    _r = int(SKY_TOP[0] + (SKY_BOT[0] - SKY_TOP[0]) * _t)
    _g = int(SKY_TOP[1] + (SKY_BOT[1] - SKY_TOP[1]) * _t)
    _b = int(SKY_TOP[2] + (SKY_BOT[2] - SKY_TOP[2]) * _t)
    pygame.draw.line(_SKY_SURF, (_r, _g, _b), (0, _y), (SCREEN_W, _y))

# ─────────────────────────────────────────────
# GAME ENTITIES
# ─────────────────────────────────────────────
class Bullet:
    def __init__(self, x, y, vx, vy, color, owner='player'):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.owner = owner
        self.alive = True
        self.w, self.h = 6, 3
        self.max_trail = 18 if owner == 'player' else 0
        self.trail = deque(maxlen=self.max_trail) if self.max_trail else []

    def update(self):
        if self.max_trail:
            self.trail.append((self.x, self.y))
        self.x += self.vx
        self.y += self.vy
        if self.x > SCREEN_W + 50 or self.x < -50 or self.y < -50 or self.y > SCREEN_H + 50:
            self.alive = False

    def draw(self, surf):
        if self.owner == 'player':
            self._draw_laser(surf)
        else:
            pygame.draw.rect(surf, self.color, (int(self.x), int(self.y), self.w, self.h))
            pygame.draw.rect(surf, WHITE, (int(self.x)+1, int(self.y)+1, self.w-2, 1))

    def _draw_laser(self, surf):
        all_pts = list(self.trail) + [(self.x, self.y)]
        n = len(all_pts)
        if n >= 2:
            for i in range(n - 1):
                t = (i + 1) / n  # 0=oldest/dim, 1=newest/bright
                x1 = int(all_pts[i][0] + self.w // 2)
                y1 = int(all_pts[i][1] + self.h // 2)
                x2 = int(all_pts[i+1][0] + self.w // 2)
                y2 = int(all_pts[i+1][1] + self.h // 2)
                # Outer glow — fades to black at tail
                pygame.draw.line(surf,
                    (int(10 * t), int(40 * t), int(85 * t)),
                    (x1, y1), (x2, y2), 6)
                # Core beam — fades to black at tail
                pygame.draw.line(surf,
                    (int(self.color[0] * t), int(self.color[1] * t), int(self.color[2] * t)),
                    (x1, y1), (x2, y2), 2)

class Bomb:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = random.uniform(-1, 1)
        self.vy = 0
        self.alive = True
        self.w, self.h = 6, 8

    def update(self, terrain_heights, camera_x):
        self.vy += GRAVITY * 0.4
        self.x += self.vx
        self.y += self.vy
        # Check ground collision
        screen_x = int(self.x)
        terrain_x = int((screen_x + camera_x) / TERRAIN_RESOLUTION)
        terrain_x = max(0, min(terrain_x, len(terrain_heights)-1))
        ground_y = terrain_heights[terrain_x]
        if self.y + self.h >= ground_y:
            self.alive = False

    def draw(self, surf):
        # Bomb shape
        pygame.draw.ellipse(surf, ORANGE, (int(self.x), int(self.y), self.w, self.h))
        pygame.draw.line(surf, YELLOW, (int(self.x)+3, int(self.y)),
                         (int(self.x)+3, int(self.y)-5), 2)

class Coin:
    def __init__(self, world_x, world_y, color):
        self.world_x = float(world_x)
        self.world_y = float(world_y)
        self.vx = random.uniform(-2, 2)
        self.vy = random.uniform(-5, -2)
        self.color = color
        self.alive = True
        self.settled = False
        self.r = 6
        self.lifetime = 420  # 7 seconds

    def update(self, terrain_heights, camera_x):
        self.lifetime -= 1
        if self.lifetime <= 0:
            self.alive = False
            return
        if not self.settled:
            self.vy += GRAVITY * 0.8
            self.world_x += self.vx
            self.world_y += self.vy
            tidx = max(0, min(int(self.world_x / TERRAIN_RESOLUTION), len(terrain_heights)-1))
            if self.world_y + self.r >= terrain_heights[tidx]:
                self.world_y = terrain_heights[tidx] - self.r
                self.vy = 0
                self.vx = 0
                self.settled = True
        sx = self.world_x - camera_x
        if sx < -60 or sx > SCREEN_W + 60:
            self.alive = False

    def draw(self, surf, camera_x):
        sx = int(self.world_x - camera_x)
        sy = int(self.world_y)
        if -10 < sx < SCREEN_W + 10:
            pygame.draw.circle(surf, self.color, (sx, sy), self.r)
            shine = tuple(min(255, c + 90) for c in self.color)
            pygame.draw.circle(surf, shine, (sx - 2, sy - 2), 2)
            pygame.draw.circle(surf, WHITE, (sx, sy), self.r, 1)

WAVE_COLOR      = (180, 60, 220)   # purple
WAVE_SPEED      = 8                # px per frame expansion (×1.2 from original 5)
WAVE_WIDTH      = 5                # arc stroke width (px)
WAVE_ARC_MAX    = math.radians(7.5)  # half-angle → full arc = 15°
WAVE_ARC_GROW   = math.radians(0.35) # half-angle added per frame
WAVE_KILL_R     = SCREEN_W + SCREEN_H + 300  # die once unreachable
WAVE_TRAIL_LEN  = 50               # ghost snapshots kept for trail

class Wave:
    """Expanding arc fired along the gun's aim direction (max 15° wide)."""
    def __init__(self, x, y, angle):
        self.x = x
        self.y = y
        self.angle = angle
        self.r = float(GUN_LENGTH)
        self.half_arc = math.radians(1.5)
        self.alive = True
        self.trail = deque()   # each entry: (r, half_arc)

    def update(self):
        # snapshot before moving — builds the trail behind the head
        self.trail.append((self.r, self.half_arc))
        if len(self.trail) > WAVE_TRAIL_LEN:
            self.trail.popleft()
        self.r += WAVE_SPEED
        self.half_arc = min(WAVE_ARC_MAX, self.half_arc + WAVE_ARC_GROW)
        if self.r > WAVE_KILL_R:
            self.alive = False

    def _draw_arc(self, surf, cx, cy, r, half_arc, color, width):
        r = int(r)
        if r < width:
            return
        rect = pygame.Rect(cx - r, cy - r, r * 2, r * 2)
        pa = -self.angle
        pygame.draw.arc(surf, color, rect, pa - half_arc, pa + half_arc, min(r, width))

    def draw(self, surf):
        if not self.alive:
            return
        cx, cy = int(self.x), int(self.y)

        # Trail — ghost arcs fading from dim to bright toward the head
        n = len(self.trail)
        for i, (tr, tha) in enumerate(self.trail):
            fade = (i + 1) / (n + 1)   # 0=oldest, approaches 1 near head
            tc = (int(WAVE_COLOR[0] * fade * 0.55),
                  int(WAVE_COLOR[1] * fade * 0.55),
                  int(WAVE_COLOR[2] * fade * 0.55))
            self._draw_arc(surf, cx, cy, tr, tha, tc, max(1, WAVE_WIDTH - 2))

        # Head — glow then bright core
        self._draw_arc(surf, cx, cy, self.r, self.half_arc, (100, 0, 160), WAVE_WIDTH + 6)
        self._draw_arc(surf, cx, cy, self.r, self.half_arc, WAVE_COLOR,    WAVE_WIDTH)
        self._draw_arc(surf, cx, cy, self.r, self.half_arc, (230, 160, 255), max(1, WAVE_WIDTH - 2))

    def hits_alien(self, alien):
        """True if the arc ring band currently sweeps over the alien."""
        ax = alien.screen_x + alien.w // 2
        ay = alien.y + alien.h // 2
        dist = math.hypot(ax - self.x, ay - self.y)
        if abs(dist - self.r) > alien.w // 2 + WAVE_WIDTH + 2:
            return False
        # Angle check — is alien within the arc sweep?
        alien_angle = math.atan2(ay - self.y, ax - self.x)
        diff = (alien_angle - self.angle + math.pi) % (2 * math.pi) - math.pi
        return abs(diff) <= self.half_arc


class Alien:
    TYPES = ['swooper', 'hoverer', 'diver']
    _COLORS = [RED, PURPLE, CYAN, ORANGE]

    def __init__(self, screen_x, world_x):
        self.world_x = world_x
        self.screen_x = screen_x
        self.y = random.randint(80, 200)
        self.type = random.choice(self.TYPES)
        color_idx = random.randint(0, len(self._COLORS) - 1)
        self.surf = ALIEN_SURFS[color_idx]
        self.coin_color = self._COLORS[color_idx]
        self.w = self.surf.get_width()
        self.h = self.surf.get_height()
        self.alive = True
        self.hp = 2
        self.shoot_timer = random.randint(120, 360)
        self.bomb_timer = random.randint(180, 480)
        self.anim_t = random.uniform(0, 100)
        # Movement
        self.vx = random.uniform(-1.5, -0.5) * 0.7
        self.base_y = self.y
        self.flash_timer = 0

    def update(self, bullets, bombs, player_screen_x, player_y, camera_x):
        self.anim_t += 0.05
        # Hovering motion
        if self.type == 'hoverer':
            self.y = self.base_y + math.sin(self.anim_t) * 30
        elif self.type == 'swooper':
            self.y = self.base_y + math.sin(self.anim_t * 1.5) * 60
        elif self.type == 'diver':
            self.y = self.base_y + abs(math.sin(self.anim_t * 0.8)) * 80

        self.screen_x += self.vx - SCROLL_SPEED * 0.5
        if self.screen_x < -100:
            self.alive = False

        if self.flash_timer > 0:
            self.flash_timer -= 1

        # Shooting at player
        self.shoot_timer -= 1
        if self.shoot_timer <= 0:
            self.shoot_timer = random.randint(120, 360)
            dx = player_screen_x - self.screen_x
            dy = player_y - self.y
            dist = max(1, math.sqrt(dx*dx + dy*dy))
            vx = dx/dist * ALIEN_BULLET_SPEED
            vy = dy/dist * ALIEN_BULLET_SPEED
            b = Bullet(self.screen_x + self.w//2, self.y + self.h//2,
                       vx, vy, MAGENTA, 'alien')
            bullets.append(b)
            SND_ALIEN_SHOOT.play()

        # Dropping bombs
        self.bomb_timer -= 1
        if self.bomb_timer <= 0:
            self.bomb_timer = random.randint(180, 480)
            bombs.append(Bomb(self.screen_x + self.w//2, self.y + self.h))

    def draw(self, surf):
        if self.flash_timer > 0 and self.flash_timer % 4 < 2:
            flash_surf = self.surf.copy()
            flash_surf.fill(WHITE, special_flags=pygame.BLEND_RGB_ADD)
            surf.blit(flash_surf, (int(self.screen_x), int(self.y)))
        else:
            surf.blit(self.surf, (int(self.screen_x), int(self.y)))
        # HP bar
        for i in range(self.hp):
            pygame.draw.rect(surf, GREEN, (int(self.screen_x) + i*8, int(self.y)-6, 6, 3))

# ─────────────────────────────────────────────
# PLAYER
# ─────────────────────────────────────────────
class Player:
    def __init__(self):
        self.x = 80.0
        self.y = float(TERRAIN_GROUND_Y - VEHICLE_H - 15)
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.shoot_cooldown = 0
        self.lives = 3
        self.score = 0
        self.invincible = 0
        # Track contact offsets (front and rear)
        self.wheel_offsets = [(6, VEHICLE_H - 4), (VEHICLE_W - 11, VEHICLE_H - 4)]
        self.tilt = 0.0  # body tilt angle
        self.fire_rate_boost = 0  # frames remaining for rapid-fire
        self.spread_shot = 0     # frames remaining for spread shot
        self.cyan_coins = 0      # cyan coins collected toward next spread activation
        self.purple_coins = 0   # purple coins collected toward wave fire
        self.wave_fire = 0      # frames remaining for wave fire powerup
        self.orange_coins = 0   # orange coins collected toward bullet speedup
        self.bullet_speedup = 0 # frames remaining for bullet speedup powerup
        self.dead = False
        self.dead_timer = 0

    def get_ground_y(self, terrain_heights, camera_x):
        """Get ground y under player center."""
        world_x = self.x + camera_x
        idx = int(world_x / TERRAIN_RESOLUTION)
        idx = max(0, min(idx, len(terrain_heights)-1))
        return terrain_heights[idx]

    def get_wheel_ground_y(self, terrain_heights, camera_x, offset_x):
        """Ground y under a specific wheel."""
        world_x = (self.x + offset_x) + camera_x
        idx = int(world_x / TERRAIN_RESOLUTION)
        idx = max(0, min(idx, len(terrain_heights)-1))
        return terrain_heights[idx]

    def update(self, keys, terrain_heights, camera_x, bullets, waves):
        if self.dead:
            self.dead_timer -= 1
            return

        if self.invincible > 0:
            self.invincible -= 1

        # Horizontal movement
        moving = False
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.vx = -PLAYER_SPEED
            moving = True
        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.vx = PLAYER_SPEED
            moving = True
        else:
            self.vx *= 0.7

        self.x += self.vx
        self.x = max(10, min(self.x, SCREEN_W - VEHICLE_W - 10))

        # Gravity
        self.vy += GRAVITY
        self.y += self.vy

        # Wheel positions for ground detection
        wy1 = self.get_wheel_ground_y(terrain_heights, camera_x, self.wheel_offsets[0][0])
        wy2 = self.get_wheel_ground_y(terrain_heights, camera_x, self.wheel_offsets[1][0])
        ground_y = min(wy1, wy2)  # highest point (lowest y value) wins

        # Land on ground
        vehicle_bottom = self.y + VEHICLE_H - 6  # wheels bottom
        if vehicle_bottom >= ground_y and self.vy >= 0:
            self.y = ground_y - VEHICLE_H + 6
            self.vy = 0
            self.on_ground = True
        else:
            self.on_ground = False

        # Compute tilt from wheel heights
        dy = wy2 - wy1
        dx = self.wheel_offsets[1][0] - self.wheel_offsets[0][0]
        self.tilt = math.atan2(dy, dx)

        # Jump
        if (keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w]) and self.on_ground:
            self.vy = JUMP_VEL
            self.on_ground = False
            SND_JUMP.play()

        # Shoot (up-right)
        self.shoot_cooldown -= 1
        if self.fire_rate_boost > 0:
            self.fire_rate_boost -= 1
        if self.spread_shot > 0:
            self.spread_shot -= 1
        if self.wave_fire > 0:
            self.wave_fire -= 1
        if self.bullet_speedup > 0:
            self.bullet_speedup -= 1
        shoot_cd = 13 if self.fire_rate_boost > 0 else 18
        if (keys[pygame.K_LCTRL] or keys[pygame.K_z] or keys[pygame.K_x]) and self.shoot_cooldown <= 0:
            self.shoot_cooldown = shoot_cd
            tx = self.x + VEHICLE_W // 2
            ty = self.y + VEHICLE_H // 3
            mx, my = pygame.mouse.get_pos()
            dx = mx - tx
            dy = my - ty
            dist = max(1, math.sqrt(dx*dx + dy*dy))
            ndx, ndy = dx / dist, dy / dist
            bx = tx + ndx * GUN_LENGTH
            by = ty + ndy * GUN_LENGTH
            spd = LASER_SPEED * 2 if self.bullet_speedup > 0 else LASER_SPEED
            bullets.append(Bullet(bx, by, ndx * spd, ndy * spd, LASER_BLUE, 'player'))
            if self.spread_shot > 0:
                a = math.radians(5)
                ca, sa = math.cos(a), math.sin(a)
                bullets.append(Bullet(bx, by,
                                      (ndx * ca - ndy * sa) * spd,
                                      (ndx * sa + ndy * ca) * spd,
                                      LASER_BLUE, 'player'))
            if self.wave_fire > 0 and len(waves) < 2:
                waves.append(Wave(bx, by, math.atan2(ndy, ndx)))
                SND_WAVE.play()
            SND_SHOOT.play()

    def hit(self):
        if self.invincible > 0:
            return False
        self.lives = max(0, self.lives - 1)
        self.invincible = 90
        SND_HIT.play()
        return True

    def draw(self, surf):
        if self.dead:
            return

        # Blink when invincible
        if self.invincible > 0 and (self.invincible // 6) % 2 == 0:
            return

        # Build full tank on a temporary surface then rotate to match terrain tilt
        tank = pygame.Surface((VEHICLE_W, VEHICLE_H), pygame.SRCALPHA)

        # ── Caterpillar tracks ────────────────────────────────────────────
        ty0 = _HULL_H   # y where tracks begin on the temp surface
        # Outer track band
        pygame.draw.rect(tank, TANK_DARK, (0, ty0, VEHICLE_W, _TRACK_H))
        # Sprocket wheels at left and right ends
        spr_cy = ty0 + _TRACK_H // 2
        for spr_x in (_SPUR_R, VEHICLE_W - _SPUR_R):
            pygame.draw.circle(tank, (40, 90, 30),  (spr_x, spr_cy), _SPUR_R)
            pygame.draw.circle(tank, TANK_HULL,      (spr_x, spr_cy), _SPUR_R - 2)
            pygame.draw.circle(tank, TANK_DARK,      (spr_x, spr_cy), _SPUR_R,     1)
            pygame.draw.circle(tank, TANK_DARK,      (spr_x, spr_cy), _SPUR_R - 3, 1)
        # Road wheels between sprockets
        road_cy = spr_cy
        for rwx in (15, 24, 33):
            pygame.draw.circle(tank, (38, 84, 28), (rwx, road_cy), _ROAD_R)
            pygame.draw.circle(tank, TANK_DARK,    (rwx, road_cy), _ROAD_R, 1)
        # Upper and lower track run bands (lighter strip)
        pygame.draw.rect(tank, (42, 92, 32), (_SPUR_R, ty0,                  VEHICLE_W - _SPUR_R * 2, 2))
        pygame.draw.rect(tank, (42, 92, 32), (_SPUR_R, ty0 + _TRACK_H - 2,  VEHICLE_W - _SPUR_R * 2, 2))
        # Animated track links along upper & lower runs
        anim = int(self.x * 0.45) % _LINK_W
        for lx in range(_SPUR_R - anim, VEHICLE_W - _SPUR_R + _LINK_W, _LINK_W):
            if _SPUR_R <= lx <= VEHICLE_W - _SPUR_R:
                pygame.draw.line(tank, TANK_DARK, (lx, ty0),                (lx, ty0 + 2),              1)
                pygame.draw.line(tank, TANK_DARK, (lx, ty0 + _TRACK_H - 2), (lx, ty0 + _TRACK_H - 1),  1)

        # ── Hull body ─────────────────────────────────────────────────────
        hx = 3   # hull inset from vehicle edge
        hw = VEHICLE_W - hx * 2
        pygame.draw.rect(tank, TANK_HULL,  (hx, 2, hw, _HULL_H - 1))          # main body
        pygame.draw.rect(tank, TANK_LIGHT, (hx + 2, 3, hw - 4, 3))            # top highlight
        pygame.draw.rect(tank, TANK_DARK,  (hx + hw - 5, 3, 5, _HULL_H - 4)) # right shadow
        pygame.draw.line(tank, TANK_DARK,  (hx, _HULL_H), (hx + hw, _HULL_H), 1)  # bottom edge

        # ── Rotate entire tank surface to terrain tilt ────────────────────
        rotated = pygame.transform.rotate(tank, -math.degrees(self.tilt))
        rw, _ = rotated.get_size()
        surf.blit(rotated, (int(self.x) - (rw - VEHICLE_W) // 2, int(self.y)))

        # ── Turret & gun (drawn on main surf, not rotated surface) ────────
        tx = int(self.x + VEHICLE_W // 2)
        ty = int(self.y + VEHICLE_H // 3)

        mx, my = pygame.mouse.get_pos()
        angle = math.atan2(my - ty, mx - tx)
        gx = tx + int(math.cos(angle) * GUN_LENGTH)
        gy = ty + int(math.sin(angle) * GUN_LENGTH)
        pygame.draw.line(surf, (14, 34, 10), (tx, ty), (gx, gy), GUN_WIDTH + 2)
        pygame.draw.line(surf, GUN_COL,      (tx, ty), (gx, gy), GUN_WIDTH)

        pygame.draw.circle(surf, (20, 48, 14),  (tx, ty), TURRET_RADIUS + 1)
        pygame.draw.circle(surf, TURRET_COL,    (tx, ty), TURRET_RADIUS)
        pygame.draw.circle(surf, (90, 170, 65), (tx - 2, ty - 2), 3)

# ─────────────────────────────────────────────
# TERRAIN RENDERING
# ─────────────────────────────────────────────
def draw_terrain(surf, terrain_heights, camera_x):
    cam_idx = int(camera_x / TERRAIN_RESOLUTION)
    pts_screen = int(SCREEN_W / TERRAIN_RESOLUTION) + 2

    # Build polygon for terrain surface
    poly = [(0, SCREEN_H)]
    for i in range(pts_screen):
        idx = cam_idx + i
        if 0 <= idx < len(terrain_heights):
            sx = i * TERRAIN_RESOLUTION
            sy = int(terrain_heights[idx])
            poly.append((sx, sy))
    poly.append((SCREEN_W, SCREEN_H))

    if len(poly) >= 3:
        # Draw the moon body
        pygame.draw.polygon(surf, MOON_SURFACE, poly)
        # Surface details
        for i in range(1, len(poly)-1):
            x, y = poly[i]
            if i % 3 == 0:
                pygame.draw.line(surf, MOON_DARK, (x, y), (x+2, y+4), 1)
        # Surface top line
        top_pts = poly[1:-1]
        if len(top_pts) > 1:
            pygame.draw.lines(surf, MOON_DARK, False, top_pts, 2)
        # Shadow rim
        shadow_pts = [(p[0], p[1]+4) for p in top_pts]
        if len(shadow_pts) > 1:
            pygame.draw.lines(surf, MOON_SHADOW, False, shadow_pts, 1)

    # Draw craters on surface (world-stable: seeded per 512-px world chunk)
    _rng = random.Random()
    _chunk_w = 512
    for chunk in range(int(camera_x / _chunk_w), int((camera_x + SCREEN_W) / _chunk_w) + 1):
        _rng.seed(chunk * 6173 + 1001)
        for _ in range(4):
            world_rx = chunk * _chunk_w + _rng.randint(0, _chunk_w - 1)
            rx = world_rx - camera_x
            if rx < -30 or rx > SCREEN_W + 30:
                continue
            ridx = max(0, min(int(world_rx / TERRAIN_RESOLUTION), len(terrain_heights) - 1))
            ry = int(terrain_heights[ridx])
            cr = _rng.randint(8, 20)
            pygame.draw.ellipse(surf, MOON_DARK, (rx - cr, ry - cr // 3, cr * 2, cr // 2))
            pygame.draw.arc(surf, MOON_SHADOW, (rx - cr, ry - cr // 3, cr * 2, cr // 2),
                            math.pi, 2 * math.pi, 1)

def draw_rocks(surf, camera_x, terrain_heights):
    """Draw decorative rocks on terrain (world-stable: seeded per 320-px world chunk)."""
    _rng = random.Random()
    _chunk_w = 320
    _cols = [MOON_DARK, DKGRAY, BROWN]
    for chunk in range(int(camera_x / _chunk_w), int((camera_x + SCREEN_W) / _chunk_w) + 1):
        _rng.seed(chunk * 8191 + 7777)
        for _ in range(5):
            world_rx = chunk * _chunk_w + _rng.randint(0, _chunk_w - 1)
            rx = world_rx - camera_x
            if rx < -30 or rx > SCREEN_W + 30:
                continue
            ridx = max(0, min(int(world_rx / TERRAIN_RESOLUTION), len(terrain_heights) - 1))
            ry = int(terrain_heights[ridx])
            rh = _rng.randint(4, 16)
            rw = _rng.randint(6, 20)
            col = _cols[_rng.randint(0, len(_cols) - 1)]
            pygame.draw.ellipse(surf, col, (rx - rw // 2, ry - rh, rw, rh))
            pygame.draw.ellipse(surf, MOON_SHADOW, (rx - rw // 2 + 1, ry - rh + rh // 2, rw - 2, rh // 2))

# ─────────────────────────────────────────────
# SKY / BACKGROUND
# ─────────────────────────────────────────────
def draw_sky(surf, camera_x):
    # Gradient sky (single blit from pre-built surface)
    surf.blit(_SKY_SURF, (0, 0))

    # Stars (parallax)
    for (sx, sy, size, brightness) in STARS:
        star_x = int((sx - camera_x * 0.05) % SCREEN_W)
        c = int(brightness * 255)
        col = (c, c, c)
        surf.set_at((star_x, sy), col)
        if size > 1:
            surf.set_at((star_x+1, sy), col)
            surf.set_at((star_x, sy+1), col)

    # Moon in background (parallax)
    moon_x = int(600 - camera_x * 0.03) % (SCREEN_W + 200) - 100
    moon_y = 80
    pygame.draw.circle(surf, (230, 230, 200), (moon_x, moon_y), 45)
    pygame.draw.circle(surf, (200, 200, 170), (moon_x, moon_y), 45, 2)
    # Craters on bg moon
    for cx, cy, cr in [(moon_x-15, moon_y+5, 8), (moon_x+12, moon_y-10, 6), (moon_x-5, moon_y+15, 5)]:
        pygame.draw.circle(surf, (210, 210, 180), (cx, cy), cr)
        pygame.draw.circle(surf, (190, 190, 160), (cx, cy), cr, 1)

    # Distant mountains (parallax layer 2) — local RNG so global state is unaffected
    _mrng = random.Random(42)
    for i in range(12):
        mx = int((i * 200 - camera_x * 0.15) % (SCREEN_W + 200)) - 50
        mh = _mrng.randint(40, 100)
        mw = _mrng.randint(60, 120)
        pts = [(mx, TERRAIN_GROUND_Y), (mx+mw//2, TERRAIN_GROUND_Y-mh), (mx+mw, TERRAIN_GROUND_Y)]
        pygame.draw.polygon(surf, (35, 32, 50), pts)
        pygame.draw.lines(surf, (50, 45, 70), False, pts[:-1], 1)

# ─────────────────────────────────────────────
# POWERUP POPUP
# ─────────────────────────────────────────────
class PowerupPopup:
    DURATION = 90  # 1.5 s at 60 fps

    def __init__(self, text):
        self.text   = text
        self.timer  = self.DURATION

    @property
    def alive(self):
        return self.timer > 0

    def update(self):
        self.timer -= 1

def draw_popup(surf, popup):
    if popup is None or not popup.alive:
        return

    frame    = PowerupPopup.DURATION - popup.timer   # 0 → DURATION
    t_norm   = popup.timer / PowerupPopup.DURATION   # 1 → 0

    # Fade in over first 15 %, hold, fade out over last 20 %
    if t_norm > 0.85:
        alpha = int(255 * (1.0 - t_norm) / 0.15)
    elif t_norm < 0.20:
        alpha = int(255 * t_norm / 0.20)
    else:
        alpha = 255

    # Per-character shimmer: each letter has a phase offset → wave of colour
    chars = list(popup.text)
    char_surfs = []
    for i, ch in enumerate(chars):
        phase = frame * 0.30 + i * 0.55
        r = 255
        g = int(160 + 95 * abs(math.sin(phase)))
        b = int(30  + 120 * abs(math.sin(phase + 1.4)))
        s = FONT_POPUP.render(ch, True, (r, g, b))
        char_surfs.append(s)

    if not char_surfs:
        return

    total_w = sum(s.get_width() for s in char_surfs)
    ch_h    = char_surfs[0].get_height()

    # Subtle vertical float
    float_y = int(6 * math.sin(frame * 0.12))

    cx = SCREEN_W // 2 - total_w // 2
    cy = SCREEN_H // 2 - ch_h // 2 + float_y

    # Shadow pass (dark, offset)
    sx = cx + 3
    sy = cy + 3
    for s in char_surfs:
        shadow = FONT_POPUP.render(list(popup.text)[char_surfs.index(s)], True, (20, 10, 40))
        shadow.set_alpha(alpha // 2)
        surf.blit(shadow, (sx, sy))
        sx += s.get_width()

    # Main shimmer pass
    x = cx
    for s in char_surfs:
        s.set_alpha(alpha)
        surf.blit(s, (x, cy))
        x += s.get_width()

# ─────────────────────────────────────────────
# HUD
# ─────────────────────────────────────────────
def draw_hud(surf, player, camera_x, level_length):
    surf.blit(FONT_SM.render(f"SCORE: {player.score:06d}", True, YELLOW), (10, 8))
    surf.blit(FONT_SM.render(f"LIVES: {'* ' * player.lives}", True, CYAN), (10, 26))

    # Progress bar
    progress = min(1.0, camera_x / (level_length - SCREEN_W))
    bar_w = 260
    bar_x = SCREEN_W//2 - bar_w//2
    pygame.draw.rect(surf, DKGRAY, (bar_x, 10, bar_w, 10))
    pygame.draw.rect(surf, GREEN, (bar_x, 10, int(bar_w * progress), 10))
    pygame.draw.rect(surf, WHITE, (bar_x, 10, bar_w, 10), 1)
    surf.blit(FONT_TINY.render("CHECKPOINT", True, WHITE), (bar_x + bar_w + 8, 8))

    # Rapid-fire indicator
    if player.fire_rate_boost > 0:
        secs = math.ceil(player.fire_rate_boost / 60)
        surf.blit(FONT_TINY.render(f"RAPID FIRE  {secs}s", True, RED), (SCREEN_W - 160, 8))

    # Spread-shot indicator / cyan coin progress
    if player.spread_shot > 0:
        secs = math.ceil(player.spread_shot / 60)
        surf.blit(FONT_TINY.render(f"SPREAD  {secs}s", True, CYAN), (SCREEN_W - 160, 22))
    elif player.cyan_coins > 0:
        surf.blit(FONT_TINY.render(f"SPREAD  {'o' * player.cyan_coins}{'.' * (3 - player.cyan_coins)}", True, CYAN), (SCREEN_W - 160, 22))

    # Wave fire indicator
    if player.wave_fire > 0:
        secs = math.ceil(player.wave_fire / 60)
        surf.blit(FONT_TINY.render(f"WAVE FIRE  {secs}s", True, PURPLE), (SCREEN_W - 160, 36))
    elif player.purple_coins > 0:
        surf.blit(FONT_TINY.render(f"WAVE  {'o' * player.purple_coins}{'.' * (3 - player.purple_coins)}", True, PURPLE), (SCREEN_W - 160, 36))

    # Bullet speedup indicator
    if player.bullet_speedup > 0:
        secs = math.ceil(player.bullet_speedup / 60)
        surf.blit(FONT_TINY.render(f"SPD X2  {secs}s", True, ORANGE), (SCREEN_W - 160, 50))
    elif player.orange_coins > 0:
        surf.blit(FONT_TINY.render(f"SPD X2  {'o' * player.orange_coins}{'.' * (3 - player.orange_coins)}", True, ORANGE), (SCREEN_W - 160, 50))

    # Controls reminder
    surf.blit(FONT_TINY.render("ARROWS/WASD:MOVE  SPACE:JUMP  LMB:FIRE", True, GRAY), (10, SCREEN_H - 18))

# ─────────────────────────────────────────────
# CROSSHAIR
# ─────────────────────────────────────────────
def draw_crosshair(surf, pos):
    x, y = int(pos[0]), int(pos[1])
    size = 14
    gap = 5
    color = YELLOW
    outline = BLACK
    thickness = 2
    # Outline for visibility
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        pygame.draw.line(surf, outline, (x - size + dx, y + dy), (x - gap + dx, y + dy), thickness)
        pygame.draw.line(surf, outline, (x + gap + dx, y + dy), (x + size + dx, y + dy), thickness)
        pygame.draw.line(surf, outline, (x + dx, y - size + dy), (x + dx, y - gap + dy), thickness)
        pygame.draw.line(surf, outline, (x + dx, y + gap + dy), (x + dx, y + size + dy), thickness)
    # Main crosshair lines
    pygame.draw.line(surf, color, (x - size, y), (x - gap, y), thickness)
    pygame.draw.line(surf, color, (x + gap, y), (x + size, y), thickness)
    pygame.draw.line(surf, color, (x, y - size), (x, y - gap), thickness)
    pygame.draw.line(surf, color, (x, y + gap), (x, y + size), thickness)
    # Center dot
    pygame.draw.circle(surf, outline, (x, y), 3)
    pygame.draw.circle(surf, color, (x, y), 2)

# ─────────────────────────────────────────────
# FINISH LINE
# ─────────────────────────────────────────────
def draw_finish(surf, finish_screen_x, terrain_heights, camera_x):
    ridx = int((finish_screen_x + camera_x) / TERRAIN_RESOLUTION)
    ridx = max(0, min(ridx, len(terrain_heights)-1))
    gy = int(terrain_heights[ridx])
    t = pygame.time.get_ticks() // 300
    # Checkered flag pole
    pygame.draw.line(surf, WHITE, (int(finish_screen_x), gy), (int(finish_screen_x), gy-80), 3)
    for row in range(4):
        for col in range(4):
            color = WHITE if (row+col) % 2 == 0 else BLACK
            pygame.draw.rect(surf, color, (int(finish_screen_x)+3+col*8, gy-80+row*8, 8, 8))
    c = [YELLOW, CYAN, GREEN, ORANGE, WHITE][t % 5]
    surf.blit(FONT_MD.render("FINISH!", True, c), (int(finish_screen_x)-30, gy-110))

# ─────────────────────────────────────────────
# ALIEN SPAWNER
# ─────────────────────────────────────────────
class AlienSpawner:
    def __init__(self):
        self.spawn_timer = 234  # 180 * 1.3
        self.wave = 0

    def update(self, aliens, camera_x):
        self.spawn_timer -= 1
        if self.spawn_timer <= 0:
            self.wave += 1
            count = 1 + self.wave // 3
            for _ in range(min(count, 3)):
                aliens.append(Alien(SCREEN_W + random.randint(0, 100),
                                    camera_x + SCREEN_W + random.randint(0, 200)))
            self.spawn_timer = max(117, int((240 - self.wave * 10) * 1.3))

# ─────────────────────────────────────────────
# MAIN GAME LOOP
# ─────────────────────────────────────────────
def game_loop():
    terrain_heights = generate_terrain(LEVEL_LENGTH + SCREEN_W * 2)
    player = Player()
    camera_x = 0.0
    bullets = []
    bombs = []
    aliens = []
    coins = []
    particles = []
    waves = []
    active_popup = None
    spawner = AlienSpawner()

    FINISH_WORLD_X = LEVEL_LENGTH - 200
    won = False
    game_over = False

    # Pixel-art scanline overlay
    scanline_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    for y in range(0, SCREEN_H, 2):
        pygame.draw.line(scanline_surf, (0, 0, 0, 40), (0, y), (SCREEN_W, y))

    font_big = FONT_LG
    font_med = FONT_MD

    show_title = True
    title_timer = 0
    _vplay(VOX_TITLE)

    pygame.mouse.set_visible(False)
    mouse_held = False   # tracks left-button held state via events

    running = True
    while running:
        dt = clock.tick(FPS)
        keys = pygame.key.get_pressed()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_held = True
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                mouse_held = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if event.key == pygame.K_r and (game_over or won):
                    return True  # restart
                if event.key == pygame.K_RETURN and show_title:
                    show_title = False
                    SND_ROBOT_START.play()
                    _vplay(VOX_READY)

        if show_title:
            title_timer += 1
            screen.fill(BLACK)
            draw_sky(screen, 0)
            draw_terrain(screen, terrain_heights, 0)
            tc = [YELLOW, CYAN, WHITE, ORANGE][(title_timer//20) % 4]
            t1 = font_big.render("MOON PATROL", True, tc)
            screen.blit(t1, (SCREEN_W//2 - t1.get_width()//2, 180))
            t2 = font_med.render("REACH THE FINISH LINE!", True, WHITE)
            screen.blit(t2, (SCREEN_W//2 - t2.get_width()//2, 260))
            t3 = FONT_TINY.render("ARROWS/WASD  SPACE:JUMP  LMB:FIRE", True, GRAY)
            screen.blit(t3, (SCREEN_W//2 - t3.get_width()//2, 310))
            t4 = font_med.render("PRESS ENTER TO START", True, [WHITE,YELLOW][(title_timer//30)%2])
            screen.blit(t4, (SCREEN_W//2 - t4.get_width()//2, 380))
            screen.blit(scanline_surf, (0, 0))
            pygame.display.flip()
            continue

        if game_over or won:
            screen.fill(BLACK)
            if won:
                msg = font_big.render("YOU WIN!", True, YELLOW)
                sc = font_med.render(f"SCORE: {player.score:06d}", True, CYAN)
                screen.blit(msg, (SCREEN_W//2 - msg.get_width()//2, 220))
                screen.blit(sc, (SCREEN_W//2 - sc.get_width()//2, 300))
            else:
                msg = font_big.render("GAME OVER", True, RED)
                sc = font_med.render(f"SCORE: {player.score:06d}", True, WHITE)
                screen.blit(msg, (SCREEN_W//2 - msg.get_width()//2, 220))
                screen.blit(sc, (SCREEN_W//2 - sc.get_width()//2, 300))
            restart = font_med.render("PRESS R TO RESTART", True, GRAY)
            screen.blit(restart, (SCREEN_W//2 - restart.get_width()//2, 380))
            screen.blit(scanline_surf, (0, 0))
            pygame.display.flip()
            continue

        # ── UPDATE ──
        # Scroll camera
        camera_x += SCROLL_SPEED
        camera_x = min(camera_x, FINISH_WORLD_X - 10)

        # Score from progress
        player.score = int(camera_x * 2)

        # Update player
        player.update(keys, terrain_heights, camera_x, bullets, waves)

        if player.lives == 0 and not game_over:
            game_over = True
            SND_ROBOT_GAMEOVER.play()
            _vplay(VOX_GAMEOVER)

        # Mouse firing toward crosshair
        mouse_pos = pygame.mouse.get_pos()
        lmb = mouse_held or pygame.mouse.get_pressed()[0]
        if lmb and player.shoot_cooldown <= 0 and not player.dead:
            player.shoot_cooldown = 13 if player.fire_rate_boost > 0 else 18
            tx = player.x + VEHICLE_W // 2
            ty = player.y + VEHICLE_H // 3
            dx = mouse_pos[0] - tx
            dy = mouse_pos[1] - ty
            dist = max(1, math.sqrt(dx * dx + dy * dy))
            ndx, ndy = dx / dist, dy / dist
            bx = tx + ndx * GUN_LENGTH
            by = ty + ndy * GUN_LENGTH
            spd = LASER_SPEED * 2 if player.bullet_speedup > 0 else LASER_SPEED
            bullets.append(Bullet(bx, by, ndx * spd, ndy * spd, LASER_BLUE, 'player'))
            if player.spread_shot > 0:
                # Rotate aim direction by 5° for extra bullet
                a = math.radians(5)
                ca, sa = math.cos(a), math.sin(a)
                bullets.append(Bullet(bx, by,
                                      (ndx * ca - ndy * sa) * spd,
                                      (ndx * sa + ndy * ca) * spd,
                                      LASER_BLUE, 'player'))
            if player.wave_fire > 0 and len(waves) == 0:
                waves.append(Wave(bx, by, math.atan2(ndy, ndx)))
                SND_WAVE.play()
            SND_SHOOT.play()

        # Check win
        finish_screen_x = FINISH_WORLD_X - camera_x
        if finish_screen_x < player.x + VEHICLE_W + 10:
            won = True
            SND_WIN.play()
            continue


        # Spawner
        spawner.update(aliens, camera_x)

        # Update bullets
        for b in bullets:
            b.update()
        bullets[:] = [b for b in bullets if b.alive]

        # Update bombs
        for bm in bombs:
            bm.update(terrain_heights, camera_x)
        bombs[:] = [bm for bm in bombs if bm.alive]

        # Update aliens
        for alien in aliens:
            alien.update(bullets, bombs, player.x, player.y, camera_x)
        aliens[:] = [a for a in aliens if a.alive]

        # Bullet collisions
        player_rect = pygame.Rect(player.x+4, player.y+4, VEHICLE_W-8, VEHICLE_H-8)
        for b in bullets:
            if b.owner == 'alien':
                br = pygame.Rect(b.x, b.y, b.w, b.h)
                if player_rect.colliderect(br) and not player.dead:
                    b.alive = False
                    player.hit()
                    for _ in range(8):
                        particles.append(Particle(player.x + VEHICLE_W//2, player.y + VEHICLE_H//2))

            elif b.owner == 'player':
                br = pygame.Rect(b.x, b.y, b.w, b.h)
                for alien in aliens:
                    ar = pygame.Rect(alien.screen_x, alien.y, alien.w, alien.h)
                    if ar.colliderect(br) and alien.alive:
                        b.alive = False
                        alien.hp -= 1
                        alien.flash_timer = 12
                        if alien.hp <= 0:
                            alien.alive = False
                            player.score += 500
                            SND_EXPLODE.play()
                            for _ in range(20):
                                particles.append(Particle(alien.screen_x + alien.w//2,
                                                          alien.y + alien.h//2))
                            for _ in range(random.randint(2, 4)):
                                coins.append(Coin(
                                    alien.screen_x + camera_x + alien.w//2 + random.uniform(-12, 12),
                                    alien.y + alien.h//2,
                                    alien.coin_color))
                        break

        # Bomb collision with player
        for bm in bombs:
            bmr = pygame.Rect(bm.x, bm.y, bm.w, bm.h)
            if player_rect.colliderect(bmr) and not player.dead:
                bm.alive = False
                player.hit()
                for _ in range(12):
                    particles.append(Particle(player.x + VEHICLE_W//2, player.y + VEHICLE_H//2))

        # Coins
        for c in coins:
            c.update(terrain_heights, camera_x)
        player_rect = pygame.Rect(player.x, player.y, VEHICLE_W, VEHICLE_H)
        for c in coins:
            cr = pygame.Rect(c.world_x - camera_x - c.r, c.world_y - c.r, c.r * 2, c.r * 2)
            if c.alive and player_rect.colliderect(cr):
                c.alive = False
                if c.color == RED:
                    player.fire_rate_boost = max(player.fire_rate_boost, 600)
                    SND_ROBOT_POWERUP.play()
                    _vplay(VOX_RAPIDFIRE)
                    active_popup = PowerupPopup("RAPID FIRE")
                elif c.color == CYAN:
                    player.cyan_coins += 1
                    if player.cyan_coins >= 3:
                        player.cyan_coins = 0
                        player.spread_shot = max(player.spread_shot, 600)
                        SND_ROBOT_POWERUP.play()
                        _vplay(VOX_SPREAD)
                        active_popup = PowerupPopup("SPREAD SHOT")
                elif c.color == PURPLE:
                    player.purple_coins += 1
                    if player.purple_coins >= 3:
                        player.purple_coins = 0
                        player.wave_fire = max(player.wave_fire, 600)
                        SND_ROBOT_POWERUP.play()
                        _vplay(VOX_WAVE)
                        active_popup = PowerupPopup("WAVE FIRE")
                elif c.color == ORANGE:
                    player.orange_coins += 1
                    if player.orange_coins >= 3:
                        player.orange_coins = 0
                        player.bullet_speedup = max(player.bullet_speedup, 600)
                        SND_ROBOT_POWERUP.play()
                        _vplay(VOX_SPEED)
                        active_popup = PowerupPopup("SPEED BOOST")
                player.score += 100
        coins[:] = [c for c in coins if c.alive]

        # Waves
        for w in waves:
            w.update()
        for w in waves:
            for alien in aliens:
                if alien.alive and w.hits_alien(alien):
                    alien.hp -= 1
                    if alien.hp <= 0:
                        alien.alive = False
                        player.score += 500
                        SND_EXPLODE.play()
                        for _ in range(20):
                            particles.append(Particle(alien.screen_x + alien.w//2,
                                                      alien.y + alien.h//2))
                        for _ in range(random.randint(2, 4)):
                            coins.append(Coin(
                                alien.screen_x + camera_x + alien.w//2 + random.uniform(-12, 12),
                                alien.y + alien.h//2,
                                alien.coin_color))
        waves[:] = [w for w in waves if w.alive]

        # Particles
        for p in particles:
            p.update()
        particles[:] = [p for p in particles if p.life > 0]

        # ── DRAW ──
        screen.fill(BLACK)
        draw_sky(screen, camera_x)
        draw_terrain(screen, terrain_heights, camera_x)
        draw_rocks(screen, camera_x, terrain_heights)

        # Finish line
        if finish_screen_x < SCREEN_W + 100:
            draw_finish(screen, finish_screen_x, terrain_heights, camera_x)

        # Draw coins
        for c in coins:
            c.draw(screen, camera_x)

        # Draw bombs
        for bm in bombs:
            bm.draw(screen)

        # Draw aliens
        for alien in aliens:
            alien.draw(screen)

        # Draw bullets
        for b in bullets:
            b.draw(screen)

        # Draw waves
        for w in waves:
            w.draw(screen)

        # Draw player
        player.draw(screen)

        # Particles
        for p in particles:
            p.draw(screen)

        # HUD
        draw_hud(screen, player, camera_x, LEVEL_LENGTH)

        # Powerup popup
        if active_popup:
            active_popup.update()
            draw_popup(screen, active_popup)

        # Scanlines
        screen.blit(scanline_surf, (0, 0))

        # Crosshair (drawn on top of everything)
        draw_crosshair(screen, pygame.mouse.get_pos())

        # Pixelate for 8-bit feel (subtle)
        # (commented out for performance - uncomment for more retro look)
        # tmp = pixelate(screen, 2)
        # screen.blit(tmp, (0,0))

        pygame.display.flip()

    return False

def main():
    while game_loop():
        pass
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
