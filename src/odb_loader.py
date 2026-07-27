"""
ODB Data Loader — Convert extracted .npz to MeshData
======================================================
Runs in standard Python (NOT Abaqus Python).
Loads the .npz produced by odb_bridge.py and converts it
into our project's MeshData format, which feeds directly
into the renderer and PPT generator.
"""

from __future__ import annotations

import os
import subprocess
import sys
import numpy as np
import pyvista as pv

from .mock_data import MeshData


# Path to the Abaqus Commands directory
_ABAQUS_BAT = r"D:\ABAQUS\2025\Commands\abaqus.bat"


def run_odb_extraction(odb_path: str, output_npz: str | None = None) -> str:
    """
    Call Abaqus Python to extract data from an .odb file.

    Parameters
    ----------
    odb_path : str
        Path to the .odb file.
    output_npz : str or None
        Where to save the .npz.  Default: <odb_path>_extracted.npz

    Returns
    -------
    output_npz : str
        Path to the generated .npz file.

    Raises
    ------
    subprocess.CalledProcessError
        If Abaqus extraction fails.
    """
    if output_npz is None:
        output_npz = odb_path.replace(".odb", "_extracted.npz")

    bridge_script = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "odb_bridge.py",
    )

    cmd = [
        _ABAQUS_BAT, "python",
        bridge_script,
        odb_path,
        output_npz,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    # Always print stdout for debugging
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        err_msg = result.stderr.strip() if result.stderr else f"exit code {result.returncode}"
        print(f"[ABAQUS ERROR] {err_msg}")
        raise RuntimeError(f"Abaqus extraction failed:\n{err_msg}")

    if not os.path.exists(output_npz):
        raise FileNotFoundError(f"Extraction did not produce {output_npz}")

    return output_npz


def load_npz_to_mesh(npz_path: str) -> MeshData:
    """
    Load a .npz (produced by odb_bridge.py) into a MeshData object.

    The .npz must contain at minimum:
        points   : (N, 3)  float32
        cells    : (M, K)  int32
        cell_types: (M,)   int32
    Optional scalar fields:
        stress_vm, stress_tensor, displacement, disp_mag
    """
    archive = np.load(npz_path)

    points = archive["points"]
    cells_flat = archive["cells"]
    cell_types = archive["cell_types"]

    # -- Build PyVista UnstructuredGrid ------------------------------------
    n_cells = len(cell_types)
    # PyVista needs: [n1, id0,id1,..., n2, id0,id1,...]
    npe = cells_flat.shape[1] if cells_flat.ndim == 2 else 4
    cell_array = np.zeros((n_cells, npe + 1), dtype=np.int64)
    cell_array[:, 0] = npe
    cell_array[:, 1:] = cells_flat

    ugrid = pv.UnstructuredGrid(cell_array.ravel(), cell_types, points)
    n_nodes = ugrid.n_points

    # -- Stress ------------------------------------------------------------
    svm = archive.get("stress_vm", np.zeros(n_nodes, dtype=np.float32))
    stensor_raw = archive.get(
        "stress_tensor",
        np.zeros((n_nodes, 6), dtype=np.float32),
    )
    # Pad stress tensor to 6 columns if 2D (4 columns: S11,S22,S33,S12)
    n_stress_cols = stensor_raw.shape[1]
    if n_stress_cols < 6:
        stensor = np.zeros((n_nodes, 6), dtype=np.float64)
        stensor[:, :n_stress_cols] = stensor_raw
    else:
        stensor = stensor_raw.astype(np.float64)

    # -- Displacement ------------------------------------------------------
    disp_raw = archive.get("displacement", np.zeros((n_nodes, 3), dtype=np.float32))
    n_disp_cols = disp_raw.shape[1]
    if n_disp_cols < 3:
        disp = np.zeros((n_nodes, 3), dtype=np.float64)
        disp[:, :n_disp_cols] = disp_raw
    else:
        disp = disp_raw.astype(np.float64)
    disp_mag = archive.get("disp_mag", np.linalg.norm(disp, axis=1))

    # -- Principal stresses ------------------------------------------------
    sxx, syy, sxy = stensor[:, 0], stensor[:, 1], stensor[:, 3]
    s_avg = (sxx + syy) / 2.0
    s_diff = (sxx - syy) / 2.0
    R = np.sqrt(s_diff ** 2 + sxy ** 2)
    prin_max = s_avg + R
    prin_min = s_avg - R

    return MeshData(
        mesh=ugrid,
        node_ids=np.arange(n_nodes),
        stress_von_mises=svm.astype(np.float64),
        stress_tensor=stensor.astype(np.float64),
        displacement=disp.astype(np.float64),
        principal_stress_max=prin_max.astype(np.float64),
        principal_stress_min=prin_min.astype(np.float64),
        displacement_magnitude=disp_mag.astype(np.float64),
    )


# =========================================================================
# Self-test
# =========================================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/odb_loader.py <file.npz>")
        print("  Loads a .npz (from odb_bridge) and prints a data summary.")
        sys.exit(1)

    data = load_npz_to_mesh(sys.argv[1])
    svm = data.stress_von_mises
    print(f"Nodes: {data.n_nodes:,}  |  Cells: {data.n_cells:,}")
    print(f"Stress range: {svm.min():.2f} – {svm.max():.2f} MPa")
    print(f"Disp range:   {data.displacement_magnitude.min():.4f} – "
          f"{data.displacement_magnitude.max():.4f} mm")
    idx = int(np.argmax(svm))
    pt = data.mesh.points[idx]
    print(f"Peak stress:  {svm[idx]:.2f} MPa @ ({pt[0]:.1f}, {pt[1]:.1f}, {pt[2]:.1f})")
