# Pathfinding Visualizer (Python + pygame)

Watch four classic search algorithms explore a grid in real time, and compare how many cells each one checks and whether it finds the cheapest path.

## Run it
```bash
pip install pygame
python pathfinder.py
```

## Controls
| Input | Action |
|---|---|
| Left-drag | Draw walls |
| Right-drag | Erase walls |
| Drag green / red | Move start / goal |
| 1 / 2 / 3 / 4 | A* / Dijkstra / BFS / Greedy Best-First |
| Space | Run the search |
| M | Generate a random maze (recursive backtracker) |
| W | Add "mud" patches that cost 6× to cross |
| C / R | Clear everything / reset the search |

## The algorithms
| Algorithm | Priority | Shortest path? | Uses weights? |
|---|---|---|---|
| **A\*** | cost so far + distance to goal | ✅ Yes | ✅ |
| **Dijkstra** | cost so far | ✅ Yes | ✅ |
| **BFS** | first in, first out | Fewest steps only | ❌ |
| **Greedy** | distance to goal | ❌ Not guaranteed | ❌ |

All four share **one search loop** (a Python generator that yields after every step so the UI can animate). They differ only in how they rank the cells waiting to be explored.

### Example run (same maze with mud)
| | Cells explored | Path cost |
|---|---|---|
| A* | 653 | **234** |
| Dijkstra | 700 | **234** |
| BFS | 747 | 293 |
| Greedy | 337 | 328 |

A* finds the same optimal path as Dijkstra while exploring fewer cells, because the Manhattan-distance heuristic steers it toward the goal.
