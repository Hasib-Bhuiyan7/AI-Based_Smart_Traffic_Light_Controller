import pandas as pd
import matplotlib.pyplot as plt
import textwrap
import numpy as np
import os

# -------------------- Step 1: Setup Folders and Load Data --------------------
csv_file = "tmc_summary_data.csv"
folder_name = "CITY Data 2024-2026"

if not os.path.exists(folder_name):
    os.makedirs(folder_name)

txt_output = os.path.join(folder_name, "intersection_names.txt")

if not os.path.exists(csv_file):
    print(f"Error: {csv_file} not found.")
else:
    df = pd.read_csv(csv_file)
    df['count_date'] = pd.to_datetime(df['count_date'])
    df['year'] = df['count_date'].dt.year

    with open(txt_output, "w") as f:
        f.write("TMC SUMMARY INTERSECTION LIST (2024-2026)\n")
        f.write("=" * 40 + "\n\n")


    def format_label(name, width=12):
        replacements = {
            "Avenue": "Ave", "Road": "Rd", "Street": "St", "Boulevard": "Blvd",
            "Drive": "Dr", "Crescent": "Cres", "Parkway": "Pkwy", "Terrace": "Terr",
            "Square": "Sq", "Highway": "Hwy", "Expressway": "Expy", "North": "N",
            "South": "S", "East": "E", "West": "W", "Collectors": "Coll",
            "Ramp": "Rp", "Park": "Pk", "Trail": "Trl", "Heights": "Hts",
            "Valley": "Vly", "Centre": "Ctr", "Station": "Stn", "Gardiner": "Gdnr"
        }
        name = str(name).title().strip()
        for word, abbrev in replacements.items():
            name = name.replace(f" {word}", f" {abbrev}").replace(f"{word} ", f"{abbrev} ")
        return '\n'.join(textwrap.wrap(name, width=width))


    # -------------------- Step 3: Targeted Loop (2024-2026) --------------------
    years = [2024, 2025, 2026]
    top_n = 25
    label_font = 5
    label_rotation = 45
    fig_size = (14, 7)

    for year in years:
        year_df = df[df['year'] == year].copy()
        if year_df.empty:
            continue

        # Data Slicing
        top_25 = year_df.sort_values(by="total_vehicle", ascending=False).head(top_n).copy()
        bottom_25 = year_df.sort_values(by="total_vehicle", ascending=True).head(top_n).copy()

        # Save to TXT
        with open(txt_output, "a") as f:
            f.write(f"--- YEAR: {year} ---\nTOP {top_n} BUSIEST:\n")
            for i, loc in enumerate(top_25['location_name'], 1):
                f.write(f"  {i}. {loc}\n")
            f.write(f"\n{top_n} LEAST BUSY:\n")
            for i, loc in enumerate(bottom_25['location_name'], 1):
                f.write(f"  {i}. {loc}\n")
            f.write("\n" + "-" * 40 + "\n\n")


        # Define a helper function to avoid repeating the dual-axis logic
        def plot_dual_axis(data, title, filename):
            data = data.copy()
            data["ratio"] = data["total_pedestrian"] / data["total_vehicle"]
            avg_r = data["ratio"].mean()

            fig, ax1 = plt.subplots(figsize=fig_size)
            indices = np.arange(len(data))
            labs = [format_label(n) for n in data['location_name']]

            # Left Axis
            ax1.bar(indices - 0.175, data['total_vehicle'], width=0.35, color='#1f77b4', label='Total Vehicles')
            ax1.bar(indices + 0.175, data['total_pedestrian'], width=0.35, color='#ff7f0e', label='Total Pedestrians')
            ax1.set_ylabel("Traffic Volume (14 Hr Count)", fontsize=10, fontweight='bold')
            ax1.set_xticks(indices)
            ax1.set_xticklabels(labs, rotation=label_rotation, ha='right', fontsize=label_font, rotation_mode='anchor')

            # Right Axis
            ax2 = ax1.twinx()
            ax2.plot(indices, data['ratio'], color='green', marker='o', markersize=4, linestyle='--',
                     label='Ped-to-Veh Ratio')
            ax2.axhline(y=avg_r, color='red', linestyle=':', label=f'Avg Ratio: {avg_r:.4f}')
            ax2.set_ylabel("Ratio Scale", color='green', fontsize=10, fontweight='bold')
            ax2.tick_params(axis='y', labelcolor='green')

            plt.title(title, fontsize=16, fontweight='bold')

            # Annotation for study period
            ax1.text(0.02, 0.95, "Data: 14-Hour Study (06:00 AM-8:00 PM)", transform=ax1.transAxes,
                     fontsize=9, verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.5))

            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2, prop={'size': 8}, loc='upper right')

            plt.tight_layout()
            plt.savefig(os.path.join(folder_name, filename), dpi=300)
            plt.show()


        # --- Generate Plot 1: Busiest Ratios ---
        plot_dual_axis(top_25, f"Top {top_n} Busiest Intersections ({year})", f"busiest_ratios_{year}.png")

        # --- Generate Plot 2: Least Busy Ratios ---
        plot_dual_axis(bottom_25, f"{top_n} Least Busy Intersections ({year})", f"least_busy_ratios_{year}.png")

        # --- Generate Plot 3: Approach Counts ---
        plt.figure(figsize=fig_size)
        appr_w = 0.18
        x_appr = np.arange(len(top_25))
        plt.bar(x_appr - 1.5 * appr_w, top_25['n_appr_vehicle'], width=appr_w, color='#1f77b4', label='North')
        plt.bar(x_appr - 0.5 * appr_w, top_25['e_appr_vehicle'], width=appr_w, color='#ff7f0e', label='East')
        plt.bar(x_appr + 0.5 * appr_w, top_25['s_appr_vehicle'], width=appr_w, color='#2ca02c', label='South')
        plt.bar(x_appr + 1.5 * appr_w, top_25['w_appr_vehicle'], width=appr_w, color='#d62728', label='West')

        plt.xticks(x_appr, [format_label(n) for n in top_25['location_name']], rotation=label_rotation, ha='right',
                   fontsize=label_font, rotation_mode='anchor')
        plt.ylabel("Vehicle Count")
        plt.title(f"Top {top_n} Busiest Intersections ({year}) - By Approach", fontsize=16, fontweight='bold')
        plt.legend(prop={'size': 8})
        plt.tight_layout()
        plt.savefig(os.path.join(folder_name, f"busiest_approach_{year}.png"), dpi=300)
        plt.show()

    print(f"\nSuccess! All charts (Busiest, Least Busy, and Approach) saved in: '{folder_name}'")