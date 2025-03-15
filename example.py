from parser import parse
from renderer import ChainbeetRenderer, ChainbeetRenderConfig
import skia as sk

if __name__ == '__main__':
    chart = parse(open(f'assets/gengaozo.json', 'r').read())
    renderer = ChainbeetRenderer(chart, ChainbeetRenderConfig())
    image = renderer.render()
    image.save(open('gengaozo.png', 'wb'), sk.EncodedImageFormat.kPNG)
