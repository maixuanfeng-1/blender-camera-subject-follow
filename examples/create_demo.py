"""Create an original studio scene and animate its camera with the actual add-on.

blender --background --factory-startup --python examples/create_demo.py
Append -- --render to also render the README assets (Cycles CPU).
"""
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import camera_subject_follow as addon

addon.register()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 24
scene.cycles.use_denoising = True
scene.render.resolution_x = 720
scene.render.resolution_y = 540
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.fps = 24
scene.view_settings.view_transform = 'AgX'
scene.world.color = (0.12, 0.12, 0.12)
scene.render.film_transparent = False
scene.render.image_settings.color_mode = 'RGB'


def material(name, color, metallic=0, roughness=0.35):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    return m


orange = material('Terracotta enamel', (0.8, 0.16, 0.055), 0.25, 0.24)
dark = material('Charcoal metal', (0.018, 0.025, 0.035), 0.6, 0.24)
glass = material('Blue lens glass', (0.035, 0.18, 0.26), 0.75, 0.12)
cream = material('Warm white', (0.7, 0.65, 0.55), 0.15, 0.3)
ground = material('Slate studio floor', (0.045, 0.06, 0.082), 0.1, 0.5)


def finish(obj, name, mat):
    obj.name = name
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def box(name, position, size, mat, bevel=0.08):
    bpy.ops.mesh.primitive_cube_add(size=1, location=position)
    o = bpy.context.object
    o.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    finish(o, name, mat)
    mod = o.modifiers.new('Soft manufactured edges', 'BEVEL')
    mod.width, mod.segments = bevel, 5
    o.modifiers.new('Weighted corner normals', 'WEIGHTED_NORMAL')
    return o


def cylinder(name, position, radius, depth, mat, lens=False):
    bpy.ops.mesh.primitive_cylinder_add(vertices=80, radius=radius, depth=depth, location=position)
    o = finish(bpy.context.object, name, mat)
    if lens:
        o.rotation_euler.x = math.pi / 2
    mod = o.modifiers.new('Edge highlights', 'BEVEL')
    mod.width, mod.segments = 0.025, 3
    o.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return o


box('Camera body', (0, 0, 1.35), (2.25, 0.82, 1.42), orange, 0.14)
box('Top plate', (0, 0, 2.04), (2.05, 0.74, 0.09), dark, 0.04)
box('Rear screen', (0, 0.426, 1.37), (1.32, 0.05, 0.87), dark, 0.04)
box('Viewfinder', (-0.77, -0.44, 1.8), (0.32, 0.09, 0.2), glass, 0.035)
box('Front grip', (0.88, -0.44, 1.3), (0.22, 0.15, 0.9), dark, 0.05)
cylinder('Lens mount', (-0.12, -0.48, 1.34), 0.61, 0.18, cream, True)
cylinder('Lens barrel', (-0.12, -0.67, 1.34), 0.55, 0.3, dark, True)
cylinder('Lens rim', (-0.12, -0.84, 1.34), 0.49, 0.07, cream, True)
cylinder('Front glass', (-0.12, -0.885, 1.34), 0.42, 0.035, glass, True)
cylinder('Inner lens', (-0.12, -0.908, 1.34), 0.23, 0.01, dark, True)
cylinder('Shutter', (0.76, -0.05, 2.13), 0.12, 0.09, cream)
cylinder('Mode dial', (-0.7, 0.02, 2.15), 0.18, 0.11, dark)
for angle in range(0, 360, 20):
    a = math.radians(angle)
    o = box('Lens knurl', (-0.12 + 0.55 * math.cos(a), -0.68, 1.34 + 0.55 * math.sin(a)),
            (0.022, 0.2, 0.055), dark, 0.008)
    o.rotation_euler.y = -a
cylinder('Display plinth', (0, 0, 0.4), 1.72, 0.4, cream)
cylinder('Plinth base', (0, 0, 0.16), 1.86, 0.12, dark)
box('Studio ground', (0, 0, -0.05), (200, 200, 0.1), ground, 0)


def area(name, position, energy, size, color):
    data = bpy.data.lights.new(name, 'AREA')
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = position
    obj.rotation_euler = (Vector((0, 0, 1)) - obj.location).to_track_quat('-Z', 'Y').to_euler()
    data.energy, data.shape, data.size, data.color = energy, 'DISK', size, color


area('Warm key', (1, -4, 7), 1000, 5, (1, 0.78, 0.62))
area('Cool fill', (-5, -2, 4), 850, 4, (0.5, 0.72, 1))
area('Rim light', (2, 4, 5), 1200, 3, (0.7, 0.85, 1))
bpy.ops.object.empty_add(location=(0, 0, 1.1))
target = bpy.context.object
target.name = 'Focus target - pick me'
target.empty_display_type = 'SPHERE'
target.empty_display_size = 0.16
data = bpy.data.cameras.new('Demo lens')
camera = bpy.data.objects.new('Animated camera', data)
scene.collection.objects.link(camera)
scene.camera = camera
camera.location = (5.5, -7, 4.2)
camera.data.lens = 48
camera.data.dof.aperture_fstop = 7.1
camera.camera_subject_follow.target = target
motion = camera.camera_subject_motion
motion.preset = 'ORBIT'
motion.radius = 8.3
motion.height = 2.6
motion.points = 24
motion.start_frame, motion.end_frame = 1, 145
motion.interpolation = 'LINEAR'
motion.loop = 'REPEAT'
motion.fit_timeline = True
assert bpy.ops.camera_subject_follow.create_path() == {'FINISHED'}
path = motion.path
path.data.resolution_u = 32
path.color = (0.12, 0.85, 0.67, 1)
scene.frame_set(1)

# This file also plays without the add-on: constraints, curves and keys are native.
for selected in bpy.context.selected_objects:
    selected.select_set(False)
path.select_set(True)
bpy.context.view_layer.objects.active = path
for screen in bpy.data.screens:
    for a in screen.areas:
        if a.type == 'VIEW_3D':
            a.spaces.active.region_3d.view_perspective = 'CAMERA'
            a.spaces.active.show_region_ui = True
            a.spaces.active.shading.type = 'MATERIAL'
scene['Demo instructions'] = 'Press N > 相机跟随. Play frames 1-145. Tab on the selected curve to edit control points.'
scene['License'] = 'GPL-3.0-or-later; original procedural scene, no external assets.'
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'examples' / 'camera-follow-demo.blend'))

if '--render' in sys.argv:
    output = ROOT / '.test-output' / 'demo-frames'
    output.mkdir(parents=True, exist_ok=True)
    coordinates = []
    for i in range(36):
        frame = 1 + i * 4
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        p = camera.evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world.translation
        coordinates.append(list(p))
        scene.render.filepath = str(output / f'{i:03d}.png')
        bpy.ops.render.render(write_still=True)
        print('DEMO_FRAME', i, flush=True)
    (output / 'positions.json').write_text(json.dumps(coordinates))
    scene.frame_set(1)
    scene.cycles.samples = 64
    scene.render.resolution_x, scene.render.resolution_y = 1400, 1000
    scene.render.filepath = str(output / 'hero-render.png')
    bpy.ops.render.render(write_still=True)
