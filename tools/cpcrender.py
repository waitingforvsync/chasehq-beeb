import sys
from PIL import Image
# CPC hardware colour -> RGB
HW = {0x40:(128,128,128),0x41:(128,128,128),0x42:(0,255,128),0x43:(255,255,128),0x44:(0,0,128),0x45:(255,0,128),0x46:(0,128,128),0x47:(255,128,128),
0x48:(255,0,128),0x49:(255,255,128),0x4A:(255,255,0),0x4B:(255,255,255),0x4C:(255,0,0),0x4D:(255,0,255),0x4E:(255,128,0),0x4F:(255,128,255),
0x50:(0,0,128),0x51:(0,255,128),0x52:(0,255,0),0x53:(0,255,255),0x54:(0,0,0),0x55:(0,0,255),0x56:(0,128,0),0x57:(0,128,255),
0x58:(128,0,128),0x59:(128,255,128),0x5A:(128,255,0),0x5B:(128,255,255),0x5C:(128,0,0),0x5D:(128,0,255),0x5E:(128,128,0),0x5F:(128,128,255)}
PAL = [0x54,0x54,0x4B,0x59,0x44,0x55,0x4E,0x4A,0x56,0x5A,0x5D,0x47,0x53,0x5E,0x5C,0x40]
def pens(b):
    p0 = ((b>>7)&1) | ((b>>3)&1)<<1 | ((b>>5)&1)<<2 | ((b>>1)&1)<<3
    p1 = ((b>>6)&1) | ((b>>2)&1)<<1 | ((b>>4)&1)<<2 | ((b>>0)&1)<<3
    return p0, p1
def screen(mem, base, wbytes=64, lines=192, scale=3):
    im = Image.new('RGB', (wbytes*2*2*scale//2*1, lines*scale))
    im = Image.new('RGB', (wbytes*4, lines))  # mode 0 pixels are 2 wide
    px = im.load()
    for y in range(lines):
        a = base + (y>>3)*wbytes + (y&7)*0x800
        for x in range(wbytes):
            p0,p1 = pens(mem[(a+x)&0xFFFF])
            for k,p in ((0,p0),(1,p1)):
                c = HW[PAL[p]]
                px[x*4+k*2,y]=c; px[x*4+k*2+1,y]=c
    return im.resize((im.width*2, im.height*2), Image.NEAREST)
def linear(data, wbytes, lines):
    im = Image.new('RGB', (wbytes*4, lines)); px = im.load()
    for y in range(lines):
        for x in range(wbytes):
            p0,p1 = pens(data[y*wbytes+x])
            for k,p in ((0,p0),(1,p1)):
                c = HW[PAL[p]]; px[x*4+k*2,y]=c; px[x*4+k*2+1,y]=c
    return im.resize((im.width*2, im.height*2), Image.NEAREST)
