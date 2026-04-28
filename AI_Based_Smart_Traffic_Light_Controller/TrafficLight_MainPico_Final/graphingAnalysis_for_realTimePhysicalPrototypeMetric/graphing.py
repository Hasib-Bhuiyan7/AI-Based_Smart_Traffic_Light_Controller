import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# -------------------- LOAD DATA --------------------
modern_path = "MODERN_cycle_log.csv"
traditional_path = "TRADITIONAL_cycle_log.csv"

modern = pd.read_csv(modern_path)
traditional = pd.read_csv(traditional_path)

# -------------------- CLEAN / ALIGN --------------------
min_len = min(len(modern), len(traditional))
modern = modern.iloc[:min_len]
traditional = traditional.iloc[:min_len]

cycles = np.arange(min_len)

# -------------------- HELPER: SMOOTHING --------------------
def smooth(data, window=5):
    return pd.Series(data).rolling(window=window, min_periods=1).mean()

# -------------------- 1. AVERAGE TOTAL SYSTEM WAIT TIME --------------------
plt.figure()
plt.plot(cycles, smooth(modern["avg_wait"]), label="AI Traffic Light")
plt.plot(cycles, smooth(traditional["avg_wait"]), label="Fixed-Time Traffic Light")
plt.title("Average Total System Waiting Time Comparison")
plt.xlabel("Cycle")
plt.ylabel("Average Wait Time (seconds)")
plt.legend()
plt.grid()
plt.tight_layout()
plt.savefig("graph_avg_wait.png")

# -------------------- 2. VEHICLES PASSED/THROUGHPUT PER CYCLE --------------------
modern_throughput = modern["vehicles_passed"]
traditional_throughput = traditional["vehicles_passed"]
plt.figure()
plt.plot(cycles, smooth(modern_throughput), label="AI Traffic Light")
plt.plot(cycles, smooth(traditional_throughput), label="Fixed-Time Traffic Light")
plt.title("Vehicles Passed(Throughput) per Cycle")
plt.xlabel("Cycle")
plt.ylabel("Vehicles Passed(Throughput)")
plt.legend()
plt.grid()
plt.tight_layout()
plt.savefig("graph_throughput.png")

# -------------------- 3. CUMULATIVE VEHICLES --------------------
plt.figure()
plt.plot(cycles, modern["vehicles_passed"].cumsum(), label="AI Traffic Light")
plt.plot(cycles, traditional["vehicles_passed"].cumsum(), label="Fixed-Time Traffic Light")
plt.title("Cumulative Vehicles Passed Over Time")
plt.xlabel("Cycle")
plt.ylabel("Total Vehicles Passed")
plt.legend()
plt.grid()
plt.tight_layout()
plt.savefig("graph_cumulative.png")

# -------------------- 4. TOTAL WAIT TIME --------------------
modern_total_wait = modern["wait_W"] + modern["wait_E"] + modern["wait_N"] + modern["wait_S"]
traditional_total_wait = traditional["wait_W"] + traditional["wait_E"] + traditional["wait_N"] + traditional["wait_S"]

plt.figure()
plt.plot(cycles, smooth(modern_total_wait), label="AI Traffic Light")
plt.plot(cycles, smooth(traditional_total_wait), label="Fixed-Time Traffic Light")
plt.title("Total System Wait Time")
plt.xlabel("Cycle")
plt.ylabel("Total Wait Time (seconds)")
plt.legend()
plt.grid()
plt.tight_layout()
plt.savefig("graph_total_wait.png")

# Create matrix: rows=time, cols=direction
modern_heat = np.vstack([
    modern["wait_N"],
    modern["wait_S"],
    modern["wait_E"],
    modern["wait_W"]
]).T

traditional_heat = np.vstack([
    traditional["wait_N"],
    traditional["wait_S"],
    traditional["wait_E"],
    traditional["wait_W"]
]).T

# ----- AI HEATMAP -----
plt.figure()
plt.imshow(modern_heat, aspect='auto')
plt.colorbar(label="Wait Time")
plt.title("AI Traffic Light - Wait Time Heatmap")
plt.xlabel("Direction (N, S, E, W)")
plt.ylabel("Time Step")
plt.xticks([0,1,2,3], ["N","S","E","W"])

plt.tight_layout()
plt.savefig("heatmap_ai.png")

# ----- TRADITIONAL HEATMAP -----
plt.figure()
plt.imshow(traditional_heat, aspect='auto')
plt.colorbar(label="Wait Time")
plt.title("Fixed-Time Traffic Light - Wait Time Heatmap")
plt.xlabel("Direction (N, S, E, W)")
plt.ylabel("Time Step")
plt.xticks([0,1,2,3], ["N","S","E","W"])

plt.tight_layout()
plt.savefig("heatmap_traditional.png")

# -------------------- 5. GREEN TIME BEHAVIOR --------------------
plt.figure()
plt.plot(cycles, modern["green_duration"], label="AI Adaptive Green Time")
plt.plot(cycles, traditional["green_duration"], label="Fixed Green Time")
plt.title("Green Light Duration Comparison")
plt.xlabel("Cycle")
plt.ylabel("Green Time (seconds)")
plt.legend()
plt.grid()
plt.tight_layout()
plt.savefig("graph_green_time.png")

# -------------------- 6. EFFICIENCY METRIC --------------------
# Efficiency = vehicles passed / total wait
modern_eff = modern_throughput / (modern_total_wait + 1e-5)
traditional_eff = traditional_throughput / (traditional_total_wait + 1e-5)

plt.figure()
plt.plot(cycles, smooth(modern_eff), label="AI Traffic Light")
plt.plot(cycles, smooth(traditional_eff), label="Fixed-Time Traffic Light")
plt.title("System Efficiency (Vehicles / Wait Time)")
plt.xlabel("Cycle")
plt.ylabel("Efficiency Ratio")
plt.legend()
plt.grid()
plt.tight_layout()
plt.savefig("graph_efficiency.png")

# -------------------- 7. AVG WAIT TIME PER VEHICLE --------------------
modern_total_cars = modern["WEST"] + modern["EAST"] + modern["NORTH"] + modern["SOUTH"]
traditional_total_cars = traditional["WEST"] + traditional["EAST"] + traditional["NORTH"] + traditional["SOUTH"]
modern_avg_wait_perVehicle = modern_total_wait / modern_total_cars.clip(lower=1)
traditional_avg_wait_perVehicle = traditional_total_wait / traditional_total_cars.clip(lower=1)

# ----- BOX PLOT -----
plt.figure()
plt.boxplot(
    [modern_avg_wait_perVehicle, traditional_avg_wait_perVehicle],
    tick_labels=["AI Traffic Light", "Fixed-Time Traffic"],
    showmeans=True
)

plt.title("Distribution of Average Wait Time per Vehicle")
plt.ylabel("Wait Time (seconds)")
plt.grid(True)

plt.tight_layout()
plt.savefig("boxplot_wait_time.png")


# -------------------- 8. WAIT PER SERVED VEHICLE --------------------
modern_wait_per_served = modern_total_wait / modern_throughput.clip(lower=1)
traditional_wait_per_served = traditional_total_wait / traditional_throughput.clip(lower=1)

plt.figure()
plt.plot(cycles, smooth(modern_wait_per_served), label="AI Traffic Light")
plt.plot(cycles, smooth(traditional_wait_per_served), label="Fixed-Time Traffic Light")
plt.title("Wait time per each vehicle served: RATIO comparison between wait time vs vehicle served")
plt.xlabel("Cycle")
plt.ylabel("Wait Time/Vehicles Served")
plt.legend()
plt.grid()
plt.tight_layout()
plt.savefig("graph_Wait_Per_Served_Vehicle.png")

# -------------------- 9. BAR CHART TO REPRESENT THROUGHPUT, AVG WAIT AND EFFICIENCY --------------------
import numpy as np
import matplotlib.pyplot as plt

labels = ["Throughput", "Avg Wait per Vehicle", "Efficiency"]

modern_values = [
    modern_throughput.mean(),
    modern_avg_wait_perVehicle.mean(),
    modern_eff.mean()
]

traditional_values = [
    traditional_throughput.mean(),
    traditional_avg_wait_perVehicle.mean(),
    traditional_eff.mean()
]

x = np.arange(len(labels))
width = 0.35

plt.figure()
plt.bar(x - width/2, modern_values, width, label="AI Traffic Light")
plt.bar(x + width/2, traditional_values, width, label="Fixed-Time Traffic Light")

plt.xticks(x, labels)
plt.title("Traffic System Performance Comparison")
plt.ylabel("Metric Value")
plt.legend()
plt.grid(axis='y')

plt.tight_layout()
plt.savefig("graph_comparison_bar.png")
# -------------------- SHOW ALL --------------------
plt.show()