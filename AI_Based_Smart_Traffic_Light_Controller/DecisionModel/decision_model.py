import os
import joblib


def is_rush_hour(hour: int) -> int:
    """
    1 = rush hour, 0 = off-peak.

    Example:
    - Morning rush: 07:00–09:00
    - Evening rush: 16:00–18:00
    """
    return 1 if (7 <= hour <= 9) or (16 <= hour <= 18) else 0


MODEL_PATH = os.path.join(os.path.dirname(__file__), "decision_model.pkl")

_bundle = joblib.load(MODEL_PATH)
_model = _bundle["model"]
_feature_names = _bundle["feature_names"]

EXPECTED_FEATURES = [
    "cars_N", "cars_S", "cars_E", "cars_W",
    "wait_N", "wait_S", "wait_E", "wait_W",
    "phase_flag", "rush_flag", "ped_flag",
    "cars_active", "cars_opposing",
    "wait_active", "wait_opposing",
    "active_imbalance", "opposing_imbalance",
    "cars_pressure", "wait_pressure",
    "cars_ratio", "wait_ratio",
]

if _feature_names != EXPECTED_FEATURES:
    raise ValueError(
        "Feature mismatch between saved model and decision_model.py.\n"
        f"Model expects: {_feature_names}\n"
        f"Code uses    : {EXPECTED_FEATURES}"
    )


def build_features(
    cars_N, cars_S, cars_E, cars_W,
    wait_N, wait_S, wait_E, wait_W,
    phase_flag, ped_flag, hour
):
    """
    Build the exact feature vector used during training.

    Parameters
    ----------
    cars_N, cars_S, cars_E, cars_W : int/float
        Raw car counts from detection/system state.
    wait_N, wait_S, wait_E, wait_W : float
        Raw waiting times from the controller/system state.
    phase_flag : int
        0 = North-South phase
        1 = East-West phase
    ped_flag : int
        1 if pedestrians are waiting for the current phase, else 0
    hour : int
        Hour of day in 24h format (0-23)

    Returns
    -------
    list[float]
        Final feature vector including derived features.
    """
    rush_flag = is_rush_hour(hour)

    cars_N = float(cars_N)
    cars_S = float(cars_S)
    cars_E = float(cars_E)
    cars_W = float(cars_W)

    wait_N = float(wait_N)
    wait_S = float(wait_S)
    wait_E = float(wait_E)
    wait_W = float(wait_W)

    phase_flag = float(phase_flag)
    ped_flag = float(ped_flag)
    rush_flag = float(rush_flag)

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


def predict_green_time(
    cars_N, cars_S, cars_E, cars_W,
    wait_N, wait_S, wait_E, wait_W,
    phase_flag, ped_flag, hour
) -> int:
    """
    Predict green time in seconds.

    Returns
    -------
    int
        Suggested green time clamped to 10-60 seconds.
    """
    features = build_features(
        cars_N, cars_S, cars_E, cars_W,
        wait_N, wait_S, wait_E, wait_W,
        phase_flag, ped_flag, hour
    )

    t_raw = _model.predict([features])[0]
    t_sec = int(round(t_raw))

    # Safety clamp
    t_sec = max(10, min(t_sec, 60))

    return t_sec