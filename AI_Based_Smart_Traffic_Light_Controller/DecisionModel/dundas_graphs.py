from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt


# =========================
# USER SETTINGS
# =========================
BASE_DIR = Path(".")
DATA_DIR = BASE_DIR / "Graphs"

SUMMARY_CSV = DATA_DIR / "dundas_summary_metrics.csv"
STEP_CSV = DATA_DIR / "dundas_step_metrics.csv"
DECISION_CSV = DATA_DIR / "dundas_decision_log.csv"

OUTPUT_DIR = DATA_DIR
OUTPUT_DIR.mkdir(exist_ok=True)


# =========================
# HELPERS
# =========================
def improvement_percent(ai_value, fixed_value, higher_is_better=True):
    if fixed_value == 0:
        return 0.0
    if higher_is_better:
        return (ai_value - fixed_value) / fixed_value * 100.0
    return (fixed_value - ai_value) / fixed_value * 100.0


def safe_profile_name(profile: str) -> str:
    return str(profile).replace(" ", "_").replace("/", "_")


def save_plot(fig, filename: str):
    out_path = OUTPUT_DIR / filename
    fig.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out_path}")


def safe_numeric_convert(df, non_numeric_cols):
    for col in df.columns:
        if col in non_numeric_cols:
            continue

        converted = pd.to_numeric(df[col], errors="coerce")

        # Only replace if at least one real numeric value was found
        if not converted.isna().all():
            df[col] = converted

    return df


# =========================
# LOAD DATA
# =========================
if not SUMMARY_CSV.exists():
    raise FileNotFoundError(f"Could not find {SUMMARY_CSV}")

if not STEP_CSV.exists():
    raise FileNotFoundError(f"Could not find {STEP_CSV}")

if not DECISION_CSV.exists():
    raise FileNotFoundError(f"Could not find {DECISION_CSV}")

summary_df = pd.read_csv(SUMMARY_CSV)
step_df = pd.read_csv(STEP_CSV)
decision_df = pd.read_csv(DECISION_CSV)

non_numeric_cols = {"run_name", "profile", "controller_mode", "phase_name", "green_phase_name"}

summary_df = safe_numeric_convert(summary_df, non_numeric_cols)
step_df = safe_numeric_convert(step_df, non_numeric_cols)
decision_df = safe_numeric_convert(decision_df, non_numeric_cols)


# =========================
# SUMMARY GRAPHS
# =========================
summary_metrics = [
    ("vehicles_arrived", "Arrivals", True),
    ("throughput_veh_per_hour", "Throughput (veh/h)", True),
    ("avg_travel_time_s", "Avg travel time (s)", False),
    ("avg_depart_delay_s", "Avg depart delay (s)", False),
    ("avg_total_queue", "Avg total queue", False),
    ("max_total_queue", "Max total queue", False),
    ("avg_total_wait_s", "Avg total wait (s)", False),
    ("avg_pending_insert", "Avg pending insert", False),
    ("completion_ratio", "Completion ratio", True),
]

profiles = sorted(summary_df["profile"].dropna().unique())

for profile in profiles:
    sub = summary_df[summary_df["profile"] == profile].copy()

    ai_row = sub[sub["controller_mode"].astype(str).str.lower() == "ai"]
    fixed_row = sub[sub["controller_mode"].astype(str).str.lower() == "fixed"]

    if ai_row.empty or fixed_row.empty:
        print(f"Skipping summary plots for profile '{profile}' because AI or Fixed row is missing.")
        continue

    ai_row = ai_row.iloc[0]
    fixed_row = fixed_row.iloc[0]

    # Raw metric comparison chart
    labels = [m[1] for m in summary_metrics]
    ai_vals = [ai_row[m[0]] for m in summary_metrics]
    fixed_vals = [fixed_row[m[0]] for m in summary_metrics]

    fig = plt.figure(figsize=(14, 7))
    x = range(len(labels))
    width = 0.4
    plt.bar([i - width / 2 for i in x], fixed_vals, width=width, label="Fixed")
    plt.bar([i + width / 2 for i in x], ai_vals, width=width, label="AI")
    plt.xticks(list(x), labels, rotation=35, ha="right")
    plt.ylabel("Value")
    plt.title(f"Fixed vs AI Summary Metrics - {profile}")
    plt.legend()
    save_plot(fig, f"summary_raw_{safe_profile_name(profile)}.png")

    # Improvement percentage chart
    improvement_labels = []
    improvement_vals = []
    for col, label, higher_is_better in summary_metrics:
        improvement_labels.append(label)
        improvement_vals.append(
            improvement_percent(ai_row[col], fixed_row[col], higher_is_better)
        )

    fig = plt.figure(figsize=(14, 7))
    x = range(len(improvement_labels))
    plt.bar(list(x), improvement_vals)
    plt.axhline(0, linewidth=1)
    plt.xticks(list(x), improvement_labels, rotation=35, ha="right")
    plt.ylabel("Improvement (%)")
    plt.title(f"AI Improvement vs Fixed - {profile}")
    save_plot(fig, f"summary_improvement_{safe_profile_name(profile)}.png")


# =========================
# STEP-BY-STEP GRAPHS
# =========================
required_step_cols = {
    "profile",
    "controller_mode",
    "sim_time",
    "arrived_step",
    "pending_to_insert",
    "total_queue",
    "total_wait",
}
missing_step_cols = required_step_cols - set(step_df.columns)

if missing_step_cols:
    print(f"Skipping some step plots because these columns are missing: {missing_step_cols}")
else:
    for profile in sorted(step_df["profile"].dropna().unique()):
        sub = step_df[step_df["profile"] == profile].copy()

        ai = sub[sub["controller_mode"].astype(str).str.lower() == "ai"].sort_values("sim_time").copy()
        fixed = sub[sub["controller_mode"].astype(str).str.lower() == "fixed"].sort_values("sim_time").copy()

        if ai.empty or fixed.empty:
            print(f"Skipping step plots for profile '{profile}' because AI or Fixed rows are missing.")
            continue

        # Total queue over time
        fig = plt.figure(figsize=(12, 6))
        plt.plot(fixed["sim_time"], fixed["total_queue"], label="Fixed")
        plt.plot(ai["sim_time"], ai["total_queue"], label="AI")
        plt.xlabel("Simulation time (s)")
        plt.ylabel("Total queue")
        plt.title(f"Total Queue Over Time - {profile}")
        plt.legend()
        save_plot(fig, f"queue_over_time_{safe_profile_name(profile)}.png")

        # Pending insert over time
        fig = plt.figure(figsize=(12, 6))
        plt.plot(fixed["sim_time"], fixed["pending_to_insert"], label="Fixed")
        plt.plot(ai["sim_time"], ai["pending_to_insert"], label="AI")
        plt.xlabel("Simulation time (s)")
        plt.ylabel("Pending insert")
        plt.title(f"Pending Insert Over Time - {profile}")
        plt.legend()
        save_plot(fig, f"pending_insert_over_time_{safe_profile_name(profile)}.png")

        # Total wait over time
        fig = plt.figure(figsize=(12, 6))
        plt.plot(fixed["sim_time"], fixed["total_wait"], label="Fixed")
        plt.plot(ai["sim_time"], ai["total_wait"], label="AI")
        plt.xlabel("Simulation time (s)")
        plt.ylabel("Total wait (s)")
        plt.title(f"Total Wait Over Time - {profile}")
        plt.legend()
        save_plot(fig, f"total_wait_over_time_{safe_profile_name(profile)}.png")

        # Cumulative arrivals
        fixed["cumulative_arrivals"] = fixed["arrived_step"].cumsum()
        ai["cumulative_arrivals"] = ai["arrived_step"].cumsum()

        fig = plt.figure(figsize=(12, 6))
        plt.plot(fixed["sim_time"], fixed["cumulative_arrivals"], label="Fixed")
        plt.plot(ai["sim_time"], ai["cumulative_arrivals"], label="AI")
        plt.xlabel("Simulation time (s)")
        plt.ylabel("Cumulative arrived vehicles")
        plt.title(f"Cumulative Arrivals Over Time - {profile}")
        plt.legend()
        save_plot(fig, f"cumulative_arrivals_{safe_profile_name(profile)}.png")

        # AI wait heatmap by direction using 5-minute bins
        wait_cols = ["wait_N", "wait_S", "wait_E", "wait_W"]
        if all(col in sub.columns for col in wait_cols):
            ai_heat = ai.copy()
            ai_heat["time_bin_min"] = (ai_heat["sim_time"] // 300).astype(int) * 5

            heat = ai_heat.groupby("time_bin_min")[wait_cols].mean().T

            fig = plt.figure(figsize=(12, 5))
            plt.imshow(heat, aspect="auto")
            plt.yticks(range(len(heat.index)), heat.index)
            plt.xticks(range(len(heat.columns)), [f"{int(c)}" for c in heat.columns])
            plt.xlabel("Time bin start (min)")
            plt.ylabel("Approach")
            plt.title(f"AI Average Wait by Direction - {profile}")
            plt.colorbar(label="Average wait (s)")
            save_plot(fig, f"wait_heatmap_ai_{safe_profile_name(profile)}.png")


# =========================
# DECISION / GREEN TIME GRAPHS
# =========================
required_decision_cols = {
    "profile",
    "controller_mode",
    "green_phase_name",
    "green_start_time",
    "base_green",
    "final_green",
}
missing_decision_cols = required_decision_cols - set(decision_df.columns)

if missing_decision_cols:
    print(f"Skipping decision plots because these columns are missing: {missing_decision_cols}")
else:
    for profile in sorted(decision_df["profile"].dropna().unique()):
        sub = decision_df[
            (decision_df["profile"] == profile) &
            (decision_df["controller_mode"].astype(str).str.lower() == "ai")
        ].copy().sort_values("green_start_time")

        if sub.empty:
            print(f"Skipping decision plots for profile '{profile}' because AI decision data is missing.")
            continue

        ew = sub[sub["green_phase_name"].astype(str).str.contains("EW", na=False)].copy()
        ns = sub[sub["green_phase_name"].astype(str).str.contains("NS", na=False)].copy()

        # Final green over time
        fig = plt.figure(figsize=(12, 6))
        if not ew.empty:
            plt.plot(ew["green_start_time"], ew["final_green"], marker="o", linestyle="-", label="EW final green")
        if not ns.empty:
            plt.plot(ns["green_start_time"], ns["final_green"], marker="o", linestyle="-", label="NS final green")
        plt.xlabel("Green start time (s)")
        plt.ylabel("Final green (s)")
        plt.title(f"AI Final Green Time Over Time - {profile}")
        plt.legend()
        save_plot(fig, f"final_green_over_time_{safe_profile_name(profile)}.png")

        # Base vs final green
        fig = plt.figure(figsize=(12, 6))
        plt.plot(sub["green_start_time"], sub["base_green"], marker="o", linestyle="-", label="Base green")
        plt.plot(sub["green_start_time"], sub["final_green"], marker="o", linestyle="-", label="Final green")
        plt.xlabel("Green start time (s)")
        plt.ylabel("Green duration (s)")
        plt.title(f"AI Base vs Final Green - {profile}")
        plt.legend()
        save_plot(fig, f"base_vs_final_green_{safe_profile_name(profile)}.png")

        # Adjustment amount over time
        if "total_inc" in sub.columns and "total_dec" in sub.columns:
            sub["net_adjustment"] = sub["final_green"] - sub["base_green"]

            fig = plt.figure(figsize=(12, 6))
            plt.plot(sub["green_start_time"], sub["net_adjustment"], marker="o", linestyle="-")
            plt.axhline(0, linewidth=1)
            plt.xlabel("Green start time (s)")
            plt.ylabel("Final - Base green (s)")
            plt.title(f"AI Green Adjustment Over Time - {profile}")
            save_plot(fig, f"green_adjustment_over_time_{safe_profile_name(profile)}.png")


print("\nDone. Graphs saved in:")
print(OUTPUT_DIR.resolve())