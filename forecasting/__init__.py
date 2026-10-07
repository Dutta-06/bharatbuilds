"""Step 4: 48 h forecast models for wet-bulb and carbon intensity, with baselines.

Training (scikit-learn) happens offline in scripts/train_forecasts.py. The trained
gradient-boosted trees are exported to JSON (forecasting/trees.py) and evaluated in
pure Python, so the Lambda layer needs neither scikit-learn nor numpy.
"""
