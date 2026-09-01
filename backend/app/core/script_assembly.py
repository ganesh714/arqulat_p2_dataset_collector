import re

FIXED_IMPORTS = """import bpy
import bmesh
import math
import os
from mathutils import Vector
"""

FIXED_PHASE1 = """
# ==============================================================================
# Phase 1: Setup and Clean Scene
# ==============================================================================
bpy.ops.wm.read_factory_settings(use_empty=True)
"""

FIXED_PHASE3_TEMPLATE = """
# ==============================================================================
# Phase 3: Export & Render
# ==============================================================================
light_data = bpy.data.lights.new(name="Light", type='AREA')
light_data.energy = 1000
light_data.size = 5.0
light_obj = bpy.data.objects.new(name="Light", object_data=light_data)
bpy.context.collection.objects.link(light_obj)
light_obj.location = (4, -4, 5)

cam_data = bpy.data.cameras.new("Camera")
cam_obj = bpy.data.objects.new("Camera", cam_data)
bpy.context.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj
cam_obj.location = (0, -6, 3)

tt = cam_obj.constraints.new(type='TRACK_TO')
tt.target = {{OBJECT}}
tt.track_axis = 'TRACK_NEGATIVE_Z'
tt.up_axis = 'UP_Y'
bpy.context.view_layer.update()

cwd = os.getcwd()
bpy.ops.object.select_all(action='DESELECT')
{{OBJECT}}.select_set(True)
bpy.ops.export_scene.gltf(
    filepath=os.path.join(cwd, "model.glb"),
    export_format='GLB',
    use_selection=True,
    export_apply=True
)

try:
    bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'
except TypeError:
    bpy.context.scene.render.engine = 'BLENDER_EEVEE'

bpy.context.scene.render.filepath = os.path.join(cwd, "render.png")
bpy.context.scene.render.resolution_x = 512
bpy.context.scene.render.resolution_y = 512
bpy.context.scene.render.film_transparent = True
bpy.ops.render.render(write_still=True)
"""

def extract_final_object_name(phase2_code: str) -> str | None:
    if not phase2_code:
        return None
        
    lines = [line.strip() for line in phase2_code.splitlines() if line.strip()]
    if not lines:
        return None
        
    last_line = lines[-1]
    
    # Looking for a plain assignment: something = "..." or something = '...'
    # or even just something = some_var (we extract the LHS)
    # Looking for: final_object_name = "my_var" or final_object_name = my_var
    match = re.match(r"^final_object_name\s*=\s*['\"]?([A-Za-z0-9_]+)['\"]?", last_line)
    if match:
        return match.group(1)
        
    return None

def assemble_executable_script(phase2_code: str) -> str:
    phase2_code = phase2_code or ""
    
    final_object_name = extract_final_object_name(phase2_code)
    if not final_object_name:
        final_object_name = "fallback_obj"
        
    # Remove the final_object_name assignment line from the code
    # It was only for the backend to parse, it shouldn't be in the final script
    lines = phase2_code.split('\n')
    if lines:
        last_line_idx = len(lines) - 1
        while last_line_idx >= 0 and not lines[last_line_idx].strip():
            last_line_idx -= 1
        if last_line_idx >= 0 and re.match(r"^final_object_name\s*=", lines[last_line_idx].strip()):
            lines.pop(last_line_idx)
            phase2_code = '\n'.join(lines)
        
    phase3 = FIXED_PHASE3_TEMPLATE.replace("{{OBJECT}}", final_object_name)
    
    full_script = FIXED_IMPORTS
    full_script += FIXED_PHASE1
    full_script += "\n# ==============================================================================\n"
    full_script += "# Phase 2: Core Geometry & Materials\n"
    full_script += "# ==============================================================================\n"
    full_script += phase2_code
    if not phase2_code.endswith("\n"):
        full_script += "\n"
    full_script += phase3
    
    return full_script

def assemble_training_script(think_block: str, phase2_code: str) -> str:
    think_block = think_block or ""
    
    # Strip <think> tags if they were accidentally included by the user
    think_block = re.sub(r"^<think>\s*", "", think_block, flags=re.IGNORECASE)
    think_block = re.sub(r"\s*</think>$", "", think_block, flags=re.IGNORECASE)
    
    full_script = f"<think>\n{think_block}\n</think>\n"
    full_script += assemble_executable_script(phase2_code)
    
    return full_script

def validate_think_block(text: str) -> list[str]:
    warnings = []
    text = text or ""
    
    if not re.search(r'^To create ".*" procedurally in Blender, I need', text.strip(), re.IGNORECASE):
        warnings.append("Think block must start with: To create \"...\" procedurally in Blender, I need")
        
    if "1. Materials:" not in text and "1. materials:" not in text.lower():
        warnings.append("Think block is missing the '1. Materials:' section.")
        
    if "Pipeline:" not in text and "pipeline:" not in text.lower():
        warnings.append("Think block is missing the 'Pipeline:' section.")
        
    return warnings

def validate_phase2_code(code: str) -> list[str]:
    warnings = []
    code = code or ""
    
    if not extract_final_object_name(code):
        warnings.append("Last non-empty line of Phase 2 must be an object assignment (e.g. final_object_name = ...).")
        
    forbidden_patterns = [
        (r"shade_naked", "shade_naked() does not exist. Use shade_smooth()."),
        (r"TexClouds", "ShaderNodeTexClouds does not exist. Use ShaderNodeTexNoise."),
        (r"import\s+numpy", "Do not import numpy. Use math and mathutils."),
        (r"import\s+random", "Do not import random. Use math and mathutils.noise."),
        (r"GLTF_SEPARATE", "Do not use GLTF_SEPARATE. Always use GLB."),
        (r"export_scene\.gltf.*export_scene\.gltf", "Duplicate export_scene.gltf calls detected."),
    ]
    
    for pattern, warning in forbidden_patterns:
        if re.search(pattern, code, re.DOTALL):
            warnings.append(warning)
            
    # Also check hardcoded paths
    if "/tmp/" in code or "/path/to/" in code:
        warnings.append("Do not use hardcoded paths like /tmp/ or /path/to/.")
        
    return warnings
