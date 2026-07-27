"""
PPT Report Runner
=================
Generates mock data, renders all images, and assembles the final PPTX.
"""

import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from src.mock_data import generate_mock_dataset
from src.renderer import render_report_suite
from src.ppt_generator import generate_pptx


def main():
    output_dir = os.path.join(PROJECT_ROOT, "output")
    os.makedirs(output_dir, exist_ok=True)

    # ---- Step 1: Data -----------------------------------------------------
    print("=" * 60)
    print("  Step 1/3: Generating mock dataset ...")
    print("=" * 60)
    data = generate_mock_dataset(seed=42)
    svm = data.stress_von_mises
    idx_peak = int(svm.argmax())
    peak_xyz = data.mesh.points[idx_peak]
    print(f"  Nodes: {data.n_nodes:,}  |  Cells: {data.n_cells:,}")
    print(f"  Peak stress: {svm[idx_peak]:.2f} MPa "
          f"@ node #{idx_peak} ({peak_xyz[0]:.1f}, {peak_xyz[1]:.1f}, {peak_xyz[2]:.1f})")

    # ---- Step 2: Render ---------------------------------------------------
    print("\n" + "=" * 60)
    print("  Step 2/3: Rendering all images ...")
    print("=" * 60)
    t0 = time.perf_counter()
    results = render_report_suite(data, output_dir)
    t1 = time.perf_counter()
    for name, path in results.items():
        print(f"  [{name:16s}]  {os.path.getsize(path)/1024:6.1f} KB")
    print(f"  Total render time: {t1 - t0:.1f}s")

    # ---- Step 3: PPTX -----------------------------------------------------
    print("\n" + "=" * 60)
    print("  Step 3/3: Assembling PowerPoint report ...")
    print("=" * 60)
    pptx_path = generate_pptx(data, output_dir)
    file_size_kb = os.path.getsize(pptx_path) / 1024
    num_slides = None
    try:
        from pptx import Presentation
        prs = Presentation(pptx_path)
        num_slides = len(prs.slides)
    except Exception:
        pass

    print(f"  Slides: {num_slides}  |  Size: {file_size_kb:.0f} KB")
    print(f"  Saved: {pptx_path}")

    print("\n" + "=" * 60)
    print("  Full report pipeline complete. Ready for review!")
    print("=" * 60)


if __name__ == "__main__":
    main()
