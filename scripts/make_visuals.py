"""Compose README graphics from actual Blender renders and exported path coordinates.

Requires Pillow (only for asset development, not for the add-on).
Set --font to a readable font available on your computer.
"""
import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'images'
FRAMES = ROOT / '.test-output' / 'demo-frames'
BG = '#101a27'
FG = '#edf1f5'
MUTED = '#a9bacb'
GREEN = '#6ce0bc'
ORANGE = '#ff996d'

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--font', required=True)
args = parser.parse_args()


def font(size):
    return ImageFont.truetype(args.font, size)


def label(draw, xy, text, size=24, fill=FG, **kw):
    draw.text(xy, text, font=font(size), fill=fill, **kw)


def arrow(draw, p, q, fill, width=2):
    draw.line([p, q], fill=fill, width=width)
    a = math.atan2(q[1]-p[1], q[0]-p[0])
    arms = [(q[0]-12*math.cos(a+d), q[1]-12*math.sin(a+d)) for d in (-0.4, 0.4)]
    draw.line([arms[0], q, arms[1]], fill=fill, width=width)


def cover():
    im = Image.new('RGB', (1600, 900), BG)
    d = ImageDraw.Draw(im)
    label(d, (80, 58), 'BLENDER ADD-ON', 24, GREEN)
    label(d, (80, 140), 'Camera', 91)
    label(d, (80, 246), 'Subject Follow', 82)
    label(d, (84, 380), 'Choose a path.', 38)
    label(d, (84, 435), 'Keep your subject in focus.', 32, MUTED)
    photo = ImageOps.fit(Image.open(FRAMES/'hero-render.png').convert('RGB'), (700, 650), centering=(0.5, 0.55))
    mask = Image.new('L', photo.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 699, 649), radius=26, fill=255)
    im.paste(photo, (820, 125), mask)
    d = ImageDraw.Draw(im)
    # A deliberately schematic orbit and tracking ray, clearly separated from the render.
    cx, cy, rx, ry = 350, 656, 236, 74
    pts = [(cx+rx*math.cos(i*2*math.pi/180), cy+ry*math.sin(i*2*math.pi/180)) for i in range(181)]
    d.line(pts, fill=GREEN, width=3)
    for a in (0, math.pi/2, math.pi, math.pi*1.5):
        x,y=cx+rx*math.cos(a),cy+ry*math.sin(a)
        d.rectangle((x-6,y-6,x+6,y+6),fill=BG,outline=GREEN,width=2)
    p=(cx+rx*math.cos(0.8),cy+ry*math.sin(0.8))
    arrow(d,p,(cx,cy),MUTED)
    d.rounded_rectangle((p[0]-17,p[1]-12,p[0]+17,p[1]+12),4,fill=ORANGE)
    d.ellipse((cx-10,cy-10,cx+10,cy+10),fill=FG)
    label(d,(240,758),'EDITABLE PATH + SUBJECT LOCK',18,MUTED)
    d.line((80,817,1520,817),fill='#324253',width=1)
    label(d,(80,845),'14 paths  /  Start & end shots  /  Native Blender animation',21,MUTED)
    label(d,(1220,845),'FREE & OPEN SOURCE',20,GREEN)
    im.save(OUT/'cover.png',optimize=True)
    ImageOps.fit(im,(1280,640)).save(OUT/'social-preview.png',optimize=True)


def demo():
    positions=json.loads((FRAMES/'positions.json').read_text())
    gif=[]
    for i,xyz in enumerate(positions):
        im=Image.new('RGB',(1120,570),BG)
        d=ImageDraw.Draw(im)
        label(d,(26,20),'ONE PATH. SUBJECT ALWAYS IN FOCUS.',25)
        label(d,(25,76),'PATH OVERVIEW',15,MUTED)
        label(d,(397,76),'ACTUAL CAMERA RENDER',15,MUTED)
        cx,cy,rx,ry=190,300,138,90
        pts=[(cx+rx*math.cos(j*2*math.pi/180),cy+ry*math.sin(j*2*math.pi/180)) for j in range(181)]
        d.line(pts,fill=GREEN,width=3)
        for a in range(0,360,45):
            x,y=cx+rx*math.cos(math.radians(a)),cy+ry*math.sin(math.radians(a))
            d.rectangle((x-3,y-3,x+3,y+3),fill=GREEN)
        x,y=cx+xyz[0]/8.3*rx,cy+xyz[1]/8.3*ry
        arrow(d,(x,y),(cx,cy),MUTED)
        d.rounded_rectangle((x-13,y-9,x+13,y+9),3,fill=ORANGE)
        d.ellipse((cx-8,cy-8,cx+8,cy+8),fill=FG)
        label(d,(117,425),'SUBJECT',16,MUTED)
        label(d,(26,505),'Native Bézier curve',20,GREEN)
        photo=Image.open(FRAMES/f'{i:03d}.png').convert('RGB').resize((696,522),Image.Resampling.LANCZOS)
        im.paste(photo.crop((0,22,696,422)),(397,104))
        d=ImageDraw.Draw(im)
        label(d,(405,522),f'Orbit preset  ·  Frame {1+i*4:03d} / 145',16,MUTED)
        gif.append(im.quantize(colors=256,method=Image.Quantize.MEDIANCUT))
    gif[0].save(OUT/'demo.gif',save_all=True,append_images=gif[1:],duration=150,loop=0,optimize=False,disposal=2)


def presets():
    data=json.loads((ROOT/'docs/preset-geometry.json').read_text())
    names=['Orbit','Ellipse','90° arc','180° arc','Dolly in','Dolly out','Truck','Crane',
           'S-curve','Rising helix','Spiral in','Figure eight','Wave','Arched flyover']
    im=Image.new('RGB',(1440,1350),BG)
    d=ImageDraw.Draw(im)
    label(d,(60,40),'14 paths. Your control points.',48)
    label(d,(62,111),'Generated from the add-on geometry. Edit every curve in Blender.',23,MUTED)
    for i,(item,name) in enumerate(zip(data,names)):
        ox,oy=50+(i%4)*350,195+(i//4)*277
        d.line((ox,oy+253,ox+310,oy+253),fill='#324253',width=1)
        pts=item['points']
        proj=[(p[0]+p[1]*0.48,-p[1]*0.35-p[2]*1.25) for p in pts]
        xmin,xmax=min(p[0] for p in proj),max(p[0] for p in proj)
        ymin,ymax=min(p[1] for p in proj),max(p[1] for p in proj)
        scale=min(260/max(xmax-xmin,0.1),145/max(ymax-ymin,0.1))
        coords=[(ox+155+(p[0]-(xmin+xmax)/2)*scale,oy+108+(p[1]-(ymin+ymax)/2)*scale) for p in proj]
        if item['cyclic']:coords.append(coords[0])
        d.line(coords,fill=GREEN,width=3,joint='curve')
        for p in coords[::max(1,len(coords)//8)]:
            d.rectangle((p[0]-3,p[1]-3,p[0]+3,p[1]+3),fill=BG,outline=GREEN,width=1)
        arrow(d,coords[-8],coords[-1],ORANGE,3)
        label(d,(ox+5,oy+203),f'{i+1:02d}',18,MUTED)
        label(d,(ox+45,oy+198),name,25)
    label(d,(780,1135),'Draw your own curve.',30)
    label(d,(780,1184),'Bind it. Edit it. Keep it.',26,GREEN)
    im.save(OUT/'presets.png',optimize=True)


OUT.mkdir(parents=True,exist_ok=True)
cover()
demo()
presets()
for p in OUT.iterdir():
    print(p.name,p.stat().st_size)
