# Demo media and reproducibility

The three-move preview uses actual cameras driven by Camera Subject Follow 1.2.1 in an original procedural studio scene:

1. Orbit: 60 consecutive rendered frames.
2. Dolly in: 60 consecutive rendered frames.
3. Rising helix: 60 consecutive rendered frames.

Each move runs at 15 fps for four seconds. The short videos add a four-second download/try card, for 16 seconds total. There is no soundtrack. Captions and path diagrams are added in postproduction; they are not Blender interface recordings. The teaser GIF shows the same three moves at an average of 8 fps.

For every source frame, the renderer checks the evaluated subject projection against the center of the camera frame (error below `0.00001` in normalized frame coordinates), and checks that depth-of-field focus still targets the subject. This verifies subject centering, not obstacle avoidance or constant subject screen size.

## Rebuild

The original example scene is included in the repository. Render it using a Blender executable (the public media was made with Blender 4.3.2):

```sh
blender --background --factory-startup --python-exit-code 1 --python examples/render_launch_demo.py
```

Source renders and a camera-position manifest are written to ignored `.test-output/launch-frames/`. This command operates in a separate factory session and never saves over the example scene.

Compose the media with Pillow and imageio-ffmpeg in a development Python environment:

```sh
python3 -m pip install Pillow imageio-ffmpeg
python3 scripts/build_launch_media.py --font /path/to/latin-font.ttf --cjk-font /path/to/chinese-font.ttf --output /path/to/media-output
```

Font files are read locally and not redistributed. The add-on itself needs none of these development dependencies. The generated manifest documents frame rate, duration and projection error. Release assets provide the MP4 versions; the static demo page also serves same-origin landscape MP4s for browser playback.

## 分享时说明

素材展示的是插件实际生成的运镜，包含环绕、推进、螺旋升降。路线示意与字幕为后期说明，不是插件界面录屏。模型、材质和灯光由本项目代码生成，没有外部素材依赖。

可用于介绍本项目；请保留项目链接，并遵守仓库 GPL-3.0-or-later 许可。原版提供无音乐 MP4 和字幕文件，便于自行配音。
