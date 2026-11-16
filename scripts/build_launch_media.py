"""Compose real rendered moves into launch MP4s and GIFs.

Development dependencies: Pillow and imageio-ffmpeg. These are not add-on dependencies.
Run examples/render_launch_demo.py in Blender first. Provide local font paths;
fonts are not bundled or redistributed.
"""
import argparse
import json
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
FRAMES = ROOT / '.test-output/launch-frames'
FPS = 15
BG, FG, MUTED, GREEN, ORANGE = '#101a27', '#edf1f5', '#a9bacb', '#6ce0bc', '#ff996d'
SLUG = 'maixuanfeng-1/blender-camera-subject-follow'
URL = 'https://github.com/' + SLUG
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--font', required=True, help='Latin font path')
parser.add_argument('--cjk-font', required=True, help='Chinese font path')
parser.add_argument('--output', required=True, type=Path)
parser.add_argument('--teaser-only', action='store_true', help='Rebuild the GIF and covers without re-encoding MP4s')
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
manifest = json.loads((FRAMES/'manifest.json').read_text())
assert len(manifest) == 3
for record in manifest:
    assert record['frame_count'] == 60 and record['max_center_error'] < 0.00001

FONTS = {}
def text(draw, xy, value, size, color=FG, zh=False):
    key = (zh, size)
    if key not in FONTS:
        FONTS[key] = ImageFont.truetype(args.cjk_font if zh else args.font, size)
    draw.text(xy, value, font=FONTS[key], fill=color, spacing=int(size*0.24))


def diagram(draw, record, frame, box):
    x, y, w, h = box
    positions = record['positions']
    def project(point):
        return point[0] + point[1]*0.4, -point[1]*0.35-point[2]*0.9
    allpoints = [project(p) for p in positions]
    center = project((0, 0, 1.1))
    xmin = min(p[0] for p in allpoints + [center]); xmax = max(p[0] for p in allpoints + [center])
    ymin = min(p[1] for p in allpoints + [center]); ymax = max(p[1] for p in allpoints + [center])
    scale = min(w/max(xmax-xmin, 1), h/max(ymax-ymin, 1))
    def fit(p):return (x+w/2+(p[0]-(xmin+xmax)/2)*scale, y+h/2+(p[1]-(ymin+ymax)/2)*scale)
    pts = [fit(p) for p in allpoints]
    draw.line(pts, fill=GREEN, width=4, joint='curve')
    for px,py in pts[::7]:
        draw.rectangle((px-4,py-4,px+4,py+4),fill=BG,outline=GREEN,width=2)
    a,b=pts[frame],fit(center)
    draw.line([a,b],fill=MUTED,width=2)
    draw.ellipse((b[0]-7,b[1]-7,b[0]+7,b[1]+7),fill=FG)
    draw.rounded_rectangle((a[0]-16,a[1]-11,a[0]+16,a[1]+11),4,fill=ORANGE)


def compose(index, vertical=False, zh=False):
    segment = min(index//60, 2)
    ending = index >= 180
    local = index % 60
    record = manifest[segment]
    source = Image.open(FRAMES/record['preset'].lower()/f'{local:03d}.png').convert('RGB')
    names = ['环绕', '推进', '螺旋升降'] if zh else ['Orbit', 'Dolly in', 'Rising helix']
    benefit = ['相机绕着主体运动','从远处推进到近处','旋转的同时升高'] if zh else ['Move around the subject.','Move closer to the subject.','Orbit while gaining height.']
    im = Image.new('RGB',(1080,1920) if vertical else (1920,1080),BG)
    d = ImageDraw.Draw(im)
    if vertical:
        text(d,(64,108),'Blender  /  FREE & OPEN SOURCE',27,GREEN)
        text(d,(64,180),'相机沿路走\n主体一直在画面里',62,zh=True)
        text(d,(64,366),'01  选主体   →   02  选路径   →   03  生成动画',26,MUTED,True)
        im.paste(source.resize((960,720),Image.Resampling.LANCZOS),(60,450))
        d = ImageDraw.Draw(im)
        text(d,(64,1210),f'0{segment+1}   {names[segment]}',45,GREEN,True)
        text(d,(64,1280),benefit[segment],30,MUTED,True)
        diagram(d,record,local,(120,1400,650,155))
        text(d,(64,1610),'14 种可编辑路径 · 主体跟随 · 景深对焦',29,FG,True)
        text(d,(64,1680),'免费插件与示例工程  /  GitHub',32,GREEN,True)
        text(d,(64,1740),'maixuanfeng-1',29,MUTED)
        text(d,(64,1784),'blender-camera-subject-follow',30,FG)
        text(d,(64,1845),'实际插件渲染 · 路线示意与字幕为后期说明',22,MUTED,True)
    else:
        text(d,(64,52),'CAMERA SUBJECT FOLLOW  /  BLENDER',30,GREEN)
        title = '相机沿路走，\n主体一直在画面里。' if zh else 'Let the camera move.\nKeep your subject\nin frame.'
        text(d,(64,156),title,52,FG,zh)
        text(d,(64,400),f'0{segment+1}  {names[segment]}',42,GREEN,zh)
        text(d,(64,470),benefit[segment],26,MUTED,zh)
        diagram(d,record,local,(115,585,450,210))
        text(d,(64,845),'14 种可编辑路径' if zh else '14 editable paths',30,FG,zh)
        text(d,(64,900),'主体跟随 · 景深对焦' if zh else 'Subject tracking + DOF focus',25,MUTED,zh)
        text(d,(64,955),'免费插件与示例工程' if zh else 'Free add-on + example scene',25,GREEN,zh)
        im.paste(source.resize((1104,828),Image.Resampling.LANCZOS),(752,144))
        d=ImageDraw.Draw(im)
        text(d,(752,990),SLUG,23,MUTED)
        text(d,(752,1033),'真实插件渲染 · 路线示意为后期说明' if zh else 'Actual add-on render. Path overview and captions added for explanation.',18,MUTED,zh)
    if ending:
        overlay=Image.new('RGBA',im.size,(9,16,25,225))
        im=Image.alpha_composite(im.convert('RGBA'),overlay).convert('RGB')
        d=ImageDraw.Draw(im)
        y=570 if vertical else 260
        x=80 if vertical else 180
        text(d,(x,y),'拿走示例，试一次。' if zh else 'Try it with the example.',62,FG,zh)
        text(d,(x,y+112),'下载插件 ZIP + 示例工程' if zh else 'Download the add-on ZIP + demo scene',34,GREEN,zh)
        text(d,(x,y+188),'打开示例 → 把半径从 8.3 改到 10 → 生成新路径' if zh else 'Open the scene. Change radius 8.3 to 10. Generate a new path.',27,MUTED,zh)
        text(d,(x,y+300),'github.com/maixuanfeng-1',32,FG)
        text(d,(x,y+355),'blender-camera-subject-follow',34,FG)
        text(d,(x,y+460),'有用再 Star，卡住就反馈。' if zh else 'Useful? A star helps. Stuck? Tell us where.',30,GREEN,zh)
        text(d,(x,y+525),'已验证 macOS / Blender 4.3.2 & 5.1.0' if zh else 'Tested on macOS / Blender 4.3.2 & 5.1.0',24,MUTED,zh)
        text(d,(x,y+565),'当前插件界面为中文' if zh else 'Current add-on interface: Simplified Chinese',22,MUTED,zh)
    return im


ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
for name,vertical,zh in [('camera-follow-demo.en.mp4',False,False),('相机跟随_横版_16秒.mp4',False,True),('相机跟随_竖版_16秒.mp4',True,True)]:
    if args.teaser_only:
        continue
    size=(1080,1920) if vertical else (1920,1080)
    command=[ffmpeg,'-hide_banner','-loglevel','error','-y','-f','rawvideo','-vcodec','rawvideo',
             '-pix_fmt','rgb24','-s',f'{size[0]}x{size[1]}','-r',str(FPS),'-i','-',
             '-an','-c:v','libx264','-preset','fast','-crf','21','-pix_fmt','yuv420p','-movflags','+faststart',str(args.output/name)]
    process=subprocess.Popen(command,stdin=subprocess.PIPE)
    try:
        for index in range(240):
            im=compose(index,vertical,zh)
            process.stdin.write(im.tobytes())
            if index in (0,70,130,190):
                im.save(args.output/f'{"vertical" if vertical else "landscape-zh" if zh else "landscape-en"}-{index:03d}.jpg',quality=90)
    finally:
        process.stdin.close()
    if process.wait()!=0:raise RuntimeError(f'Encoding failed: {name}')
    print('VIDEO_COMPLETE',name,flush=True)

# Caption timing is provided for editors who want to add their own narration.
captions_en = '''1
00:00:00,000 --> 00:00:04,000
Orbit: the camera moves around the subject.

2
00:00:04,000 --> 00:00:08,000
Dolly in: move closer, keep tracking the subject.

3
00:00:08,000 --> 00:00:12,000
Rising helix: orbit while gaining height.

4
00:00:12,000 --> 00:00:16,000
Free add-on and example scene on GitHub.
'''
captions_zh = '''1
00:00:00,000 --> 00:00:04,000
环绕：相机绕着主体运动。

2
00:00:04,000 --> 00:00:08,000
推进：从远处推进到近处，持续朝向主体。

3
00:00:08,000 --> 00:00:12,000
螺旋升降：旋转的同时升高。

4
00:00:12,000 --> 00:00:16,000
GitHub 免费下载插件与示例工程。
'''
(args.output/'captions.en.srt').write_text(captions_en)
(args.output/'captions.zh-CN.srt').write_text(captions_zh)

# Silent looping teaser, 3 actual moves. 12 seconds at 8 fps.
frames=[]
for seg in range(3):
    for i in range(32):
        source_index=seg*60+int(i*1.875)
        frame=compose(source_index,False,False).resize((720,405),Image.Resampling.LANCZOS)
        frames.append(frame.quantize(colors=256,method=Image.Quantize.MEDIANCUT))
gif=args.output/'camera-follow-three-moves.gif'
frames[0].save(gif,save_all=True,append_images=frames[1:],duration=[120,130]*48,loop=0,disposal=2,optimize=False)
poster=compose(0,False,False)
poster.save(args.output/'launch-cover.png',optimize=True)
vertical_cover=compose(0,True,True)
vertical_cover.save(args.output/'试用招募封面.png',optimize=True)
(args.output/'media-manifest.json').write_text(json.dumps({
    'duration_seconds':16,'fps':15,'moves':[r['preset'] for r in manifest],
    'actual_frames':180,'audio':False,'source':'Actual add-on-generated Blender Cycles renders',
    'captions':'Postproduction explanatory captions and path overview',
    'max_center_error':max(r['max_center_error'] for r in manifest),
},indent=2))
print('LAUNCH_MEDIA_COMPLETE',flush=True)
