# ============================================================
# backend/tools/test_creative_mapping.py
# ============================================================
# PURPOSE:
#   - Standalone tester for Creative Mapping logic.
#   - Lets you run ticker mapping experiments from CLI,
#     without touching ai_engine.py or production routes.
#
# USAGE EXAMPLES:
#   python -m backend.tools.test_creative_mapping "Taylor Swift is impacting markets"
#   python -m backend.tools.test_creative_mapping "the market will rise this month"
#
# EXPECTED OUTPUT:
#   Belief: <your input>
#   Candidates: [ {symbol, score, why}, ... ]
#   Best: {symbol, score, why}
#
# SAFETY:
#   - Reads from creative_mapper only.
#   - No changes to strategy pipeline.
# ============================================================

import sys
from backend.signal_mapping.creative_mapper import generate_symbol_candidates, choose_best_candidate

def main():
    # --------------------------------------------------------
    # Handle CLI args
    # --------------------------------------------------------
    if len(sys.argv) < 2:
        print("Usage: python -m backend.tools.test_creative_mapping \"<belief>\"")
        raise SystemExit(1)

    belief = sys.argv[1]

    # --------------------------------------------------------
    # Generate candidates
    # --------------------------------------------------------
    cands = generate_symbol_candidates(belief)
    best = choose_best_candidate(cands)

    # --------------------------------------------------------
    # Pretty print results
    # --------------------------------------------------------
    print("===================================")
    print(" Belief:", belief)
    print("===================================")
    print(" Candidates:")
    for c in cands:
        print(f"  - {c['symbol']} (score={c['score']}) :: {c['why']}")
    print("===================================")
    print(" Best Candidate:", best if best else "None (fallback to SPY/QQQ)")
    print("===================================")


if __name__ == "__main__":
    main()
