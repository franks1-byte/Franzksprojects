"""
NEON DODGER
Dodge the falling meteors, grab the energy orbs, and survive as long as you can.

Controls: Left/Right or A/D to move, SPACE to dash, P to pause, R to restart.
Requires: pip install pygame
"""
import math
import random
import sys

import pygame

WIDTH, HEIGHT = 800, 600
FPS = 60

BG = (8, 6, 20)
CYAN = (0, 240, 255)
MAGENTA = (255, 40, 200)
YELLOW = (255, 230, 60)
WHITE = (240, 240, 255)


class Particle:
    def __init__(self, x, y, color):
        angle = random.uniform(0, math.tau)
        speed = random.uniform(1, 5)
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(angle) * speed, math.sin(angle) * speed
        self.life = random.randint(20, 40)
        self.color = color

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.1
        self.life -= 1

    def draw(self, surf):
        if self.life > 0:
            r = max(1, self.life // 10)
            pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), r)


class Player:
    SPEED = 6
    DASH_SPEED = 18
    DASH_COOLDOWN = 60  # frames

    def __init__(self):
        self.w, self.h = 44, 18
        self.x = WIDTH / 2
        self.y = HEIGHT - 60
        self.dash_timer = 0
        self.cooldown = 0
        self.trail = []

    @property
    def rect(self):
        return pygame.Rect(self.x - self.w / 2, self.y - self.h / 2, self.w, self.h)

    def update(self, keys):
        direction = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        speed = self.DASH_SPEED if self.dash_timer > 0 else self.SPEED
        self.x = max(self.w / 2, min(WIDTH - self.w / 2, self.x + direction * speed))
        self.dash_timer = max(0, self.dash_timer - 1)
        self.cooldown = max(0, self.cooldown - 1)
        self.trail.append((self.x, self.y))
        self.trail = self.trail[-12:]

    def dash(self):
        if self.cooldown == 0:
            self.dash_timer = 10
            self.cooldown = self.DASH_COOLDOWN

    def draw(self, surf):
        for i, (tx, ty) in enumerate(self.trail):
            alpha = i / len(self.trail)
            color = (int(CYAN[0] * alpha), int(CYAN[1] * alpha * 0.6), int(CYAN[2] * alpha))
            pygame.draw.rect(surf, color, (tx - self.w / 2, ty - 4, self.w, 8), border_radius=4)
        pygame.draw.rect(surf, CYAN, self.rect, border_radius=8)
        pygame.draw.rect(surf, WHITE, self.rect.inflate(-16, -10), border_radius=4)


class Meteor:
    def __init__(self, level):
        self.r = random.randint(12, 30)
        self.x = random.uniform(self.r, WIDTH - self.r)
        self.y = -self.r
        self.speed = random.uniform(3, 5) + level * 0.6
        self.wobble = random.uniform(0, math.tau)

    def update(self):
        self.y += self.speed
        self.wobble += 0.05
        self.x += math.sin(self.wobble) * 0.8

    def collides(self, rect):
        cx = max(rect.left, min(self.x, rect.right))
        cy = max(rect.top, min(self.y, rect.bottom))
        return (self.x - cx) ** 2 + (self.y - cy) ** 2 < self.r ** 2

    def draw(self, surf):
        pygame.draw.circle(surf, (90, 10, 70), (int(self.x), int(self.y)), self.r + 4)
        pygame.draw.circle(surf, MAGENTA, (int(self.x), int(self.y)), self.r)
        pygame.draw.circle(surf, (255, 150, 230), (int(self.x - self.r / 3), int(self.y - self.r / 3)), self.r // 3)


class Orb:
    def __init__(self):
        self.x = random.uniform(30, WIDTH - 30)
        self.y = -10
        self.t = 0

    def update(self):
        self.y += 3
        self.t += 0.15

    def collides(self, rect):
        return rect.inflate(20, 20).collidepoint(self.x, self.y)

    def draw(self, surf):
        pulse = 8 + math.sin(self.t) * 3
        pygame.draw.circle(surf, (80, 70, 10), (int(self.x), int(self.y)), int(pulse + 6))
        pygame.draw.circle(surf, YELLOW, (int(self.x), int(self.y)), int(pulse))


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Neon Dodger")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 22, bold=True)
        self.big_font = pygame.font.SysFont("consolas", 56, bold=True)
        self.stars = [(random.uniform(0, WIDTH), random.uniform(0, HEIGHT), random.uniform(0.5, 2)) for _ in range(120)]
        self.best = 0
        self.reset()

    def reset(self):
        self.player = Player()
        self.meteors, self.orbs, self.particles = [], [], []
        self.score = 0
        self.frames = 0
        self.lives = 3
        self.invincible = 0
        self.shake = 0
        self.paused = False
        self.game_over = False

    @property
    def level(self):
        return self.frames // (FPS * 15)  # harder every 15 seconds

    def burst(self, x, y, color, n=25):
        self.particles += [Particle(x, y, color) for _ in range(n)]

    def update(self):
        keys = pygame.key.get_pressed()
        self.player.update(keys)
        self.frames += 1
        self.score += 1

        spawn_chance = 0.03 + self.level * 0.01
        if random.random() < spawn_chance:
            self.meteors.append(Meteor(self.level))
        if random.random() < 0.006:
            self.orbs.append(Orb())

        for m in self.meteors:
            m.update()
            if self.invincible == 0 and m.collides(self.player.rect):
                self.lives -= 1
                self.invincible = 90
                self.shake = 15
                self.burst(m.x, m.y, MAGENTA, 40)
                m.y = HEIGHT + 100
                if self.lives <= 0:
                    self.game_over = True
                    self.best = max(self.best, self.score // 10)
        for o in self.orbs:
            o.update()
            if o.collides(self.player.rect):
                self.score += 500
                self.burst(o.x, o.y, YELLOW)
                o.y = HEIGHT + 100

        self.meteors = [m for m in self.meteors if m.y < HEIGHT + 50]
        self.orbs = [o for o in self.orbs if o.y < HEIGHT + 50]
        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.life > 0]
        self.invincible = max(0, self.invincible - 1)
        self.shake = max(0, self.shake - 1)

    def draw(self):
        canvas = pygame.Surface((WIDTH, HEIGHT))
        canvas.fill(BG)
        for i, (sx, sy, sp) in enumerate(self.stars):
            sy = (sy + sp * (1 + self.level * 0.3)) % HEIGHT
            self.stars[i] = (sx, sy, sp)
            shade = int(80 * sp)
            canvas.set_at((int(sx), int(sy)), (shade, shade, shade + 40))

        for m in self.meteors:
            m.draw(canvas)
        for o in self.orbs:
            o.draw(canvas)
        if self.invincible % 10 < 5:
            self.player.draw(canvas)
        for p in self.particles:
            p.draw(canvas)

        hud = self.font.render(f"SCORE {self.score // 10:06d}   LEVEL {self.level + 1}   LIVES {'♥' * self.lives}", True, WHITE)
        canvas.blit(hud, (16, 12))
        dash_ready = "DASH READY" if self.player.cooldown == 0 else "DASH ..."
        canvas.blit(self.font.render(dash_ready, True, CYAN if self.player.cooldown == 0 else (80, 80, 110)), (WIDTH - 150, 12))

        if self.paused:
            self.center_text(canvas, "PAUSED", "Press P to continue")
        if self.game_over:
            self.center_text(canvas, "GAME OVER", f"Score {self.score // 10}  •  Best {self.best}  •  R to restart")

        offset = (random.randint(-self.shake, self.shake), random.randint(-self.shake, self.shake)) if self.shake else (0, 0)
        self.screen.fill(BG)
        self.screen.blit(canvas, offset)
        pygame.display.flip()

    def center_text(self, surf, title, subtitle):
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        surf.blit(shade, (0, 0))
        t = self.big_font.render(title, True, MAGENTA)
        s = self.font.render(subtitle, True, WHITE)
        surf.blit(t, t.get_rect(center=(WIDTH / 2, HEIGHT / 2 - 30)))
        surf.blit(s, s.get_rect(center=(WIDTH / 2, HEIGHT / 2 + 30)))

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE and not self.game_over:
                        self.player.dash()
                    elif event.key == pygame.K_p and not self.game_over:
                        self.paused = not self.paused
                    elif event.key == pygame.K_r and self.game_over:
                        self.reset()
                    elif event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        sys.exit()
            if not self.paused and not self.game_over:
                self.update()
            self.draw()
            self.clock.tick(FPS)


if __name__ == "__main__":
    Game().run()
