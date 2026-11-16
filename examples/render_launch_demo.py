"""Render three real add-on moves for the launch video. No external assets.

blender --background --factory-startup --python examples/render_launch_demo.py
"""
import json
from pathlib import Path
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import camera_subject_follow as addon

addon.register()
bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'examples/camera-follow-demo.blend'))
scene = bpy.context.scene
camera = scene.camera
target = camera.camera_subject_follow.target
motion = camera.camera_subject_motion
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 24
scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y = 864, 648
scene.render.resolution_percentage = 100
scene.render.fps = 15
camera.data.lens = 48
camera.data.dof.aperture_fstop = 7.1
output = ROOT / '.test-output/launch-frames'
output.mkdir(parents=True, exist_ok=True)
records = []

for preset, settings in (
    ('ORBIT', dict(radius=8.3, height=2.6, rise=2.0, turns=1.0)),
    ('DOLLY_IN', dict(radius=5.4, height=1.9, length=5.0)),
    ('HELIX', dict(radius=8.3, height=1.1, rise=2.7, turns=0.6)),
):
    motion.preset = preset
    motion.points = 32
    motion.start_frame, motion.end_frame = 1, 61
    motion.interpolation = 'LINEAR'
    motion.loop = 'NONE'
    motion.start_progress, motion.end_progress = 0, 1
    motion.angle = 0
    motion.fit_timeline = True
    for key, value in settings.items():
        setattr(motion, key, value)
    # Use the same base camera transform for each preset's initial direction.
    motion.enabled = False
    scene.frame_set(1)
    camera.location = (5.5, -7, 4.2)
    bpy.context.view_layer.update()
    assert bpy.ops.camera_subject_follow.create_path() == {'FINISHED'}
    folder = output / preset.lower()
    folder.mkdir(exist_ok=True)
    positions = []
    max_center_error = 0.0
    for i in range(60):
        scene.frame_set(1 + i)
        bpy.context.view_layer.update()
        graph = bpy.context.evaluated_depsgraph_get()
        evaluated = camera.evaluated_get(graph)
        projection = world_to_camera_view(scene, evaluated, target.matrix_world.translation)
        error = max(abs(projection.x - 0.5), abs(projection.y - 0.5))
        max_center_error = max(max_center_error, error)
        assert projection.z > 0 and error < 0.00001, (preset, i, projection)
        assert camera.data.dof.focus_object == target
        positions.append(list(evaluated.matrix_world.translation))
        frame = folder / f'{i:03d}.png'
        if not frame.exists():
            scene.render.filepath = str(frame)
            bpy.ops.render.render(write_still=True)
        print(f'LAUNCH_FRAME {preset} {i + 1}/60', flush=True)
    records.append(dict(preset=preset, positions=positions, max_center_error=max_center_error,
                        frame_count=60, fps=15, target=target.name))
    (output / 'manifest.json').write_text(json.dumps(records, indent=2))

print('LAUNCH_RENDER_COMPLETE', flush=True)
