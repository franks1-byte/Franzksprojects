"""
Verification suite. Perft counts every legal move sequence to a fixed depth; if a single rule
(castling, en passant, promotion, pins, checks) were wrong, these numbers would not match the
published values from the Chess Programming Wiki.

Run:  python test_engine.py
"""
import time

from chess_engine import Board, Engine, perft

PERFT_CASES = [
    # (name, FEN, depth, expected)
    ("Start position", Board.START, 4, 197281),
    ("Kiwipete (castling, pins, en passant)", "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1", 3, 97862),
    ("Position 3 (en passant edge cases)", "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", 4, 43238),
    ("Position 4 (promotions, checks)", "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1", 3, 9467),
    ("Position 5", "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8", 3, 62379),
]


def run_perft():
    ok = True
    for label, fen, depth, expected in PERFT_CASES:
        board = Board(fen)
        before = board.fen()
        t = time.time()
        got = perft(board, depth)
        status = "PASS" if got == expected else "FAIL"
        ok &= got == expected
        assert board.fen() == before, "push/pop did not restore the board!"
        print(f"  {status}  {label:40s} depth {depth}: {got:>7} (expected {expected})  {time.time() - t:.1f}s")
    return ok


def run_tactics():
    """The engine should find these forced wins (answers verified with the python-chess library)."""
    cases = [
        ("Mate in 1 (back rank)", "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1", {"d1d8"}),
        ("Smothered mate in 1", "6rk/6pp/8/6N1/8/8/8/4Q1K1 w - - 0 1", {"g5f7"}),
        ("Mate in 2 (rook ladder)", "7k/8/8/8/8/8/R7/1R4K1 w - - 0 1", {"a2a7", "b1b7"}),
        ("Knight fork wins the queen", "q3k3/8/8/1N6/8/8/8/4K3 w - - 0 1", {"b5c7"}),
        ("Grab the hanging rook", "4k3/8/8/3r4/8/8/3Q4/4K3 w - - 0 1", {"d2d5"}),
    ]
    ok = True
    engine = Engine()
    for label, fen, answers in cases:
        engine.tt.clear()
        move = engine.best_move(Board(fen), max_depth=4, time_limit=20, verbose=False).uci()
        good = move in answers
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {label:30s} engine played {move}  (expected {' or '.join(sorted(answers))})")
    return ok


def run_rules():
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= cond
        print(f"  {'PASS' if cond else 'FAIL'}  {label}")

    b = Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    check("Stalemate detected", b.outcome() == "Draw by stalemate")
    b = Board("6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1")
    b.push(b.parse_move("d1d8"))
    check("Checkmate detected", b.outcome() == "White wins by checkmate")
    b = Board()
    for mv in ["g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1", "f6g8"]:
        b.push(b.parse_move(mv))
    check("Threefold repetition detected", b.outcome() == "Draw by threefold repetition")
    check("Insufficient material (K+B vs K)", Board("8/8/4k3/8/8/2B5/8/4K3 w - - 0 1").outcome() == "Draw by insufficient material")
    b = Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    b.push(b.parse_move("e1g1"))
    check("Castling moves the rook", b.fen().startswith("r3k2r/8/8/8/8/8/8/R4RK1 b kq"))
    b = Board("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1")
    b.push(b.parse_move("e5d6"))
    check("En passant removes the pawn", b.fen().startswith("4k3/8/3P4/8/8/8/8/4K3"))
    b = Board("8/4P2k/8/8/8/8/8/4K3 w - - 0 1")
    b.push(b.parse_move("e7e8n"))
    check("Under-promotion to knight", b.fen().startswith("4N3/7k"))
    b = Board()
    h0 = b.hash
    b.push(b.parse_move("e2e4"))
    check("Zobrist hash updates match a full recompute", b.hash == b.compute_hash())
    b.pop()
    check("Hash restored after undo", b.hash == h0)
    return ok


if __name__ == "__main__":
    print("Perft (move generation correctness):")
    p = run_perft()
    print("\nRules:")
    r = run_rules()
    print("\nTactics (engine strength):")
    t = run_tactics()
    print("\nALL TESTS PASSED" if p and r and t else "\nSOME TESTS FAILED")
