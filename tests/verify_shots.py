import json
import sys
from pathlib import Path
from types import SimpleNamespace

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Quaternion, Vector


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


def position(obj):
    bpy.context.view_layer.update()
    return obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world.translation.copy()


def check_shot(camera, reference, label):
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = camera.evaluated_get(depsgraph)
    check((evaluated.matrix_world.translation - reference.matrix_world.translation).length < 2e-5, label + " position matches")
    for point in ((0, 0, 0), (1, 2, 1), (-2, 1, 2)):
        actual = world_to_camera_view(bpy.context.scene, evaluated, Vector(point))
        expected = world_to_camera_view(bpy.context.scene, reference, Vector(point))
        if (actual - expected).length >= 3e-5:
            print("SHOT_MISMATCH", label, tuple(actual), tuple(expected),
                  "rotation", tuple(evaluated.matrix_world.to_quaternion()), tuple(reference.matrix_world.to_quaternion()),
                  "camera", [(name, getattr(evaluated.data, name), getattr(reference.data, name)) for name in addon.SHOT_CAMERA_FIELDS])
        check((actual - expected).length < 3e-5, label + " landmark projection matches")
    for name in addon.SHOT_CAMERA_FIELDS:
        actual, expected = getattr(evaluated.data, name), getattr(reference.data, name)
        check(actual == expected if isinstance(actual, str) else abs(actual - expected) < 1e-4, label + " camera " + name + " matches")


addon.register()
scene = bpy.context.scene
parent = new_object("Existing camera parent")
parent.location = (2, -1, 1)
parent.rotation_euler.z = 0.6
parent.scale = (1.2, 1.2, 1.2)
camera = new_object("Shot camera", bpy.data.cameras.new("Original lens data"))
camera.parent = parent
scene.camera = camera
camera.location = (7, -8, 3)
camera.keyframe_insert(data_path="location", frame=1)
camera.location = (9, -4, 5)
camera.keyframe_insert(data_path="location", frame=101)
original_action = camera.animation_data.action
original_data = camera.data
original_data.lens = 35
original_data.keyframe_insert(data_path="lens", frame=1)
original_data.lens = 65
original_data.keyframe_insert(data_path="lens", frame=101)
original_lens_action = original_data.animation_data.action
subject = new_object("Focus subject")
camera.camera_subject_follow.target = subject
motion = camera.camera_subject_motion
motion.start_frame, motion.end_frame = 1, 101
motion.interpolation = 'LINEAR'
scene.frame_set(51)
base_position = position(camera)

references = []
for index, (coordinates, lens, fit) in enumerate((((8, -7, 3), 28, 'HORIZONTAL'), ((-4, 6, 5), 78, 'VERTICAL'))):
    reference = new_object("Reference " + str(index), bpy.data.cameras.new("Reference lens " + str(index)))
    reference.location = coordinates
    reference.rotation_mode = 'QUATERNION'
    reference.rotation_quaternion = (Vector((1, 1, 1)) - reference.location).to_track_quat('-Z', 'Y') @ Quaternion((0, 0, 1), 0.12 * (index + 1))
    reference.data.lens = lens
    reference.data.shift_x = 0.12 if index == 0 else -0.08
    reference.data.shift_y = -0.06 if index == 0 else 0.1
    reference.data.sensor_width = 36 + index * 4
    reference.data.sensor_height = 24 + index * 4
    reference.data.sensor_fit = fit
    references.append(reference)
bpy.context.view_layer.update()
shots = camera.camera_subject_shots
shots.source = 'REFERENCE'
shots.start.source_camera, shots.end.source_camera = references
before_constraints = [(item.name, item.type) for item in camera.constraints]
check(bpy.ops.camera_subject_follow.capture_shot(side='START') == {'FINISHED'}, "Start reference captured")
check(bpy.ops.camera_subject_follow.capture_shot(side='END') == {'FINISHED'}, "End reference captured")
check(camera.data == original_data, "Capture does not replace camera data")
check(before_constraints == [(item.name, item.type) for item in camera.constraints], "Capture does not alter camera constraints")
check(shots.start.snapshot != references[0], "Start snapshot is independent")
check(shots.end.snapshot != references[1], "End snapshot is independent")
count = len(bpy.data.objects)
check(bpy.ops.camera_subject_follow.capture_shot(side='START') == {'FINISHED'}, "Start can be re-recorded")
check(len(bpy.data.objects) == count, "Re-recording reuses owned snapshot")

check(bpy.ops.camera_subject_follow.create_shot_path() == {'FINISHED'}, "Shot path generated")
path = motion.path
check(path.data.splines[0].type == 'BEZIER', "Shot path is editable native Bezier")
check(not path.data.splines[0].use_cyclic_u, "Shot path has separate endpoints")
check(len(path.data.splines[0].bezier_points) == shots.points, "Shot path respects point count")
check(camera.data != original_data and shots.original_data == original_data, "Shot framing uses independent camera data")
check(camera.animation_data.action == original_action, "Original object action preserved")
check(original_data.animation_data.action == original_lens_action, "Original lens action preserved")
scene.frame_set(1)
check_shot(camera, shots.start.snapshot, "First shot")
scene.frame_set(101)
check_shot(camera, shots.end.snapshot, "Last shot")
scene.frame_set(51)
check(28 < camera.data.lens < 78, "Lens transitions between recorded values")
check(camera.data.dof.focus_object == subject, "Autofocus remains on subject")

shots.framing = 'SUBJECT'
check(camera.data == original_data, "Subject mode restores original lens data")
bpy.context.view_layer.update()
evaluated = camera.evaluated_get(bpy.context.evaluated_depsgraph_get())
projection = world_to_camera_view(scene, evaluated, subject.matrix_world.translation)
check(abs(projection.x - 0.5) < 1e-5 and abs(projection.y - 0.5) < 1e-5, "Subject mode keeps subject centered")
shots.framing = 'MATCH'
scene.frame_set(101)
check_shot(camera, shots.end.snapshot, "Returning to matching mode")
scene.frame_set(51)
motion.enabled = False
check(camera.data == original_data, "Pausing restores original camera data")
check((position(camera) - base_position).length < 2e-5, "Pausing restores original animated position")
motion.enabled = True
scene.frame_set(1)
check_shot(camera, shots.start.snapshot, "Resuming shot motion")
scene.frame_set(51)
check(bpy.ops.camera_subject_follow.unbind_path() == {'FINISHED'}, "Shot motion unbinds")
check(camera.data == original_data, "Unbinding restores original camera data")
check((position(camera) - base_position).length < 2e-5, "Unbinding restores original animation")
check(addon.shot_rotation_constraint(camera) is None, "Unbinding removes only owned rotation constraint")
check(bpy.ops.camera_subject_follow.bind_path() == {'FINISHED'}, "Shot path rebinds")
motion.reverse = True
addon.animate_path(bpy.context, camera)
scene.frame_set(1)
check_shot(camera, shots.end.snapshot, "Reverse first shot")
scene.frame_set(101)
check_shot(camera, shots.start.snapshot, "Reverse last shot")
motion.reverse = False

motion.preset = 'ORBIT'
check(bpy.ops.camera_subject_follow.create_path() == {'FINISHED'}, "Normal preset still creates after shot motion")
check(camera.data == original_data, "Normal preset restores original lens animation")
check(addon.shot_rotation_constraint(camera) is None, "Normal preset restores subject tracking")
shots.source = 'CAMERA'
scene.frame_set(26)
check(bpy.ops.camera_subject_follow.capture_shot(side='START') == {'FINISHED'}, "Existing curve start captured")
scene.frame_set(76)
check(bpy.ops.camera_subject_follow.capture_shot(side='END') == {'FINISHED'}, "Existing curve end captured")
existing_path = motion.path
existing_controls = [tuple(point.co) for point in existing_path.data.splines[0].bezier_points]
check(abs(shots.start.progress - 0.25) < 1e-5 and abs(shots.end.progress - 0.75) < 1e-5, "Existing path records actual progress")
check(bpy.ops.camera_subject_follow.use_shot_range() == {'FINISHED'}, "Existing curve segment applied")
check(motion.path == existing_path, "Segment playback reuses existing curve")
check([tuple(point.co) for point in existing_path.data.splines[0].bezier_points] == existing_controls, "Segment playback preserves edited controls")
scene.frame_set(1)
check(abs(addon.path_follower(camera).offset_factor - 0.25) < 1e-5, "Segment starts at recorded progress")
check_shot(camera, shots.start.snapshot, "Segment first shot")
scene.frame_set(101)
check(abs(addon.path_follower(camera).offset_factor - 0.75) < 1e-5, "Segment ends at recorded progress")
check_shot(camera, shots.end.snapshot, "Segment last shot")

area = next(item for item in bpy.context.screen.areas if item.type == 'VIEW_3D')
region = next(item for item in area.regions if item.type == 'WINDOW')
with bpy.context.temp_override(area=area, region=region):
    space = bpy.context.space_data
    space.use_local_camera = False
    space.lock_camera = True
    space.region_3d.view_perspective = 'CAMERA'
    preview_frame = scene.frame_current
    check(bpy.ops.camera_subject_follow.preview_shot(side='START') == {'FINISHED'}, "Recorded frame preview opens")
    check(scene.frame_current == shots.start.frame, "Preview uses recorded scene frame")
    check(scene.camera == camera, "Preview preserves render camera")
    check(space.use_local_camera and space.camera == shots.start.snapshot, "Preview uses frozen local reference")
    check(not space.lock_camera, "Preview protects reference from camera-lock navigation")
    check(bpy.ops.camera_subject_follow.camera_view() == {'FINISHED'}, "Preview returns to render camera")
    check(not space.use_local_camera and space.lock_camera, "Preview restores prior viewport options")
    check(scene.frame_current == preview_frame, "Returning from preview restores scene frame")
    shots.source = 'VIEW'
    check(bpy.ops.camera_subject_follow.capture_shot(side='START') == {'FINISHED'}, "Current camera view can be recorded")
    check(shots.start.path == motion.path, "Camera-view recording retains path metadata")
    space.region_3d.view_perspective = 'PERSP'
    check(bpy.ops.camera_subject_follow.capture_shot(side='START') == {'FINISHED'}, "Free viewport can be recorded")
    check(shots.start.path is None, "Free viewport does not claim existing curve progress")
    check(shots.start.snapshot.data.type == 'PERSP', "Free viewport produces perspective reference")

shots.source = 'REFERENCE'
references[0].location = references[1].location
shots.shape = 'STRAIGHT'
shots.points = 2
bpy.context.view_layer.update()
bpy.ops.camera_subject_follow.capture_shot(side='START')
bpy.ops.camera_subject_follow.capture_shot(side='END')
check(bpy.ops.camera_subject_follow.create_shot_path() == {'FINISHED'}, "Stationary pan and zoom can be generated")
for frame in (1, 51, 101):
    scene.frame_set(frame)
    check((position(camera) - shots.start.snapshot.matrix_world.translation).length < 2e-5, "Stationary shot stays at recorded position " + str(frame))
scene.frame_set(1)
check_shot(camera, shots.start.snapshot, "Stationary first shot")
scene.frame_set(101)
check_shot(camera, shots.end.snapshot, "Stationary last shot")
stationary_path = motion.path
for point in stationary_path.data.splines[0].bezier_points:
    point.co += Vector((1, 2, 0))
    point.handle_left += Vector((1, 2, 0))
    point.handle_right += Vector((1, 2, 0))
bpy.ops.camera_subject_follow.bind_path()
scene.frame_set(51)
check((position(camera) - (shots.start.snapshot.matrix_world.translation + Vector((1, 2, 0)))).length < 2e-5, "Stationary point editing respects curve-local offset")
for point in stationary_path.data.splines[0].bezier_points:
    point.co -= Vector((1, 2, 0))
    point.handle_left -= Vector((1, 2, 0))
    point.handle_right -= Vector((1, 2, 0))
bpy.ops.camera_subject_follow.bind_path()
scene.frame_set(101)

icons = set(bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"].enum_items.keys())


class LayoutProbe:
    def row(self, **kwargs):
        return self

    def separator(self):
        pass

    def prop(self, owner, name, **kwargs):
        check(name in owner.bl_rna.properties, "Shot UI property " + name + " valid")

    def label(self, **kwargs):
        if "icon" in kwargs:
            check(kwargs["icon"] in icons, "Shot UI status icon valid")

    def operator(self, identifier, **kwargs):
        if "icon" in kwargs:
            check(kwargs["icon"] in icons, "Shot UI icon " + kwargs["icon"] + " valid")
        category, operator = identifier.split(".")
        getattr(getattr(bpy.ops, category), operator).get_rna_type()
        return SimpleNamespace()


addon.CSF_PT_ShotFrames.draw(SimpleNamespace(layout=LayoutProbe()), bpy.context)
bpy.ops.wm.save_as_mainfile(filepath=str(TEST_OUTPUT / "shots_test.blend"))
camera_name = camera.name
snapshot_names = (shots.start.snapshot.name, shots.end.snapshot.name)
addon.unregister()
bpy.ops.wm.open_mainfile(filepath=str(TEST_OUTPUT / "shots_test.blend"))
camera = bpy.data.objects[camera_name]
scene = bpy.context.scene
scene.frame_set(1)
check_shot(camera, bpy.data.objects[snapshot_names[0]], "Reload without addon first shot")
scene.frame_set(101)
check_shot(camera, bpy.data.objects[snapshot_names[1]], "Reload without addon last shot")
addon.register()
check(camera.camera_subject_shots.start.snapshot.name == snapshot_names[0], "Recorded shots persist in blend")
check(bpy.ops.camera_subject_follow.unbind_path() == {'FINISHED'}, "Reloaded shot path can be unbound")
check(camera.data.name == "Original lens data", "Original camera data restores after reload")
check(camera.data.animation_data.action is not None, "Original lens animation survives reload")
addon.unregister()
print("CSF_SHOTS_VERIFICATION " + json.dumps({"count": len(checks), "endpoint_projection": True, "native_reload": True}))
