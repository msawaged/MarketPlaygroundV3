#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from belief_parser import parse_belief

test_beliefs = [
    "Tesla will rally to 200",
    "Bitcoin will hit 100k soon", 
    "NVDA going to moon",
    "TSLA calls look good"
]

for belief in test_beliefs:
    parsed = parse_belief(belief)
    print(f"'{belief}' → ticker: {parsed['ticker']}, direction: {parsed['direction']}")