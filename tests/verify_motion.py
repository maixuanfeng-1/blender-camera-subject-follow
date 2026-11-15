import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TEST_OUTPUT = ROOT / ".test-output" / bpy.app.version_string
TEST_OUTPUT.mkdir(parents=True, exist_ok=True)
import camera_subject_follow as addon

checks = []


def check(condition, label):
    if not condition:
        raise AssertionError(label)
    checks.append(label)


def new_object(name, data=None):
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def world_position(obj):
    bpy.context.view_layer.update()
    return obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world.translation.copy()


def check_camera(camera, label):
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = camera.evaluated_get(depsgraph)
    subject = camera.camera_subject_follow.target.evaluated_get(depsgraph)
    projected = world_to_camera_view(bpy.context.scene, evaluated, subject.matrix_world.translation)
    check(abs(projected.x - 0.5) < 2e-5 and abs(projected.y - 0.5) < 2e-5 and projected.z > 0, label + " aims at subject")
    rig = camera.camera_subject_motion.rig.evaluated_get(depsgraph)
    check((rig.matrix_world.translation - evaluated.matrix_world.translation).length < 2e-5, label + " follows path exactly")
    check(camera.data.dof.focus_object == camera.camera_subject_follow.target, label + " retains autofocus")


addon.register()
scene = bpy.context.scene
camera = new_object("Motion camera", bpy.data.cameras.new("Motion lens"))
scene.camera = camera
parent = new_object("Original camera parent")
parent.location = (2, 3, -1)
parent.rotation_euler.z = 0.4
camera.parent = parent
camera.location = (8, -8, 4)
camera.keyframe_insert(data_path="location", frame=1)
camera.location = (12, -3, 6)
camera.keyframe_insert(data_path="location", frame=200)
original_action = camera.animation_data.action
original_curves = [(curve.data_path, len(curve.keyframe_points)) for collection in addon.fcurve_collections(camera) for curve in collection]
scene.frame_set(1)
base_position = world_position(camera)
subject = new_object("Motion subject")
subject.location = (2, 1, 0.5)
camera.camera_subject_follow.target = subject
settings = camera.camera_subject_motion
settings.start_frame = 1
settings.end_frame = 101
settings.interpolation = 'LINEAR'
settings.points = 16
created_paths = []

for preset, label, description in addon.PRESETS:
    settings.preset = preset
    check(bpy.ops.camera_subject_follow.create_path() == {'FINISHED'}, preset + " created")
    path = settings.path
    created_paths.append(path)
    check(path.data.splines[0].type == 'BEZIER', preset + " uses real Bezier controls")
    check(len(path.data.splines[0].bezier_points) == 16, preset + " has requested control count")
    positions = []
    for frame in (1, 26, 51, 76, 101):
        scene.frame_set(frame)
        check_camera(camera, preset + " frame " + str(frame))
        positions.append(world_position(camera))
    check(max((position - positions[0]).length for position in positions) > 0.1, preset + " visibly moves camera")
    check((positions[-1] - positions[0]).length < 1e-4 if path.data.splines[0].use_cyclic_u else True, preset + " closure correct")

check(camera.animation_data.action == original_action, "Camera original action untouched")
check([(curve.data_path, len(curve.keyframe_points)) for collection in addon.fcurve_collections(camera) for curve in collection] == original_curves, "Camera original keyframes untouched")
check(camera.parent == parent, "Camera original parent preserved")
extra_constraint = camera.constraints.new('COPY_LOCATION')
extra_constraint.target = parent
addon.bind_camera(bpy.context, camera)
check_camera(camera, "Rebinding puts path position after user-added constraints")
camera.constraints.remove(extra_constraint)
check(len([item for item in camera.constraints if item.type == 'COPY_LOCATION']) == 1, "Repeated presets reuse one position constraint")
check(len([obj for obj in scene.objects if obj.camera_subject_motion.owner_camera == camera]) == 1, "Repeated presets reuse one controller")

settings.reverse = True
check(bpy.ops.camera_subject_follow.animate_path() == {'FINISHED'}, "Reverse animation generated")
follow = addon.path_follower(camera)
check(abs(follow.offset_factor - 1) < 1e-6, "Reverse starts at path end")
scene.frame_set(101)
check(abs(follow.offset_factor) < 1e-6, "Reverse ends at path start")
settings.reverse = False
settings.interpolation = 'EASE'
addon.animate_path(bpy.context, camera)
scene.frame_set(11)
check(0 < follow.offset_factor < 0.05, "Smooth easing has slow start")
scene.frame_set(51)
check(abs(follow.offset_factor - 0.5) < 1e-4, "Smooth easing midpoint correct")
settings.interpolation = 'SINE'
addon.animate_path(bpy.context, camera)
scene.frame_set(11)
check(0 < follow.offset_factor < 0.05, "Sine easing has slow start")

settings.interpolation = 'LINEAR'
settings.loop = 'REPEAT'
addon.animate_path(bpy.context, camera)
scene.frame_set(126)
check(abs(follow.offset_factor - 0.25) < 1e-5, "Repeat cycle wraps progress")
settings.loop = 'MIRROR'
addon.animate_path(bpy.context, camera)
scene.frame_set(126)
check(abs(follow.offset_factor - 0.75) < 1e-5, "Ping-pong cycle reverses progress")
settings.loop = 'NONE'
settings.start_frame = 10
settings.end_frame = 210
settings.fit_timeline = True
addon.animate_path(bpy.context, camera)
check((scene.frame_start, scene.frame_end) == (10, 210), "Scene frame range synced on request")
progress_curves = [curve for collection in addon.fcurve_collections(settings.rig) for curve in collection if curve.data_path == follow.path_from_id("offset_factor")]
check(len(progress_curves) == 1 and len(progress_curves[0].keyframe_points) == 2, "Updating animation replaces only progress keys")
settings.auto_animate = False
bpy.ops.camera_subject_follow.create_path()
follow = addon.path_follower(camera)
scene.frame_set(110)
check(abs(follow.offset_factor) < 1e-6, "Creating without animation clears stale progress animation")
follow.offset_factor = 0.37
scene.frame_set(130)
check(abs(follow.offset_factor - 0.37) < 1e-6, "Manual progress stays editable without animation")
settings.auto_animate = True
addon.animate_path(bpy.context, camera)

settings.enabled = False
scene.frame_set(1)
check((world_position(camera) - base_position).length < 1e-5, "Disabling path restores original animated position")
settings.enabled = True
check_camera(camera, "Resuming path")
check(bpy.ops.camera_subject_follow.unbind_path() == {'FINISHED'}, "Unbind operator succeeds")
check((world_position(camera) - base_position).length < 1e-5, "Unbinding restores original animated position")
check(settings.path in scene.objects.values(), "Unbinding retains editable curve")
check(bpy.ops.camera_subject_follow.bind_path() == {'FINISHED'}, "Retained curve rebinds")

settings.preset = 'ORBIT'
settings.center_mode = 'SUBJECT'
settings.moving_center = True
settings.start_frame = 1
settings.end_frame = 101
settings.fit_timeline = False
bpy.ops.camera_subject_follow.create_path()
scene.frame_set(26)
before_move = world_position(camera)
subject.location += Vector((3, -2, 1))
after_move = world_position(camera)
check((after_move - before_move - Vector((3, -2, 1))).length < 1e-4, "Path translates with moving subject")
check_camera(camera, "Moving-center path")
settings.points = 24
settings.radius = 8
check(bpy.ops.camera_subject_follow.rebuild_path() == {'FINISHED'}, "Preset rebuild works")
check(len(settings.path.data.splines[0].bezier_points) == 24, "Rebuild updates control count")

check(bpy.ops.camera_subject_follow.edit_path() == {'FINISHED'}, "Curve edit mode opens")
check(bpy.context.mode == 'EDIT_CURVE', "Native curve edit mode active")
bpy.ops.curve.select_all(action='SELECT')
bpy.ops.curve.subdivide(number_cuts=1)
bpy.ops.object.mode_set(mode='OBJECT')
check(len(settings.path.data.splines[0].bezier_points) == 48, "Native subdivision adds editable points")
check_camera(camera, "Subdivided curve")
for selected in bpy.context.selected_objects:
    selected.select_set(False)
created_paths[1].select_set(True)
bpy.context.view_layer.objects.active = created_paths[1]
check(bpy.ops.camera_subject_follow.selected_path() == {'FINISHED'}, "User selected curve binds")
check(addon.path_follower(camera).target == created_paths[1], "Binding updates to selected curve")

camera_two = new_object("Second motion camera", bpy.data.cameras.new("Second motion lens"))
camera_two.location = (-6, -5, 4)
camera_two.camera_subject_follow.target = subject
camera_two.camera_subject_motion.path = created_paths[0]
addon.bind_camera(bpy.context, camera_two)
check(camera_two.camera_subject_motion.rig != settings.rig, "Two cameras have independent progress controllers")
check_camera(camera_two, "Second camera shared curve")
check(not addon.curve_is_valid(settings, new_object("Not a curve")), "Non-curve path rejected")
child_curve = new_object("Invalid child curve", bpy.data.curves.new("Child curve data", 'CURVE'))
child_curve.parent = camera
check(not addon.curve_is_valid(settings, child_curve), "Camera-dependent curve rejected")
check(not addon.target_is_valid(camera.camera_subject_follow, settings.rig), "Controller cannot be its own camera subject")

icons = set(bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"].enum_items.keys())


class LayoutProbe:
    def row(self, **kwargs):
        return self

    def separator(self):
        pass

    def prop(self, owner, name, **kwargs):
        check(name in owner.bl_rna.properties, "UI property " + name + " valid")

    def operator(self, identifier, **kwargs):
        if "icon" in kwargs:
            check(kwargs["icon"] in icons, "UI icon " + kwargs["icon"] + " valid")
        category, operator = identifier.split(".")
        getattr(getattr(bpy.ops, category), operator).get_rna_type()
        return SimpleNamespace()


for panel in (addon.CSF_PT_SubjectFollow, addon.CSF_PT_MotionCreate, addon.CSF_PT_MotionBinding, addon.CSF_PT_MotionAnimation):
    panel.draw(SimpleNamespace(layout=LayoutProbe()), bpy.context)
check(bpy.ops.camera_subject_follow.edit_path() == {'FINISHED'}, "UI edit-mode branch opens")
addon.CSF_PT_MotionBinding.draw(SimpleNamespace(layout=LayoutProbe()), bpy.context)
bpy.ops.object.mode_set(mode='OBJECT')

scene.camera = camera
bpy.ops.wm.save_as_mainfile(filepath=str(TEST_OUTPUT / "motion_test.blend"))
saved_camera_name = camera.name
saved_subject_name = subject.name
saved_rig_name = settings.rig.name
addon.unregister()
bpy.ops.wm.open_mainfile(filepath=str(TEST_OUTPUT / "motion_test.blend"))
camera = bpy.data.objects[saved_camera_name]
subject = bpy.data.objects[saved_subject_name]
scene = bpy.context.scene
scene.frame_set(26)
without_addon = world_position(camera)
scene.frame_set(76)
check((world_position(camera) - without_addon).length > 0.1, "Native path animation works without addon after reload")
check(camera.data.dof.focus_object == subject, "Native autofocus works without addon after reload")
addon.register()
check(camera.camera_subject_motion.rig.name == saved_rig_name, "Motion settings persist after reload")
check_camera(camera, "Reloaded motion")
addon.unregister()
print("CSF_MOTION_VERIFICATION " + json.dumps({"count": len(checks), "presets": len(addon.PRESETS), "native_reload": True, "ui_validated": True}))
