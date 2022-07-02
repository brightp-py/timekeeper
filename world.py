import pygame
import numpy as np

from generate import ground_img

class Level:
    """
    An environment for units to travel in.

    Attributes:
        terrain: A 2D numpy array of integers. 0 is empty, 1 is wall.
        spawn: A tuple (x, y) of the spawn location.
        enemies: A list of Enemy spawn locations.
    """

    def __init__(self, terrain: np.array, spawn, enemies, ground=None):
        self.terrain = terrain
        self.spawn = spawn
        self.enemies = enemies

        self.w, self.h = terrain.shape
        if ground:
            self.ground = ground
        else:
            self.ground = ground_img((self.w, self.h))
        
        self.terrain_flat = self.terrain.flatten()
        
    def _flat(self, n):
        if n.shape == (2,):
            # single point
            return (n[0].astype(int) * self.h + n[1]).astype(int)
        return (n[:, 0].astype(int) * self.h + n[:, 1]).astype(int)
    
    def __deepcopy__(self, _):
        return Level(self.terrain.copy(), self.spawn, self.enemies,
            self.ground)
    
    def __getitem__(self, key):
        if key.shape == (0,):
            return []
        return self.terrain_flat[self._flat(key)]
        
    @staticmethod
    def from_image(filepath):
        img = pygame.image.load(filepath)
        data = pygame.surfarray.pixels3d(img)

        # terrain is a 2D array of integers. 1 where data is black, else 0.
        terrain = np.all(data == (0, 0, 0), axis=2).astype(int)

        # find the spawn location, where the image is blue
        spawn = np.argwhere(np.all(data == (0, 0, 255), axis=2))[0]

        # find the enemy spawn locations, where the image is red
        enemies = np.argwhere(np.all(data == (255, 0, 0), axis=2))

        return Level(terrain, spawn, enemies)
    
    def set_at(self, key, value):
        self.terrain_flat[self._flat(key)] = value
        self.terrain = self.terrain_flat.reshape((self.w, self.h))
    
    def draw(self, screen, camera):
        
        left, top = map(int, camera)

        offset_l, offset_t = 0, 0
        if left < 0:
            offset_l = -left
            left = 0
        if top < 0:
            offset_t = -top
            top = 0
        
        right = left + screen.get_width() + 1
        bottom = top + screen.get_height() + 1

        # generate a surface with the terrain
        terr = self.terrain[left:right, top:bottom].astype(np.uint8) * 255
        surf = pygame.surfarray.make_surface(terr)
        surf.set_colorkey((0, 0, 0))

        # draw the terrain
        screen.blit(self.ground, (-camera[0], -camera[1]))
        screen.blit(surf, (offset_l, offset_t))
        # if offset_l > 0:
        #     pygame.draw.rect(screen, (255, 255, 255), 
        #         (0, 0, offset_l, screen.get_height()))
        # if offset_t > 0:
        #     pygame.draw.rect(screen, (255, 255, 255), 
        #         (0, 0, screen.get_width(), offset_t))
        # if right > self.w:
        #     pygame.draw.rect(screen, (255, 255, 255), 
        #         (right - self.w, 0, screen.get_width(), screen.get_height()))
        # if bottom > self.h:
        #     pygame.draw.rect(screen, (255, 255, 255), 
        #         (0, bottom - self.h, screen.get_width(), screen.get_height()))

if __name__ == "__main__":
    test = Level.from_image("level/test.png")
    print(test.terrain.shape)
    print(test.spawn)
    print(test.enemies)
