#!/bin/bash

echo "🔧 FORCING NUMPY AND JOBLIB VERSIONS FOR MODEL COMPATIBILITY..."

pip install numpy==1.23.5
pip install joblib==1.2.0
pip install scikit-learn==1.2.2

echo "✅ ENVIRONMENT PATCH COMPLETE"

echo "📦 Installing all project dependencies..."
pip install -r backend/requirements.txt

echo "🧠 Training AI model..."
python3 backend/train_model.py

echo "✅ MODEL TRAINING COMPLETE"

