#!/usr/bin/env python3
"""Moon Patrol - 1990s style sideways scrolling arcade game"""

import pygame
import sys
import math
import random
import array

pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

# --- Constants ---
SCREEN_W, SCREEN_H = 800, 600
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
MOON_SURFACE = (180, 170, 140)
MOON_DARK    = (120, 110, 90)
MOON_SHADOW  = (80, 75, 60)
SKY_TOP      = (5, 5, 20)
SKY_BOT      = (20, 10, 50)

# Game settings
GRAVITY       = 0.4
SCROLL_SPEED  = 3.0
PLAYER_SPEED  = 2.5
JUMP_VEL      = -10
BULLET_SPEED  = 8
ALIEN_BULLET_SPEED = 4
LEVEL_LENGTH  = 12000   # pixels of terrain to generate

screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("MOON PATROL")
clock = pygame.time.Clock()

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

# Pre-generate sounds
SND_SHOOT    = gen_shoot_sound()
SND_EXPLODE  = gen_explosion_sound()
SND_ALIEN_SHOOT = gen_alien_shoot_sound()
SND_JUMP     = gen_jump_sound()
SND_HIT      = gen_hit_sound()
SND_WIN      = gen_win_sound()

# ─────────────────────────────────────────────
# TERRAIN GENERATION
# ─────────────────────────────────────────────
TERRAIN_GROUND_Y = 420  # baseline y on screen
TERRAIN_RESOLUTION = 4  # pixels per terrain sample

def generate_terrain(length):
    """Generate undulating moon surface heights (y positions, screen coords)."""
    points = length // TERRAIN_RESOLUTION + 10
    heights = []
    # Use multiple sine waves + random craters
    h = TERRAIN_GROUND_Y
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
# PIXEL ART DRAWING HELPERS
# ─────────────────────────────────────────────
def draw_pixel_rect(surf, color, x, y, w, h):
    pygame.draw.rect(surf, color, (x, y, w, h))

def draw_8bit_text(surf, text, x, y, color=WHITE, scale=2):
    font = pygame.font.SysFont("monospace", 14 * scale // 2, bold=True)
    img = font.render(text, False, color)
    img = pygame.transform.scale(img, (img.get_width() * scale // 2, img.get_height() * scale // 2))
    surf.blit(img, (x, y))

def pixelate(surf, factor=2):
    small = pygame.transform.scale(surf, (surf.get_width()//factor, surf.get_height()//factor))
    return pygame.transform.scale(small, (surf.get_width(), surf.get_height()))

# ─────────────────────────────────────────────
# VEHICLE SPRITE (8-bit pixel art)
# ─────────────────────────────────────────────
# 16x10 pixel art, each char = 1 pixel
VEHICLE_PIXELS = [
    "................",
    "....BBBBBBBB....",
    "...BBBBBBBBBB...",
    "..BBBWWBBBWWBB..",
    "..BBBBBBBBBBBB..",
    ".GGGGGGGGGGGGGG.",
    ".GGGYYYYYYYYGGG.",
    "................",
    "..OOO......OOO..",
    "..OOO......OOO..",
]
VEHICLE_COLOR_MAP = {
    'B': LTBLUE, 'W': WHITE, 'G': DKGRAY, 'Y': YELLOW, 'O': GRAY,
    '.': None,
}

def build_vehicle_surf():
    pw = 3  # pixel width
    surf = pygame.Surface((16*pw, 10*pw), pygame.SRCALPHA)
    for row, line in enumerate(VEHICLE_PIXELS):
        for col, ch in enumerate(line):
            color = VEHICLE_COLOR_MAP.get(ch)
            if color:
                pygame.draw.rect(surf, color, (col*pw, row*pw, pw, pw))
    return surf

VEHICLE_SURF = build_vehicle_surf()
VEHICLE_W = VEHICLE_SURF.get_width()
VEHICLE_H = VEHICLE_SURF.get_height()

# Wheel pixel art
WHEEL_PIXELS = [
    ".OOO.",
    "OOOOO",
    "OWOOO",
    "OOOOO",
    ".OOO.",
]
def build_wheel_surf():
    pw = 3
    surf = pygame.Surface((5*pw, 5*pw), pygame.SRCALPHA)
    cmap = {'O': GRAY, 'W': WHITE, '.': None}
    for row, line in enumerate(WHEEL_PIXELS):
        for col, ch in enumerate(line):
            c = cmap.get(ch)
            if c:
                pygame.draw.rect(surf, c, (col*pw, row*pw, pw, pw))
    return surf

WHEEL_SURF = build_wheel_surf()
WHEEL_W = WHEEL_SURF.get_width()
WHEEL_H = WHEEL_SURF.get_height()

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
ALIEN_SURFS = [ALIEN_SURF_R, ALIEN_SURF_P, ALIEN_SURF_C]

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
            alpha = int(255 * self.life / self.max_life)
            s = pygame.Surface((self.size, self.size))
            s.fill(self.color)
            s.set_alpha(alpha)
            surf.blit(s, (int(self.x), int(self.y)))

# ─────────────────────────────────────────────
# STAR FIELD
# ─────────────────────────────────────────────
STARS = [(random.randint(0, SCREEN_W), random.randint(0, TERRAIN_GROUND_Y - 50),
          random.choice([1, 1, 1, 2]), random.uniform(0.2, 1.0))
         for _ in range(150)]

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

    def update(self):
        self.x += self.vx
        self.y += self.vy
        if self.x > SCREEN_W + 50 or self.x < -50 or self.y < -50 or self.y > SCREEN_H + 50:
            self.alive = False

    def draw(self, surf):
        pygame.draw.rect(surf, self.color, (int(self.x), int(self.y), self.w, self.h))
        # Glow
        pygame.draw.rect(surf, WHITE, (int(self.x)+1, int(self.y)+1, self.w-2, 1))

class Bomb:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = random.uniform(-1, 1)
        self.vy = 0
        self.alive = True
        self.w, self.h = 6, 8

    def update(self, terrain_heights, camera_x):
        self.vy += GRAVITY * 0.8
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

class Alien:
    TYPES = ['swooper', 'hoverer', 'diver']

    def __init__(self, screen_x, world_x):
        self.world_x = world_x
        self.screen_x = screen_x
        self.y = random.randint(80, 200)
        self.type = random.choice(self.TYPES)
        self.surf = random.choice(ALIEN_SURFS)
        self.w = self.surf.get_width()
        self.h = self.surf.get_height()
        self.alive = True
        self.hp = 2
        self.shoot_timer = random.randint(60, 180)
        self.bomb_timer = random.randint(90, 240)
        self.anim_t = random.uniform(0, 100)
        # Movement
        self.vx = random.uniform(-1.5, -0.5)
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
            self.shoot_timer = random.randint(60, 180)
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
            self.bomb_timer = random.randint(90, 240)
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
        self.wheel_rot = [0.0, 0.0]  # front and rear wheel rotation
        # Wheel offsets from vehicle bottom-left
        self.wheel_offsets = [(6, VEHICLE_H - 4), (VEHICLE_W - 11, VEHICLE_H - 4)]
        self.tilt = 0.0  # body tilt angle
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

    def update(self, keys, terrain_heights, camera_x, bullets):
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

        # Wheel rotation (proportional to horizontal speed)
        speed_factor = abs(self.vx) + SCROLL_SPEED
        self.wheel_rot[0] = (self.wheel_rot[0] + speed_factor * 0.15) % (2*math.pi)
        self.wheel_rot[1] = (self.wheel_rot[1] + speed_factor * 0.15) % (2*math.pi)

        # Jump
        if (keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w]) and self.on_ground:
            self.vy = JUMP_VEL
            self.on_ground = False
            SND_JUMP.play()

        # Shoot (up-right)
        self.shoot_cooldown -= 1
        if (keys[pygame.K_LCTRL] or keys[pygame.K_z] or keys[pygame.K_x]) and self.shoot_cooldown <= 0:
            self.shoot_cooldown = 18
            # Fire diagonally up-right
            bx = self.x + VEHICLE_W
            by = self.y + VEHICLE_H // 3
            bullets.append(Bullet(bx, by, BULLET_SPEED, -BULLET_SPEED * 0.5, YELLOW, 'player'))
            # Also fire straight right
            bullets.append(Bullet(bx, by + 6, BULLET_SPEED, 0, CYAN, 'player'))
            SND_SHOOT.play()

    def hit(self):
        if self.invincible > 0:
            return False
        self.lives -= 1
        self.invincible = 90
        SND_HIT.play()
        if self.lives <= 0:
            self.dead = True
            self.dead_timer = 120
        return True

    def draw(self, surf, terrain_heights, camera_x):
        if self.dead:
            return

        # Blink when invincible
        if self.invincible > 0 and (self.invincible // 6) % 2 == 0:
            return

        # Draw wheels (behind vehicle body)
        for i, (ox, oy) in enumerate(self.wheel_offsets):
            wx = int(self.x + ox - WHEEL_W//2)
            wy_terrain = self.get_wheel_ground_y(terrain_heights, camera_x, ox)
            wy = int(wy_terrain - WHEEL_H + 2)

            # Rotate wheel
            rot_surf = pygame.transform.rotate(WHEEL_SURF, -math.degrees(self.wheel_rot[i]))
            rw, rh = rot_surf.get_size()
            surf.blit(rot_surf, (wx - rw//2 + WHEEL_W//2, wy - rh//2 + WHEEL_H//2))

        # Draw vehicle body (tilted)
        rotated = pygame.transform.rotate(VEHICLE_SURF, -math.degrees(self.tilt))
        rw, rh = rotated.get_size()
        body_y = self.y
        surf.blit(rotated, (int(self.x) - (rw - VEHICLE_W)//2, int(body_y)))

        # Exhaust flame
        if random.random() < 0.5:
            fx = int(self.x) + 2
            fy = int(self.y) + VEHICLE_H - 4
            pygame.draw.ellipse(surf, ORANGE, (fx, fy, 6, 4))
            pygame.draw.ellipse(surf, YELLOW, (fx+1, fy+1, 4, 2))

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
        top_pts = [p for p in poly[1:-1]]
        if len(top_pts) > 1:
            pygame.draw.lines(surf, MOON_DARK, False, top_pts, 2)
        # Shadow rim
        shadow_pts = [(p[0], p[1]+4) for p in top_pts]
        if len(shadow_pts) > 1:
            pygame.draw.lines(surf, MOON_SHADOW, False, shadow_pts, 1)

    # Draw craters on surface
    random.seed(int(camera_x / 100))
    for _ in range(5):
        rx = random.randint(0, SCREEN_W)
        world_rx = rx + camera_x
        ridx = int(world_rx / TERRAIN_RESOLUTION)
        ridx = max(0, min(ridx, len(terrain_heights)-1))
        ry = int(terrain_heights[ridx])
        cr = random.randint(8, 20)
        pygame.draw.ellipse(surf, MOON_DARK, (rx-cr, ry-cr//3, cr*2, cr//2))
        pygame.draw.arc(surf, MOON_SHADOW, (rx-cr, ry-cr//3, cr*2, cr//2), math.pi, 2*math.pi, 1)

def draw_rocks(surf, camera_x, terrain_heights):
    """Draw decorative rocks on terrain."""
    random.seed(int(camera_x / 80) + 7777)
    for _ in range(8):
        rx = random.randint(0, SCREEN_W)
        world_rx = rx + camera_x
        ridx = int(world_rx / TERRAIN_RESOLUTION)
        ridx = max(0, min(ridx, len(terrain_heights)-1))
        ry = int(terrain_heights[ridx])
        rh = random.randint(4, 16)
        rw = random.randint(6, 20)
        col = random.choice([MOON_DARK, DKGRAY, BROWN])
        pygame.draw.ellipse(surf, col, (rx-rw//2, ry-rh, rw, rh))
        pygame.draw.ellipse(surf, MOON_SHADOW, (rx-rw//2+1, ry-rh+rh//2, rw-2, rh//2))

# ─────────────────────────────────────────────
# SKY / BACKGROUND
# ─────────────────────────────────────────────
def draw_sky(surf, camera_x):
    # Gradient sky
    for y in range(TERRAIN_GROUND_Y):
        t = y / TERRAIN_GROUND_Y
        r = int(SKY_TOP[0] + (SKY_BOT[0]-SKY_TOP[0]) * t)
        g = int(SKY_TOP[1] + (SKY_BOT[1]-SKY_TOP[1]) * t)
        b = int(SKY_TOP[2] + (SKY_BOT[2]-SKY_TOP[2]) * t)
        pygame.draw.line(surf, (r, g, b), (0, y), (SCREEN_W, y))

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

    # Distant mountains (parallax layer 2)
    random.seed(42)
    for i in range(12):
        mx = int((i * 200 - camera_x * 0.15) % (SCREEN_W + 200)) - 50
        mh = random.randint(40, 100)
        mw = random.randint(60, 120)
        pts = [(mx, TERRAIN_GROUND_Y), (mx+mw//2, TERRAIN_GROUND_Y-mh), (mx+mw, TERRAIN_GROUND_Y)]
        pygame.draw.polygon(surf, (35, 32, 50), pts)
        pygame.draw.lines(surf, (50, 45, 70), False, pts[:-1], 1)

# ─────────────────────────────────────────────
# HUD
# ─────────────────────────────────────────────
def draw_hud(surf, player, camera_x, level_length):
    # Score
    font = pygame.font.SysFont("monospace", 18, bold=True)
    surf.blit(font.render(f"SCORE: {player.score:06d}", True, YELLOW), (10, 8))
    surf.blit(font.render(f"LIVES: {'* ' * player.lives}", True, CYAN), (10, 28))

    # Progress bar
    progress = min(1.0, camera_x / (level_length - SCREEN_W))
    bar_w = 300
    bar_x = SCREEN_W//2 - bar_w//2
    pygame.draw.rect(surf, DKGRAY, (bar_x, 10, bar_w, 12))
    pygame.draw.rect(surf, GREEN, (bar_x, 10, int(bar_w * progress), 12))
    pygame.draw.rect(surf, WHITE, (bar_x, 10, bar_w, 12), 1)
    surf.blit(font.render("CHECKPOINT", True, WHITE), (bar_x + bar_w + 8, 6))

    # Controls reminder (small)
    small = pygame.font.SysFont("monospace", 11, bold=True)
    surf.blit(small.render("ARROWS/WASD: MOVE  SPACE: JUMP  CTRL/Z: FIRE", True, GRAY), (10, SCREEN_H-20))

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
    font = pygame.font.SysFont("monospace", 20, bold=True)
    c = [YELLOW, CYAN, GREEN, ORANGE, WHITE][t % 5]
    surf.blit(font.render("FINISH!", True, c), (int(finish_screen_x)-20, gy-110))

# ─────────────────────────────────────────────
# ALIEN SPAWNER
# ─────────────────────────────────────────────
class AlienSpawner:
    def __init__(self):
        self.spawn_timer = 180
        self.wave = 0

    def update(self, aliens, camera_x):
        self.spawn_timer -= 1
        if self.spawn_timer <= 0:
            self.wave += 1
            count = 1 + self.wave // 3
            for _ in range(min(count, 3)):
                aliens.append(Alien(SCREEN_W + random.randint(0, 100),
                                    camera_x + SCREEN_W + random.randint(0, 200)))
            self.spawn_timer = max(90, 240 - self.wave * 10)

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
    particles = []
    spawner = AlienSpawner()

    FINISH_WORLD_X = LEVEL_LENGTH - 200
    won = False
    game_over = False

    # Pixel-art scanline overlay
    scanline_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    for y in range(0, SCREEN_H, 2):
        pygame.draw.line(scanline_surf, (0, 0, 0, 40), (0, y), (SCREEN_W, y))

    font_big = pygame.font.SysFont("monospace", 48, bold=True)
    font_med = pygame.font.SysFont("monospace", 24, bold=True)
    font_sml = pygame.font.SysFont("monospace", 16, bold=True)

    show_title = True
    title_timer = 0

    running = True
    while running:
        dt = clock.tick(FPS)
        keys = pygame.key.get_pressed()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if event.key == pygame.K_r and (game_over or won):
                    return True  # restart
                if event.key == pygame.K_RETURN and show_title:
                    show_title = False

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
            t3 = font_sml.render("ARROWS/WASD: Move   SPACE: Jump   CTRL/Z: Fire", True, GRAY)
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
        player.update(keys, terrain_heights, camera_x, bullets)

        # Check win
        finish_screen_x = FINISH_WORLD_X - camera_x
        if finish_screen_x < player.x + VEHICLE_W + 10:
            won = True
            SND_WIN.play()
            continue

        # Check player dead
        if player.dead and player.dead_timer <= 0:
            game_over = True
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
                        break

        # Bomb collision with player
        for bm in bombs:
            bmr = pygame.Rect(bm.x, bm.y, bm.w, bm.h)
            if player_rect.colliderect(bmr) and not player.dead:
                bm.alive = False
                player.hit()
                for _ in range(12):
                    particles.append(Particle(player.x + VEHICLE_W//2, player.y + VEHICLE_H//2))

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

        # Draw bombs
        for bm in bombs:
            bm.draw(screen)

        # Draw aliens
        for alien in aliens:
            alien.draw(screen)

        # Draw bullets
        for b in bullets:
            b.draw(screen)

        # Draw player
        player.draw(screen, terrain_heights, camera_x)

        # Particles
        for p in particles:
            p.draw(screen)

        # HUD
        draw_hud(screen, player, camera_x, LEVEL_LENGTH)

        # Scanlines
        screen.blit(scanline_surf, (0, 0))

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
