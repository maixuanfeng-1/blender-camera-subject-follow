import json
import sys
from pathlib import Path
from types import SimpleNamespace

import bpy


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


def reject(camera, kind, obj, label):
    try:
        addon.assign_picked_object(camera, kind, obj)
    except ValueError:
        check(True, label)
    else:
        raise AssertionError(label)


def new_object(name, data=None):
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    return obj


addon.register()
camera = new_object("Picker camera", bpy.data.cameras.new("Picker lens"))
camera.location = (5, -6, 4)
bpy.context.scene.camera = camera
subject = new_object("Pick subject")
subject.location = (1, 2, 0)
other = new_object("Other subject")
path = new_object("Pick path", bpy.data.curves.new("Picker path data", 'CURVE'))
reference = new_object("Pick reference", bpy.data.cameras.new("Reference lens"))
addon.assign_picked_object(camera, 'SUBJECT', subject)
check(camera.camera_subject_follow.target == subject, "Subject picker assigns clicked object")
check(addon.managed_constraint(camera).target == subject, "Picking updates Track To target immediately")
check(camera.data.dof.focus_object == subject, "Picking updates DOF target immediately")
reject(camera, 'SUBJECT', camera, "Self pick rejected")
reject(camera, 'SUBJECT', None, "Empty click rejected")
child = new_object("Camera child")
child.parent = camera
reject(camera, 'SUBJECT', child, "Camera child rejected")
check(camera.camera_subject_follow.target == subject, "Invalid picks preserve previous target")
addon.assign_picked_object(camera, 'PATH', path)
check(camera.camera_subject_motion.path == path, "Curve picker assigns curve")
reject(camera, 'PATH', subject, "Non-curve path pick rejected")
check(camera.camera_subject_motion.path == path, "Invalid path pick preserves curve")
addon.assign_picked_object(camera, 'START_CAMERA', reference)
addon.assign_picked_object(camera, 'END_CAMERA', reference)
check(camera.camera_subject_shots.start.source_camera == reference, "Start camera picker assigns camera")
check(camera.camera_subject_shots.end.source_camera == reference, "End camera picker assigns camera")
reject(camera, 'START_CAMERA', subject, "Non-camera reference rejected")

for obj in bpy.context.selected_objects:
    obj.select_set(False)
subject.select_set(True)
other.select_set(True)
bpy.context.view_layer.objects.active = subject
original_selected = set(bpy.context.selected_objects)
original_active = bpy.context.view_layer.objects.active
area = next(item for item in bpy.context.screen.areas if item.type == 'VIEW_3D')
region = next(item for item in area.regions if item.type == 'WINDOW')
real_bpy = addon.bpy
calls = []


def native_selection_stub(*args, **kwargs):
    calls.append((args, kwargs))
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    reference.select_set(True)
    bpy.context.view_layer.objects.active = reference
    return {'FINISHED', 'PASS_THROUGH'}


try:
    addon.bpy = SimpleNamespace(ops=SimpleNamespace(view3d=SimpleNamespace(select=native_selection_stub)))
    picked = addon.pick_object_in_area(bpy.context, area, region, (35, 46))
    check(picked == reference, "Viewport recognizes native finished-plus-pass-through picking result")
    check(calls[0][1]["location"] == (35, 46), "Viewport uses click coordinates")
    check(calls[0][0][1] is False, "Temporary native selection does not add undo step")
    check(set(bpy.context.selected_objects) == original_selected, "Picking restores multi-selection")
    check(bpy.context.view_layer.objects.active == original_active, "Picking restores active object")

    def failing_selection(*args, **kwargs):
        native_selection_stub(*args, **kwargs)
        raise RuntimeError("Selection cancelled")

    addon.bpy.ops.view3d.select = failing_selection
    try:
        addon.pick_object_in_area(bpy.context, area, region, (35, 46))
    except RuntimeError:
        pass
    check(set(bpy.context.selected_objects) == original_selected, "Backend failure restores selection")
    check(bpy.context.view_layer.objects.active == original_active, "Backend failure restores active object")
finally:
    addon.bpy = real_bpy

restore_calls = []
status_calls = []
reports = []
fake_region = SimpleNamespace(type='WINDOW', x=100, y=200, width=600, height=400)
fake_area = SimpleNamespace(type='VIEW_3D', regions=[fake_region], tag_redraw=lambda: None)
fake_window = SimpleNamespace(screen=SimpleNamespace(areas=[fake_area]), cursor_modal_restore=lambda: restore_calls.append(True))


def make_operator(kind='SUBJECT'):
    operator = SimpleNamespace(
        kind=kind, _camera=camera, _window=fake_window,
        _workspace=SimpleNamespace(status_text_set=lambda text: status_calls.append(text)),
        _finished=False, report=lambda level, text: reports.append(text),
    )
    operator.finish = lambda: addon.CSF_OT_PickObject.finish(operator)
    return operator


real_picker = addon.pick_object_in_area
try:
    received = []

    def pick_stub(context, picked_area, picked_region, location):
        received.append(location)
        return other

    addon.pick_object_in_area = pick_stub
    operator = make_operator()
    event = SimpleNamespace(type='LEFTMOUSE', value='PRESS', mouse_x=140, mouse_y=260)
    result = addon.CSF_OT_PickObject.modal(operator, bpy.context, event)
    check(result == {'FINISHED'}, "Click finishes modal picking")
    check(camera.camera_subject_follow.target == other, "Modal click assigns subject")
    check(received == [(40, 60)], "Modal converts window coordinates to region coordinates")
    check(len(restore_calls) == 1, "Successful pick restores eyedropper cursor")
    addon.CSF_OT_PickObject.cancel(operator, bpy.context)
    check(len(restore_calls) == 1, "Cleanup is idempotent")
    check(status_calls[-1] is None, "Successful pick clears status text")
    operator = make_operator()
    event.type = 'ESC'
    check(addon.CSF_OT_PickObject.modal(operator, bpy.context, event) == {'CANCELLED'}, "Escape cancels picking")
    check(camera.camera_subject_follow.target == other, "Cancellation preserves target")
    operator = make_operator()
    event.type = 'MIDDLEMOUSE'
    check(addon.CSF_OT_PickObject.modal(operator, bpy.context, event) == {'PASS_THROUGH'}, "Viewport navigation passes through")
    addon.pick_object_in_area = lambda *args: None
    event.type = 'LEFTMOUSE'
    check(addon.CSF_OT_PickObject.modal(operator, bpy.context, event) == {'RUNNING_MODAL'}, "Empty pick permits retry")
    check(camera.camera_subject_follow.target == other, "Empty pick does not clear target")
    operator.finish()
finally:
    addon.pick_object_in_area = real_picker

buttons = []


class LayoutProbe:
    def row(self, **kwargs):
        return self

    def separator(self):
        pass

    def prop(self, owner, name, **kwargs):
        pass

    def operator(self, identifier, **kwargs):
        properties = SimpleNamespace()
        buttons.append((identifier, kwargs, properties))
        return properties


addon.CSF_PT_SubjectFollow.draw(SimpleNamespace(layout=LayoutProbe()), bpy.context)
check(any(name == 'camera_subject_follow.pick_object' and props.kind == 'SUBJECT' and options.get('icon') == 'EYEDROPPER' for name, options, props in buttons), "Subject panel has dedicated modal eyedropper")
check(all(options.get('icon') != 'EYEDROPPER' for name, options, props in buttons if name == 'camera_subject_follow.use_selected'), "Selected-object shortcut no longer uses misleading eyedropper icon")
addon.unregister()
print("CSF_PICKER_VERIFICATION " + json.dumps({"count": len(checks), "selection_preserved": True, "modal_cancel": True}))
