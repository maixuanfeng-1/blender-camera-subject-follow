# Camera Subject Follow guide

[Install](../README.md#install) · [中文完整指南](GUIDE.zh-CN.md)

The current interface uses Simplified Chinese. This guide describes the same controls in English and includes their visible labels.

## A first orbit

Select the camera in the top panel. Use the independent eyedropper beside **跟随主体** to pick your subject in the 3D View or Outliner. Right-click or Esc cancels; clicking empty space lets you try again. **使用选中物体** is a separate shortcut that uses the already selected object. Picking works in Object Mode and restores your selection.

Select **圆形环绕** under **贝赛尔路径预设**. Adjust radius, base height and control-point count. **按主体估算尺寸** estimates dimensions from the subject and current camera position; check the result for your scene.

Set the start/end frames under **运镜动画**, then click **创建预设并绑定相机**. The default creates a curve, binds the camera and generates motion. Switch to camera view and play. Without a subject, the add-on creates an Empty at the path center as a focus target.

## Path shapes and dimensions

| Preset | Chinese label | Useful controls |
| --- | --- | --- |
| Orbit | 圆形环绕 | Radius, height |
| Ellipse | 椭圆环绕 | Radius, height |
| 90° arc | 90° 弧线 | Radius, height |
| 180° arc | 180° 半环绕 | Radius, height |
| Dolly in | 推进 | Distance, travel length, height |
| Dolly out | 拉远 | Distance, travel length, height |
| Truck | 左右横移 | Distance, travel length, height |
| Crane | 垂直升降 | Distance, height, rise |
| S-curve | S 形穿行 | Radius, travel length, height |
| Rising helix | 螺旋升降 | Radius, turns, rise |
| Spiral in | 螺旋收拢 | Radius, turns, rise |
| Figure eight | 8 字环绕 | Radius, height |
| Wave | 波浪穿行 | Radius, travel length, rise |
| Arched flyover | 拱形飞越 | Distance, travel length, rise |

Preset control-point count ranges from 4 to 256. More turns usually need more points. Curves start with automatic handles; you can change handle types using Blender's native curve tools. Rise can be negative.

The center can be the subject origin, 3D cursor or world origin. The initial direction is based on the camera's position relative to the center, with an additional start-angle offset.

**路径随主体平移** makes the path translate with the subject chosen when the curve is created or rebuilt, retaining world orientation. Changing the focus target later does not reparent an existing path.

## Edit control points

In **路径绑定与控制点**, choose **编辑控制点** to enter native curve Edit Mode. Select adjacent points (or all points) and use **细分加点** to add points between them. **延伸点** extrudes a selected endpoint; move the mouse and confirm. Open a closed path before trying to extend an endpoint.

**反转曲线** reverses control-point order. **闭合路径** connects or disconnects the ends. **完成编辑** returns to Object Mode. Select the path object to move, rotate or scale the entire route.

Changing preset dimensions does not immediately change an existing curve. **按参数重建路径** rebuilds it and replaces its manually edited control points after confirmation. The path object's transform is kept. Creating another preset keeps the old curve and rebinds the camera to the new one.

## Bind your own curve

Use the eyedropper beside **路径曲线**, then click **绑定摄像机**. Alternatively select your curve first and click **绑定选中曲线**. The add-on uses Blender's native path behavior; use one continuous spline per path object for predictable results.

Binding controls the camera's position while retaining subject tracking and focus. **启用路径运动** pauses and resumes the path. **解绑** removes the add-on's position constraint, restores the original camera animation and keeps the curve/controller available for reuse.

## Timing and loops

The end frame must be greater than the start frame. Choose linear progress (**匀速**), smooth start/stop (**柔和启停**) or sine easing (**正弦缓动**). Curve evaluation can produce small speed variations even with linear progress.

- **单次** holds the endpoints outside the selected frame range.
- **重复** repeats the move. Open curves jump from the end to the start; closed curves suit seamless loops.
- **往返** plays back and forth along the route.
- **反向运动** reverses the next generated animation.
- **同步场景帧范围** changes the scene range only when enabled.

Click **生成 / 更新运镜动画** after changing timing. This updates the independent path controller's progress keys rather than overwriting the camera's original position keys. The “from/to” progress controls limit playback to a path segment.

The progress slider lets you preview manually. Existing keys will take over again when you change frames. Use the empty-keyframe button to clear generated motion first. In matched-shot mode, clearing also removes generated orientation/lens keys and freezes the current framing; use the timeline to preview the full composition transition.

## Record start and end shots

### Connect two views

1. Under **首尾画面**, choose the viewport (**当前视角**), active camera (**当前摄像机**) or reference cameras (**指定相机**) as the source.
2. Compose the opening and click **记录起始画面**.
3. Compose the ending and click **记录结束画面**.
4. Set framing mode, straight/arc/S connection, sideways bend, middle lift and point count.
5. Set output start/end frames and click **连接首尾画面并生成运镜**.

**匹配首尾构图** transitions camera position, orientation, focal length, shift and orthographic scale to match the recorded endpoints. **持续看向主体** retains aim tracking and the original lens behavior, so a deliberately off-center reference will not keep its off-center direction in this mode. Both modes can retain depth-of-field focus.

The references must use the same perspective/orthographic projection type. Camera-based capture preserves camera framing; ordinary perspective-view capture adapts vertical field of view to the scene render aspect ratio. A stationary pan/zoom is supported. If a zero-length path is later edited into a route, bind it again to enable path motion.

The eye icon previews a recorded shot through a local reference camera at its recorded frame. **返回当前相机** restores the previous viewport/frame without replacing the scene render camera. Capturing records camera framing, not a snapshot of object/light animation: scene content still follows the output timeline.

Recording an endpoint again updates its existing reference. Reference cameras are kept in the path collection and saved in the `.blend`. Generated shot framing uses an independent orientation controller and camera-data copy; pausing, unbinding or returning to subject mode can restore the original camera/lens animation.

### Choose a section of an existing curve

Bind the existing route, choose **当前摄像机** as the source, and use the timeline to record two positions. Click **已有路径仅播放首尾之间**. This regenerates progress between the two recorded values while preserving the curve's edited points. Both shots must come from the same bound path and current camera.

A larger starting progress than ending progress plays that section backward. On closed curves, the numerical interval is interpolated directly; it does not automatically cross the 1→0 seam.

## Tracking, focus and free composition

**持续朝向主体** and **景深自动对焦** are independent switches. The target is the subject's object origin. For a specific feature, create an Empty at that point, parent it to the subject and pick the Empty.

A lower f-stop usually produces stronger background blur. Clearing the subject restores the focus settings previously taken over by the add-on. Clearing a subject does not unbind the path.

Aim tracking controls orientation. If camera-to-view navigation feels constrained, temporarily disable **持续朝向主体** before adjusting a free composition. Also check that the scene camera selected in the add-on is the camera being shown in the viewport.

The add-on does not avoid obstacles or maintain constant subject screen size by changing focal length.

## Save and share

Save your `.blend` normally to keep paths, references and target selections. Installing the add-on never automatically saves your scene. Existing motion and focus use native Follow Path, Copy Location and Track To constraints plus keys and focus objects. A saved animation can play without this add-on; changing its panel settings needs the add-on installed.

## Button reference

| Visible label | Meaning |
| --- | --- |
| 相机跟随 | Camera Follow sidebar tab |
| 主体锁定与对焦 | Subject tracking and focus |
| 跟随主体 | Subject target |
| 使用选中物体 | Use selected object |
| 持续朝向主体 | Keep aiming at subject |
| 景深自动对焦 | Depth-of-field focus follows target |
| 贝赛尔路径预设 | Bézier path presets |
| 创建预设并绑定相机 | Create preset and bind camera |
| 路径绑定与控制点 | Path binding and control points |
| 编辑控制点 / 细分加点 | Edit control points / subdivide |
| 绑定摄像机 / 解绑 | Bind camera / unbind |
| 运镜动画 | Camera motion timing |
| 起始帧 / 结束帧 | Start frame / end frame |
| 生成 / 更新运镜动画 | Generate/update motion |
| 首尾画面 | Start/end shots |
| 匹配首尾构图 | Match endpoint framing |
| 记录起始画面 / 记录结束画面 | Capture start/end shot |
