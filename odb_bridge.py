"""
ABAQUS ODB Bridge — Extract mesh + field data from .odb
=========================================================
Run INSIDE the Abaqus Python environment:

    abaqus python odb_bridge.py input.odb [output.npz]

Output: a .npz file containing:
    points      : (N, 3) float32 — node coordinates
    cells       : (M, K) int32   — element connectivity (K nodes per cell)
    cell_types  : (M,)  int32    — VTK cell type codes
    stress_vm   : (N,)  float32 — von Mises stress (last frame)
    stress_tensor: (N, 6) float32 — Voigt notation
    displacement: (N, 3) float32 — displacement vector
    disp_mag    : (N,)  float32 — displacement magnitude
"""

import sys
import os
import numpy as np

# -- Abaqus imports (only available inside Abaqus Python) -------------------
from odbAccess import openOdb
from abaqusConstants import *


# VTK cell-type mapping for Abaqus element types → VTK
# Ref: https://vtk.org/wp-content/uploads/2015/04/file-formats.pdf
_VTK_TETRA = 10
_VTK_HEXAHEDRON = 12
_VTK_WEDGE = 13
_VTK_PYRAMID = 14
_VTK_QUAD = 9
_VTK_TRIANGLE = 5

# Abaqus element-type name → (VTK_type, nodes_per_elem, local_face_order)
_ELEM_TYPE_MAP = {
    "C3D4":  (_VTK_TETRA, 4),
    "C3D4H": (_VTK_TETRA, 4),
    "C3D10": (_VTK_TETRA, 10),      # quadratic tet
    "C3D10H": (_VTK_TETRA, 10),
    "C3D8":  (_VTK_HEXAHEDRON, 8),
    "C3D8H": (_VTK_HEXAHEDRON, 8),
    "C3D8R": (_VTK_HEXAHEDRON, 8),
    "C3D8RH": (_VTK_HEXAHEDRON, 8),
    "C3D20": (_VTK_HEXAHEDRON, 20),  # quadratic hex
    "C3D20H": (_VTK_HEXAHEDRON, 20),
    "C3D20R": (_VTK_HEXAHEDRON, 20),
    "C3D6":  (_VTK_WEDGE, 6),
    "C3D6H": (_VTK_WEDGE, 6),
    "C3D15": (_VTK_WEDGE, 15),
}

# Abaqus → VTK node reordering for linear elements
# (Abaqus local node numbering differs from VTK for some types)
_NODE_REORDER = {
    "C3D8": [0, 1, 2, 3, 4, 5, 6, 7],
    "C3D8R": [0, 1, 2, 3, 4, 5, 6, 7],
    "C3D8H": [0, 1, 2, 3, 4, 5, 6, 7],
    "C3D4": [0, 1, 2, 3],
    "C3D4H": [0, 1, 2, 3],
    "C3D6": [0, 1, 2, 3, 4, 5],
    "C3D6H": [0, 1, 2, 3, 4, 5],
}


def _get_first_step_frame(odb):
    """Return (step_obj, frame_obj) for the last frame of the first static step,
    or the only/first step+frame if not static."""
    if not odb.steps:
        raise ValueError("ODB has no steps.")
    step_key = list(odb.steps.keys())[0]
    step = odb.steps[step_key]
    if not step.frames:
        raise ValueError(f"Step '{step_key}' has no frames.")
    # Pick the last frame (final state)
    last_frame_idx = len(step.frames) - 1
    frame = step.frames[last_frame_idx]
    print(f"  Step: '{step_key}'  |  Frame: #{last_frame_idx}")
    return step, frame


def _extract_nodes(odb):
    """Return (coords, node_labels_map) where coords is (N,3)."""
    instance = odb.rootAssembly.instances[list(odb.rootAssembly.instances.keys())[0]]
    n_nodes = len(instance.nodes)
    coords = np.zeros((n_nodes, 3), dtype=np.float32)
    label_map = {}
    for i, node in enumerate(instance.nodes):
        coords[i] = node.coordinates
        label_map[node.label] = i
    print(f"  Nodes: {n_nodes:,}")
    return coords, label_map


def _extract_elements(odb, label_map):
    """Return (connectivity, cell_types) arrays in VTK convention."""
    instance = odb.rootAssembly.instances[list(odb.rootAssembly.instances.keys())[0]]
    elements = instance.elements

    # Group by element type
    elems_by_type = {}
    for elem in elements:
        etype = elem.type.upper()
        elems_by_type.setdefault(etype, []).append(elem)

    # Build arrays
    conn_chunks, type_chunks = [], []
    for etype, elems_list in elems_by_type.items():
        vtk_type, npe = _ELEM_TYPE_MAP.get(etype, (None, None))
        if vtk_type is None:
            print(f"  [WARN] Unknown element type '{etype}' — skipping {len(elems_list)} elements")
            continue

        reorder = _NODE_REORDER.get(etype, list(range(npe)))
        conn = np.zeros((len(elems_list), npe), dtype=np.int32)
        for ie, elem in enumerate(elems_list):
            labels = [elem.connectivity[i] for i in reorder]
            conn[ie] = [label_map[l] for l in labels]

        conn_chunks.append(conn)
        type_chunks.append(np.full(len(elems_list), vtk_type, dtype=np.int32))
        print(f"  {' ' + etype + ':':10s} {len(elems_list):,} elements (VTK type {vtk_type})")

    connectivity = np.vstack(conn_chunks) if conn_chunks else np.array([], dtype=np.int32)
    cell_types = np.concatenate(type_chunks) if type_chunks else np.array([], dtype=np.int32)
    print(f"  Total elements: {len(cell_types):,}")
    return connectivity, cell_types


def _extract_field(frame, field_id: str, n_nodes: int):
    """
    Extract a nodal field from the frame.

    Parameters
    ----------
    field_id : str
        One of 'S' (stress), 'U' (displacement).
    n_nodes : int
        Total node count.

    Returns
    -------
    np.ndarray or None
    """
    try:
        fo = frame.fieldOutputs[field_id]
    except KeyError:
        print(f"  [WARN] Field '{field_id}' not found in frame")
        return None

    # Get the first sub-field (e.g. S-S11, U-U1)
    # For stress, there are sub-locations (integration point, centroid, nodal)
    sub_fields = list(fo.values)
    if not sub_fields:
        return None

    # Prefer nodal-averaged data
    sf = sub_fields[0]
    for candidate in sub_fields:
        if hasattr(candidate, 'positions') and candidate.positions is not None:
            sf = candidate

    data = np.zeros((n_nodes, len(sf.componentLabels)), dtype=np.float32)
    for entry in sf.values:
        node_label = entry.nodeLabel
        # node_label from Abaqus starts at 1
        data[node_label - 1] = entry.data

    return data


def _compute_von_mises(stress_tensor):
    """von Mises from Voigt tensor (S11,S22,S33,S12,S13,S23)."""
    if stress_tensor is None:
        return None
    s = stress_tensor
    return np.sqrt(
        0.5 * (
            (s[:,0] - s[:,1])**2 +
            (s[:,1] - s[:,2])**2 +
            (s[:,2] - s[:,0])**2 +
            6 * (s[:,3]**2 + s[:,4]**2 + s[:,5]**2)
        )
    )


def extract_odb(odb_path: str, output_path: str) -> None:
    """
    Main extraction routine.

    Reads an .odb file and writes a .npz archive with:
      points, cells, cell_types,
      stress_vm, stress_tensor, displacement, disp_mag
    """
    print(f"Opening ODB: {odb_path}")
    odb = openOdb(odb_path, readOnly=True)

    try:
        step, frame = _get_first_step_frame(odb)
        points, label_map = _extract_nodes(odb)
        cells, cell_types = _extract_elements(odb, label_map)

        # Stress
        print("  Extracting stress field (S)...")
        stress_tensor = _extract_field(frame, 'S', len(points))
        stress_vm = _compute_von_mises(stress_tensor) if stress_tensor is not None else None

        # Displacement
        print("  Extracting displacement field (U)...")
        disp = _extract_field(frame, 'U', len(points))
        disp_mag = np.linalg.norm(disp, axis=1) if disp is not None else None

        # Save
        save_dict = {
            "points": points,
            "cells": cells,
            "cell_types": cell_types,
        }
        if stress_vm is not None:
            save_dict["stress_vm"] = stress_vm
            save_dict["stress_tensor"] = stress_tensor
        if disp is not None:
            save_dict["displacement"] = disp
            save_dict["disp_mag"] = disp_mag

        np.savez_compressed(output_path, **save_dict)
        print(f"\n  Saved: {output_path}  ({os.path.getsize(output_path)/1024:.0f} KB)")

        # Quick summary
        if stress_vm is not None:
            idx = np.argmax(stress_vm)
            pt = points[idx]
            print(f"  Peak von Mises: {stress_vm[idx]:.2f} MPa @ node #{idx} ({pt[0]:.1f},{pt[1]:.1f},{pt[2]:.1f})")

    finally:
        odb.close()


# =========================================================================
# CLI
# =========================================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: abaqus python odb_bridge.py <input.odb> [output.npz]")
        print("  Extracts mesh + stress/displacement fields from an ABAQUS ODB.")
        sys.exit(1)

    odb_path = sys.argv[1]
    if not os.path.exists(odb_path):
        print(f"ERROR: file not found: {odb_path}")
        sys.exit(1)

    output = sys.argv[2] if len(sys.argv) > 2 else odb_path.replace(".odb", "_extracted.npz")
    extract_odb(odb_path, output)
