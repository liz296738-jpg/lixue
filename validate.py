"""
Validation Script — Render Mock Mesh to Offscreen PNG
======================================================
Generates the cantilever-beam mock dataset and exports a
multi-view offscreen render to output/test_mesh.png.
"""

import os
import sys

# Ensure the project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pyvista as pv

from src.mock_data import generate_mock_dataset

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def render_to_png(data, filepath: str) -> None:
    """
    Render 4 views of the mesh (stress + displacement) into a single
    composite PNG using PyVista off-screen plotting.
    """
    mesh = data.mesh
    mesh.point_data["von Mises (MPa)"] = data.stress_von_mises
    mesh.point_data["Displacement Mag (mm)"] = data.displacement_magnitude
    mesh.point_data["Displacement"] = data.displacement

    plotter = pv.Plotter(
        shape=(2, 2),
        window_size=[1600, 800],
        off_screen=True,
        notebook=False,
    )
    plotter.background_color = "#1a1a2e"

    # ----- view 1: von Mises stress, isometric ----------------------------
    plotter.subplot(0, 0)
    plotter.add_mesh(
        mesh,
        scalars="von Mises (MPa)",
        cmap="jet",
        show_edges=True,
        edge_color="#444444",
        line_width=0.5,
        lighting=True,
        specular=0.3,
        smooth_shading=True,
    )
    plotter.add_text(
        "von Mises Stress (MPa)",
        position="upper_edge",
        font_size=11,
        color="white",
    )
    plotter.view_isometric()

    # ----- view 2: displacement magnitude, front --------------------------
    plotter.subplot(0, 1)
    plotter.add_mesh(
        mesh,
        scalars="Displacement Mag (mm)",
        cmap="viridis",
        show_edges=True,
        edge_color="#444444",
        line_width=0.5,
        lighting=True,
        specular=0.3,
        smooth_shading=True,
    )
    plotter.add_text(
        "Displacement Magnitude (mm)",
        position="upper_edge",
        font_size=11,
        color="white",
    )
    plotter.view_xy()

    # ----- view 3: warped by displacement (exaggerated) -------------------
    plotter.subplot(1, 0)
    warped = mesh.warp_by_vector("Displacement", factor=50.0)
    warped.point_data["von Mises (MPa)"] = data.stress_von_mises
    plotter.add_mesh(
        warped,
        scalars="von Mises (MPa)",
        cmap="jet",
        show_edges=False,
        lighting=True,
        specular=0.4,
        smooth_shading=True,
    )
    plotter.add_text(
        "Deformed Shape (×50 exaggeration)",
        position="upper_edge",
        font_size=11,
        color="white",
    )
    plotter.view_isometric()

    # ----- view 4: Y-normal clip to reveal interior stress ----------------
    plotter.subplot(1, 1)
    # Clip above the hole centre to show the stress-concentration region
    clipped = mesh.clip(normal='y', origin=(0, 1.0, 0.0), invert=False)
    if clipped.n_points > 0:
        plotter.add_mesh(
            clipped,
            scalars="von Mises (MPa)",
            cmap="plasma",
            show_edges=True,
            edge_color="#444444",
            line_width=0.5,
            lighting=True,
            specular=0.3,
            smooth_shading=True,
        )
    else:
        plotter.add_mesh(
            mesh,
            scalars="von Mises (MPa)",
            cmap="plasma",
            show_edges=True,
            edge_color="#444444",
            line_width=0.5,
            lighting=True,
            specular=0.3,
            smooth_shading=True,
        )
    plotter.add_text(
        "Y-Clip @ Hole — von Mises (MPa)",
        position="upper_edge",
        font_size=11,
        color="white",
    )
    plotter.view_isometric()

    # ---- save ------------------------------------------------------------
    plotter.show(auto_close=False, interactive=False)
    plotter.screenshot(filepath, return_img=False)
    plotter.close()
    print(f"  [OK] Render saved -> {filepath}")


def print_summary(data) -> None:
    """Pretty-print key dataset statistics."""
    svm = data.stress_von_mises
    disp = data.displacement_magnitude
    print("=" * 60)
    print("  Report Automator Pro — Mock Dataset Summary")
    print("=" * 60)
    print(f"  Mesh type      : {type(data.mesh).__name__}")
    print(f"  Nodes          : {data.n_nodes:,}")
    print(f"  Cells          : {data.n_cells:,}")
    print(f"  Cell types     : {np.unique(data.mesh.celltypes)}")
    print(f"  Bounds X       : [{data.mesh.bounds[0]:.2f}, {data.mesh.bounds[1]:.2f}]")
    print(f"  Bounds Y       : [{data.mesh.bounds[2]:.2f}, {data.mesh.bounds[3]:.2f}]")
    print(f"  Bounds Z       : [{data.mesh.bounds[4]:.2f}, {data.mesh.bounds[5]:.2f}]")
    print("-" * 60)
    print(f"  von Mises      : {svm.min():.2f} – {svm.max():.2f} MPa  (mean: {svm.mean():.2f})")
    print(f"  Disp magnitude : {disp.min():.4f} – {disp.max():.4f} mm  (mean: {disp.mean():.4f})")
    print(f"  Principal max  : {data.principal_stress_max.min():.2f} – {data.principal_stress_max.max():.2f} MPa")
    print(f"  Principal min  : {data.principal_stress_min.min():.2f} – {data.principal_stress_min.max():.2f} MPa")
    print(f"  Field arrays   : {data.stress_tensor.shape} (stress tensor)")
    print(f"                   {data.displacement.shape} (displacement)")
    print("=" * 60)


def main():
    print("\n" + "=" * 60)
    print("  Step 1: Generating mock dataset ...")
    print("=" * 60 + "\n")

    data = generate_mock_dataset(seed=42)

    print_summary(data)

    print("\n" + "=" * 60)
    print("  Step 2: Rendering off-screen PNG ...")
    print("=" * 60 + "\n")

    output_path = os.path.join(OUTPUT_DIR, "test_mesh.png")
    render_to_png(data, output_path)

    print("\n" + "=" * 60)
    print("  Validation complete!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
