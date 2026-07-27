"""
Core Rendering Pipeline for Report Automator Pro
==================================================
Headless off-screen rendering engine with intelligent auto-camera
positioning, professional colormap styling, and high-resolution
export for commercial-grade CAE report generation.

Design principles:
- Headless: all rendering happens in memory via FBO (Frame Buffer Object);
  no GUI window is ever spawned.
- Deterministic: camera placement is computed from mesh geometry and
  field statistics — same input always produces the same image.
- Presentation-ready: white background, anti-aliased scalar bars,
  and 1080p+ output suitable for direct embedding into PPT slides.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import pyvista as pv

from .mock_data import MeshData


# ---------------------------------------------------------------------------
# Camera configuration
# ---------------------------------------------------------------------------

@dataclass
class CameraPreset:
    """Named camera orientation."""
    elevation: float
    azimuth: float
    roll: float = 0.0


# Industry-standard presets
CAMERA_PRESETS = {
    "isometric":       CameraPreset(elevation=30.0,  azimuth=45.0),
    "front":           CameraPreset(elevation=0.0,   azimuth=0.0),
    "top":             CameraPreset(elevation=90.0,  azimuth=0.0),
    "right":           CameraPreset(elevation=0.0,   azimuth=90.0),
    "trimetric":       CameraPreset(elevation=20.0,  azimuth=30.0),
    "presentation":    CameraPreset(elevation=25.0,  azimuth=60.0),
}


# ---------------------------------------------------------------------------
# Smart camera placement
# ---------------------------------------------------------------------------

def _find_critical_region(
    mesh: pv.UnstructuredGrid,
    field: np.ndarray,
    mode: str = "max",
) -> np.ndarray:
    """
    Locate the 3-D coordinate of the most critical node.

    Parameters
    ----------
    mesh : UnstructuredGrid
    field : (N_nodes,) array
        Scalar field to search (e.g. von Mises stress).
    mode : str
        "max" → highest-stress node (default for failure analysis).
        "min" → lowest-value node.
        "centroid" → geometric centroid of the mesh.

    Returns
    -------
    focal_point : (3,) ndarray
    """
    if mode == "centroid":
        return mesh.center

    idx = np.argmax(field) if mode == "max" else np.argmin(field)
    return mesh.points[idx].copy()


def _compute_camera_from_focal(
    focal_point: np.ndarray,
    mesh_bounds: np.ndarray,
    preset: CameraPreset,
    distance_factor: float = 2.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Derive camera position and up-vector from a focal point and preset.

    The camera distance is scaled to the mesh's bounding-box diagonal so
    the entire geometry is visible regardless of absolute model size.

    Parameters
    ----------
    focal_point : (3,) ndarray
    mesh_bounds : (6,) ndarray  [xmin, xmax, ymin, ymax, zmin, zmax]
    preset : CameraPreset
    distance_factor : float
        Multiplier on bounding-box diagonal for camera distance.

    Returns
    -------
    camera_position : (3,) ndarray
    up_vector : (3,) ndarray
    """
    diag = np.linalg.norm(
        np.array([
            mesh_bounds[1] - mesh_bounds[0],
            mesh_bounds[3] - mesh_bounds[2],
            mesh_bounds[5] - mesh_bounds[4],
        ])
    )
    distance = diag * distance_factor

    elev_rad = np.radians(preset.elevation)
    azim_rad = np.radians(preset.azimuth)

    # Spherical → Cartesian (Z-up convention for PyVista)
    x = distance * np.cos(elev_rad) * np.sin(azim_rad)
    y = distance * np.cos(elev_rad) * np.cos(azim_rad)
    z = distance * np.sin(elev_rad)

    camera_pos = focal_point + np.array([x, y, z])

    # Up vector: rotate world-up [0,0,1] by azimuth
    up = np.array([
        -np.sin(elev_rad) * np.sin(azim_rad),
        -np.sin(elev_rad) * np.cos(azim_rad),
         np.cos(elev_rad),
    ])

    return camera_pos, up


# ---------------------------------------------------------------------------
# Scalar bar styling
# ---------------------------------------------------------------------------

def _add_professional_scalar_bar(
    plotter: pv.Plotter,
    title: str,
    vertical: bool = False,
    **kwargs,
) -> None:
    """
    Add a report-quality colour bar with anti-aliased labels.

    Position defaults:
      - vertical=False  → horizontal bar below the model
      - vertical=True   → vertical bar on the right edge
    """
    defaults = dict(
        title=title,
        vertical=vertical,
        title_font_size=16,
        label_font_size=12,
        font_family="arial",
        color="k",
        bold=False,
        shadow=False,
        n_labels=7,
        fmt="%.2f",
        # Compact positioning
        position_x=0.15 if not vertical else 0.88,
        position_y=0.02 if not vertical else 0.15,
        width=0.70 if not vertical else 0.04,
        height=0.08 if not vertical else 0.60,
    )
    defaults.update(kwargs)
    plotter.add_scalar_bar(**defaults)


# ---------------------------------------------------------------------------
# Core render functions
# ---------------------------------------------------------------------------

def render_scalar_field(
    mesh_data: MeshData,
    output_path: str,
    *,
    field_name: str = "stress_von_mises",
    field_label: str = "von Mises Stress (MPa)",
    cmap: str = "jet",
    camera_preset: str = "isometric",
    focus_mode: str = "max",
    background_color: str = "white",
    resolution: Tuple[int, int] = (1920, 1080),
    show_edges: bool = True,
    edge_color: str = "#cccccc",
    edge_width: float = 0.3,
    add_bounding_box: bool = True,
    window_title: str = "Report Automator Pro",
) -> str:
    """
    Render a scalar field onto the mesh with intelligent camera placement.

    This is the primary entry point for generating high-resolution
    CAE report figures.

    Parameters
    ----------
    mesh_data : MeshData
        The mock dataset from mock_data.py.
    output_path : str
        Where to save the PNG. Directories are created if needed.
    field_name : str
        Attribute name on MeshData for the scalar field.
    field_label : str
        Display label for the colour bar.
    cmap : str
        Matplotlib/PyVista colormap name.
    camera_preset : str
        Key into CAMERA_PRESETS.
    focus_mode : str
        "max", "min", or "centroid" — where the camera looks.
    background_color : str
        CSS colour for the background.
    resolution : (int, int)
        Output image width × height.
    show_edges : bool
        Whether to draw mesh edges (wireframe overlay).
    edge_color : str
        Colour of mesh edges.
    edge_width : float
        Line width of mesh edges.
    add_bounding_box : bool
        Show a subtle wireframe bounding box.
    window_title : str
        Title rendered in the top-left corner.

    Returns
    -------
    output_path : str
        The same path, for chaining.
    """
    # ---- prepare ----------------------------------------------------------
    mesh = mesh_data.mesh.copy()
    field = getattr(mesh_data, field_name)

    # Attach scalar data to mesh for PyVista
    mesh.point_data[field_label] = field

    # ---- camera -----------------------------------------------------------
    focal_point = _find_critical_region(mesh, field, mode=focus_mode)
    preset = CAMERA_PRESETS.get(camera_preset, CAMERA_PRESETS["isometric"])
    cam_pos, cam_up = _compute_camera_from_focal(
        focal_point, mesh.bounds, preset
    )

    # ---- plotter ----------------------------------------------------------
    plotter = pv.Plotter(
        window_size=list(resolution),
        off_screen=True,
        notebook=False,
    )
    plotter.background_color = background_color

    # ---- mesh actor -------------------------------------------------------
    plotter.add_mesh(
        mesh,
        scalars=field_label,
        cmap=cmap,
        show_edges=show_edges,
        edge_color=edge_color,
        line_width=edge_width,
        lighting=True,
        specular=0.25,
        specular_power=30,
        smooth_shading=True,
        interpolate_before_map=True,
    )

    # ---- annotations ------------------------------------------------------
    if add_bounding_box:
        plotter.add_bounding_box(
            color="gray",
            line_width=1.0,
            opacity=0.5,
            corner_factor=0.0,
        )

    plotter.add_text(
        window_title,
        position="upper_left",
        font_size=14,
        color="gray",
        font="arial",
    )

    _add_professional_scalar_bar(plotter, title=field_label, vertical=False)

    # ---- apply camera -----------------------------------------------------
    plotter.camera.position = cam_pos
    plotter.camera.focal_point = focal_point
    plotter.camera.up = cam_up
    plotter.camera.roll = preset.roll

    # ---- render -----------------------------------------------------------
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    plotter.show(auto_close=False, interactive=False)
    plotter.screenshot(output_path, return_img=False)
    plotter.close()

    return output_path


def render_stress(
    mesh_data: MeshData,
    output_dir: str,
    zoom_to_critical: bool = True,
) -> str:
    """
    Convenience: render von Mises stress at 1080p with optimal settings.
    """
    out = os.path.join(output_dir, "high_res_stress.png")
    return render_scalar_field(
        mesh_data,
        out,
        field_name="stress_von_mises",
        field_label="von Mises Stress (MPa)",
        cmap="jet",
        camera_preset="isometric",
        focus_mode="max" if zoom_to_critical else "centroid",
        show_edges=False,
        add_bounding_box=True,
        window_title="Report Automator Pro  |  von Mises Stress",
    )


def render_displacement(
    mesh_data: MeshData,
    output_dir: str,
    zoom_to_critical: bool = True,
) -> str:
    """
    Convenience: render displacement magnitude at 1080p.
    """
    out = os.path.join(output_dir, "high_res_displacement.png")
    return render_scalar_field(
        mesh_data,
        out,
        field_name="displacement_magnitude",
        field_label="Displacement Magnitude (mm)",
        cmap="viridis",
        camera_preset="isometric",
        focus_mode="max" if zoom_to_critical else "centroid",
        show_edges=False,
        add_bounding_box=True,
        window_title="Report Automator Pro  |  Displacement",
    )


def render_report_suite(
    mesh_data: MeshData,
    output_dir: str,
) -> dict:
    """
    Full report rendering suite — exports multiple pre-composed views
    for direct insertion into a PPT report deck.

    Returns a dict mapping view name → file path.
    """
    os.makedirs(output_dir, exist_ok=True)
    results = {}

    # ---- View A: von Mises isometric (main hero shot) ---------------------
    results["stress_iso"] = render_stress(mesh_data, output_dir)

    # ---- View B: von Mises front view ------------------------------------
    out = os.path.join(output_dir, "stress_front.png")
    results["stress_front"] = render_scalar_field(
        mesh_data, out,
        field_name="stress_von_mises",
        field_label="von Mises Stress (MPa)",
        cmap="jet",
        camera_preset="front",
        focus_mode="centroid",
        show_edges=False,
        add_bounding_box=True,
        window_title="Report Automator Pro  |  Stress — Front View",
    )

    # ---- View C: von Mises top view --------------------------------------
    out = os.path.join(output_dir, "stress_top.png")
    results["stress_top"] = render_scalar_field(
        mesh_data, out,
        field_name="stress_von_mises",
        field_label="von Mises Stress (MPa)",
        cmap="jet",
        camera_preset="top",
        focus_mode="centroid",
        show_edges=False,
        add_bounding_box=True,
        window_title="Report Automator Pro  |  Stress — Top View",
    )

    # ---- View D: displacement (default) ----------------------------------
    results["displacement"] = render_displacement(mesh_data, output_dir)

    # ---- View E: white mesh wireframe (geometry check) -------------------
    out = os.path.join(output_dir, "mesh_wireframe.png")
    results["mesh_wf"] = render_scalar_field(
        mesh_data, out,
        field_name="stress_von_mises",
        field_label="von Mises Stress (MPa)",
        cmap="gray",
        camera_preset="isometric",
        focus_mode="centroid",
        background_color="white",
        show_edges=True,
        edge_color="#333333",
        edge_width=1.0,
        add_bounding_box=True,
        window_title="Report Automator Pro  |  Mesh Topology",
    )

    return results


# ---------------------------------------------------------------------------
# Self-test entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import time
    from .mock_data import generate_mock_dataset

    print("=" * 60)
    print("  Renderer Pipeline — Self-Test")
    print("=" * 60)

    # ---- generate data ----------------------------------------------------
    print("\n[1/3] Generating mock dataset ...")
    data = generate_mock_dataset(seed=42)

    # ---- identify critical node -------------------------------------------
    idx_max = np.argmax(data.stress_von_mises)
    pt_max = data.mesh.points[idx_max]
    print(f"      Max stress node #{idx_max} at "
          f"({pt_max[0]:.2f}, {pt_max[1]:.2f}, {pt_max[2]:.2f}) "
          f"= {data.stress_von_mises[idx_max]:.2f} MPa")

    # ---- render hero shot -------------------------------------------------
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output"
    )
    print(f"\n[2/3] Rendering hero shot to {output_dir} ...")
    t0 = time.perf_counter()
    path = render_stress(data, output_dir)
    elapsed = time.perf_counter() - t0
    print(f"      Done in {elapsed:.2f}s → {path}")

    # ---- render full suite ------------------------------------------------
    print(f"\n[3/3] Rendering full report suite ...")
    results = render_report_suite(data, output_dir)
    for name, path in results.items():
        size_kb = os.path.getsize(path) / 1024
        print(f"      [{name:16s}] {size_kb:6.1f} KB  {path}")

    print("\n" + "=" * 60)
    print("  All renders complete.")
    print("=" * 60)
