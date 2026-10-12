"""
PATHFINDING VISUALIZER
Watch A*, Dijkstra, BFS and Greedy Best-First search explore a grid in real time.

Mouse:   Left-drag = draw walls   Right-drag = erase
         Drag the green (start) or red (goal) square to move it
Keys:    1 A*   2 Dijkstra   3 BFS   4 Greedy
         SPACE run   M generate maze   W random weights   C clear   R reset search
Requires: pip install pygame
"""
import heapq
import random
import sys
from collections import deque

import pygame

COLS, ROWS = 50, 32
CELL = 20
PANEL = 64
WIDTH, HEIGHT = COLS * CELL, ROWS * CELL + PANEL
STEPS_PER_FRAME = 6

COLORS = {
    "bg": (14, 14, 26), "grid": (28, 28, 46), "wall": (150, 156, 190),
    "open": (40, 90, 160), "closed": (24, 48, 96), "path": (255, 214, 60),
    "start": (60, 230, 120), "goal": (255, 70, 90), "weight": (90, 60, 30), "text": (230, 230, 245),
}
ALGOS = {pygame.K_1: "A*", pygame.K_2: "Dijkstra", pygame.K_3: "BFS", pygame.K_4: "Greedy"}


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class Grid:
    def __init__(self):
        self.walls = set()
        self.weights = {}  # cell -> extra cost (mud). BFS ignores weights.
        self.start = (5, ROWS // 2)
        self.goal = (COLS - 6, ROWS // 2)

    def in_bounds(self, c):
        return 0 <= c[0] < COLS and 0 <= c[1] < ROWS

    def neighbors(self, c):
        x, y = c
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if self.in_bounds(n) and n not in self.walls:
                yield n

    def cost(self, c):
        return 1 + self.weights.get(c, 0)

    def generate_maze(self):
        """Randomized depth-first backtracker carving passages on odd cells."""
        self.weights.clear()
        self.walls = {(x, y) for x in range(COLS) for y in range(ROWS)}
        stack = [(1, 1)]
        self.walls.discard((1, 1))
        while stack:
            x, y = stack[-1]
            options = [(x + dx, y + dy, dx, dy) for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2))
                       if 0 < x + dx < COLS - 1 and 0 < y + dy < ROWS - 1 and (x + dx, y + dy) in self.walls]
            if not options:
                stack.pop()
                continue
            nx, ny, dx, dy = random.choice(options)
            self.walls.discard((x + dx // 2, y + dy // 2))
            self.walls.discard((nx, ny))
            stack.append((nx, ny))
        # knock out a few extra walls so there are multiple routes
        for _ in range(COLS * ROWS // 25):
            self.walls.discard((random.randrange(1, COLS - 1), random.randrange(1, ROWS - 1)))
        self.start, self.goal = (1, 1), (COLS - 3 if COLS % 2 == 0 else COLS - 2, ROWS - 3 if ROWS % 2 == 0 else ROWS - 2)
        self.walls.discard(self.start)
        self.walls.discard(self.goal)

    def random_weights(self):
        self.weights = {}
        for _ in range(4):  # a few blobs of "mud"
            cx, cy, r = random.randrange(COLS), random.randrange(ROWS), random.randint(3, 6)
            for x in range(cx - r, cx + r + 1):
                for y in range(cy - r, cy + r + 1):
                    if self.in_bounds((x, y)) and manhattan((x, y), (cx, cy)) <= r:
                        self.weights[(x, y)] = 5


def search(grid, algo):
    """
    Generator: yields (open_set, closed_set, path) after each expansion so the UI can animate.
    All four algorithms share one loop; they differ only in the priority they give each cell.
    """
    start, goal = grid.start, grid.goal
    came_from = {start: None}
    g = {start: 0}
    closed = set()

    if algo == "BFS":
        frontier = deque([start])
        pop = frontier.popleft
        push = lambda cell, prio: frontier.append(cell)
        open_cells = lambda: set(frontier)
    else:
        frontier = [(0, 0, start)]
        counter = 0  # tie-breaker so heapq never compares tuples of cells

        def pop():
            return heapq.heappop(frontier)[2]

        def push(cell, prio):
            nonlocal counter
            counter += 1
            heapq.heappush(frontier, (prio, counter, cell))

        open_cells = lambda: {c for _, _, c in frontier}

    while frontier:
        current = pop()
        if current in closed:
            continue
        closed.add(current)
        if current == goal:
            path = []
            while current:
                path.append(current)
                current = came_from[current]
            yield open_cells(), closed, path[::-1]
            return

        for n in grid.neighbors(current):
            step = 1 if algo == "BFS" else grid.cost(n)
            new_g = g[current] + step
            if n not in g or new_g < g[n]:
                g[n] = new_g
                came_from[n] = current
                h = manhattan(n, goal)
                prio = {"A*": new_g + h, "Dijkstra": new_g, "Greedy": h, "BFS": 0}[algo]
                push(n, prio)
        yield open_cells(), closed, None

    yield set(), closed, []  # no path


def path_cost(grid, path):
    return sum(grid.cost(c) for c in path[1:])


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Pathfinding Visualizer")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 17, bold=True)
        self.grid = Grid()
        self.algo = "A*"
        self.dragging = None
        self.reset_search()

    def reset_search(self):
        self.runner = None
        self.open, self.closed, self.path = set(), set(), None
        self.stats = ""

    def cell_at(self, pos):
        x, y = pos[0] // CELL, (pos[1] - PANEL) // CELL
        return (x, y) if self.grid.in_bounds((x, y)) and pos[1] >= PANEL else None

    def handle_mouse(self):
        buttons = pygame.mouse.get_pressed()
        cell = self.cell_at(pygame.mouse.get_pos())
        if not cell or self.runner:
            return
        if self.dragging in ("start", "goal"):
            if cell not in self.grid.walls:
                setattr(self.grid, self.dragging, cell)
                self.reset_search()
        elif buttons[0] and cell not in (self.grid.start, self.grid.goal):
            self.grid.walls.add(cell)
            self.reset_search()
        elif buttons[2]:
            self.grid.walls.discard(cell)
            self.reset_search()

    def step(self):
        if not self.runner:
            return
        for _ in range(STEPS_PER_FRAME):
            try:
                self.open, self.closed, path = next(self.runner)
            except StopIteration:
                self.runner = None
                return
            if path is not None:
                self.path = path
                self.runner = None
                if path:
                    self.stats = f"{self.algo}: explored {len(self.closed)} cells · path {len(path)} steps · cost {path_cost(self.grid, path)}"
                else:
                    self.stats = f"{self.algo}: no path! explored {len(self.closed)} cells"
                return

    def draw(self):
        s = self.screen
        s.fill(COLORS["bg"])
        for x in range(COLS):
            for y in range(ROWS):
                c = (x, y)
                rect = pygame.Rect(x * CELL, PANEL + y * CELL, CELL - 1, CELL - 1)
                if c in self.grid.walls:
                    color = COLORS["wall"]
                elif c in self.closed:
                    color = COLORS["closed"]
                elif c in self.open:
                    color = COLORS["open"]
                elif c in self.grid.weights:
                    color = COLORS["weight"]
                else:
                    color = COLORS["grid"]
                pygame.draw.rect(s, color, rect, border_radius=3)
        if self.path:
            pts = [(x * CELL + CELL // 2, PANEL + y * CELL + CELL // 2) for x, y in self.path]
            if len(pts) > 1:
                pygame.draw.lines(s, COLORS["path"], False, pts, 5)
        for cell, key in ((self.grid.start, "start"), (self.grid.goal, "goal")):
            pygame.draw.rect(s, COLORS[key], (cell[0] * CELL, PANEL + cell[1] * CELL, CELL - 1, CELL - 1), border_radius=4)

        title = f"[{self.algo}]  1 A*  2 Dijkstra  3 BFS  4 Greedy   SPACE run  M maze  W weights  C clear"
        s.blit(self.font.render(title, True, COLORS["text"]), (12, 10))
        s.blit(self.font.render(self.stats or "Draw walls, then press SPACE", True, COLORS["path"]), (12, 36))
        pygame.display.flip()

    def run(self):
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                    pygame.quit()
                    sys.exit()
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    cell = self.cell_at(e.pos)
                    self.dragging = "start" if cell == self.grid.start else "goal" if cell == self.grid.goal else "wall"
                if e.type == pygame.MOUSEBUTTONUP:
                    self.dragging = None
                if e.type == pygame.KEYDOWN:
                    if e.key in ALGOS:
                        self.algo = ALGOS[e.key]
                        self.reset_search()
                    elif e.key == pygame.K_SPACE:
                        self.reset_search()
                        self.runner = search(self.grid, self.algo)
                    elif e.key == pygame.K_m:
                        self.grid.generate_maze()
                        self.reset_search()
                    elif e.key == pygame.K_w:
                        self.grid.random_weights()
                        self.reset_search()
                    elif e.key == pygame.K_c:
                        self.grid = Grid()
                        self.reset_search()
                    elif e.key == pygame.K_r:
                        self.reset_search()
            self.handle_mouse()
            self.step()
            self.draw()
            self.clock.tick(60)


if __name__ == "__main__":
    App().run()
