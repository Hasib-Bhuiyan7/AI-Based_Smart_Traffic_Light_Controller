import csv
import os
import math

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error


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

    if phase_flag == 0:  # NS active
        cars_active = cars_N + cars_S
        cars_opposing = cars_E + cars_W

        wait_active = wait_N + wait_S
        wait_opposing = wait_E + wait_W

        active_imbalance = abs(cars_N - cars_S)
        opposing_imbalance = abs(cars_E - cars_W)
    else:  # EW active
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
    rows = []

    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found!")
        return None, None, None

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
            return None, None, None

        for row in reader:
            try:
                X.append(build_features_from_row(row))
                y.append(float(row["best_green_time"]))
                rows.append(row)
            except ValueError as e:
                print(f"Skipping bad row due to conversion error: {e}")
                continue

    return X, y, rows


def main():
    csv_path = "optimal_dataset.csv"

    X, y, rows = load_data(csv_path)
    if X is None:
        return

    if len(X) < 20:
        print("Not enough data for a meaningful train/test split.")
        print(f"Current samples: {len(X)}")
        return

    print(f"Loaded {len(X)} samples from {csv_path}")

    X_train, X_test, y_train, y_test, rows_train, rows_test = train_test_split(
        X, y, rows, test_size=0.2, random_state=42
    )

    print(f"Train size: {len(X_train)}")
    print(f"Test size : {len(X_test)}")

    model = RandomForestRegressor(
        n_estimators=300,
        max_depth=None,
        min_samples_split=2,
        min_samples_leaf=1,
        random_state=42,
        n_jobs=-1
    )

    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    mae = mean_absolute_error(y_test, y_pred)
    rmse = math.sqrt(mean_squared_error(y_test, y_pred))

    y_pred_rounded = [int(round(v)) for v in y_pred]
    y_test_int = [int(round(v)) for v in y_test]

    exact_matches = sum(1 for yt, yp in zip(y_test_int, y_pred_rounded) if yt == yp)
    within_10 = sum(1 for yt, yp in zip(y_test_int, y_pred_rounded) if abs(yt - yp) <= 10)

    exact_acc = exact_matches / len(y_test_int)
    within_10_acc = within_10 / len(y_test_int)

    print("\nEvaluation Results")
    print("------------------")
    print(f"MAE                  : {mae:.3f}")
    print(f"RMSE                 : {rmse:.3f}")
    print(f"Exact match accuracy : {exact_acc:.3f}")
    print(f"Within 10s accuracy  : {within_10_acc:.3f}")

    print("\nFeature importances:")
    for name, importance in sorted(
        zip(FEATURE_NAMES, model.feature_importances_),
        key=lambda x: x[1],
        reverse=True
    ):
        print(f"  {name:18s}: {importance:.4f}")

    print("\nSample predictions:")
    print("-------------------")
    sample_count = min(20, len(y_test))

    for i in range(sample_count):
        row = rows_test[i]
        true_val = y_test[i]
        pred_val = y_pred[i]

        phase_name = "EW" if int(float(row["phase_flag"])) == 1 else "NS"

        print(
            f"[{i+1:02d}] "
            f"Phase={phase_name} | "
            f"N={row['cars_N']} S={row['cars_S']} E={row['cars_E']} W={row['cars_W']} | "
            f"True={true_val:.1f} | Pred={pred_val:.2f} | Rounded={int(round(pred_val))}"
        )


if __name__ == "__main__":
    main()