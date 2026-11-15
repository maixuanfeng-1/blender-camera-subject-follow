# Contributing

Bug reports, documentation fixes, translations and example scenes are welcome. You do not need to write code to help. English and Chinese issues are both welcome.

## Report a reproducible problem

Use the bug-report form and include Blender version, operating system, add-on version, expected behavior and the shortest steps that reproduce the problem. A small scene built from Blender primitives is especially useful. Remove unrelated or private scene content before sharing.

If a problem involves camera navigation, say which camera is the scene render camera and which is visible in the viewport. If it involves an edited curve, say whether you created a new preset, rebuilt an existing one or rebound a custom curve.

## Work on the code

The installable add-on is a single file, `camera_subject_follow.py`, without external dependencies. Please discuss substantial behavior changes in an issue first. Keep fixes focused and explain what changes for a Blender user.

Run the integration suites with a local Blender executable:

```sh
python3 scripts/run_tests.py --blender /path/to/blender
python3 scripts/build_release.py
```

On macOS, the executable is inside the app, for example `/Applications/Blender.app/Contents/MacOS/Blender`. Tests start separate factory sessions and write temporary scenes into ignored `.test-output/`. They do not use your open scene or save your Blender preferences. Avoid running two instances for the same Blender version concurrently because they share output filenames.

The packaging workflow checks syntax and builds the installation ZIP. It does not replace Blender integration tests. Include the Blender versions you actually tested in a pull request.

## Useful contributions

- Confirm behavior on Windows/Linux and additional Blender versions.
- Translate the interface using Blender's localization mechanisms while preserving existing `.blend` properties.
- Add focused regression coverage for reproducible rig/curve bugs.
- Improve beginner instructions or share an original, small example scene.

Do not rename saved property identifiers casually: existing `.blend` files depend on them. Preserve unrelated user constraints, keys and camera data when changing rig behavior.

Contributions are provided under the project's **GPL-3.0-or-later** license. Keep third-party assets out of examples unless their redistribution terms are documented and compatible.

## 中文

欢迎反馈真实问题、改进教程、贡献翻译或提交小型示例。请说明 Blender 版本、操作系统、插件版本与最短复现步骤。修改代码后按上面的命令验证，并在 PR 中写明实际测试的版本。不要随意重命名保存在 `.blend` 中的属性标识；兼容已有工程很重要。
