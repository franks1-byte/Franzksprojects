"""
Chess engine: full rules + an AI that searches with alpha-beta pruning.

Board: 0x88 representation (a 128-square array where off-board squares are detected with
`square & 0x88`, which makes move generation fast and simple).

Rules implemented: all piece moves, castling (with "can't castle through check"), en passant,
promotion (all four pieces), check, checkmate, stalemate, 50-move rule, threefold repetition,
insufficient material. Correctness is verified with "perft" (counting every legal position to a depth
and comparing with the known values).

AI: iterative deepening, alpha-beta, quiescence search, MVV-LVA move ordering, killer moves,
transposition table with Zobrist hashing, and piece-square tables for positional play.
"""
import random
import time

# ---------------------------------------------------------------- constants
EMPTY = "."
WHITE, BLACK = "w", "b"
N, S, E, W = -16, 16, 1, -1
KNIGHT_DIRS = (N + N + E, N + N + W, S + S + E, S + S + W, E + E + N, E + E + S, W + W + N, W + W + S)
BISHOP_DIRS = (N + E, N + W, S + E, S + W)
ROOK_DIRS = (N, S, E, W)
KING_DIRS = BISHOP_DIRS + ROOK_DIRS
VALUES = {"P": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 0}
MATE = 100000

# Piece-square tables (from White's point of view, a8..h1 row by row). Encourage good squares.
PST = {
    "P": [0, 0, 0, 0, 0, 0, 0, 0, 50, 50, 50, 50, 50, 50, 50, 50, 10, 10, 20, 30, 30, 20, 10, 10,
          5, 5, 10, 25, 25, 10, 5, 5, 0, 0, 0, 20, 20, 0, 0, 0, 5, -5, -10, 0, 0, -10, -5, 5,
          5, 10, 10, -20, -20, 10, 10, 5, 0, 0, 0, 0, 0, 0, 0, 0],
    "N": [-50, -40, -30, -30, -30, -30, -40, -50, -40, -20, 0, 0, 0, 0, -20, -40, -30, 0, 10, 15, 15, 10, 0, -30,
          -30, 5, 15, 20, 20, 15, 5, -30, -30, 0, 15, 20, 20, 15, 0, -30, -30, 5, 10, 15, 15, 10, 5, -30,
          -40, -20, 0, 5, 5, 0, -20, -40, -50, -40, -30, -30, -30, -30, -40, -50],
    "B": [-20, -10, -10, -10, -10, -10, -10, -20, -10, 0, 0, 0, 0, 0, 0, -10, -10, 0, 5, 10, 10, 5, 0, -10,
          -10, 5, 5, 10, 10, 5, 5, -10, -10, 0, 10, 10, 10, 10, 0, -10, -10, 10, 10, 10, 10, 10, 10, -10,
          -10, 5, 0, 0, 0, 0, 5, -10, -20, -10, -10, -10, -10, -10, -10, -20],
    "R": [0, 0, 0, 0, 0, 0, 0, 0, 5, 10, 10, 10, 10, 10, 10, 5, -5, 0, 0, 0, 0, 0, 0, -5, -5, 0, 0, 0, 0, 0, 0, -5,
          -5, 0, 0, 0, 0, 0, 0, -5, -5, 0, 0, 0, 0, 0, 0, -5, -5, 0, 0, 0, 0, 0, 0, -5, 0, 0, 0, 5, 5, 0, 0, 0],
    "Q": [-20, -10, -10, -5, -5, -10, -10, -20, -10, 0, 0, 0, 0, 0, 0, -10, -10, 0, 5, 5, 5, 5, 0, -10,
          -5, 0, 5, 5, 5, 5, 0, -5, 0, 0, 5, 5, 5, 5, 0, -5, -10, 5, 5, 5, 5, 5, 0, -10,
          -10, 0, 5, 0, 0, 0, 0, -10, -20, -10, -10, -5, -5, -10, -10, -20],
    "K": [-30, -40, -40, -50, -50, -40, -40, -30, -30, -40, -40, -50, -50, -40, -40, -30, -30, -40, -40, -50, -50, -40, -40, -30,
          -30, -40, -40, -50, -50, -40, -40, -30, -20, -30, -30, -40, -40, -30, -30, -20, -10, -20, -20, -20, -20, -20, -20, -10,
          20, 20, 0, 0, 0, 0, 20, 20, 20, 30, 10, 0, 0, 10, 30, 20],
    "K_END": [-50, -40, -30, -20, -20, -30, -40, -50, -30, -20, -10, 0, 0, -10, -20, -30, -30, -10, 20, 30, 30, 20, -10, -30,
              -30, -10, 30, 40, 40, 30, -10, -30, -30, -10, 30, 40, 40, 30, -10, -30, -30, -10, 20, 30, 30, 20, -10, -30,
              -30, -30, 0, 0, 0, 0, -30, -30, -50, -30, -30, -30, -30, -30, -30, -50],
}


def sq(name):  # "e4" -> 0x88 index
    return (8 - int(name[1])) * 16 + (ord(name[0]) - 97)


def name(s):  # 0x88 index -> "e4"
    return "abcdefgh"[s & 7] + str(8 - (s >> 4))


def color_of(piece):
    return WHITE if piece.isupper() else BLACK


def pst_index(s, color):  # map 0x88 square to 0..63 from that side's point of view
    r, f = s >> 4, s & 7
    return (r if color == WHITE else 7 - r) * 8 + f


# Zobrist hashing: random 64-bit number per (piece, square), XORed together = position fingerprint
_rng = random.Random(2026)
ZOBRIST = {(p, s): _rng.getrandbits(64) for p in "PNBRQKpnbrqk" for s in range(128) if not s & 0x88}
Z_SIDE = _rng.getrandbits(64)
Z_CASTLE = {c: _rng.getrandbits(64) for c in "KQkq"}
Z_EP = {f: _rng.getrandbits(64) for f in range(8)}


class Move:
    __slots__ = ("frm", "to", "promo", "flag")

    def __init__(self, frm, to, promo=None, flag=None):
        self.frm, self.to, self.promo, self.flag = frm, to, promo, flag  # flag: 'ep', 'castle', 'double'

    def uci(self):
        return name(self.frm) + name(self.to) + (self.promo.lower() if self.promo else "")

    def __eq__(self, o):
        return isinstance(o, Move) and (self.frm, self.to, self.promo) == (o.frm, o.to, o.promo)

    def __hash__(self):
        return hash((self.frm, self.to, self.promo))

    __repr__ = uci


class Board:
    START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    def __init__(self, fen=START):
        self.load(fen)

    # ------------------------------------------------------------ setup / FEN
    def load(self, fen):
        parts = fen.split()
        self.b = [EMPTY] * 128
        r = 0
        for row in parts[0].split("/"):
            f = 0
            for ch in row:
                if ch.isdigit():
                    f += int(ch)
                else:
                    self.b[r * 16 + f] = ch
                    f += 1
            r += 1
        self.turn = parts[1]
        self.castling = "" if parts[2] == "-" else parts[2]
        self.ep = None if parts[3] == "-" else sq(parts[3])
        self.halfmove = int(parts[4]) if len(parts) > 4 else 0
        self.fullmove = int(parts[5]) if len(parts) > 5 else 1
        self.kings = {color_of(p): s for s, p in enumerate(self.b) if p in "Kk"}
        self.history = []
        self.hash = self.compute_hash()
        self.positions = [self.hash]

    def fen(self):
        rows = []
        for r in range(8):
            row, empty = "", 0
            for f in range(8):
                p = self.b[r * 16 + f]
                if p == EMPTY:
                    empty += 1
                else:
                    row += (str(empty) if empty else "") + p
                    empty = 0
            rows.append(row + (str(empty) if empty else ""))
        return f"{'/'.join(rows)} {self.turn} {self.castling or '-'} {name(self.ep) if self.ep is not None else '-'} {self.halfmove} {self.fullmove}"

    def compute_hash(self):
        h = 0
        for s, p in enumerate(self.b):
            if p != EMPTY and not s & 0x88:
                h ^= ZOBRIST[(p, s)]
        if self.turn == BLACK:
            h ^= Z_SIDE
        for c in self.castling:
            h ^= Z_CASTLE[c]
        if self.ep is not None:
            h ^= Z_EP[self.ep & 7]
        return h

    # ------------------------------------------------------------ attacks
    def attacked(self, s, by):
        """Is square s attacked by color `by`? (Looks outward from s, which is faster than generating all moves.)"""
        b = self.b
        pawn, knight, bishop, rook, queen, king = ("PNBRQK" if by == WHITE else "pnbrqk")
        pawn_from = (S + E, S + W) if by == WHITE else (N + E, N + W)
        for d in pawn_from:
            t = s + d
            if not t & 0x88 and b[t] == pawn:
                return True
        for d in KNIGHT_DIRS:
            t = s + d
            if not t & 0x88 and b[t] == knight:
                return True
        for d in KING_DIRS:
            t = s + d
            if not t & 0x88 and b[t] == king:
                return True
        for dirs, pieces in ((BISHOP_DIRS, (bishop, queen)), (ROOK_DIRS, (rook, queen))):
            for d in dirs:
                t = s + d
                while not t & 0x88:
                    if b[t] != EMPTY:
                        if b[t] in pieces:
                            return True
                        break
                    t += d
        return False

    def in_check(self, color=None):
        color = color or self.turn
        return self.attacked(self.kings[color], BLACK if color == WHITE else WHITE)

    # ------------------------------------------------------------ move generation
    def pseudo_moves(self, captures_only=False):
        b, me = self.b, self.turn
        them = BLACK if me == WHITE else WHITE
        moves = []
        for s in range(128):
            if s & 0x88:
                continue
            p = b[s]
            if p == EMPTY or color_of(p) != me:
                continue
            kind = p.upper()
            if kind == "P":
                fwd, start_rank, promo_rank = (N, 6, 0) if me == WHITE else (S, 1, 7)
                t = s + fwd
                if not captures_only and not t & 0x88 and b[t] == EMPTY:
                    self._add_pawn(moves, s, t, promo_rank)
                    t2 = t + fwd
                    if s >> 4 == start_rank and b[t2] == EMPTY:
                        moves.append(Move(s, t2, flag="double"))
                for d in (fwd + E, fwd + W):
                    t = s + d
                    if t & 0x88:
                        continue
                    if b[t] != EMPTY and color_of(b[t]) == them:
                        self._add_pawn(moves, s, t, promo_rank)
                    elif t == self.ep:
                        moves.append(Move(s, t, flag="ep"))
            elif kind in "NK":
                for d in (KNIGHT_DIRS if kind == "N" else KING_DIRS):
                    t = s + d
                    if t & 0x88:
                        continue
                    if b[t] == EMPTY:
                        if not captures_only:
                            moves.append(Move(s, t))
                    elif color_of(b[t]) == them:
                        moves.append(Move(s, t))
            else:
                dirs = BISHOP_DIRS if kind == "B" else ROOK_DIRS if kind == "R" else KING_DIRS
                for d in dirs:
                    t = s + d
                    while not t & 0x88:
                        if b[t] == EMPTY:
                            if not captures_only:
                                moves.append(Move(s, t))
                        else:
                            if color_of(b[t]) == them:
                                moves.append(Move(s, t))
                            break
                        t += d
        if not captures_only:
            self._castle_moves(moves)
        return moves

    def _add_pawn(self, moves, s, t, promo_rank):
        if t >> 4 == promo_rank:
            for pr in "QRBN":
                moves.append(Move(s, t, pr if self.turn == WHITE else pr.lower()))
        else:
            moves.append(Move(s, t))

    def _castle_moves(self, moves):
        me = self.turn
        them = BLACK if me == WHITE else WHITE
        rank = 0x70 if me == WHITE else 0x00
        k_right, q_right = ("K", "Q") if me == WHITE else ("k", "q")
        if self.kings[me] != rank + 4 or self.attacked(rank + 4, them):
            return
        b = self.b
        if k_right in self.castling and b[rank + 5] == b[rank + 6] == EMPTY \
                and not self.attacked(rank + 5, them) and not self.attacked(rank + 6, them):
            moves.append(Move(rank + 4, rank + 6, flag="castle"))
        if q_right in self.castling and b[rank + 3] == b[rank + 2] == b[rank + 1] == EMPTY \
                and not self.attacked(rank + 3, them) and not self.attacked(rank + 2, them):
            moves.append(Move(rank + 4, rank + 2, flag="castle"))

    def legal_moves(self, captures_only=False):
        legal = []
        me = self.turn
        for m in self.pseudo_moves(captures_only):
            self.push(m)
            if not self.in_check(me):
                legal.append(m)
            self.pop()
        return legal

    # ------------------------------------------------------------ make / unmake
    def push(self, m):
        b = self.b
        piece, captured = b[m.frm], b[m.to]
        self.history.append((m, captured, self.castling, self.ep, self.halfmove, self.hash))
        h = self.hash ^ ZOBRIST[(piece, m.frm)]
        if captured != EMPTY:
            h ^= ZOBRIST[(captured, m.to)]
        if self.ep is not None:
            h ^= Z_EP[self.ep & 7]
        for c in self.castling:
            h ^= Z_CASTLE[c]

        b[m.to], b[m.frm] = piece, EMPTY
        if m.flag == "ep":
            cap_sq = m.to + (S if self.turn == WHITE else N)
            h ^= ZOBRIST[(b[cap_sq], cap_sq)]
            b[cap_sq] = EMPTY
        elif m.flag == "castle":
            rook_from, rook_to = (m.to + 1, m.to - 1) if m.to > m.frm else (m.to - 2, m.to + 1)
            rook = b[rook_from]
            b[rook_to], b[rook_from] = rook, EMPTY
            h ^= ZOBRIST[(rook, rook_from)] ^ ZOBRIST[(rook, rook_to)]
        if m.promo:
            b[m.to] = m.promo
        h ^= ZOBRIST[(b[m.to], m.to)]

        if piece in "Kk":
            self.kings[self.turn] = m.to
        # moving a king or rook (or capturing a rook) removes castling rights
        for corner, right in ((0x77, "K"), (0x70, "Q"), (0x07, "k"), (0x00, "q")):
            if m.frm == corner or m.to == corner:
                self.castling = self.castling.replace(right, "")
        if piece == "K":
            self.castling = self.castling.replace("K", "").replace("Q", "")
        elif piece == "k":
            self.castling = self.castling.replace("k", "").replace("q", "")
        for c in self.castling:
            h ^= Z_CASTLE[c]

        self.ep = (m.frm + m.to) // 2 if m.flag == "double" else None
        if self.ep is not None:
            h ^= Z_EP[self.ep & 7]
        self.halfmove = 0 if piece in "Pp" or captured != EMPTY else self.halfmove + 1
        if self.turn == BLACK:
            self.fullmove += 1
        self.turn = BLACK if self.turn == WHITE else WHITE
        self.hash = h ^ Z_SIDE
        self.positions.append(self.hash)

    def pop(self):
        m, captured, self.castling, self.ep, self.halfmove, self.hash = self.history.pop()
        self.positions.pop()
        self.turn = BLACK if self.turn == WHITE else WHITE
        if self.turn == BLACK:
            self.fullmove -= 1
        b = self.b
        piece = b[m.to]
        if m.promo:
            piece = "P" if self.turn == WHITE else "p"
        b[m.frm], b[m.to] = piece, captured
        if m.flag == "ep":
            b[m.to + (S if self.turn == WHITE else N)] = "p" if self.turn == WHITE else "P"
        elif m.flag == "castle":
            rook_from, rook_to = (m.to + 1, m.to - 1) if m.to > m.frm else (m.to - 2, m.to + 1)
            b[rook_from], b[rook_to] = b[rook_to], EMPTY
        if piece in "Kk":
            self.kings[self.turn] = m.frm
        return m

    # ------------------------------------------------------------ game state
    def is_repetition(self, times=3):
        return self.positions.count(self.hash) >= times

    def insufficient_material(self):
        pieces = [p.upper() for p in self.b if p not in (EMPTY,) and p.upper() != "K"]
        return not pieces or (len(pieces) == 1 and pieces[0] in "NB")

    def outcome(self):
        """Returns None while the game is on, else a description string."""
        if not self.legal_moves():
            if self.in_check():
                return ("Black" if self.turn == WHITE else "White") + " wins by checkmate"
            return "Draw by stalemate"
        if self.halfmove >= 100:
            return "Draw by 50-move rule"
        if self.is_repetition():
            return "Draw by threefold repetition"
        if self.insufficient_material():
            return "Draw by insufficient material"
        return None

    def parse_move(self, text):
        text = text.strip().lower()
        for m in self.legal_moves():
            if m.uci() == text or (len(text) == 4 and m.uci() == text + "q"):
                return m
        return None

    def __str__(self):
        glyphs = dict(zip("KQRBNPkqrbnp", "♔♕♖♗♘♙♚♛♜♝♞♟"))
        lines = []
        for r in range(8):
            row = " ".join(glyphs.get(self.b[r * 16 + f], "·") for f in range(8))
            lines.append(f"{8 - r}  {row}")
        lines.append("   a b c d e f g h")
        return "\n".join(lines)


# ---------------------------------------------------------------- perft (rules verification)
def perft(board, depth):
    if depth == 0:
        return 1
    total = 0
    for m in board.legal_moves():
        board.push(m)
        total += perft(board, depth - 1)
        board.pop()
    return total


# ---------------------------------------------------------------- AI
class Engine:
    def __init__(self):
        self.tt = {}  # hash -> (depth, score, flag, best_move)
        self.killers = {}
        self.nodes = 0

    def evaluate(self, board):
        """Score from the side-to-move's point of view: material + piece-square bonuses."""
        score = 0
        material = sum(VALUES[p.upper()] for p in board.b if p not in (EMPTY,) and p.upper() not in "KP")
        endgame = material <= 2600
        for s in range(128):
            if s & 0x88:
                continue
            p = board.b[s]
            if p == EMPTY:
                continue
            c = color_of(p)
            kind = p.upper()
            table = PST["K_END"] if kind == "K" and endgame else PST[kind]
            val = VALUES[kind] + table[pst_index(s, c)]
            score += val if c == WHITE else -val
        return score if board.turn == WHITE else -score

    def order(self, board, moves, tt_move, ply):
        def key(m):
            if m == tt_move:
                return -10_000_000
            victim = board.b[m.to]
            if victim != EMPTY or m.flag == "ep":  # MVV-LVA: big victim, small attacker first
                v = VALUES[victim.upper()] if victim != EMPTY else 100
                return -1_000_000 - v * 10 + VALUES[board.b[m.frm].upper()] // 10
            if m.promo:
                return -900_000
            if m in self.killers.get(ply, ()):
                return -500_000
            return 0
        return sorted(moves, key=key)

    def quiescence(self, board, alpha, beta):
        """Keep searching captures so we never stop in the middle of an exchange."""
        self.nodes += 1
        stand = self.evaluate(board)
        if stand >= beta:
            return beta
        alpha = max(alpha, stand)
        for m in self.order(board, board.legal_moves(captures_only=True), None, 99):
            board.push(m)
            score = -self.quiescence(board, -beta, -alpha)
            board.pop()
            if score >= beta:
                return beta
            alpha = max(alpha, score)
        return alpha

    def search(self, board, depth, alpha, beta, ply):
        self.nodes += 1
        if ply > 0 and (board.is_repetition(2) or board.halfmove >= 100):
            return 0
        entry = self.tt.get(board.hash)
        tt_move = entry[3] if entry else None
        if entry and entry[0] >= depth and ply > 0:
            _, score, flag, _ = entry
            if flag == "exact" or (flag == "lower" and score >= beta) or (flag == "upper" and score <= alpha):
                return score
        if depth == 0:
            return self.quiescence(board, alpha, beta)

        moves = board.legal_moves()
        if not moves:
            return -MATE + ply if board.in_check() else 0  # prefer faster mates

        alpha0, best, best_move = alpha, -MATE * 2, None
        for m in self.order(board, moves, tt_move, ply):
            board.push(m)
            score = -self.search(board, depth - 1, -beta, -alpha, ply + 1)
            board.pop()
            if score > best:
                best, best_move = score, m
            alpha = max(alpha, score)
            if alpha >= beta:
                if board.b[m.to] == EMPTY:  # remember quiet moves that cause cut-offs
                    self.killers.setdefault(ply, [])
                    if m not in self.killers[ply]:
                        self.killers[ply] = [m] + self.killers[ply][:1]
                break
        flag = "upper" if best <= alpha0 else "lower" if best >= beta else "exact"
        self.tt[board.hash] = (depth, best, flag, best_move)
        return best

    def best_move(self, board, max_depth=4, time_limit=3.0, verbose=True):
        """Iterative deepening: search depth 1, 2, 3… reusing earlier results to order moves."""
        self.nodes, start, best = 0, time.time(), None
        for depth in range(1, max_depth + 1):
            score = self.search(board, depth, -MATE * 2, MATE * 2, 0)
            entry = self.tt.get(board.hash)
            if entry and entry[3]:
                best = entry[3]
            elapsed = time.time() - start
            if verbose:
                shown = f"mate in {(MATE - abs(score) + 1) // 2}" if abs(score) > MATE - 100 else f"{score / 100:+.2f}"
                print(f"  depth {depth}: {best.uci() if best else '-':6s} eval {shown:>9s}  {self.nodes:>7} nodes  {elapsed:.2f}s")
            if abs(score) > MATE - 100 or elapsed > time_limit / 3:
                break  # found a mate, or the next depth would likely run out of time
        if best is None:
            best = board.legal_moves()[0]
        return best


# ---------------------------------------------------------------- play in the terminal
def main():
    board, engine = Board(), Engine()
    print("Chess engine. Enter moves like e2e4 (promotion: e7e8n). Commands: undo, moves, fen, quit.")
    side = input("Play as (w)hite or (b)lack? [w] ").strip().lower() or "w"
    human = BLACK if side.startswith("b") else WHITE
    while True:
        print("\n" + str(board))
        result = board.outcome()
        if result:
            print("\n" + result)
            break
        if board.in_check():
            print("Check!")
        if board.turn == human:
            cmd = input("Your move: ").strip().lower()
            if cmd == "quit":
                break
            if cmd == "undo" and len(board.history) >= 2:
                board.pop()
                board.pop()
                continue
            if cmd == "moves":
                print(" ".join(m.uci() for m in board.legal_moves()))
                continue
            if cmd == "fen":
                print(board.fen())
                continue
            move = board.parse_move(cmd)
            if not move:
                print("Illegal move. Type 'moves' to see legal moves.")
                continue
            board.push(move)
        else:
            print("Engine thinking…")
            move = engine.best_move(board)
            print(f"Engine plays {move.uci()}")
            board.push(move)


if __name__ == "__main__":
    main()
