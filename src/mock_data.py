"""
Mock Data Generator for Report Automator Pro
=============================================
Generates a synthetic cantilever beam mesh with a hole,
annotated with realistic CAE-style stress and displacement fields.

Mesh: UnstructuredGrid — cantilever beam (rectangular plate) with a circular hole.
Fields: Stress (scalar + tensor) and Displacement (vector) on nodes.
"""

import numpy as np
import pyvista as pv
from dataclasses import dataclass, field
from typing import Tuple, Dict


# ---------------------------------------------------------------------------
# Dataclasses for type-safe field storage
# ---------------------------------------------------------------------------

@dataclass
class MeshData:
    """Container holding the PyVista mesh and all CAE field arrays."""
    mesh: pv.UnstructuredGrid
    node_ids: np.ndarray
    stress_von_mises: np.ndarray          # scalar (N_nodes,)
    stress_tensor: np.ndarray             # (N_nodes, 6) — Voigt notation: σxx,σyy,σzz,τxy,τyz,τzx
    displacement: np.ndarray              # (N_nodes, 3) — Ux, Uy, Uz
    principal_stress_max: np.ndarray      # (N_nodes,)
    principal_stress_min: np.ndarray      # (N_nodes,)
    displacement_magnitude: np.ndarray    # (N_nodes,)

    @property
    def n_nodes(self) -> int:
        return self.mesh.n_points

    @property
    def n_cells(self) -> int:
        return self.mesh.n_cells


# ---------------------------------------------------------------------------
# Mesh generation
# ---------------------------------------------------------------------------

def create_cantilever_beam_mesh(
    length: float = 10.0,
    height: float = 2.0,
    width: float = 1.0,
    hole_radius: float = 0.4,
    hole_center: Tuple[float, float, float] = (5.0, 1.0, 0.0),
    mesh_resolution: Tuple[int, int, int] = (80, 16, 8),
) -> pv.UnstructuredGrid:
    """
    Create a cantilever-beam UnstructuredGrid — a rectangular prism with a
    cylindrical through-hole, meshed with tetrahedral elements.

    Parameters
    ----------
    length : float
        Beam length along X-axis.
    height : float
        Beam height along Y-axis.
    width  : float
        Beam width (thickness) along Z-axis.
    hole_radius : float
        Radius of the circular hole.
    hole_center : tuple
        (x, y, z) centre of the hole.
    mesh_resolution : tuple
        (nx, ny, nz) voxelisation before marching cubes.

    Returns
    -------
    pv.UnstructuredGrid
    """
    nx, ny, nz = mesh_resolution

    # ---- voxel grid representing the beam --------------------------------
    x = np.linspace(0, length, nx)
    y = np.linspace(0, height, ny)
    z = np.linspace(-width / 2, width / 2, nz)
    X, Y, Z = np.meshgrid(x, y, z, indexing='ij')

    # ---- boolean mask: remove hole region --------------------------------
    dist_from_hole_axis = np.sqrt(
        (Y - hole_center[1]) ** 2 + (Z - hole_center[2]) ** 2
    )
    mask = dist_from_hole_axis >= hole_radius

    # ---- build uniform grid, then threshold ------------------------------
    grid = pv.StructuredGrid(X, Y, Z)
    grid['mask'] = mask.ravel(order='F')
    thresholded = grid.threshold(value=0.5, scalars='mask')   # keep solids

    # ---- tetrahedralise --------------------------------------------------
    ugrid = thresholded.cast_to_unstructured_grid()
    # If the grid is all-hex, convert to tetrahedra for a true unstructured mesh
    try:
        ugrid = ugrid.triangulate()
    except Exception:
        pass

    ugrid.clear_data()   # remove temporary scalar
    return ugrid


# ---------------------------------------------------------------------------
# Synthetic field generation
# ---------------------------------------------------------------------------

def _analytical_cantilever_displacement(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    L: float,
    H: float,
    P: float = 1000.0,
    E: float = 210e9,
    nu: float = 0.3,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Pseudo-analytical displacement for a tip-loaded cantilever (Timoshenko-style).

    Returns (Ux, Uy, Uz) arrays, same shape as x, y, z.
    """
    I = (1.0 * H ** 3) / 12.0          # moment of inertia (unit width)
    G = E / (2 * (1 + nu))             # shear modulus

    Ux = (P / (6 * E * I)) * (
        3 * nu * (y - H / 2) ** 2 * (L - x)
        + (4 + 5 * nu) * (H ** 2 / 4) * x
        + (3 * L - x) * x * (y - H / 2)
    )
    Uy = -(P / (6 * E * I)) * (
        x ** 2 * (3 * L - x)
        + 3 * nu * (y - H / 2) ** 2 * (L - x)
        + (4 + 5 * nu) * (H ** 2 / 4) * x
    )
    Uz = np.zeros_like(x)

    # Scale to mm-scale displacements
    scale = 1e3   # convert m → mm
    return Ux * scale, Uy * scale, Uz * scale


def _stress_from_displacement(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    L: float,
    H: float,
    P: float = 1000.0,
    E: float = 210e9,
    nu: float = 0.3,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Derive stress components from cantilever beam bending theory.

    Returns σxx, σyy, τxy (MPa), von Mises (MPa).
    """
    I = H ** 3 / 12.0
    y_neutral = H / 2

    sigma_xx = (P * (L - x) * (y - y_neutral)) / I / 1e6   # MPa
    sigma_yy = np.full_like(x, 1.2)                         # small residual (MPa)
    tau_xy = (P / (2 * I)) * ((H / 2) ** 2 - (y - y_neutral) ** 2) / 1e6

    svm = np.sqrt(sigma_xx ** 2 + sigma_yy ** 2 - sigma_xx * sigma_yy + 3 * tau_xy ** 2)

    return sigma_xx, sigma_yy, tau_xy, svm


def _add_hole_stress_concentration(
    xx: np.ndarray, yy: np.ndarray,
    svm: np.ndarray,
    hole_center: Tuple[float, float],
    hole_radius: float,
    kt: float = 3.0,
) -> np.ndarray:
    """
    Superimpose a stress-concentration factor around the hole edge
    (Kirsch solution approximation) to mimic a real FE result.
    """
    dist = np.sqrt((xx - hole_center[0]) ** 2 + (yy - hole_center[1]) ** 2)
    # Concentration decays as ~1/r² from hole edge
    factor = np.where(
        dist > hole_radius,
        1.0 + (kt - 1.0) * (hole_radius / dist) ** 2,
        kt,
    )
    return svm * factor


def compute_fields(
    mesh: pv.UnstructuredGrid,
    length: float = 10.0,
    height: float = 2.0,
    tip_load: float = 1000.0,
    youngs_modulus: float = 210e9,
    poisson_ratio: float = 0.3,
    hole_center: Tuple[float, float] = (5.0, 1.0),
    hole_radius: float = 0.4,
    noise_level: float = 0.02,
    seed: int = 42,
) -> MeshData:
    """
    Compute and attach synthetic FE fields to the mesh nodes.

    Parameters
    ----------
    mesh : pv.UnstructuredGrid
        Cantilever beam mesh.
    length, height : float
        Beam dimensions.
    tip_load : float
        Tip load magnitude (N).
    youngs_modulus : float
        Young's modulus (Pa).
    poisson_ratio : float
        Poisson's ratio.
    hole_center : tuple
        (x, y) centre of the hole.
    hole_radius : float
        Radius of the hole.
    noise_level : float
        Relative Gaussian noise added to simulate numerical noise.
    seed : int
        RNG seed for reproducibility.

    Returns
    -------
    MeshData
    """
    rng = np.random.default_rng(seed)
    pts = mesh.points   # (N, 3)
    x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]

    # ---- displacements ---------------------------------------------------
    ux, uy, uz = _analytical_cantilever_displacement(
        x, y, z, length, height, tip_load, youngs_modulus, poisson_ratio
    )
    disp = np.column_stack([ux, uy, uz])
    disp_mag = np.sqrt(ux ** 2 + uy ** 2 + uz ** 2)

    # ---- stresses --------------------------------------------------------
    sig_xx, sig_yy, tau_xy, svm = _stress_from_displacement(
        x, y, z, length, height, tip_load, youngs_modulus, poisson_ratio
    )

    # Hole stress concentration
    svm = _add_hole_stress_concentration(x, y, svm, hole_center, hole_radius)

    # Build full Voigt stress tensor (σxx, σyy, σzz, τxy, τyz, τzx)
    sig_zz = np.full_like(x, 0.0)          # plane-stress assumption
    tau_yz = np.zeros_like(x)
    tau_zx = np.zeros_like(x)
    stress_tensor = np.column_stack([sig_xx, sig_yy, sig_zz, tau_xy, tau_yz, tau_zx])

    # Principal stresses (2D simplification)
    sig_avg = (sig_xx + sig_yy) / 2
    sig_diff = (sig_xx - sig_yy) / 2
    R = np.sqrt(sig_diff ** 2 + tau_xy ** 2)
    prin_max = sig_avg + R
    prin_min = sig_avg - R

    # ---- add noise -------------------------------------------------------
    noise_scale_disp = noise_level * np.abs(disp_mag).mean()
    noise_scale_stress = noise_level * np.abs(svm).mean()

    disp_mag += rng.normal(0, noise_scale_disp, size=disp_mag.shape)
    svm += rng.normal(0, noise_scale_stress, size=svm.shape)
    prin_max += rng.normal(0, noise_scale_stress, size=prin_max.shape)
    prin_min += rng.normal(0, noise_scale_stress, size=prin_min.shape)
    stress_tensor += rng.normal(0, noise_scale_stress, size=stress_tensor.shape)

    # ---- assemble --------------------------------------------------------
    return MeshData(
        mesh=mesh,
        node_ids=np.arange(mesh.n_points),
        stress_von_mises=svm,
        stress_tensor=stress_tensor,
        displacement=disp,
        principal_stress_max=prin_max,
        principal_stress_min=prin_min,
        displacement_magnitude=disp_mag,
    )


# ---------------------------------------------------------------------------
# Convenience builder
# ---------------------------------------------------------------------------

def generate_mock_dataset(
    length: float = 10.0,
    height: float = 2.0,
    width: float = 1.0,
    hole_radius: float = 0.4,
    hole_center: Tuple[float, float, float] = (5.0, 1.0, 0.0),
    resolution: Tuple[int, int, int] = (80, 16, 8),
    tip_load: float = 1000.0,
    youngs_modulus: float = 210e9,
    poisson_ratio: float = 0.3,
    noise_level: float = 0.02,
    seed: int = 42,
) -> MeshData:
    """
    One-stop function: build mesh + compute all CAE fields.

    Returns
    -------
    MeshData
    """
    mesh = create_cantilever_beam_mesh(
        length=length,
        height=height,
        width=width,
        hole_radius=hole_radius,
        hole_center=hole_center,
        mesh_resolution=resolution,
    )
    return compute_fields(
        mesh=mesh,
        length=length,
        height=height,
        tip_load=tip_load,
        youngs_modulus=youngs_modulus,
        poisson_ratio=poisson_ratio,
        hole_center=(hole_center[0], hole_center[1]),
        hole_radius=hole_radius,
        noise_level=noise_level,
        seed=seed,
    )


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Generating mock dataset …")
    data = generate_mock_dataset()
    print(f"  Nodes         : {data.n_nodes:,}")
    print(f"  Cells         : {data.n_cells:,}")
    print(f"  Stress range  : {data.stress_von_mises.min():.2f} – {data.stress_von_mises.max():.2f} MPa")
    print(f"  Disp mag range: {data.displacement_magnitude.min():.4f} – {data.displacement_magnitude.max():.4f} mm")
    print("Done.")
