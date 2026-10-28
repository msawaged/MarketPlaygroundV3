# backend/gpt_test_driver.py

from ai_engine.gpt4_strategy_generator import generate_strategy_with_gpt4

if __name__ == "__main__":
    test_belief = "I believe TSLA will rise 20% over the next 3 months due to strong earnings and EV demand"
    result = generate_strategy_with_gpt4(test_belief)
    print("\n🧠 GPT Strategy Output:\n")
    print(result)
