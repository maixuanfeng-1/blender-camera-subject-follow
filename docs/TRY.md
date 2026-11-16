# Try your first camera move in about three minutes

[中文](#三分钟试用) · [Watch the demo](https://maixuanfeng-1.github.io/blender-camera-subject-follow/) · [Give feedback](https://github.com/maixuanfeng-1/blender-camera-subject-follow/issues/new?template=trial.yml)

**A useful first task:** open the included product scene, change the orbit radius and see the camera keep pointing at the product.

1. Download the [add-on ZIP](https://github.com/maixuanfeng-1/blender-camera-subject-follow/releases/download/v1.2.1/camera_subject_follow-v1.2.1.zip) and [example scene](https://github.com/maixuanfeng-1/blender-camera-subject-follow/releases/download/v1.2.1/camera-follow-demo.blend).
2. In Blender, use **Edit → Preferences → Add-ons → Install from Disk** to install the ZIP, then enable **Camera Subject Follow**.
3. Open the example scene and press **N → 相机跟随**. Play frames **1–145** to see the existing orbit.
4. Under **贝赛尔路径预设**, change **半径 / 距离** from `8.3` to `10`. Click **创建预设并绑定相机**. It keeps the old curve and creates/binds a new route. Play again to see the wider orbit.
5. If you want to try hand editing, select the active path, click **编辑控制点**, move one point with **G**, then return to Object Mode. The curve remains editable.

The current UI is Chinese; the [English button reference](GUIDE.md#button-reference) helps map controls. Save a copy of the example if you want to keep your changes. Other presets are in the same selector.

**Useful feedback takes one sentence:** your Blender version/OS, whether the move worked, and the step that took the most effort. Use the [trial form](https://github.com/maixuanfeng-1/blender-camera-subject-follow/issues/new?template=trial.yml). A small screenshot helps if something failed.

Tested locally on macOS Blender 4.3.2 and 5.1.0. Other systems and releases need confirmation. If the add-on helps, a star is welcome; installation, examples and support are free.

## 三分钟试用

**先做一个具体小任务：打开产品示例，把环绕半径改大，检查相机是否仍对准主体。**

1. 下载 [插件 ZIP](https://github.com/maixuanfeng-1/blender-camera-subject-follow/releases/download/v1.2.1/camera_subject_follow-v1.2.1.zip) 和 [示例工程](https://github.com/maixuanfeng-1/blender-camera-subject-follow/releases/download/v1.2.1/camera-follow-demo.blend)。
2. 在 Blender「编辑 → 偏好设置 → 插件 → 从磁盘安装」中选 ZIP，启用 **Camera Subject Follow**。
3. 打开示例，按 **N → 相机跟随**，播放 **1–145 帧**，先看现有环绕。
4. 在「贝赛尔路径预设」把「半径 / 距离」从 `8.3` 改为 `10`，点击「创建预设并绑定相机」。它会保留旧曲线，新建并绑定更宽的路线。再播放一次检查。
5. 想改路线，可以选中当前路径，点「编辑控制点」，用 **G** 移动一个点，再回到物体模式。

想保留修改时另存示例工程。其他路径样式也在同一个下拉框中。

欢迎用一句话 [反馈试用结果](https://github.com/maixuanfeng-1/blender-camera-subject-follow/issues/new?template=trial.yml)：**Blender 版本 / 系统、能否完成运镜、哪一步最卡。** 遇到错误可附小截图。

目前已在 macOS 的 Blender 4.3.2 和 5.1.0 上验证，其他系统和版本欢迎反馈。如果工具对你有帮助，再点一个 Star 就很好；安装包、示例和使用支持均免费。
