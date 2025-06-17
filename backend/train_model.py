# train_model.py

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from joblib import dump

# Path to your historic data CSV
DATA_FILE = "historic_data.csv"

def main():
    # 1) Load the full dataset
    df = pd.read_csv(DATA_FILE)

    # 2) Drop any rows missing required columns
    required_cols = [
        "impliedVolatility",
        "volume",
        "mid_price",
        "strike",
        "openInterest",
        "underlyingReturn",
        "assetType",
        "realizedPL"
    ]
    df = df.dropna(subset=required_cols)

    # If there aren’t enough rows, abort
    if len(df) < 10:
        print(f"[train_model.py] Not enough rows to train (only {len(df)}). Skipping.")
        return

    # 3) Define feature columns X and target y
    feature_cols = [
        "impliedVolatility",
        "volume",
        "mid_price",
        "strike",
        "openInterest",
        "underlyingReturn",
        "assetType"
    ]
    X = df[feature_cols]
    y = df["realizedPL"]

    # 4) Specify numeric vs. categorical features
    numeric_features = [
        "impliedVolatility",
        "volume",
        "mid_price",
        "strike",
        "openInterest",
        "underlyingReturn"
    ]
    categorical_features = ["assetType"]

    # 5) Build transformers
    numeric_transformer = StandardScaler()
    categorical_transformer = OneHotEncoder(handle_unknown="ignore")

    # 6) ColumnTransformer: scale numeric, one-hot encode assetType
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, numeric_features),
            ("cat", categorical_transformer, categorical_features)
        ]
    )

    # 7) Build the pipeline: preprocessing + random forest regressor
    model_pipeline = Pipeline(steps=[
        ("preprocessor", preprocessor),
        (
            "regressor",
            RandomForestRegressor(
                n_estimators=200,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
        )
    ])

    # 8) Split into train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.1, random_state=42
    )

    # 9) Fit the model
    model_pipeline.fit(X_train, y_train)

    # 10) Evaluate on test set
    r2 = model_pipeline.score(X_test, y_test)
    print(f"[train_model.py] Training rows: {len(X_train)}, Test rows: {len(X_test)}")
    print(f"[train_model.py] R^2 on test set: {r2:.4f}")

    # 11) Save the full pipeline to disk
    dump(model_pipeline, "best_model.joblib")
    print("[train_model.py] Trained model saved to best_model.joblib")

if __name__ == "__main__":
    main()
