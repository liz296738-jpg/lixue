"""
ABAQUS ODB Bridge — Extract mesh + field data from .odb
=========================================================
Run INSIDE the Abaqus Python environment:

    abaqus python odb_bridge.py input.odb [output.npz]

Output: a .npz file containing mesh geometry + stress/displacement fields.
"""

import sys, os, numpy as np
from odbAccess import openOdb
from abaqusConstants import *

# VTK cell-type codes
VTK_TETRA, VTK_HEXAHEDRON = 10, 12
VTK_WEDGE, VTK_PYRAMID = 13, 14
VTK_QUAD, VTK_TRIANGLE = 9, 5

_ELEM_TYPE_MAP = {
    # 3D solid
    "C3D4":(VTK_TETRA,4),"C3D4H":(VTK_TETRA,4),"C3D10":(VTK_TETRA,10),"C3D10H":(VTK_TETRA,10),
    "C3D8":(VTK_HEXAHEDRON,8),"C3D8H":(VTK_HEXAHEDRON,8),"C3D8R":(VTK_HEXAHEDRON,8),"C3D8RH":(VTK_HEXAHEDRON,8),
    "C3D20":(VTK_HEXAHEDRON,20),"C3D20H":(VTK_HEXAHEDRON,20),"C3D20R":(VTK_HEXAHEDRON,20),
    "C3D6":(VTK_WEDGE,6),"C3D6H":(VTK_WEDGE,6),"C3D15":(VTK_WEDGE,15),
    # 2D plane stress/strain
    "CPS3":(VTK_TRIANGLE,3),"CPS4":(VTK_QUAD,4),"CPS4R":(VTK_QUAD,4),"CPS4I":(VTK_QUAD,4),
    "CPS6":(VTK_TRIANGLE,6),"CPS8":(VTK_QUAD,8),"CPS8R":(VTK_QUAD,8),
    "CPE3":(VTK_TRIANGLE,3),"CPE4":(VTK_QUAD,4),"CPE4R":(VTK_QUAD,4),"CPE6":(VTK_TRIANGLE,6),"CPE8":(VTK_QUAD,8),
    "CAX3":(VTK_TRIANGLE,3),"CAX4":(VTK_QUAD,4),"CAX4R":(VTK_QUAD,4),"CAX6":(VTK_TRIANGLE,6),"CAX8":(VTK_QUAD,8),
    # 3D shell
    "S3":(VTK_TRIANGLE,3),"S4":(VTK_QUAD,4),"S4R":(VTK_QUAD,4),"S8R":(VTK_QUAD,8),
    "STRI3":(VTK_TRIANGLE,3),"STRI65":(VTK_TRIANGLE,6),
}

_NODE_REORDER = {
    "C3D8":[0,1,2,3,4,5,6,7],"C3D8R":[0,1,2,3,4,5,6,7],"C3D8H":[0,1,2,3,4,5,6,7],
    "C3D4":[0,1,2,3],"C3D4H":[0,1,2,3],"C3D6":[0,1,2,3,4,5],"C3D6H":[0,1,2,3,4,5],
    "CPS3":[0,1,2],"CPS4":[0,1,2,3],"CPS4R":[0,1,2,3],
    "CPE3":[0,1,2],"CPE4":[0,1,2,3],"CPE4R":[0,1,2,3],
    "CAX3":[0,1,2],"CAX4":[0,1,2,3],"CAX4R":[0,1,2,3],
    "S3":[0,1,2],"S4":[0,1,2,3],"S4R":[0,1,2,3],"STRI3":[0,1,2],
}

def _get_last_frame(odb):
    step = odb.steps[list(odb.steps.keys())[0]]
    frame = step.frames[len(step.frames) - 1]
    print(f"  Step: '{list(odb.steps.keys())[0]}'  |  Frame: #{len(step.frames)-1}")
    return step, frame

def _extract_nodes(odb):
    inst = odb.rootAssembly.instances[list(odb.rootAssembly.instances.keys())[0]]
    n_nodes = len(inst.nodes)
    coords = np.zeros((n_nodes, 3), dtype=np.float32)
    label_map = {node.label: i for i, node in enumerate(inst.nodes)}
    for i, node in enumerate(inst.nodes):
        coords[i] = node.coordinates
    print(f"  Nodes: {n_nodes:,}")
    return coords, label_map

def _extract_elements(odb, label_map):
    inst = odb.rootAssembly.instances[list(odb.rootAssembly.instances.keys())[0]]
    by_type = {}
    for elem in inst.elements:
        et = elem.type.upper()
        by_type.setdefault(et, []).append(elem)
    conns, types = [], []
    for et, elems in by_type.items():
        info = _ELEM_TYPE_MAP.get(et)
        if info is None:
            print(f"  [WARN] Unknown element type '{et}' -- skipping {len(elems):,} elements")
            continue
        vtk_type, npe = info
        reorder = _NODE_REORDER.get(et, list(range(npe)))
        conn = np.zeros((len(elems), npe), dtype=np.int32)
        for ie, elem in enumerate(elems):
            conn[ie] = [label_map[elem.connectivity[r]] for r in reorder]
        conns.append(conn)
        types.append(np.full(len(elems), vtk_type, dtype=np.int32))
        print(f"  {' ' + et + ':':10s} {len(elems):,} elements (VTK type {vtk_type})")
    if not conns:
        return (np.array([], dtype=np.int32).reshape(0,3), np.array([], dtype=np.int32))
    return (np.vstack(conns), np.concatenate(types))

def _extract_field(frame, field_id, n_nodes):
    try:
        fo = frame.fieldOutputs[field_id]
    except KeyError:
        print(f"  [WARN] Field '{field_id}' not found")
        return None, None
    n_comp = len(fo.componentLabels)

    # Try to get nodal-averaged data via bulkDataBlocks
    data = np.zeros((n_nodes, n_comp), dtype=np.float32)
    count = 0

    # Abaqus stores field data in bulkDataBlocks (efficient array access)
    for blk in fo.bulkDataBlocks:
        blk_data = blk.data       # ndarray (M, n_comp)
        blk_labels = blk.nodeLabels  # ndarray (M,)
        if blk_labels is None or len(blk_labels) == 0:
            # Might be element-based; try elementLabels
            blk_labels = blk.elementLabels
            if blk_labels is None:
                continue
        for i in range(len(blk_labels)):
            nl = blk_labels[i]
            if nl is not None and 1 <= nl <= n_nodes:
                data[nl - 1] = blk_data[i, :n_comp]
                count += 1

    print(f"  -> {field_id}: {count:,} node values extracted ({n_comp} components)")
    return data, fo.componentLabels

def _compute_von_mises(stress_tensor):
    if stress_tensor is None:
        return None
    s = stress_tensor
    n_comp = s.shape[1]
    if n_comp >= 6:
        # 3D: S11,S22,S33,S12,S13,S23
        vm = np.sqrt(0.5 * ((s[:,0]-s[:,1])**2 + (s[:,1]-s[:,2])**2 +
                             (s[:,2]-s[:,0])**2 + 6*(s[:,3]**2+s[:,4]**2+s[:,5]**2)))
    elif n_comp == 4:
        # 2D plane stress: S11,S22,S33,S12  (S33=0 for plane stress, but Abaqus may include it)
        vm = np.sqrt(s[:,0]**2 - s[:,0]*s[:,1] + s[:,1]**2 + 3*s[:,3]**2)
    elif n_comp == 3:
        # 2D plane stress minimal: S11,S22,S12
        vm = np.sqrt(s[:,0]**2 - s[:,0]*s[:,1] + s[:,1]**2 + 3*s[:,2]**2)
    else:
        vm = np.zeros(len(s), dtype=np.float32)
    return vm

def extract_odb(odb_path, output_path):
    print(f"Opening ODB: {odb_path}")
    odb = openOdb(odb_path, readOnly=True)
    try:
        step, frame = _get_last_frame(odb)
        points, label_map = _extract_nodes(odb)
        cells, cell_types = _extract_elements(odb, label_map)
        print(f"  Total elements: {len(cell_types):,}")

        print("  Extracting stress field (S)...")
        st, comps = _extract_field(frame, 'S', len(points))
        svm = _compute_von_mises(st) if st is not None else None
        print(f"  Extracting displacement field (U)...")
        disp, disp_comps = _extract_field(frame, 'U', len(points))
        disp_mag = np.linalg.norm(disp, axis=1) if disp is not None else None

        save = {"points": points, "cells": cells, "cell_types": cell_types}
        if svm is not None:
            save["stress_vm"] = svm
            save["stress_tensor"] = st
        if disp is not None:
            save["displacement"] = disp
            save["disp_mag"] = disp_mag
        np.savez_compressed(output_path, **save)
        print(f"\n  Saved: {output_path}  ({os.path.getsize(output_path)/1024:.0f} KB)")
        if svm is not None and len(svm) > 0:
            idx = int(np.argmax(svm))
            pt = points[idx]
            print(f"  Peak von Mises: {svm[idx]:.2f} @ node #{idx} ({pt[0]:.1f},{pt[1]:.1f},{pt[2]:.1f})")
    finally:
        odb.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: abaqus python odb_bridge.py <input.odb> [output.npz]")
        sys.exit(1)
    odb_path = sys.argv[1]
    if not os.path.exists(odb_path):
        print(f"ERROR: file not found: {odb_path}")
        sys.exit(1)
    output = sys.argv[2] if len(sys.argv) > 2 else odb_path.replace(".odb", "_extracted.npz")
    extract_odb(odb_path, output)
