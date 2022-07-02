import pygame
import sys
import numpy as np
from copy import deepcopy

import random
import time
import json

from player import *
from world import Level

pygame.init()
pygame.mixer.init()

FONT = pygame.font.Font('resource/font/Atarian/SF Atarian System.ttf', 20)
BIGFONT = pygame.font.Font('resource/font/Atarian/SF Atarian System Bold.ttf',
    40)

class Matrix:
    """
    A numpy array that saves instructions for each player unit's actions.
    """

    def __init__(self, num_players=20, per_second=30, spawn_rate=1, actions=4):
        assert num_players % 2 == 0
        self.num_players = num_players
        self.per_second = per_second
        self.spawn_rate = spawn_rate
        self.actions = actions
        
        self.fps = self.spawn_rate * self.per_second
        self.data_height = num_players // 2
        self.data_width = (num_players + 1) * self.fps
        self.data = np.zeros((self.data_height, self.data_width, actions))
    
    def __getitem__(self, key):
        if key >= self.data_height:
            start = self.fps * (self.num_players - key)
            return self.data[self.num_players - key - 1, -start:]
        else:
            end = self.fps * (self.num_players - key)
            return self.data[key, :end]
    
    def save_action(self, frame, actions):
        self.data[0, frame, :] = actions
    
    def rotate(self):
        """
        The matrix saves data with two units' actions per row. So the shortest-
        living unit and longest-living unit are in the same row. This function
        cuts out one second of each unit's actions and moves the data to the
        next row.
        """
        for i in range(1, self.data_height):
            self.data[i-1, -self.fps*i:] = self.data[i, -self.fps*i:]
        bottom = self.data_height - 1
        half = self.data_height * self.fps
        self.data[bottom, -half:] = self.data[bottom, :half]
        for i in range(self.data_height-1, 0, -1):
            end = self.fps * (self.data_height * 2 - i)
            self.data[i, :end] = self.data[i-1, self.fps:self.fps+end]
        self.data[0, :-self.fps] = 0


class World:

    def __init__(self):
        self.bullets = []
        self.units = []
        self.enemies = []

        self.level = Level.from_image('level/test.png')
        self.spawn = self.level.spawn

        for loc in self.level.enemies:
            self.enemies.append(Enemy(loc))

        self.screenshake = np.zeros(2)
    
    def __deepcopy__(self, memo):
        new_world = World()
        new_world.bullets = deepcopy(self.bullets, memo)
        new_world.units = deepcopy(self.units, memo)
        new_world.enemies = deepcopy(self.enemies, memo)
        new_world.level = deepcopy(self.level, memo)
        new_world.spawn = deepcopy(self.spawn, memo)
        # new_world.screenshake = deepcopy(self.screenshake)
        return new_world
    
    def draw(self, screen, matrix, frame, shop=None):
        if self.units:
            camera = [
                self.units[0].x - screen.get_width() // 2,
                self.units[0].y - screen.get_height() // 2]
        else:
            camera = [0, 0]
        
        camera[0] += self.screenshake[0]
        camera[1] += self.screenshake[1]
        
        screen.fill((255, 255, 255))
        self.level.draw(screen, (
            camera[0] - 2 * self.screenshake[0],
            camera[1] - 2 * self.screenshake[1]))

        for bullet in self.bullets:
            bullet.draw(screen, camera)
        for unit in self.units + self.enemies:
            if unit.is_alive(matrix, frame):
                unit.draw(screen, camera)

        if np.any(self.screenshake):
            self.screenshake = -(self.screenshake // 2)
        
        # render money in the top right corner
        if shop:
            money = BIGFONT.render('$' + str(shop.money), True, (0, 0, 0))
            screen.blit(money,
                (screen.get_width() - money.get_width() - 10, 10))
    
    def update(self, matrix, frame, shop=None):
        
        # update the bullets
        for bullet in self.bullets:
            bullet.move()
            if bullet.health <= 0:
                self.bullets.remove(bullet)
                continue
            for unit in self.units + self.enemies:
                if unit.is_alive(matrix, frame) and bullet.collide(unit):
                    bullet.collided = unit
                    if 'on_hit' in dir(bullet):
                        bullet.on_hit(unit)
                    self.bullets.remove(bullet)
                    unit.get_hurt(bullet.damage)
                    if unit.id == 0:
                        self.screenshake = np.array(
                            [bullet.damage * random.choice((-1, 1)),
                             bullet.damage * random.choice((-1, 1))],
                            dtype=int)
                    elif unit.id == -1 and not unit.is_alive(matrix, frame):
                        if shop:
                            shop.collect(unit.reward)
                    break
            if not bullet.collided and bullet.collide_wall(self.level):
                self.bullets.remove(bullet)

        # update the units
        for unit in self.units:
            if unit.is_alive(matrix, frame):
                unit.do_action(matrix, frame, self.bullets, self.level)
        
        # update the enemies
        for enemy in self.enemies:
            if enemy.is_alive(matrix, frame):
                enemy.do_action(self.units, matrix, frame, self.bullets,
                    self.level)


class Shop:
    
    COLOR = {
        'Reload': (73, 220, 10),
        'Damage': (214, 10, 10),
        'Speed': (214, 214, 10),
        'Agility': (0, 210, 255),
        'Recovery': (110, 70, 250)
    }
    COLLECTSOUND = pygame.mixer.Sound('resource/sound/pickupCoin.wav')
    COLLECTSOUND.set_volume(0.5)

    def __init__(self):
        self.stats = {
            'Reload': 2,
            'Damage': 2,
            'Speed': 2,
            'Agility': 2,
            'Recovery': 2
        }

        self.data = json.load(open('resource/data/shop.json'))

        self.money = 1000
        self.inventory = [None, None, None, None]
        self.items = [None, None, None]

        # load images, if they are found
        # otherwise, use the image "Unknown"
        path = "resource/img/item/"
        unknown = pygame.image.load(path + "Unknown.png")
        unknown.set_colorkey((0, 0, 0))
        for item in self.data:
            try:
                self.data[item]['image'] = pygame.image.load(
                    path + item + ".png")
                self.data[item]['image'].set_colorkey((0, 0, 0))
            except:
                self.data[item]['image'] = unknown
            
    def collect(self, reward):
        self.money += reward
        self.COLLECTSOUND.play()
    
    def can_craft(self, item):
        space = self.inventory.count(None)
        for material, count in self.data[item]['materials'].items():
            space += 1
            if self.inventory.count(material) < count:
                return False
        return space > 0
    
    def craft(self, item):
        for material, count in self.data[item]['materials'].items():
            for _ in range(count):
                self.remove(self.inventory.index(material))
        self.inventory[self.inventory.index(None)] = item
    
    def refresh(self):

        # find all items that can be bought
        available = ["Armor", "Battery", "Magnifier", "Plasma", "Socks"]
        for name in self.data:
            if self.can_craft(name) and name not in available:
                available.append(name)
            
        # set weights
        weights = [1] * 5 + [3] * (len(available) - 5)
        
        # pick three random items to make available
        self.items = []
        for _ in range(3):
            i = random.choices(range(len(available)), k=1, weights=weights)[0]
            self.items.append(available[i])
            available.pop(i)
            weights.pop(i)
    
    def remove(self, i):
        item = self.inventory[i]
        self.inventory[i] = None

        for stat, value in self.data[item]['stats'].items():
            self.stats[stat] -= value
    
    def purchase(self, item_id):
        item = self.items[item_id]

        if item is None:
            return
        
        assert item in self.items

        if self.data[item]['cost'] > self.money or not self.can_craft(item):
            return False
        
        self.money -= self.data[item]['cost']
        self.craft(item)
        # self.items.remove(item)
        self.items[item_id] = None

        for stat, value in self.data[item]['stats'].items():
            self.stats[stat] += value
    
    def create_player(self, pos):
        player = Player(pos)
        # player = Minotaur(pos, 0)

        reload = (self.stats['Reload'] / 3) ** 2 + 0.3
        player.reload_time = int(30 / reload)
        player.damage = round((self.stats['Damage'] / 1.4) ** 1.5 + 1)
        player.damage = player.damage * player.reload_time / 30
    
        player.max_speed = 3 + self.stats['Agility']
        player.speed = player.max_speed
        player.bullet_speed = 7 + 2 * self.stats['Speed']
        player.recovery = (np.exp(self.stats['Recovery'] / 2 - 5))\
            * player.max_speed

        for item in self.inventory:
            if item in weapon_dict:
                player.main_gun = weapon_dict[item]()
                break
        
        # print(player.recovery, player.max_speed)

        return player
    
    def per_second(self, stat_name):
        if stat_name == 'Reload':
            reload = (self.stats['Reload'] / 3) ** 2 + 0.3
            reload_time = int(30 / reload)
            val = 30 / reload_time
            unit = "bullets/s"
        elif stat_name == 'Damage':
            val = round((self.stats['Damage'] / 1.4) ** 1.5 + 1)
            unit = "dps"
        elif stat_name == 'Speed':
            val = (7 + 2 * self.stats['Speed']) * 30
            unit = "px/s"
        elif stat_name == 'Agility':
            val = (3 + self.stats['Agility']) * 30
            unit = "px/s"
        elif stat_name == 'Recovery':
            speed = 3 + self.stats['Agility']
            val = (np.exp(self.stats['Recovery'] / 2 - 5)) * speed * 30
            unit = "(px/s)/s"
        return f"{val:.2f} {unit}"
    
    def get_pressed(self, screen, pos):
        w, h = screen.get_size()

        xs = [w // 2 + w // 30]
        xs.append(xs[0] + int(7 * w / 30))

        ys = [h // 22]
        ys.append(ys[0] + int(h / 4.5))
        ys.append(ys[0] + h // 2)
        ys.append(ys[1] + h // 2)

        for i, x in enumerate(xs):
            for j, y in enumerate(ys):
                if pos[0] >= x and pos[0] <= x + w // 5:
                    if pos[1] >= y and pos[1] <= y + h // 5:
                        if i == 1 and j == 1:
                            return 'Reload', 0
                        elif j < 2:
                            return 'Shop', j * 2 + i
                        else:
                            return 'Inventory', (j - 2) * 2 + i
        return 'None', None
    
    def draw_card(self, screen, pos, item):
        w, h = screen.get_size()
        w = w // 5
        h = h // 5
        xs, ys = pos
        xs += 5

        # draw the card background
        pygame.draw.rect(screen, (60, 60, 60), (pos[0], pos[1], w, h))
        if item is None:
            return

        # draw a label at the top of the tier's color
        # bronze, then silver, then gold
        tiers = [
            (163, 83, 36),
            (140, 140, 140),
            (219, 163, 22)
        ]
        pygame.draw.rect(screen, tiers[self.data[item]['tier'] - 1], (
            pos[0], pos[1], w, 25))
        
        # render the item name
        text = FONT.render(item, True, (255, 255, 255))
        screen.blit(text, (xs, ys + 3))

        # render the cost in the top right
        text = FONT.render(f"${self.data[item]['cost']}", True,
            (255, 255, 255))
        screen.blit(text, (xs + w - text.get_width() - 16, ys + 3))

        # blit the image
        text_h = text.get_height()
        img = pygame.transform.scale(self.data[item]['image'],
            (h - text_h, h - text_h))
        img.set_colorkey((0, 0, 0))
        screen.blit(img, (xs, ys + text_h))

        # render the item's stats with colored numbers on the right
        ys += h - 3
        for stat_name, stat_value in self.data[item]['stats'].items():
            text = BIGFONT.render(
                f"{'+' if stat_value > 0 else '-'} {str(abs(stat_value))}",
                True, Shop.COLOR[stat_name])
            ys -= text.get_height()
            if ys <= pos[1] + 25:
                ys += text.get_height() * 2
                xs -= 50
            screen.blit(text, (xs + w - text.get_width() - 16, ys))
    
    def draw_shop(self, screen):

        w, h = screen.get_size()

        # fill the left half black and the right half gray over white
        screen.fill((0, 0, 0), (0, 0, w // 2, h))
        screen.fill((120, 120, 120), (w // 2, 0, w // 2, h))
        screen.fill((255, 255, 255), (w // 2, h // 2, w // 2, h // 2))

        # write the money in the bottom-left corner of the right side
        text = FONT.render('$' + str(self.money), True, (255, 255, 255))
        screen.blit(text, (w // 2, h - text.get_height()))

        # draw a horizontal bar for each stat on the left side
        x = w // 10
        y = h // 12
        bar_w = w // 2 - x * 2
        bar_h = h // 6
        for i, stat in enumerate(self.stats):
            y_here = y + i * bar_h
            color = Shop.COLOR[stat]

            statname = "Bullet Speed" if stat == "Speed" else stat

            text = FONT.render(f"{statname} ({self.per_second(stat)})",
                True, color)
            screen.blit(text, (x, y_here))

            if self.stats[stat] == 10:
                color = (255, 255, 255)
            for j in range(self.stats[stat]):
                pygame.draw.rect(screen, color, (x + j * bar_w // 10,
                    y_here + text.get_height(), bar_w // 11,
                    int(bar_h * 0.9) - text.get_height()))

        # draw the inventory
        x = w // 2 + w // 30
        y = h // 2 + h // 22
        for i, item in enumerate(self.inventory):
            dx = (i % 2) * int(7 * w / 30)
            dy = (i // 2) * int(h / 4.5)
            self.draw_card(screen, (x + dx, y + dy), item)
        
        # draw the items in the shop above the inventory
        x = w // 2 + w // 30
        y = h // 22
        for i, item in enumerate(self.items):
            dx = (i % 2) * int(7 * w / 30)
            dy = (i // 2) * int(h / 4.5)
            self.draw_card(screen, (x + dx, y + dy), item)
        
        # add a refresh button with the text "Refresh" with the items
        x += int(7 * w / 30)
        y += int(h / 4.5)
        text = BIGFONT.render("Refresh", True, (255, 255, 255))
        pygame.draw.rect(screen, self.COLOR['Reload'], (x, y, w // 5, h // 5))
        screen.blit(text, (x + w // 10 - text.get_width() // 2,
            y + h // 10 - text.get_height() // 2))
        
        # draw a green arrow in the bottom-right corner of the right side
        # pygame.draw.polygon(screen, (0, 255, 0), [
        #     (int(w * 0.91), int(h * 0.93)),
        #     (int(w * 0.91), int(h * 0.97)),
        #     (int(w * 0.95), int(h * 0.97)),
        #     (int(w * 0.95), int(h * 0.99)),
        #     (int(w * 0.99), int(h * 0.95)),
        #     (int(w * 0.95), int(h * 0.91)),
        #     (int(w * 0.95), int(h * 0.93)),])
    
    def draw(self, screen, bar_h):
        w, h = screen.get_size()

        # draw a golden bar at the top of the screen
        pygame.draw.rect(screen, Shop.COLOR['Damage'], (0, 0, w, bar_h))

        # render money in the top left corner
        text = BIGFONT.render('$' + str(self.money), True, (255, 255, 255))
        dy = (bar_h - text.get_height()) // 2
        screen.blit(text, (dy, dy))

        shopsurf = pygame.Surface((w, h - bar_h))
        self.draw_shop(shopsurf)
        screen.blit(shopsurf, (0, bar_h))
    
    def run(self, screen):
        w, h = screen.get_size()
        self.refresh()

        bar_h = 60

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        pos = pygame.mouse.get_pos()
                        if pos[0] > w - 60 and pos[1] < 60:
                            screen.fill((0, 0, 0))
                            pygame.display.flip()
                            return
                        
                        action, pressed = self.get_pressed(screen,
                            (pos[0], pos[1] - bar_h))
                        if action == 'Reload':
                            self.refresh()
                        elif action == 'Shop':
                            # print(self.items[pressed])
                            self.purchase(pressed)
                        elif action == 'Inventory':
                            self.money += self.data[self.inventory[pressed]]['cost']
                            self.remove(pressed)
            
            self.draw(screen, bar_h)
            pygame.display.flip()
            pygame.time.wait(10)


class TimeKeeper:

    def __init__(self, screensize):
        self.w, self.h = screensize
        self.screen = pygame.display.set_mode(screensize)
        pygame.display.set_caption("Time Keeper")
        self.clock = pygame.time.Clock()

        self.world = World()

        self.shop = Shop()

        self.num_players = 20
        self.per_second = 30
        self.spawn_rate = 1
        
        self.matrix = Matrix(self.num_players, self.per_second,
            self.spawn_rate)

        pygame.mixer.music.load('resource/sound/20sec.mp3')
        # pygame.mixer.music.set_volume(0)

        self.reset()
    
    def wait(self, n):
        for _ in range(int(n * self.per_second)):
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    sys.exit()
            self.clock.tick(30)
    
    def reset(self):

        self.shop.run(self.screen)

        pygame.mixer.music.rewind()
        pygame.mixer.music.play(1)
        
        self.wait(2)

        Unit.mute()
        for frame in range(self.per_second * self.spawn_rate):
            self.world.update(self.matrix, frame)
            self.world.draw(self.screen, self.matrix, frame)
            pygame.display.flip()
            self.clock.tick(30)
        Unit.unmute()

        start = time.time()

        self.matrix.rotate()
        for unit in self.world.units:
            unit.set_id(unit.id + 1)
            if unit.id >= self.num_players:
                self.world.units.remove(unit)
        # new_player = Player(self.world.spawn, 0)
        new_player = self.shop.create_player(self.world.spawn)

        self.world.units = [new_player] + self.world.units
        self.instance = deepcopy(self.world)
        self.instance.screenshake = np.zeros(2)
        self.frame = 0

        interval = time.time() - start

        self.wait(1 - float(interval))
    
    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    sys.exit()
            
            action = Player.read_action(self.screen, pygame.mouse.get_pos(),
                pygame.mouse.get_pressed())
            self.matrix.save_action(self.frame, action)

            self.clock.tick(30)
            self.instance.update(self.matrix, self.frame, self.shop)
            self.instance.draw(self.screen, self.matrix, self.frame, self.shop)
            pygame.display.flip()
            self.frame += 1

            if self.frame >= self.per_second * self.spawn_rate * self.num_players:
                self.screen.fill((0, 0, 0))
                pygame.display.flip()
                self.wait(4)
                self.reset()


if __name__ == "__main__":
    game = TimeKeeper((1000, 700))
    game.run()
