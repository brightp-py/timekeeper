import pygame
import numpy as np
import json
from perlin_numpy import generate_fractal_noise_2d

TILEDATA = json.load(open('resource/img/tile_data.json'))
GRASS = pygame.image.load('resource/img/grass_tileset.png')
DIRT = pygame.image.load('resource/img/dirt_tileset.png')

def random_ground(shape, threshold=0.5):
    w, h = shape
    w1, h1 = int(16 * np.ceil(w/16)), int(16 * np.ceil(h/16))
    noise = generate_fractal_noise_2d((w1, h1), (16, 16), octaves=1,
        persistence=0.5)
    
    # standardize noise to [0, 1]
    noise = (noise - noise.min()) / (noise.max() - noise.min())

    return np.where(noise > threshold, 1, 0)[:w, :h]

def get_tile(image, x, y):
    return image.subsurface((x*16, y*16, 16, 16))

def ground_img(screensize, seed=0):
    w = screensize[0] // 16
    h = screensize[1] // 16

    np.random.seed(seed)
    ground = random_ground((w, h), threshold=0.5)

    tile = np.zeros_like(ground)

    def mult_and_add(n: np.ndarray, ind, digit: int):
        n[ind] = n[ind] * 10 + digit

    u = np.roll(ground, 1, axis=1)
    d = np.roll(ground, -1, axis=1)
    l = np.roll(ground, 1, axis=0)
    r = np.roll(ground, -1, axis=0)

    # top left
    mult_and_add(tile, ((ground == np.roll(u, 1, axis=0)) &
        (ground == u) & (ground == l)), digit=1)
    
    # top
    mult_and_add(tile, ground == u, digit=2)

    # top right
    mult_and_add(tile, ((ground == np.roll(u, -1, axis=0)) &
        (ground == u) & (ground == r)), digit=3)
    
    # left
    mult_and_add(tile, ground == l, digit=4)

    # right
    mult_and_add(tile, ground == r, digit=6)

    # bottom left
    mult_and_add(tile, ((ground == np.roll(d, 1, axis=0)) &
        (ground == d) & (ground == l)), digit=7)
    
    # bottom
    mult_and_add(tile, ground == d, digit=8)

    # bottom right
    mult_and_add(tile, ((ground == np.roll(d, -1, axis=0)) &
        (ground == d) & (ground == r)), digit=9)
    
    surf = pygame.Surface(screensize)

    for x in range(w):
        for y in range(h):
            if ground[x, y] == 1:
                surf.blit(get_tile(GRASS, 5, 1), (x*16, y*16))
            else:
                x1, y1 = TILEDATA[str(tile[x, y])]
                surf.blit(get_tile(DIRT, x1, y1), (x*16, y*16))
    
    return surf
