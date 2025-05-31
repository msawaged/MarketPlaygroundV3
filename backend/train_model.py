# train_model.py

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
import joblib
import sys

# ─────────────────────────────────────────────────────────────────────────────
# This script reads historic_data.csv, trains a RandomForestRegressor to
# predict realized P/L at expiry for each option (based on impliedVolatility,
# volume, and mid_price), and saves the trained model to best_model.joblib.
# ─────────────────────────────────────────────────────────────────────────────

DATA_FILE  = "historic_data.csv"
MODEL_FILE = "best_model.joblib"

def main():
    # 1) Attempt to read the CSV
    try:
        df = pd.read_csv(DATA_FILE)
    except FileNotFoundError:
        print(f"ERROR: '{DATA_FILE}' not found. Exiting without training.")
        sys.exit(1)
    except pd.errors.EmptyDataError:
        print(f"ERROR: '{DATA_FILE}' is empty or malformed. Exiting without training.")
        sys.exit(1)

    # 2) Check that there is at least one data row
    #    (After read_csv, df.shape[0] counts rows excluding header.)
    num_rows = df.shape[0]
    if num_rows < 2:
        print(f"ERROR: '{DATA_FILE}' contains {num_rows} row(s) of data. Need at least 2 rows to train.")
        sys.exit(1)

    # 3) Drop any rows missing our key columns
    df = df.dropna(subset=["impliedVolatility", "volume", "mid_price", "realizedPL"])

    # 4) After dropna, check again
    num_rows_after_drop = df.shape[0]
    if num_rows_after_drop < 2:
        print(f"ERROR: After dropping NaNs, only {num_rows_after_drop} row(s) remain. Need ≥2 to train.")
        sys.exit(1)

    # 5) Build feature matrix X and target y
    #    Features: impliedVolatility, volume, mid_price
    #    Target:  realizedPL
    X = df[["impliedVolatility", "volume", "mid_price"]].to_numpy()
    y = df["realizedPL"].to_numpy()

    # 6) Split into train/test (90% train, 10% test)
    #    random_state=42 ensures reproducibility
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.10, random_state=42
    )

    # 7) Print how many rows ended up in train vs. test
    print(f"Training rows: {X_train.shape[0]}, Test rows: {X_test.shape[0]}")

    if X_train.shape[0] < 1:
        print("ERROR: No training rows after split. Cannot train. Exiting.")
        sys.exit(1)

    # 8) Fit a RandomForestRegressor
    model = RandomForestRegressor(
        n_estimators=200,
        max_depth=10,
        random_state=42
    )
    try:
        model.fit(X_train, y_train)
    except Exception as e:
        print("ERROR during model.fit():", e)
        sys.exit(1)

    # 9) Evaluate on test set
    try:
        r2 = model.score(X_test, y_test)
    except Exception as e:
        print("WARNING: Could not compute R^2 on test set:", e)
        r2 = None

    if r2 is not None:
        print(f"R^2 on test set: {r2:.4f}")
    else:
        print("R^2 on test set: n/a")

    # 10) Save the trained model to disk
    try:
        joblib.dump(model, MODEL_FILE)
        print(f"Trained model saved to {MODEL_FILE}")
    except Exception as e:
        print("ERROR saving model to disk:", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
