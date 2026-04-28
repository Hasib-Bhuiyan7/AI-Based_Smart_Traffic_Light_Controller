import csv
import joblib
import os

from sklearn.ensemble import RandomForestRegressor

# Final model feature order
FEATURE_NAMES = [
    "cars_N", "cars_S", "cars_E", "cars_W",
    "wait_N", "wait_S", "wait_E", "wait_W",
    "phase_flag", "rush_flag", "ped_flag",
    "cars_active", "cars_opposing",
    "wait_active", "wait_opposing",
    "active_imbalance", "opposing_imbalance",
    "cars_pressure", "wait_pressure",
    "cars_ratio", "wait_ratio",
]


def build_features_from_row(row):
    """
    Build the final feature vector from one CSV row.

    phase_flag:
        0 = North-South phase
        1 = East-West phase
    """
    cars_N = float(row["cars_N"])
    cars_S = float(row["cars_S"])
    cars_E = float(row["cars_E"])
    cars_W = float(row["cars_W"])

    wait_N = float(row["wait_N"])
    wait_S = float(row["wait_S"])
    wait_E = float(row["wait_E"])
    wait_W = float(row["wait_W"])

    phase_flag = float(row["phase_flag"])
    rush_flag = float(row["rush_flag"])
    ped_flag = float(row["ped_flag"])

    if phase_flag == 0:  # NS is active
        cars_active = cars_N + cars_S
        cars_opposing = cars_E + cars_W

        wait_active = wait_N + wait_S
        wait_opposing = wait_E + wait_W

        active_imbalance = abs(cars_N - cars_S)
        opposing_imbalance = abs(cars_E - cars_W)
    else:  # EW is active
        cars_active = cars_E + cars_W
        cars_opposing = cars_N + cars_S

        wait_active = wait_E + wait_W
        wait_opposing = wait_N + wait_S

        active_imbalance = abs(cars_E - cars_W)
        opposing_imbalance = abs(cars_N - cars_S)

    cars_pressure = cars_active - cars_opposing
    wait_pressure = wait_active - wait_opposing

    cars_ratio = cars_active / (cars_opposing + 1.0)
    wait_ratio = wait_active / (wait_opposing + 1.0)

    return [
        cars_N, cars_S, cars_E, cars_W,
        wait_N, wait_S, wait_E, wait_W,
        phase_flag, rush_flag, ped_flag,
        cars_active, cars_opposing,
        wait_active, wait_opposing,
        active_imbalance, opposing_imbalance,
        cars_pressure, wait_pressure,
        cars_ratio, wait_ratio,
    ]


def load_data(csv_path="optimal_dataset.csv"):
    X = []
    y = []

    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found!")
        return None, None

    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)

        required_cols = {
            "cars_N", "cars_S", "cars_E", "cars_W",
            "wait_N", "wait_S", "wait_E", "wait_W",
            "phase_flag", "rush_flag", "ped_flag",
            "best_green_time",
        }

        missing = required_cols - set(reader.fieldnames or [])
        if missing:
            print("Error: dataset is missing required columns:")
            for col in sorted(missing):
                print(" -", col)
            return None, None

        for row in reader:
            try:
                X.append(build_features_from_row(row))
                y.append(float(row["best_green_time"]))
            except ValueError as e:
                print(f"Skipping bad row due to conversion error: {e}")
                continue

    return X, y


def main():
    csv_path = "optimal_dataset.csv"
    model_path = "decision_model.pkl"

    X, y = load_data(csv_path)
    if X is None:
        return

    print(f"Loaded {len(X)} scenarios from {csv_path}")
    print(f"Training RandomForestRegressor on all {len(X)} samples...")

    model = RandomForestRegressor(
        n_estimators=300,
        max_depth=None,
        min_samples_split=2,
        min_samples_leaf=1,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X, y)

    print("Training complete on 100% of the dataset.")

    print("\nFeature importances:")
    for name, importance in sorted(
        zip(FEATURE_NAMES, model.feature_importances_),
        key=lambda x: x[1],
        reverse=True
    ):
        print(f"  {name:18s}: {importance:.4f}")

    bundle = {
        "model": model,
        "feature_names": FEATURE_NAMES,
    }
    joblib.dump(bundle, model_path)

    print(f"\nSaved model bundle to '{model_path}'")


if __name__ == "__main__":
    main()