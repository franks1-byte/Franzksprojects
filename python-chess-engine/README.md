# Chess Engine with AI (Python)

A complete chess engine in pure Python: full rules plus an AI opponent that thinks several moves ahead. No libraries.

```
8  ♜ ♞ ♝ ♛ ♚ ♝ · ♜
7  ♟ ♟ ♟ · ♟ ♟ ♟ ♟
5  · · · ♟ · · · ·
4  · · · ♙ ♞ · · ·
Engine thinking…
  depth 4: d7d5   eval  +0.75   11367 nodes  0.49s
```

## Run it
```bash
python chess_engine.py     # play against the engine (moves like e2e4, promotion e7e8q)
python test_engine.py      # run the verification suite
```
In-game commands: `moves` (list legal moves), `undo`, `fen`, `quit`.

## Rules (all of them)
Every piece move, **castling** (including "can't castle out of, through, or into check"), **en passant**, **promotion** to any piece, check, **checkmate**, **stalemate**, the **50-move rule**, **threefold repetition**, and **insufficient material**.

## How the AI thinks
| Technique | Why it helps |
|---|---|
| **Alpha-beta search** | Skips branches that can't change the result, so it searches far fewer positions than plain minimax |
| **Iterative deepening** | Searches depth 1, 2, 3… and reuses each answer to search the next depth faster |
| **Quiescence search** | Keeps following captures so it doesn't stop in the middle of a trade |
| **Transposition table** | Remembers positions already seen via **Zobrist hashing** (a 64-bit fingerprint per position) |
| **Move ordering** | Tries the best-known move first, then captures (most valuable victim, least valuable attacker), then killer moves |
| **Piece-square tables** | Knights like the center, kings hide early and centralize in the endgame, pawns want to advance |
| **Mate scoring** | Prefers the fastest checkmate |

## Board representation: 0x88
The board is a 128-square array, and only half of it is the real board. A square is off the board exactly when `square & 0x88 != 0`, so pieces "falling off the edge" are caught with a single bit test.

## Verified with perft
Perft counts every legal position to a given depth. If even one rule were wrong, these numbers would not match the published values:

| Position | Depth | Result |
|---|---|---|
| Start position | 4 | 197,281 ✅ |
| Kiwipete (castling, pins, en passant) | 3 | 97,862 ✅ |
| Position 3 (en passant edge cases) | 4 | 43,238 ✅ |
| Position 4 (promotions) | 3 | 9,467 ✅ |
| Position 5 | 3 | 62,379 ✅ |

The suite also checks each special rule, confirms the Zobrist hash matches a full recompute, and has the engine solve tactics (mate in 1, mate in 2, knight fork). The tactic answers were cross-checked with the `python-chess` library.
