# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Camera Subject Follow contributors

bl_info = {
    "name": "Camera Subject Follow - 相机主体跟随",
    "author": "Codex",
    "version": (1, 2, 1),
    "blender": (4, 2, 0),
    "location": "3D View > Sidebar > 相机跟随",
    "description": "主体吸管锁定、自动对焦、贝赛尔运镜预设与路径动画",
    "category": "Camera",
}

import math

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import Operator, Panel, PropertyGroup
from mathutils import Matrix, Vector


SHOT_PREVIEW_STATES = {}
SHOT_CAMERA_FIELDS = (
    "lens", "shift_x", "shift_y", "ortho_scale", "sensor_width", "sensor_height",
    "sensor_fit", "clip_start", "clip_end",
)


def target_is_valid(settings, target):
    camera = settings.id_data
    motion = getattr(camera, "camera_subject_motion", None)
    if motion and target == motion.rig:
        return False
    current = target
    while current is not None:
        if current == camera:
            return False
        current = current.parent
    return True


def managed_constraint(camera):
    name = camera.camera_subject_follow.constraint_name
    constraint = camera.constraints.get(name) if name else None
    return constraint if constraint and constraint.type == 'TRACK_TO' else None


def restore_focus(camera):
    settings = camera.camera_subject_follow
    if not settings.focus_managed:
        return
    dof = camera.data.dof
    if dof.focus_object == settings.last_focus_target:
        dof.focus_object = settings.previous_focus_object
        dof.use_dof = settings.previous_use_dof
    settings.focus_managed = False
    settings.previous_focus_object = None
    settings.last_focus_target = None


def sync_camera(settings, context):
    camera = settings.id_data
    if camera.type != 'CAMERA' or not camera.is_editable:
        return
    target = settings.target
    constraint = managed_constraint(camera)
    if target is None or not target_is_valid(settings, target):
        if constraint:
            camera.constraints.remove(constraint)
        settings.constraint_name = ""
        if camera.data.is_editable:
            restore_focus(camera)
        sync_shot_rotation_order(camera)
        return
    if settings.follow_rotation:
        if constraint is None:
            constraint = camera.constraints.new('TRACK_TO')
            constraint.name = "Subject Follow - 主体跟随"
            settings.constraint_name = constraint.name
        constraint.target = target
        constraint.track_axis = 'TRACK_NEGATIVE_Z'
        constraint.up_axis = 'UP_Y'
        constraint.use_target_z = False
        constraint.owner_space = 'WORLD'
        constraint.target_space = 'WORLD'
        constraint.influence = 1.0
        constraint.mute = False
        camera.constraints.move(list(camera.constraints).index(constraint), len(camera.constraints) - 1)
    elif constraint:
        constraint.mute = True
    if not camera.data.is_editable:
        return
    if settings.follow_focus:
        dof = camera.data.dof
        if not settings.focus_managed:
            settings.previous_focus_object = dof.focus_object
            settings.previous_use_dof = dof.use_dof
            settings.focus_managed = True
        dof.use_dof = True
        dof.focus_object = target
        settings.last_focus_target = target
    else:
        restore_focus(camera)
    sync_shot_rotation_order(camera)


class CSF_Settings(PropertyGroup):
    target: PointerProperty(
        name="跟随主体",
        description="用右侧吸管选取要持续拍摄的物体；跟随点为物体原点",
        type=bpy.types.Object,
        poll=target_is_valid,
        update=sync_camera,
        options=set(),
    )
    follow_rotation: BoolProperty(
        name="持续朝向主体",
        description="移动摄像机或主体时，自动转动摄像机，让主体原点保持在画面中心",
        default=True,
        update=sync_camera,
        options=set(),
    )
    follow_focus: BoolProperty(
        name="景深自动对焦",
        description="自动启用景深，并将焦点设为跟随主体；关闭时恢复原先的对焦设置",
        default=True,
        update=sync_camera,
        options=set(),
    )
    constraint_name: StringProperty(options={'HIDDEN'})
    focus_managed: BoolProperty(default=False, options={'HIDDEN'})
    previous_use_dof: BoolProperty(default=False, options={'HIDDEN'})
    previous_focus_object: PointerProperty(type=bpy.types.Object, options={'HIDDEN'})
    last_focus_target: PointerProperty(type=bpy.types.Object, options={'HIDDEN'})


def editable_scene_camera(context):
    camera = context.scene.camera
    return camera if camera and camera.is_editable else None


PICK_TYPES = (
    ('SUBJECT', "跟随主体", "拾取要拍摄的主体物体"),
    ('PATH', "路径曲线", "拾取摄像机要绑定的曲线"),
    ('START_CAMERA', "起始参考相机", "拾取起始画面的参考相机"),
    ('END_CAMERA', "结束参考相机", "拾取结束画面的参考相机"),
)


def assign_picked_object(camera, kind, obj):
    if obj is None:
        raise ValueError("没有拾取到物体，请点击 3D 视图中的物体或大纲中的物体行")
    if kind == 'SUBJECT':
        if not target_is_valid(camera.camera_subject_follow, obj):
            raise ValueError("不能选择当前摄像机、相机的子物体或运镜控制器")
        camera.camera_subject_follow.target = obj
    elif kind == 'PATH':
        if not curve_is_valid(camera.camera_subject_motion, obj):
            raise ValueError("请选择曲线，且曲线不能依赖当前摄像机或运镜控制器")
        camera.camera_subject_motion.path = obj
    else:
        if obj.type != 'CAMERA':
            raise ValueError("请选择摄像机物体")
        slot = camera.camera_subject_shots.start if kind == 'START_CAMERA' else camera.camera_subject_shots.end
        slot.source_camera = obj


def pick_object_in_area(context, area, region, location):
    selected = tuple(context.selected_objects)
    active = context.view_layer.objects.active
    try:
        with context.temp_override(area=area, region=region):
            if area.type == 'VIEW_3D':
                result = bpy.ops.view3d.select(
                    'EXEC_DEFAULT', False, location=location, extend=False,
                    deselect_all=True, select_passthrough=False, enumerate=False, object=True,
                )
                candidate = context.view_layer.objects.active
                return candidate if 'FINISHED' in result and candidate and candidate.select_get() else None
            if area.type == 'OUTLINER':
                bpy.ops.outliner.item_activate('INVOKE_DEFAULT', False, extend=False, deselect_all=True)
                return next((item for item in context.selected_ids if isinstance(item, bpy.types.Object)), None)
            return None
    finally:
        for obj in context.selected_objects:
            obj.select_set(False)
        for obj in selected:
            if obj.name in context.view_layer.objects:
                obj.select_set(True)
        context.view_layer.objects.active = active


class CSF_OT_PickObject(Operator):
    bl_idname = "camera_subject_follow.pick_object"
    bl_label = "吸管拾取"
    bl_description = "进入吸管模式，点击 3D 视图中的物体或大纲中的物体行；右键或 Esc 取消"
    bl_options = {'UNDO', 'BLOCKING'}
    kind: EnumProperty(name="拾取类型", items=PICK_TYPES, default='SUBJECT')

    @classmethod
    def description(cls, context, properties):
        label = next(item[1] for item in PICK_TYPES if item[0] == properties.kind)
        return "吸管拾取" + label + "：点击 3D 视图中的物体或大纲中的物体行；右键或 Esc 取消"

    @classmethod
    def poll(cls, context):
        return editable_scene_camera(context) is not None and context.mode == 'OBJECT' and context.window is not None

    def invoke(self, context, event):
        self._camera = context.scene.camera
        self._window = context.window
        self._workspace = context.workspace
        self._finished = False
        self._window.cursor_modal_set('EYEDROPPER')
        label = next(item[1] for item in PICK_TYPES if item[0] == self.kind)
        self._workspace.status_text_set("吸管：" + label)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def finish(self):
        if getattr(self, "_finished", False):
            return
        self._finished = True
        self._window.cursor_modal_restore()
        self._workspace.status_text_set(None)
        for area in self._window.screen.areas:
            area.tag_redraw()

    def cancel(self, context):
        self.finish()

    def modal(self, context, event):
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            self.finish()
            return {'CANCELLED'}
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            for area in self._window.screen.areas:
                if area.type not in {'VIEW_3D', 'OUTLINER'}:
                    continue
                region = next((item for item in area.regions if item.type == 'WINDOW'
                               and item.x <= event.mouse_x < item.x + item.width
                               and item.y <= event.mouse_y < item.y + item.height), None)
                if region is None:
                    continue
                try:
                    if not self._camera.is_editable:
                        raise ValueError("当前摄像机不可编辑")
                    obj = pick_object_in_area(context, area, region,
                                              (event.mouse_x - region.x, event.mouse_y - region.y))
                    assign_picked_object(self._camera, self.kind, obj)
                except (ValueError, RuntimeError) as error:
                    self.report({'WARNING'}, str(error))
                    return {'RUNNING_MODAL'}
                except ReferenceError:
                    self.finish()
                    return {'CANCELLED'}
                self.finish()
                self.report({'INFO'}, "已拾取：" + obj.name)
                return {'FINISHED'}
            return {'RUNNING_MODAL'}
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM', 'NDOF_MOTION'}:
            return {'PASS_THROUGH'}
        return {'RUNNING_MODAL'}


class CSF_OT_UseSelected(Operator):
    bl_idname = "camera_subject_follow.use_selected"
    bl_label = "使用选中物体"
    bl_description = "将当前选中的物体设为摄像机跟随主体"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return editable_scene_camera(context) is not None

    def execute(self, context):
        camera = context.scene.camera
        active = context.view_layer.objects.active
        candidates = [
            obj for obj in context.selected_objects
            if obj != camera and target_is_valid(camera.camera_subject_follow, obj)
        ]
        target = active if active in candidates else (
            candidates[0] if len(candidates) == 1 else None
        )
        if target is None:
            self.report({'WARNING'}, "请先选中一个主体物体，且不能是摄像机的子物体")
            return {'CANCELLED'}
        camera.camera_subject_follow.target = target
        self.report({'INFO'}, "已锁定主体：" + target.name)
        return {'FINISHED'}


class CSF_OT_Clear(Operator):
    bl_idname = "camera_subject_follow.clear"
    bl_label = "解除主体锁定"
    bl_description = "移除本插件的跟随约束，恢复之前的景深对焦设置"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return editable_scene_camera(context) is not None

    def execute(self, context):
        context.scene.camera.camera_subject_follow.target = None
        return {'FINISHED'}


class CSF_OT_CameraView(Operator):
    bl_idname = "camera_subject_follow.camera_view"
    bl_label = "相机视图"
    bl_description = "切换到当前场景摄像机视图"

    @classmethod
    def poll(cls, context):
        return (
            context.scene.camera is not None
            and context.area is not None
            and context.area.type == 'VIEW_3D'
        )

    def execute(self, context):
        space = context.space_data
        previous = SHOT_PREVIEW_STATES.pop(context.area.as_pointer(), None)
        if previous:
            space.use_local_camera = previous[0]
            space.lock_camera = previous[1]
            context.scene.frame_set(previous[2])
        space.camera = context.scene.camera
        if space.region_3d.view_perspective != 'CAMERA':
            region = next(
                (region for region in context.area.regions if region.type == 'WINDOW'),
                None,
            )
            if region is not None:
                with context.temp_override(region=region):
                    bpy.ops.view3d.view_camera()
        return {'FINISHED'}


class CSF_OT_AddCamera(Operator):
    bl_idname = "camera_subject_follow.add_camera"
    bl_label = "从当前视角新建摄像机"
    bl_description = "新建摄像机并设为场景摄像机，使用当前 3D 视角"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        data = bpy.data.cameras.new("运镜摄像机")
        camera = bpy.data.objects.new("运镜摄像机", data)
        context.scene.collection.objects.link(camera)
        if context.space_data and context.space_data.type == 'VIEW_3D':
            camera.matrix_world = context.space_data.region_3d.view_matrix.inverted()
            data.lens = context.space_data.lens
        elif context.scene.camera:
            camera.matrix_world = context.scene.camera.matrix_world.copy()
        else:
            camera.location = (7, -7, 5)
            camera.rotation_euler = (-camera.location).to_track_quat('-Z', 'Y').to_euler()
        context.scene.camera = camera
        return {'FINISHED'}


PRESETS = (
    ('ORBIT', "圆形环绕", "围绕主体完整环绕一周"),
    ('ELLIPSE', "椭圆环绕", "沿椭圆路径改变与主体的距离"),
    ('ARC90', "90° 弧线", "四分之一圆弧运镜"),
    ('ARC180', "180° 半环绕", "半圆弧运镜"),
    ('DOLLY_IN', "推进", "沿直线接近主体"),
    ('DOLLY_OUT', "拉远", "沿直线远离主体"),
    ('TRUCK', "左右横移", "从主体前方横向平移"),
    ('CRANE', "垂直升降", "在固定距离垂直升高或降低"),
    ('S_CURVE', "S 形穿行", "带横向摆动的前后运动"),
    ('HELIX', "螺旋升降", "绕主体旋转，同时逐渐改变高度"),
    ('SPIRAL_IN', "螺旋收拢", "逐渐收小半径的螺旋路径"),
    ('FIGURE8', "8 字环绕", "围绕中心的闭合 8 字路径"),
    ('WAVE', "波浪穿行", "横向与垂直方向同时起伏的路径"),
    ('FLYOVER', "拱形飞越", "从一侧经过主体，同时升高再降低"),
)


def curve_is_valid(settings, obj):
    if obj.type != 'CURVE':
        return False
    current = obj
    while current is not None:
        if current == settings.id_data or current == settings.rig:
            return False
        current = current.parent
    return True


def motion_constraint(camera):
    name = camera.camera_subject_motion.constraint_name
    constraint = camera.constraints.get(name) if name else None
    return constraint if constraint and constraint.type == 'COPY_LOCATION' else None


def path_follower(camera):
    rig = camera.camera_subject_motion.rig
    if rig is None or rig.camera_subject_motion.owner_camera != camera:
        return None
    return next((item for item in rig.constraints if item.type == 'FOLLOW_PATH'), None)


def sync_motion_enabled(settings, context):
    camera = settings.id_data
    if camera.type == 'CAMERA' and camera.is_editable:
        constraint = motion_constraint(camera)
        if constraint:
            constraint.mute = not settings.enabled
        sync_shot_enabled(camera, context)


class CSF_MotionSettings(PropertyGroup):
    preset: EnumProperty(name="路径样式", items=PRESETS, default='ORBIT', options=set())
    radius: FloatProperty(name="半径 / 距离", default=5, min=0.01, subtype='DISTANCE', options=set())
    height: FloatProperty(name="基础高度", default=2, subtype='DISTANCE', options=set())
    length: FloatProperty(name="行程长度", default=10, min=0.01, subtype='DISTANCE', options=set())
    rise: FloatProperty(name="升降幅度", default=4, subtype='DISTANCE', options=set())
    turns: FloatProperty(name="旋转圈数", default=1.5, min=0.1, max=20, options=set())
    points: IntProperty(name="控制点数", default=16, min=4, max=256, options=set())
    angle: FloatProperty(name="起始角度", default=0, subtype='ANGLE', options=set())
    center_mode: EnumProperty(
        name="路径中心",
        items=(
            ('SUBJECT', "跟随主体", "以主体原点为中心；没有主体时使用 3D 游标"),
            ('CURSOR', "3D 游标", "以 3D 游标所在位置为中心"),
            ('WORLD', "世界原点", "以世界坐标原点为中心"),
        ),
        default='SUBJECT', options=set(),
    )
    moving_center: BoolProperty(
        name="路径随主体平移",
        description="创建或重建预设时，让整条路径随当前主体的位置移动；保留世界朝向",
        default=False, options=set(),
    )
    path: PointerProperty(
        name="路径曲线", description="可用吸管选择已有曲线，再点击绑定摄像机",
        type=bpy.types.Object, poll=curve_is_valid, options=set(),
    )
    rig: PointerProperty(type=bpy.types.Object, options={'HIDDEN'})
    owner_camera: PointerProperty(type=bpy.types.Object, options={'HIDDEN'})
    constraint_name: StringProperty(options={'HIDDEN'})
    enabled: BoolProperty(
        name="启用路径运动", description="关闭时显示摄像机原有的位置与动画",
        default=True, update=sync_motion_enabled, options=set(),
    )
    auto_animate: BoolProperty(name="创建时生成动画", default=True, options=set())
    start_frame: IntProperty(name="起始帧", default=1, min=-1048574, max=1048574, options=set())
    end_frame: IntProperty(name="结束帧", default=120, min=-1048574, max=1048574, options=set())
    start_progress: FloatProperty(name="起始进度", default=0, min=0, max=1, subtype='FACTOR', options=set())
    end_progress: FloatProperty(name="结束进度", default=1, min=0, max=1, subtype='FACTOR', options=set())
    reverse: BoolProperty(name="反向运动", description="在下一次生成动画时反向经过路径", options=set())
    interpolation: EnumProperty(
        name="速度变化",
        items=(('LINEAR', "匀速", "沿路径匀速运动"),
               ('EASE', "柔和启停", "起点与终点速度为零，平滑加速减速"),
               ('SINE', "正弦缓动", "正弦加速减速")),
        default='EASE', options=set(),
    )
    loop: EnumProperty(
        name="循环",
        items=(('NONE', "单次", "在首尾帧外保持端点位置"),
               ('REPEAT', "重复", "重复运动；闭合路径适合无缝循环"),
               ('MIRROR', "往返", "在路径两端来回运动")),
        default='NONE', options=set(),
    )
    fit_timeline: BoolProperty(
        name="同步场景帧范围", description="生成动画时，将场景起止帧改为上述帧段",
        default=False, options=set(),
    )
    fixed_constraint: StringProperty(options={'HIDDEN'})
    fixed_anchor: PointerProperty(type=bpy.types.Object, options={'HIDDEN'})


def path_collection(scene):
    collection = scene.collection.children.get("相机运镜路径")
    if collection is None:
        collection = bpy.data.collections.new("相机运镜路径")
        scene.collection.children.link(collection)
    return collection


def preset_points(settings):
    cyclic = settings.preset in {'ORBIT', 'ELLIPSE', 'FIGURE8'}
    points = []
    radius, length, height, rise = settings.radius, settings.length, settings.height, settings.rise
    for index in range(settings.points):
        progress = index / (settings.points if cyclic else settings.points - 1)
        angle = math.tau * progress
        preset = settings.preset
        if preset in {'ORBIT', 'ELLIPSE', 'ARC90', 'ARC180'}:
            if preset == 'ARC90':
                angle *= 0.25
            elif preset == 'ARC180':
                angle *= 0.5
            point = (radius * math.cos(angle), radius * math.sin(angle) * (0.55 if preset == 'ELLIPSE' else 1), height)
        elif preset == 'DOLLY_IN':
            point = (radius + length * (1 - progress), 0, height)
        elif preset == 'DOLLY_OUT':
            point = (radius + length * progress, 0, height)
        elif preset == 'TRUCK':
            point = (radius, length * (progress - 0.5), height)
        elif preset == 'CRANE':
            point = (radius, 0, height + rise * progress)
        elif preset == 'S_CURVE':
            point = (radius + length * (1 - progress), radius * 0.6 * math.sin(angle), height)
        elif preset in {'HELIX', 'SPIRAL_IN'}:
            orbit_radius = radius * (1 - 0.75 * progress) if preset == 'SPIRAL_IN' else radius
            point = (orbit_radius * math.cos(angle * settings.turns),
                     orbit_radius * math.sin(angle * settings.turns), height + rise * progress)
        elif preset == 'FIGURE8':
            point = (radius * math.cos(angle), radius * 0.6 * math.sin(2 * angle), height)
        elif preset == 'WAVE':
            point = (radius + length * (1 - progress), radius * 0.35 * math.sin(2 * angle),
                     height + rise * 0.3 * math.sin(angle))
        else:
            point = (length * (progress - 0.5), radius, height + rise * math.sin(math.pi * progress))
        points.append(point)
    return points, cyclic


def fill_curve(curve, settings):
    points, cyclic = preset_points(settings)
    curve.data.dimensions = '3D'
    curve.data.resolution_u = 24
    curve.data.use_path = True
    curve.data.splines.clear()
    spline = curve.data.splines.new('BEZIER')
    spline.bezier_points.add(len(points) - 1)
    for point, coordinates in zip(spline.bezier_points, points):
        point.co = coordinates
        point.handle_left_type = 'AUTO'
        point.handle_right_type = 'AUTO'
    spline.use_cyclic_u = cyclic
    curve["csf_preset"] = settings.preset


def configure_path_center(curve, camera):
    settings = camera.camera_subject_motion
    subject = camera.camera_subject_follow.target
    name = curve.get("csf_center_constraint", "")
    constraint = curve.constraints.get(name) if name else None
    if not settings.moving_center or subject is None or settings.center_mode != 'SUBJECT':
        if constraint and constraint.type == 'COPY_LOCATION':
            matrix = curve.matrix_world.copy()
            curve.constraints.remove(constraint)
            curve.matrix_world = matrix
        return
    current = subject
    while current:
        if current == curve:
            raise ValueError("路径不能跟随自身或自己的子物体")
        current = current.parent
    if constraint is None:
        constraint = curve.constraints.new('COPY_LOCATION')
        constraint.name = "Subject Follow - 路径中心"
        curve["csf_center_constraint"] = constraint.name
    constraint.target = subject
    constraint.owner_space = 'WORLD'
    constraint.target_space = 'WORLD'
    constraint.use_offset = False


def make_path(context, camera):
    settings = camera.camera_subject_motion
    target = camera.camera_subject_follow.target
    if settings.center_mode == 'SUBJECT' and target:
        center = target.matrix_world.translation.copy()
    elif settings.center_mode == 'WORLD':
        center = Vector((0, 0, 0))
    else:
        center = context.scene.cursor.location.copy()
    label = next(item[1] for item in PRESETS if item[0] == settings.preset)
    data = bpy.data.curves.new("运镜 - " + label, 'CURVE')
    curve = bpy.data.objects.new("运镜 - " + label, data)
    path_collection(context.scene).objects.link(curve)
    curve.location = center
    direction = camera.matrix_world.translation - center
    heading = math.atan2(direction.y, direction.x) if direction.xy.length > 1e-6 else 0
    curve.rotation_euler.z = heading + settings.angle
    curve.show_in_front = True
    curve.hide_render = True
    curve.color = (0.12, 0.7, 0.42, 1)
    fill_curve(curve, settings)
    configure_path_center(curve, camera)
    settings.path = curve
    return curve, center


def ensure_motion_rig(context, camera):
    settings = camera.camera_subject_motion
    if settings.rig and settings.rig.camera_subject_motion.owner_camera == camera:
        return settings.rig
    rig = bpy.data.objects.new("运镜控制 - " + camera.name, None)
    path_collection(context.scene).objects.link(rig)
    rig.empty_display_type = 'PLAIN_AXES'
    rig.empty_display_size = 0.35
    rig.hide_render = True
    rig.camera_subject_motion.owner_camera = camera
    settings.rig = rig
    return rig


def bind_camera(context, camera):
    settings = camera.camera_subject_motion
    curve = settings.path
    if curve is None or not curve_is_valid(settings, curve) or not curve.data.splines:
        raise ValueError("请先选择一条有控制点的路径曲线")
    spline = curve.data.splines[0]
    if len(spline.bezier_points if spline.type == 'BEZIER' else spline.points) < 2:
        raise ValueError("路径至少需要两个控制点")
    stationary = spline.calc_length() < 1e-6
    if stationary and not curve.get("csf_shot_path"):
        raise ValueError("这条曲线没有有效长度，请移动一个控制点后再绑定")
    if curve.name not in context.scene.objects:
        raise ValueError("路径曲线必须位于当前场景")
    if not curve.data.use_path:
        if not curve.data.is_editable:
            raise ValueError("该曲线为只读数据，且没有开启路径动画")
        curve.data.use_path = True
    rig = ensure_motion_rig(context, camera)
    follow = path_follower(camera)
    if follow is None:
        follow = rig.constraints.new('FOLLOW_PATH')
        follow.name = "Subject Follow - 路径进度"
    follow.target = curve
    follow.use_fixed_location = True
    follow.use_curve_follow = False
    follow.mute = stationary
    fixed = rig.constraints.get(settings.fixed_constraint) if settings.fixed_constraint else None
    if stationary:
        anchor = settings.fixed_anchor
        if anchor is None or anchor.camera_subject_shots.owner_camera != camera:
            anchor = bpy.data.objects.new("定点取景 - " + camera.name, None)
            path_collection(context.scene).objects.link(anchor)
            anchor.empty_display_size = 0.15
            anchor.hide_render = True
            anchor.camera_subject_shots.owner_camera = camera
            settings.fixed_anchor = anchor
        anchor.parent = None
        anchor.rotation_euler = (0, 0, 0)
        anchor.scale = (1, 1, 1)
        anchor.location = spline.bezier_points[0].co if spline.type == 'BEZIER' else spline.points[0].co.to_3d()
        parent_constraint = next((item for item in anchor.constraints if item.type == 'CHILD_OF'), None)
        if parent_constraint is None:
            parent_constraint = anchor.constraints.new('CHILD_OF')
        parent_constraint.target = curve
        parent_constraint.inverse_matrix = Matrix.Identity(4)
        if fixed is None:
            fixed = rig.constraints.new('COPY_LOCATION')
            fixed.name = "Subject Follow - 固定位置"
            settings.fixed_constraint = fixed.name
        fixed.target = anchor
        fixed.owner_space = 'WORLD'
        fixed.target_space = 'WORLD'
        fixed.use_offset = False
    elif fixed and fixed.type == 'COPY_LOCATION':
        rig.constraints.remove(fixed)
        settings.fixed_constraint = ""
    constraint = motion_constraint(camera)
    if constraint is None:
        constraint = camera.constraints.new('COPY_LOCATION')
        constraint.name = "Subject Follow - 路径位置"
        settings.constraint_name = constraint.name
    constraint.target = rig
    constraint.owner_space = 'WORLD'
    constraint.target_space = 'WORLD'
    constraint.use_offset = False
    constraint.influence = 1
    constraint.use_x = constraint.use_y = constraint.use_z = True
    camera.constraints.move(list(camera.constraints).index(constraint), len(camera.constraints) - 1)
    settings.enabled = True
    constraint.mute = False
    sync_camera(camera.camera_subject_follow, context)
    apply_shot_framing(context, camera)
    return follow


def fcurve_collections(owner):
    animation = owner.animation_data
    action = animation.action if animation else None
    if action is None:
        return []
    if hasattr(action, "fcurves"):
        return [action.fcurves]
    collections = []
    slot = animation.action_slot
    for layer in action.layers:
        for strip in layer.strips:
            if strip.type == 'KEYFRAME':
                bag = strip.channelbag(slot) if slot else None
                if bag:
                    collections.append(bag.fcurves)
    return collections


def clear_animation_paths(owner, paths):
    if owner.animation_data and owner.animation_data.action and owner.animation_data.action.users > 1:
        owner.animation_data.action = owner.animation_data.action.copy()
    for collection in fcurve_collections(owner):
        for curve in list(collection):
            if curve.data_path in paths:
                collection.remove(curve)


def configure_motion_curves(owner, paths, settings):
    for collection in fcurve_collections(owner):
        for curve in collection:
            if curve.data_path not in paths:
                continue
            curve.extrapolation = 'CONSTANT'
            for point in curve.keyframe_points:
                point.interpolation = (
                    'CONSTANT' if curve.data_path == "sensor_fit"
                    else {'LINEAR': 'LINEAR', 'EASE': 'BEZIER', 'SINE': 'SINE'}[settings.interpolation]
                )
                point.easing = 'EASE_IN_OUT'
                if settings.interpolation == 'EASE':
                    point.handle_left_type = point.handle_right_type = 'FREE'
                    handle_width = (settings.end_frame - settings.start_frame) / 3
                    point.handle_left = (point.co.x - handle_width, point.co.y)
                    point.handle_right = (point.co.x + handle_width, point.co.y)
            if settings.loop != 'NONE':
                modifier = curve.modifiers.new('CYCLES')
                modifier.mode_before = modifier.mode_after = settings.loop


def clear_progress_animation(camera):
    follow = path_follower(camera)
    if follow:
        clear_animation_paths(camera.camera_subject_motion.rig, {follow.path_from_id("offset_factor")})


def animate_path(context, camera):
    settings = camera.camera_subject_motion
    follow = path_follower(camera)
    if follow is None or motion_constraint(camera) is None:
        raise ValueError("请先绑定摄像机与路径")
    if settings.end_frame <= settings.start_frame:
        raise ValueError("结束帧必须大于起始帧")
    rig = settings.rig
    clear_progress_animation(camera)
    data_path = follow.path_from_id("offset_factor")
    values = (settings.start_progress, settings.end_progress)
    if settings.reverse:
        values = values[::-1]
    for frame, value in zip((settings.start_frame, settings.end_frame), values):
        follow.offset_factor = value
        follow.keyframe_insert(data_path="offset_factor", frame=frame, group="相机路径进度")
    configure_motion_curves(rig, {data_path}, settings)
    apply_shot_framing(context, camera)
    if settings.fit_timeline:
        context.scene.frame_start = settings.start_frame
        context.scene.frame_end = settings.end_frame
    context.scene.frame_set(settings.start_frame)


def camera_reference_poll(settings, obj):
    return obj.type == 'CAMERA'


class CSF_ShotSlot(PropertyGroup):
    source_camera: PointerProperty(name="参考相机", type=bpy.types.Object, poll=camera_reference_poll, options=set())
    snapshot: PointerProperty(type=bpy.types.Object, options={'HIDDEN'})
    path: PointerProperty(type=bpy.types.Object, options={'HIDDEN'})
    progress: FloatProperty(min=0, max=1, options={'HIDDEN'})
    frame: IntProperty(options={'HIDDEN'})


def update_shot_mode(settings, context):
    camera = settings.id_data
    if camera.type == 'CAMERA' and camera.is_editable:
        apply_shot_framing(context, camera)
        context.scene.frame_set(context.scene.frame_current)


class CSF_ShotSettings(PropertyGroup):
    start: PointerProperty(type=CSF_ShotSlot)
    end: PointerProperty(type=CSF_ShotSlot)
    source: EnumProperty(
        name="画面来源",
        items=(('VIEW', "当前视角", "记录当前 3D 视角；相机视图中记录该相机的构图"),
               ('CAMERA', "当前摄像机", "记录场景摄像机在当前帧的画面"),
               ('REFERENCE', "指定相机", "分别使用吸管选择起始和结束的参考相机")),
        default='VIEW', options=set(),
    )
    framing: EnumProperty(
        name="构图方式",
        items=(('MATCH', "匹配首尾构图", "过渡记录的相机方向、焦距、偏移及正交比例；对焦仍可跟随主体"),
               ('SUBJECT', "持续看向主体", "沿路径运动，同时持续朝向跟随主体，不接管原有焦距")),
        default='MATCH', update=update_shot_mode, options=set(),
    )
    shape: EnumProperty(
        name="连接样式",
        items=(('STRAIGHT', "直线连接", "在两个画面位置之间直线移动"),
               ('ARC', "弧线连接", "在首尾位置之间向侧面弯曲"),
               ('S_CURVE', "S 形连接", "在首尾位置之间左右摆动")),
        default='ARC', options=set(),
    )
    bend: FloatProperty(name="侧向弯曲", default=2, subtype='DISTANCE', options=set())
    lift: FloatProperty(name="中段抬升", default=0, subtype='DISTANCE', options=set())
    points: IntProperty(name="连接控制点", default=6, min=2, max=128, options=set())
    bound_path: PointerProperty(type=bpy.types.Object, options={'HIDDEN'})
    rotation_constraint: StringProperty(options={'HIDDEN'})
    original_data: PointerProperty(type=bpy.types.Camera, options={'HIDDEN'})
    managed_data: PointerProperty(type=bpy.types.Camera, options={'HIDDEN'})
    orientation_rig: PointerProperty(type=bpy.types.Object, options={'HIDDEN'})
    owner_camera: PointerProperty(type=bpy.types.Object, options={'HIDDEN'})
    snapshot_kind: StringProperty(options={'HIDDEN'})


def shot_rotation_constraint(camera):
    shots = camera.camera_subject_shots
    constraint = camera.constraints.get(shots.rotation_constraint) if shots.rotation_constraint else None
    return constraint if constraint and constraint.type == 'COPY_ROTATION' else None


def shot_path_active(camera):
    shots = camera.camera_subject_shots
    follow = path_follower(camera)
    return bool(follow and motion_constraint(camera) and shots.bound_path and follow.target == shots.bound_path)


def sync_shot_rotation_order(camera):
    constraint = shot_rotation_constraint(camera)
    if constraint:
        camera.constraints.move(list(camera.constraints).index(constraint), len(camera.constraints) - 1)


def restore_shot_data(camera):
    shots = camera.camera_subject_shots
    if shots.managed_data and shots.original_data and camera.data == shots.managed_data:
        restore_focus(camera)
        camera.data = shots.original_data


def sync_shot_enabled(camera, context):
    shots = camera.camera_subject_shots
    constraint = shot_rotation_constraint(camera)
    enabled = camera.camera_subject_motion.enabled and shot_path_active(camera) and shots.framing == 'MATCH'
    if constraint:
        constraint.mute = not enabled
    if enabled and shots.managed_data and camera.data == shots.original_data:
        restore_focus(camera)
        camera.data = shots.managed_data
    elif not enabled:
        restore_shot_data(camera)
    sync_camera(camera.camera_subject_follow, context)


def validated_shots(camera):
    shots = camera.camera_subject_shots
    if shots.start.snapshot is None or shots.end.snapshot is None:
        raise ValueError("请先记录起始画面和结束画面")
    start, end = shots.start.snapshot, shots.end.snapshot
    if start.type != 'CAMERA' or end.type != 'CAMERA':
        raise ValueError("记录的画面参考相机已失效，请重新记录")
    if start.data.type != end.data.type or start.data.type not in {'PERSP', 'ORTHO'}:
        raise ValueError("首尾画面需使用相同的透视或正交投影类型")
    return start, end


def ensure_shot_data(camera):
    shots = camera.camera_subject_shots
    if camera.data == shots.managed_data:
        return camera.data
    restore_focus(camera)
    if camera.data != shots.original_data or shots.managed_data is None:
        shots.original_data = camera.data
        shots.managed_data = camera.data.copy()
        shots.managed_data.name = "首尾构图 - " + camera.name
        shots.managed_data.animation_data_clear()
    camera.data = shots.managed_data
    return camera.data


def ensure_shot_orientation(context, camera):
    shots = camera.camera_subject_shots
    rig = shots.orientation_rig
    if rig is None or rig.camera_subject_shots.owner_camera != camera:
        rig = bpy.data.objects.new("构图方向 - " + camera.name, None)
        path_collection(context.scene).objects.link(rig)
        rig.empty_display_size = 0.2
        rig.hide_render = True
        rig.camera_subject_shots.owner_camera = camera
        rig.camera_subject_shots.snapshot_kind = 'ORIENTATION'
        shots.orientation_rig = rig
    return rig


def apply_shot_framing(context, camera):
    shots = camera.camera_subject_shots
    constraint = shot_rotation_constraint(camera)
    if not shot_path_active(camera) or shots.framing != 'MATCH':
        if constraint:
            camera.constraints.remove(constraint)
            shots.rotation_constraint = ""
        restore_shot_data(camera)
        sync_camera(camera.camera_subject_follow, context)
        return
    start, end = validated_shots(camera)
    settings = camera.camera_subject_motion
    if settings.end_frame <= settings.start_frame:
        raise ValueError("结束帧必须大于起始帧")
    ordered = (end, start) if settings.reverse else (start, end)
    rig = ensure_shot_orientation(context, camera)
    rotations = [obj.matrix_world.to_quaternion() for obj in ordered]
    if rotations[0].dot(rotations[1]) < 0:
        rotations[1].negate()
    clear_animation_paths(rig, {"rotation_quaternion"})
    rig.rotation_mode = 'QUATERNION'
    for frame, rotation in zip((settings.start_frame, settings.end_frame), rotations):
        rig.rotation_quaternion = rotation
        rig.keyframe_insert(data_path="rotation_quaternion", frame=frame, group="首尾画面方向")
    configure_motion_curves(rig, {"rotation_quaternion"}, settings)
    data = ensure_shot_data(camera)
    data.type = start.data.type
    clear_animation_paths(data, set(SHOT_CAMERA_FIELDS))
    for frame, reference in zip((settings.start_frame, settings.end_frame), ordered):
        for name in SHOT_CAMERA_FIELDS:
            setattr(data, name, getattr(reference.data, name))
            data.keyframe_insert(data_path=name, frame=frame, group="首尾画面构图")
    configure_motion_curves(data, set(SHOT_CAMERA_FIELDS), settings)
    if constraint is None:
        constraint = camera.constraints.new('COPY_ROTATION')
        constraint.name = "Subject Follow - 首尾画面方向"
        shots.rotation_constraint = constraint.name
    constraint.target = rig
    constraint.owner_space = 'WORLD'
    constraint.target_space = 'WORLD'
    constraint.mix_mode = 'REPLACE'
    constraint.use_offset = False
    constraint.influence = 1
    constraint.mute = not settings.enabled
    if not settings.enabled:
        restore_shot_data(camera)
    sync_camera(camera.camera_subject_follow, context)


def capture_shot(context, camera, side):
    shots = camera.camera_subject_shots
    slot = shots.start if side == 'START' else shots.end
    source = None
    space = context.space_data
    if shots.source == 'REFERENCE':
        source = slot.source_camera
        if source is None or source.type != 'CAMERA':
            raise ValueError("请先用吸管指定该画面的参考相机")
    elif shots.source == 'CAMERA':
        source = camera
    elif space is None or space.type != 'VIEW_3D':
        raise ValueError("请在 3D 视图中记录当前视角，或改用当前摄像机作为来源")
    elif space.region_3d.view_perspective == 'CAMERA':
        source = space.camera if space.use_local_camera else context.scene.camera
    if source:
        evaluated = source.evaluated_get(context.evaluated_depsgraph_get())
        matrix = evaluated.matrix_world.copy()
        data = evaluated.data.copy()
        data.animation_data_clear()
    else:
        matrix = space.region_3d.view_matrix.inverted()
        data = camera.data.copy()
        data.animation_data_clear()
        projection = space.region_3d.window_matrix
        data.shift_x = data.shift_y = 0
        if space.region_3d.view_perspective == 'ORTHO':
            data.type = 'ORTHO'
            data.sensor_fit = 'AUTO'
            data.ortho_scale = max(2 / abs(projection[0][0]), 2 / abs(projection[1][1]))
        else:
            data.type = 'PERSP'
            data.sensor_fit = 'VERTICAL'
            data.lens = abs(projection[1][1]) * data.sensor_height / 2
    data.name = ("起始画面镜头" if side == 'START' else "结束画面镜头")
    snapshot = slot.snapshot
    if snapshot is None or snapshot.camera_subject_shots.owner_camera != camera or snapshot.camera_subject_shots.snapshot_kind != side:
        snapshot = bpy.data.objects.new("起始画面" if side == 'START' else "结束画面", data)
        path_collection(context.scene).objects.link(snapshot)
    else:
        old_data = snapshot.data
        snapshot.data = data
        if old_data.users == 0:
            bpy.data.cameras.remove(old_data)
    snapshot.matrix_world = matrix
    snapshot.hide_render = True
    snapshot.data.display_size = 0.4
    snapshot.camera_subject_shots.owner_camera = camera
    snapshot.camera_subject_shots.snapshot_kind = side
    slot.snapshot = snapshot
    slot.frame = context.scene.frame_current
    follow = path_follower(camera)
    binding = motion_constraint(camera)
    on_path = source == camera and follow and binding and not binding.mute
    slot.path = follow.target if on_path else None
    slot.progress = follow.offset_factor if on_path else 0
    return snapshot


def create_shot_path(context, camera):
    start, end = validated_shots(camera)
    settings = camera.camera_subject_motion
    shots = camera.camera_subject_shots
    if settings.end_frame <= settings.start_frame:
        raise ValueError("结束帧必须大于起始帧")
    start_position = start.matrix_world.translation
    end_position = end.matrix_world.translation
    delta = end_position - start_position
    side = Vector((-delta.y, delta.x, 0))
    side = side.normalized() if side.length > 1e-6 else Vector((1, 0, 0))
    data = bpy.data.curves.new("首尾画面连接", 'CURVE')
    data.dimensions = '3D'
    data.resolution_u = 32
    data.use_path = True
    path = bpy.data.objects.new("运镜 - 首尾画面连接", data)
    path_collection(context.scene).objects.link(path)
    path.location = start_position
    path.show_in_front = True
    path.hide_render = True
    path["csf_shot_path"] = True
    spline = data.splines.new('BEZIER')
    spline.bezier_points.add(shots.points - 1)
    for index, point in enumerate(spline.bezier_points):
        progress = index / (shots.points - 1)
        offset = 0 if shots.shape == 'STRAIGHT' else shots.bend * math.sin((math.tau if shots.shape == 'S_CURVE' else math.pi) * progress)
        point.co = delta * progress + side * offset + Vector((0, 0, shots.lift * math.sin(math.pi * progress)))
        point.handle_left_type = point.handle_right_type = 'AUTO'
    settings.path = path
    settings.start_progress, settings.end_progress = 0, 1
    shots.bound_path = path
    bind_camera(context, camera)
    animate_path(context, camera)
    return path


class CSF_OT_CaptureShot(Operator):
    bl_idname = "camera_subject_follow.capture_shot"
    bl_label = "记录画面"
    bl_description = "记录当前构图的位置、方向和镜头参数；作为可独立预览的参考相机保存"
    bl_options = {'REGISTER', 'UNDO'}
    side: EnumProperty(items=(('START', "起始", ""), ('END', "结束", "")))

    @classmethod
    def poll(cls, context):
        return editable_scene_camera(context) is not None and context.mode == 'OBJECT'

    def execute(self, context):
        try:
            capture_shot(context, context.scene.camera, self.side)
        except ValueError as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        self.report({'INFO'}, "已记录起始画面" if self.side == 'START' else "已记录结束画面")
        return {'FINISHED'}


class CSF_OT_PreviewShot(Operator):
    bl_idname = "camera_subject_follow.preview_shot"
    bl_label = "预览记录画面"
    bl_description = "通过局部参考相机预览已记录的画面，不切换场景渲染相机"
    side: EnumProperty(items=(('START', "起始", ""), ('END', "结束", "")))

    @classmethod
    def poll(cls, context):
        return context.scene.camera is not None and context.area is not None and context.area.type == 'VIEW_3D'

    def execute(self, context):
        shots = context.scene.camera.camera_subject_shots
        snapshot = (shots.start if self.side == 'START' else shots.end).snapshot
        if snapshot is None:
            self.report({'WARNING'}, "请先记录该画面")
            return {'CANCELLED'}
        space = context.space_data
        SHOT_PREVIEW_STATES.setdefault(context.area.as_pointer(), (space.use_local_camera, space.lock_camera, context.scene.frame_current))
        context.scene.frame_set((shots.start if self.side == 'START' else shots.end).frame)
        space.use_local_camera = True
        space.camera = snapshot
        space.lock_camera = False
        if space.region_3d.view_perspective != 'CAMERA':
            region = next((item for item in context.area.regions if item.type == 'WINDOW'), None)
            if region:
                with context.temp_override(region=region):
                    bpy.ops.view3d.view_camera()
        return {'FINISHED'}


class CSF_OT_CreateShotPath(Operator):
    bl_idname = "camera_subject_follow.create_shot_path"
    bl_label = "连接首尾画面并生成运镜"
    bl_description = "新建连接两个记录位置的可编辑贝赛尔曲线，绑定相机并生成首尾构图动画"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        camera = editable_scene_camera(context)
        return camera is not None and context.mode == 'OBJECT' and camera.camera_subject_shots.start.snapshot is not None and camera.camera_subject_shots.end.snapshot is not None

    def execute(self, context):
        try:
            create_shot_path(context, context.scene.camera)
        except ValueError as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        return {'FINISHED'}


class CSF_OT_UseShotRange(Operator):
    bl_idname = "camera_subject_follow.use_shot_range"
    bl_label = "已有路径仅播放首尾之间"
    bl_description = "使用同一条路径上记录的两个进度作为动画首尾，保留手动编辑过的路径"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        camera = editable_scene_camera(context)
        return camera is not None and path_follower(camera) is not None and context.mode == 'OBJECT'

    def execute(self, context):
        camera = context.scene.camera
        shots = camera.camera_subject_shots
        follow = path_follower(camera)
        try:
            validated_shots(camera)
            if not shots.start.path or shots.start.path != shots.end.path or shots.start.path != follow.target:
                raise ValueError("请在同一条已绑定路径上，以当前摄像机为来源分别记录起始和结束画面")
            if camera.camera_subject_motion.end_frame <= camera.camera_subject_motion.start_frame:
                raise ValueError("结束帧必须大于起始帧")
            settings = camera.camera_subject_motion
            settings.start_progress = shots.start.progress
            settings.end_progress = shots.end.progress
            shots.bound_path = follow.target
            animate_path(context, camera)
        except ValueError as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        return {'FINISHED'}


class CSF_OT_CreatePath(Operator):
    bl_idname = "camera_subject_follow.create_path"
    bl_label = "创建预设并绑定相机"
    bl_description = "创建可编辑的贝赛尔路径，绑定当前摄像机，并按设置生成路径动画"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return editable_scene_camera(context) is not None and context.mode == 'OBJECT'

    def execute(self, context):
        camera = context.scene.camera
        settings = camera.camera_subject_motion
        if settings.auto_animate and settings.end_frame <= settings.start_frame:
            self.report({'ERROR'}, "结束帧必须大于起始帧")
            return {'CANCELLED'}
        settings.start_progress, settings.end_progress = 0, 1
        curve, center = make_path(context, camera)
        if camera.camera_subject_follow.target is None:
            aim = bpy.data.objects.new("运镜对焦中心", None)
            path_collection(context.scene).objects.link(aim)
            aim.location = center
            aim.empty_display_type = 'SPHERE'
            aim.empty_display_size = max(0.05, settings.radius * 0.025)
            camera.camera_subject_follow.target = aim
        bind_camera(context, camera)
        if settings.auto_animate:
            animate_path(context, camera)
        else:
            clear_progress_animation(camera)
            path_follower(camera).offset_factor = 0
        self.report({'INFO'}, "已创建并绑定：" + curve.name)
        return {'FINISHED'}


class CSF_OT_BindPath(Operator):
    bl_idname = "camera_subject_follow.bind_path"
    bl_label = "绑定摄像机"
    bl_description = "将摄像机位置绑定到所选曲线，保留原有相机动画和主体对焦"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return editable_scene_camera(context) is not None and context.mode == 'OBJECT'

    def execute(self, context):
        try:
            bind_camera(context, context.scene.camera)
        except ValueError as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        return {'FINISHED'}


class CSF_OT_UnbindPath(Operator):
    bl_idname = "camera_subject_follow.unbind_path"
    bl_label = "解绑路径"
    bl_description = "解除路径位置约束，恢复摄像机原有的位置和动画；保留曲线与路径控制器"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        camera = editable_scene_camera(context)
        return camera is not None and motion_constraint(camera) is not None

    def execute(self, context):
        camera = context.scene.camera
        camera.constraints.remove(motion_constraint(camera))
        camera.camera_subject_motion.constraint_name = ""
        apply_shot_framing(context, camera)
        return {'FINISHED'}


class CSF_OT_AnimatePath(Operator):
    bl_idname = "camera_subject_follow.animate_path"
    bl_label = "生成 / 更新运镜动画"
    bl_description = "更新独立控制器的路径进度动画；保留摄像机原有关键帧"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        camera = editable_scene_camera(context)
        return camera is not None and motion_constraint(camera) is not None and path_follower(camera) is not None

    def execute(self, context):
        try:
            animate_path(context, context.scene.camera)
        except ValueError as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        return {'FINISHED'}


class CSF_OT_RebuildPath(Operator):
    bl_idname = "camera_subject_follow.rebuild_path"
    bl_label = "按参数重建路径"
    bl_description = "按当前预设与参数替换控制点；手动编辑的控制点会被替换"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        camera = editable_scene_camera(context)
        path = camera.camera_subject_motion.path if camera else None
        return path is not None and path.is_editable and bool(path.get("csf_preset")) and context.mode == 'OBJECT'

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        camera = context.scene.camera
        settings = camera.camera_subject_motion
        path = settings.path
        if not path.data.is_editable or path.data.users > 1:
            path.data = path.data.copy()
        fill_curve(path, settings)
        try:
            configure_path_center(path, camera)
        except ValueError as error:
            self.report({'WARNING'}, str(error))
        return {'FINISHED'}


class CSF_OT_ClearMotionAnimation(Operator):
    bl_idname = "camera_subject_follow.clear_motion_animation"
    bl_label = "清除生成的运镜动画"
    bl_description = "清除路径进度及首尾构图关键帧，保留当前取景；原有相机动画不受影响"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        camera = editable_scene_camera(context)
        return camera is not None and path_follower(camera) is not None

    def execute(self, context):
        camera = context.scene.camera
        clear_progress_animation(camera)
        shots = camera.camera_subject_shots
        if shot_path_active(camera):
            if shots.orientation_rig:
                clear_animation_paths(shots.orientation_rig, {"rotation_quaternion"})
            if shots.managed_data:
                clear_animation_paths(shots.managed_data, set(SHOT_CAMERA_FIELDS))
        return {'FINISHED'}


class CSF_OT_SelectPath(Operator):
    bl_idname = "camera_subject_follow.select_path"
    bl_label = "选中路径"
    bl_description = "选中曲线路径，便于移动、旋转或缩放整条路径"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        camera = editable_scene_camera(context)
        return camera is not None and camera.camera_subject_motion.path is not None and context.mode == 'OBJECT'

    def execute(self, context):
        path = context.scene.camera.camera_subject_motion.path
        if path.name not in context.view_layer.objects or path.hide_viewport:
            self.report({'WARNING'}, "路径未位于可用视图层，或已被禁用")
            return {'CANCELLED'}
        for obj in context.selected_objects:
            obj.select_set(False)
        path.hide_set(False)
        path.select_set(True)
        context.view_layer.objects.active = path
        return {'FINISHED'}


class CSF_OT_EditPath(Operator):
    bl_idname = "camera_subject_follow.edit_path"
    bl_label = "编辑控制点"
    bl_description = "进入曲线编辑模式，可移动控制点、细分加点或延伸路径"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        camera = editable_scene_camera(context)
        path = camera.camera_subject_motion.path if camera else None
        return path is not None and path.is_editable and path.data.is_editable and context.mode == 'OBJECT'

    def execute(self, context):
        if bpy.ops.camera_subject_follow.select_path() != {'FINISHED'}:
            return {'CANCELLED'}
        bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}


class CSF_OT_SelectedPath(Operator):
    bl_idname = "camera_subject_follow.selected_path"
    bl_label = "绑定选中曲线"
    bl_description = "把当前选中的曲线直接用作摄像机运动路径"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        camera = editable_scene_camera(context)
        obj = context.view_layer.objects.active
        return camera is not None and obj is not None and obj.type == 'CURVE' and context.mode == 'OBJECT'

    def execute(self, context):
        camera = context.scene.camera
        path = context.view_layer.objects.active
        if not curve_is_valid(camera.camera_subject_motion, path):
            self.report({'ERROR'}, "路径不能依赖摄像机或其运镜控制器")
            return {'CANCELLED'}
        camera.camera_subject_motion.path = path
        return bpy.ops.camera_subject_follow.bind_path()


class CSF_OT_AutoScale(Operator):
    bl_idname = "camera_subject_follow.auto_scale"
    bl_label = "按主体估算尺寸"
    bl_description = "依据主体尺寸与当前摄像机位置，估算路径半径、行程和高度"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        camera = editable_scene_camera(context)
        return camera is not None and camera.camera_subject_follow.target is not None

    def execute(self, context):
        camera = context.scene.camera
        subject = camera.camera_subject_follow.target
        delta = camera.matrix_world.translation - subject.matrix_world.translation
        size = max(subject.dimensions)
        settings = camera.camera_subject_motion
        settings.radius = max(size * 2, delta.xy.length, 0.5)
        settings.height = delta.z if abs(delta.z) > 0.01 else max(size * 0.5, 1)
        settings.length = settings.radius * 2
        settings.rise = max(size, settings.radius * 0.8)
        return {'FINISHED'}


def draw_object_picker(layout, owner, name, text, kind):
    row = layout.row(align=True)
    row.prop(owner, name, text=text)
    row.operator("camera_subject_follow.pick_object", text="", icon='EYEDROPPER').kind = kind


class CSF_PT_SubjectFollow(Panel):
    bl_label = "主体锁定与对焦"
    bl_idname = "CSF_PT_subject_follow"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "相机跟随"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = False
        layout.use_property_decorate = False
        row = layout.row(align=True)
        row.prop(context.scene, "camera", text="摄像机")
        row.operator("camera_subject_follow.add_camera", text="", icon='ADD')
        camera = context.scene.camera
        if camera is None:
            layout.label(text="未指定摄像机", icon='INFO')
            return
        if not camera.is_editable:
            layout.label(text="摄像机为只读链接数据", icon='LIBRARY_DATA_DIRECT')
            return
        settings = camera.camera_subject_follow
        layout.separator()
        draw_object_picker(layout, settings, "target", "跟随主体", 'SUBJECT')
        row = layout.row(align=True)
        row.operator("camera_subject_follow.use_selected", icon='RESTRICT_SELECT_OFF')
        row.operator("camera_subject_follow.clear", text="", icon='X')
        layout.separator()
        layout.prop(settings, "follow_rotation")
        row = layout.row()
        row.enabled = camera.data.is_editable
        row.prop(settings, "follow_focus")
        if settings.follow_focus and settings.target and camera.data.is_editable:
            layout.prop(camera.data.dof, "aperture_fstop", text="光圈 F 值")
        layout.separator()
        row = layout.row()
        row.enabled = camera.data.is_editable
        if camera.data.type == 'PERSP':
            row.prop(camera.data, "lens", text="焦距")
        elif camera.data.type == 'ORTHO':
            row.prop(camera.data, "ortho_scale", text="正交比例")
        layout.operator("camera_subject_follow.camera_view", icon='VIEW_CAMERA')


class CSF_PT_MotionCreate(Panel):
    bl_label = "贝赛尔路径预设"
    bl_idname = "CSF_PT_motion_create"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "相机跟随"
    bl_order = 10

    @classmethod
    def poll(cls, context):
        return editable_scene_camera(context) is not None

    def draw(self, context):
        layout = self.layout
        layout.use_property_decorate = False
        settings = context.scene.camera.camera_subject_motion
        layout.prop(settings, "preset")
        layout.prop(settings, "center_mode")
        layout.prop(settings, "radius")
        layout.prop(settings, "height")
        if settings.preset in {'DOLLY_IN', 'DOLLY_OUT', 'TRUCK', 'S_CURVE', 'WAVE', 'FLYOVER'}:
            layout.prop(settings, "length")
        if settings.preset in {'CRANE', 'HELIX', 'SPIRAL_IN', 'WAVE', 'FLYOVER'}:
            layout.prop(settings, "rise")
        if settings.preset in {'HELIX', 'SPIRAL_IN'}:
            layout.prop(settings, "turns")
        row = layout.row(align=True)
        row.prop(settings, "points")
        row.prop(settings, "angle")
        layout.operator("camera_subject_follow.auto_scale", icon='FULLSCREEN_ENTER')
        row = layout.row()
        row.enabled = settings.center_mode == 'SUBJECT' and context.scene.camera.camera_subject_follow.target is not None
        row.prop(settings, "moving_center")
        layout.prop(settings, "auto_animate")
        layout.operator("camera_subject_follow.create_path", icon='CURVE_BEZCURVE')


class CSF_PT_ShotFrames(Panel):
    bl_label = "首尾画面"
    bl_idname = "CSF_PT_shot_frames"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "相机跟随"
    bl_parent_id = "CSF_PT_subject_follow"
    bl_order = 5

    @classmethod
    def poll(cls, context):
        return editable_scene_camera(context) is not None

    def draw(self, context):
        layout = self.layout
        layout.use_property_decorate = False
        camera = context.scene.camera
        shots = camera.camera_subject_shots
        layout.prop(shots, "source")
        for side, slot, label in (('START', shots.start, "起始"), ('END', shots.end, "结束")):
            if shots.source == 'REFERENCE':
                draw_object_picker(layout, slot, "source_camera", label + "相机", side + '_CAMERA')
            row = layout.row(align=True)
            row.operator("camera_subject_follow.capture_shot", text="记录" + label + "画面", icon='REC').side = side
            preview = row.row(align=True)
            preview.enabled = slot.snapshot is not None
            preview.operator("camera_subject_follow.preview_shot", text="", icon='HIDE_OFF').side = side
            if slot.snapshot:
                layout.label(text=label + "已记录 · 第 " + str(slot.frame) + " 帧", icon='CHECKMARK')
        layout.operator("camera_subject_follow.camera_view", text="返回当前相机", icon='VIEW_CAMERA')
        layout.separator()
        layout.prop(shots, "framing")
        layout.prop(shots, "shape")
        if shots.shape != 'STRAIGHT':
            layout.prop(shots, "bend")
        layout.prop(shots, "lift")
        layout.prop(shots, "points")
        row = layout.row(align=True)
        row.prop(camera.camera_subject_motion, "start_frame")
        row.prop(camera.camera_subject_motion, "end_frame")
        layout.operator("camera_subject_follow.create_shot_path", icon='CURVE_BEZCURVE')
        layout.operator("camera_subject_follow.use_shot_range", icon='PREVIEW_RANGE')


class CSF_PT_MotionBinding(Panel):
    bl_label = "路径绑定与控制点"
    bl_idname = "CSF_PT_motion_binding"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "相机跟随"
    bl_order = 20

    @classmethod
    def poll(cls, context):
        return editable_scene_camera(context) is not None

    def draw(self, context):
        layout = self.layout
        settings = context.scene.camera.camera_subject_motion
        draw_object_picker(layout, settings, "path", "路径曲线", 'PATH')
        row = layout.row(align=True)
        row.operator("camera_subject_follow.bind_path", icon='LINKED')
        row.operator("camera_subject_follow.unbind_path", text="解绑", icon='UNLINKED')
        layout.operator("camera_subject_follow.selected_path", icon='RESTRICT_SELECT_OFF')
        if motion_constraint(context.scene.camera):
            layout.prop(settings, "enabled")
        follow = path_follower(context.scene.camera)
        if follow and motion_constraint(context.scene.camera):
            layout.prop(follow, "offset_factor", text="路径进度", slider=True)
        if settings.path:
            layout.separator()
            if context.mode == 'EDIT_CURVE' and context.object == settings.path:
                row = layout.row(align=True)
                row.operator("curve.subdivide", text="细分加点", icon='MOD_SUBSURF').number_cuts = 1
                row.operator_context = 'INVOKE_REGION_WIN'
                row.operator("curve.extrude_move", text="延伸点", icon='ADD')
                row = layout.row(align=True)
                row.operator("curve.switch_direction", text="反转曲线", icon='ARROW_LEFTRIGHT')
                row.operator("object.mode_set", text="完成编辑", icon='CHECKMARK').mode = 'OBJECT'
            else:
                row = layout.row(align=True)
                row.operator("camera_subject_follow.select_path", icon='RESTRICT_SELECT_OFF')
                row.operator("camera_subject_follow.edit_path", icon='EDITMODE_HLT')
            layout.operator("camera_subject_follow.rebuild_path", icon='FILE_REFRESH')
            if settings.path.data.splines:
                layout.prop(settings.path.data.splines[0], "use_cyclic_u", text="闭合路径")


class CSF_PT_MotionAnimation(Panel):
    bl_label = "运镜动画"
    bl_idname = "CSF_PT_motion_animation"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "相机跟随"
    bl_order = 30

    @classmethod
    def poll(cls, context):
        return editable_scene_camera(context) is not None

    def draw(self, context):
        layout = self.layout
        layout.use_property_decorate = False
        settings = context.scene.camera.camera_subject_motion
        row = layout.row(align=True)
        row.prop(settings, "start_frame")
        row.prop(settings, "end_frame")
        row = layout.row(align=True)
        row.prop(settings, "start_progress", text="从", slider=True)
        row.prop(settings, "end_progress", text="到", slider=True)
        layout.prop(settings, "interpolation")
        layout.prop(settings, "loop")
        layout.prop(settings, "reverse")
        layout.prop(settings, "fit_timeline")
        row = layout.row(align=True)
        row.operator("camera_subject_follow.animate_path", icon='KEY_HLT')
        row.operator("camera_subject_follow.clear_motion_animation", text="", icon='KEY_DEHLT')
        row = layout.row(align=True)
        playing = context.screen.is_animation_playing if context.screen else False
        row.operator("screen.animation_play", text="暂停" if playing else "播放", icon='PAUSE' if playing else 'PLAY')
        row.operator("camera_subject_follow.camera_view", text="相机视图", icon='VIEW_CAMERA')


CLASSES = (
    CSF_Settings,
    CSF_MotionSettings,
    CSF_ShotSlot,
    CSF_ShotSettings,
    CSF_OT_PickObject,
    CSF_OT_UseSelected,
    CSF_OT_Clear,
    CSF_OT_CameraView,
    CSF_OT_AddCamera,
    CSF_OT_CreatePath,
    CSF_OT_BindPath,
    CSF_OT_UnbindPath,
    CSF_OT_AnimatePath,
    CSF_OT_RebuildPath,
    CSF_OT_ClearMotionAnimation,
    CSF_OT_SelectPath,
    CSF_OT_EditPath,
    CSF_OT_SelectedPath,
    CSF_OT_AutoScale,
    CSF_OT_CaptureShot,
    CSF_OT_PreviewShot,
    CSF_OT_CreateShotPath,
    CSF_OT_UseShotRange,
    CSF_PT_SubjectFollow,
    CSF_PT_MotionCreate,
    CSF_PT_ShotFrames,
    CSF_PT_MotionBinding,
    CSF_PT_MotionAnimation,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Object.camera_subject_follow = PointerProperty(type=CSF_Settings)
    bpy.types.Object.camera_subject_motion = PointerProperty(type=CSF_MotionSettings)
    bpy.types.Object.camera_subject_shots = PointerProperty(type=CSF_ShotSettings)


def unregister():
    del bpy.types.Object.camera_subject_shots
    del bpy.types.Object.camera_subject_motion
    del bpy.types.Object.camera_subject_follow
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
