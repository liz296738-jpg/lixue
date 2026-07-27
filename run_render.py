"""
Render Pipeline Runner
======================
Generates mock data and runs the full report rendering suite.
"""

import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from src.mock_data import generate_mock_dataset
from src.renderer import render_stress, render_displacement, render_report_suite


def main():
    output_dir = os.path.join(PROJECT_ROOT, "output")
    os.makedirs(output_dir, exist_ok=True)

    # ---- Step 1: Generate mock data ---------------------------------------
    print("=" * 60)
    print("  Step 1/3: Generating mock dataset ...")
    print("=" * 60)
    data = generate_mock_dataset(seed=42)
    print(f"  Nodes: {data.n_nodes:,}  |  Cells: {data.n_cells:,}")
    idx_max = data.stress_von_mises.argmax()
    pt = data.mesh.points[idx_max]
    print(f"  Peak stress: {data.stress_von_mises[idx_max]:.2f} MPa "
          f"@ node #{idx_max} ({pt[0]:.1f}, {pt[1]:.1f}, {pt[2]:.1f})")

    # ---- Step 2: Render hero shots ----------------------------------------
    print("\n" + "=" * 60)
    print("  Step 2/3: Rendering hero shots (1080p) ...")
    print("=" * 60)

    t0 = time.perf_counter()
    stress_path = render_stress(data, output_dir, zoom_to_critical=True)
    t1 = time.perf_counter()
    print(f"  [OK] Stress render: {t1 - t0:.2f}s -> {stress_path}")

    disp_path = render_displacement(data, output_dir, zoom_to_critical=True)
    t2 = time.perf_counter()
    print(f"  [OK] Displacement render: {t2 - t1:.2f}s -> {disp_path}")

    # ---- Step 3: Render full report suite ---------------------------------
    print("\n" + "=" * 60)
    print("  Step 3/3: Rendering full report suite ...")
    print("=" * 60)

    results = render_report_suite(data, output_dir)
    for name, path in results.items():
        size_kb = os.path.getsize(path) / 1024
        print(f"  [{name:16s}]  {size_kb:6.1f} KB  {path}")

    total = sum(os.path.getsize(p) for p in results.values()) / 1024
    print(f"\n  Total output: {total:.0f} KB across {len(results)} files")

    print("\n" + "=" * 60)
    print("  All rendering complete. Ready for PPT assembly.")
    print("=" * 60)


if __name__ == "__main__":
    main()
