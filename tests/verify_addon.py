import json
import sys
from pathlib import Path

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


def create_object(name, data=None):
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def assert_center(camera, target, label):
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated_camera = camera.evaluated_get(depsgraph)
    evaluated_target = target.evaluated_get(depsgraph)
    point = world_to_camera_view(
        bpy.context.scene,
        evaluated_camera,
        evaluated_target.matrix_world.translation,
    )
    check(
        abs(point.x - 0.5) < 1e-5
        and abs(point.y - 0.5) < 1e-5
        and point.z > 0,
        label,
    )


addon.register()
scene = bpy.context.scene
camera = create_object("Test camera", bpy.data.cameras.new("Test lens"))
scene.camera = camera
camera.location = (5, -8, 4)
subject = create_object("Subject")
subject.location = (1, 2, 0.5)
other = create_object("Other subject")
other.location = (-2, -3, 1)
old_focus = create_object("Original focus")
camera.data.dof.focus_object = old_focus
camera.data.dof.use_dof = False
unrelated = camera.constraints.new('LIMIT_LOCATION')
settings = camera.camera_subject_follow
settings.target = subject
assert_center(camera, subject, "Eyedropper property immediately aims at subject")
check(camera.data.dof.focus_object == subject, "Focus follows subject")
check(camera.data.dof.use_dof, "Depth of field enabled")

for index, position in enumerate(((7, -2, 2), (-4, 6, 3), (1, 2, 10))):
    camera.location = position
    assert_center(camera, subject, "Camera movement %d keeps subject centered" % index)

subject.location = (3, 0, 2)
assert_center(camera, subject, "Subject movement keeps subject centered")
settings.target = other
assert_center(camera, other, "Switching subject retargets camera")
check(camera.data.dof.focus_object == other, "Switching subject updates focus")
check(len(camera.constraints) == 2, "Switching target does not duplicate constraints")
settings.follow_rotation = False
check(addon.managed_constraint(camera).mute, "Rotation can be paused")
settings.follow_rotation = True
assert_center(camera, other, "Rotation can be resumed")
settings.follow_focus = False
check(camera.data.dof.focus_object == old_focus, "Focus restores previous target")
check(not camera.data.dof.use_dof, "Focus restores previous DOF state")
settings.follow_focus = True
check(camera.data.dof.focus_object == other, "Focus can be resumed")

camera.location = (7, -6, 4)
camera.keyframe_insert(data_path="location", frame=1)
camera.location = (-6, 4, 6)
camera.keyframe_insert(data_path="location", frame=20)
other.location = (-2, 1, 0)
other.keyframe_insert(data_path="location", frame=1)
other.location = (3, 2, 2)
other.keyframe_insert(data_path="location", frame=20)
for frame in (1, 7, 14, 20):
    scene.frame_set(frame)
    assert_center(camera, other, "Animated frame %d tracks correctly" % frame)

child = create_object("Camera child")
child.parent = camera
check(not addon.target_is_valid(settings, camera), "Self target rejected")
check(not addon.target_is_valid(settings, child), "Camera child target rejected")

camera_two = create_object("Second camera", bpy.data.cameras.new("Second lens"))
camera_two.location = (-4, -5, 3)
camera_two.camera_subject_follow.target = subject
assert_center(camera_two, subject, "Second camera has its own subject")
check(settings.target == other, "Second camera does not change first camera")

settings.target = None
check(addon.managed_constraint(camera) is None, "Clearing removes owned constraint")
check(unrelated in camera.constraints.values(), "User constraint preserved")
check(camera.data.dof.focus_object == old_focus, "Clearing restores original focus")
check(not camera.data.dof.use_dof, "Clearing restores original DOF state")

settings.target = other
camera.data.dof.focus_object = old_focus
settings.follow_focus = False
check(camera.data.dof.focus_object == old_focus, "Manual focus changes preserved")
settings.follow_focus = True

scene.camera = camera_two
for selected in bpy.context.selected_objects:
    selected.select_set(False)
other.select_set(True)
bpy.context.view_layer.objects.active = other
check(bpy.ops.camera_subject_follow.use_selected() == {'FINISHED'}, "Selected target operator works")
check(camera_two.camera_subject_follow.target == other, "Selected target assigned")
check(bpy.ops.camera_subject_follow.clear() == {'FINISHED'}, "Clear operator works")
camera_two.camera_subject_follow.target = subject
bpy.data.objects.remove(subject, do_unlink=True)
bpy.context.view_layer.update()
check(camera_two.camera_subject_follow.target is None, "Deleted target handled safely")

scene.camera = camera
settings.follow_rotation = True
settings.follow_focus = True
settings.target = other
bpy.ops.wm.save_as_mainfile(filepath=str(TEST_OUTPUT / "follow_test.blend"))
addon.unregister()
bpy.ops.wm.open_mainfile(filepath=str(TEST_OUTPUT / "follow_test.blend"))
camera = bpy.data.objects["Test camera"]
other = bpy.data.objects["Other subject"]
assert_center(camera, other, "Native tracking survives save and load without addon")
check(camera.data.dof.focus_object == other, "Native focus survives save and load without addon")
addon.register()
check(camera.camera_subject_follow.target == other, "Settings survive reload")
camera.camera_subject_follow.target = None
check(camera.data.dof.focus_object == bpy.data.objects["Original focus"], "Saved focus snapshot restores after reload")
check(camera.constraints.get("Limit Location") is not None, "User constraint survives reload and clearing")
addon.unregister()
print("CSF_VERIFICATION " + json.dumps({"count": len(checks), "checks": checks}))
