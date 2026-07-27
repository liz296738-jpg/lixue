from .mock_data import (
    MeshData,
    create_cantilever_beam_mesh,
    compute_fields,
    generate_mock_dataset,
)
from .renderer import (
    CameraPreset,
    CAMERA_PRESETS,
    render_scalar_field,
    render_stress,
    render_displacement,
    render_report_suite,
)
from .ppt_generator import (
    SlideSpec,
    generate_pptx,
    generate_full_report,
)
