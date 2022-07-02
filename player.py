from pickle import FALSE
import pygame
import numpy as np
import skimage.draw as draw

pygame.mixer.init()
pygame.mixer.set_num_channels(8)

DEBUG = False

shoot_channel = pygame.mixer.Channel(5)

class Unit:
    """
    A character that can be played by the player or by an AI. The character
    can follow the mouse cursor and shoot in any direction.
    """
    SIDE = 20

    SHOOT_SOUND = pygame.mixer.Sound('resource/sound/laserShoot.wav')
    SHOOT_SOUND.set_volume(0.1)
    SHOOT_QUIET = pygame.mixer.Sound('resource/sound/laserShoot.wav')
    SHOOT_QUIET.set_volume(0.1)
    HURT_SOUND = pygame.mixer.Sound('resource/sound/hitHurt.wav')
    HURT_SOUND.set_volume(0.4)
    silent = False

    def __init__(self, pos, color):
        self.x, self.y = pos
        self.reload = 0 # time until next shot
        self.reload_time = 9 # time between shots
        self.bullet_speed = 8
        self.damage = 4

        self.main_color = color
        self.main_gun = Gun()

        self.color = color
        self.gun = self.main_gun
        
        self.id = -1
        self.cursor_loc = (0, 0)

        # collision radius is the maximum possible distance from the center of
        # the unit that a bullet could collide with it
        self.collision_radius = Unit.SIDE * np.sqrt(2) / 2

        self.hitzone = np.array([])

        self.effects = []
    
    @staticmethod
    def mute():
        Unit.silent = True
    
    @staticmethod
    def unmute():
        Unit.silent = False
    
    def get_pos(self):
        return np.array((self.x, self.y))
    
    def draw(self, screen, camera):
        # create a Surface object to draw the unit on first
        unit = pygame.Surface((Unit.SIDE, Unit.SIDE))
        unit.fill((0, 0, 0))
        unit.set_colorkey((0, 0, 0))

        # get relative position of the unit
        x = int(self.x - Unit.SIDE // 2 - camera[0])
        y = int(self.y - Unit.SIDE // 2 - camera[1])

        # save the center of the Surface
        center_x, center_y = Unit.SIDE // 2, Unit.SIDE // 2

        # draw a circle centered on the unit's position
        pygame.draw.circle(unit, self.color, (center_x, center_y),
            int(Unit.SIDE * 0.35))

        # draw a cursor where the unit is aiming
        pygame.draw.circle(unit, self.color,
            (center_x + self.cursor_loc[0], center_y + self.cursor_loc[1]),
            int(Unit.SIDE * 0.08))

        # save all non-black pixels in the hitzone
        self.hitzone = np.transpose(np.array(np.where(
            np.any(pygame.surfarray.pixels3d(unit) != 0, 2)), dtype=float))
        self.hitzone += (self.x, self.y)
        self.hitzone += 0.5 - Unit.SIDE // 2
        
        # draw the unit on the screen
        screen.blit(unit, (x, y))

        return x, y
    
    def add_effect(self, f):
        self.effects.append(f)

    def update(self):
        self.color = self.main_color
        self.gun = self.main_gun

        done = []
        for i, effect in enumerate(self.effects):
            if effect(self):
                done.append(i)

        for i in done[::-1]:
            self.effects.pop(i)

    def shoot(self, bullets, direction, **argv):
        # add a bullet to the list of bullets
        self.gun.shoot(bullets, (self.x + direction[0], self.y + direction[1]),
            direction, self, self.color, self.damage)
        # bullets.append(Bullet((self.x + direction[0], self.y + direction[1]),
        #     direction, self, self.color, self.damage))
        if not Unit.silent and not shoot_channel.get_busy():
            if self.id == 0:
                # Unit.SHOOT_SOUND.play()
                shoot_channel.play(Unit.SHOOT_SOUND)
            else:
                # Unit.SHOOT_QUIET.play()
                shoot_channel.play(Unit.SHOOT_QUIET)
            
    def move(self, speed: int, direction, level):
        if direction[0] == 0 and direction[1] == 0:
            return
        
        if self.hitzone.shape == (0,):
            return
        
        direction = np.array(direction)
        direction /= np.linalg.norm(direction)

        # iteratively move the unit and check for collisions
        for i in range(1, int(speed) + 1):
            if np.any(level[self.hitzone + direction * i] != 0):
                break
            self.x += direction[0]
            self.y += direction[1]


class Player(Unit):
    """
    A controllable unit.
    """

    COLOR = (0, 255, 255)
    COLOR_GHOST = (255, 255, 255)

    def __init__(self, pos, id=0):
        super().__init__(pos, Player.COLOR if id==0 else Player.COLOR_GHOST)
        self.id = id
        self.max_speed = 4
        self.speed = self.max_speed
        self.recovery = 0.02
    
    # def __deepcopy__(self, memo):
    #     new_unit = Player((self.x, self.y), self.id)
    #     new_unit.speed = self.speed
    #     new_unit.max_speed = self.max_speed
    #     new_unit.reload = self.reload
    #     new_unit.reload_time = self.reload_time
    #     new_unit.cursor_loc = self.cursor_loc
    #     new_unit.hitzone = self.hitzone.copy()
    #     return new_unit
    
    def set_id(self, id):
        self.id = id
        self.color = Player.COLOR if id==0 else Player.COLOR_GHOST
    
    def is_alive(self, matrix, frame):
        return frame < (matrix.num_players - self.id) * matrix.fps
    
    def get_hurt(self, damage):
        self.speed = self.max_speed / (damage + 1)
        if self.id == 0 and not Unit.silent:
            Unit.HURT_SOUND.play()
    
    def do_action(self, matrix, frame, bullets, level):
        self.update()

        # current setup is four actions:
        # 0: mouse position x from center
        # 1: mouse position y from center
        # 2: stop moving
        # 3: shoot
        actions = matrix[self.id][frame]

        # if distance > Unit.SIDE/2, use full speed.
        # else, use speed based on distance
        distance = np.sqrt(actions[0]**2 + actions[1]**2) + 1e-8
        if distance > Unit.SIDE/2:
            speed = self.speed
        else:
            speed = self.speed * distance / Unit.SIDE
        
        # heal speed
        if self.speed < self.max_speed:
            self.speed += self.recovery
            if self.speed > self.max_speed:
                self.speed = self.max_speed
        
        # get unit vector of the direction
        u_dir = (actions[0] / distance, actions[1] / distance)
        
        # move the character
        if distance > 4 and not actions[2]:
            # self.x += speed * u_dir[0]
            # self.y += speed * u_dir[1]
            self.move(speed, u_dir, level)
        
        # set cursor location to where the unit is aiming
        self.cursor_loc = (u_dir[0] * 0.45 * Unit.SIDE,
            u_dir[1] * 0.45 * Unit.SIDE)

        # if shooting, reload
        if self.reload > 1:
            self.reload -= 1
            return
        if actions[3]:
            self.reload = self.reload_time
            dx = self.bullet_speed * u_dir[0]
            dy = self.bullet_speed * u_dir[1]
            self.shoot(bullets, (dx, dy))
    
    @staticmethod
    def read_action(screen, mouse_pos, mouse_pressed):
        center_x = screen.get_width() // 2
        center_y = screen.get_height() // 2
        x, y = mouse_pos
        x -= center_x
        y -= center_y
        return [x, y, mouse_pressed[0], mouse_pressed[2]]
    

class Enemy(Unit):
    """
    A unit that fires at the Player and has HP.
    """

    def __init__(self, pos):
        super().__init__(pos, (255, 0, 0))
        self.speed = 3
        self.hp = 10
        self.reload = 0
        self.reload_time = 9

        self.reward = 2
    
    def is_alive(self, _, __):
        return self.hp > 0
    
    def get_hurt(self, damage):
        self.hp -= damage
        if DEBUG:
            print(self.hp)
        if self.hp <= 0:
            self.hp = 0
        
    def do_action(self, units, matrix, frame, bullets, level):
        self.update()

        if len(units) == 0:
            return

        # pick a player to target
        def distance(unit):
            denom = 1 if unit.is_alive(matrix, frame) else 1e-10
            return np.linalg.norm(unit.get_pos() - self.get_pos()) / denom
        target = min(units, key=distance)
        target_dis = np.linalg.norm(target.get_pos() - self.get_pos())
        
        if target_dis > 300:
            return
        
        # move towards the target if not too close
        u_dir = (target.get_pos() - self.get_pos()) / np.linalg.norm(
            target.get_pos() - self.get_pos())
        if target_dis > 100:
            # self.x += self.speed * u_dir[0]
            # self.y += self.speed * u_dir[1]
            self.move(self.speed, u_dir, level)

        # set cursor location to where the unit is aiming
        self.cursor_loc = (u_dir[0] * 0.45 * Unit.SIDE,
            u_dir[1] * 0.45 * Unit.SIDE)
        
        # shoot at the target
        if self.reload > 1:
            self.reload -= 1
            return
        dx = Bullet.SPEED * u_dir[0]
        dy = Bullet.SPEED * u_dir[1]
        self.shoot(bullets, (dx, dy))
        self.reload = self.reload_time


class Bullet:
    """
    A short beam that travels in a single direction until it hits something.
    """

    SPEED = 12
    LIFESPAN = 60

    def __init__(self, pos, vel, parent, color, damage = 4):
        self.x, self.y = pos
        self.vel = vel
        self.parent = parent
        self.color = color
        self.health = Bullet.LIFESPAN
        self.damage = damage
        self.speed = np.sqrt(self.vel[0]**2 + self.vel[1]**2)

        self.collided = False
    
    def is_alive(self):
        return self.health > 0 and not self.collided
    
    def get_pos(self):
        return self.x, self.y
    
    def get_explosion(self, center):
        # return a list of points that make up the circular explosion
        rad = int(np.sqrt(self.damage) * 3)
        x0, y0 = center
        
        # create a list of points from x - rad to x + rad, y - rad to y + rad
        points = []
        for x in range(int(x0) - rad, int(x0) + rad + 1):
            for y in range(int(y0) - rad, int(y0) + rad + 1):
                if np.linalg.norm(np.array([x, y]) - center) <= rad:
                    points.append((x, y))
        
        return np.array(points)

    def draw(self, screen, camera):
        # get relative position of the bullet
        x, y = self.x - camera[0], self.y - camera[1]

        # draw a line from the front of the bullet to the back
        pygame.draw.line(screen, self.color, (x, y),
            (int(x - self.vel[0]), int(y - self.vel[1])), 3)
        
        if DEBUG:
            left = x - (self.vel[0] if self.vel[0] > 0 else 0) - 4
            right = x - (self.vel[0] if self.vel[0] < 0 else 0) + 4
            top = y - (self.vel[1] if self.vel[1] > 0 else 0) - 4
            bottom = y - (self.vel[1] if self.vel[1] < 0 else 0) + 4

            pygame.draw.rect(screen, (255, 255, 0),
                (left, top, right - left, bottom - top), 1)

    def move(self):
        # move the bullet in the direction it is facing
        self.x += self.vel[0]
        self.y += self.vel[1]
        self.health -= 1
    
    def distanceFromPoint(self, x, y, points: np.ndarray):
        if self.vel[0] < 1:
            return np.abs(points[:, 0] - x)
        
        if self.vel[1] < 1:
            return np.abs(points[:, 1] - y)
        
        return np.abs(
            -self.vel[0] * (x - points[:, 0]) -
            -self.vel[1] * (y - points[:, 1])) / self.speed
    
    def collide(self, unit):
        if self.health == Bullet.LIFESPAN or unit.id == self.parent.id or \
            unit.hitzone.shape[0] == 0:
            return False

        # get left, right, top, bottom of the bullet
        left = self.x - (self.vel[0] if self.vel[0] > 0 else 0) - 4
        right = self.x - (self.vel[0] if self.vel[0] < 0 else 0) + 4
        top = self.y - (self.vel[1] if self.vel[1] > 0 else 0) - 4
        bottom = self.y - (self.vel[1] if self.vel[1] < 0 else 0) + 4

        colliding = (
            (left <= unit.hitzone[:, 0]) & (right >= unit.hitzone[:, 0]) &
            (top <= unit.hitzone[:, 1]) & (bottom >= unit.hitzone[:, 1]) &
            (self.distanceFromPoint(self.x, self.y, unit.hitzone) <= 2))
        
        return np.any(colliding)
    
    def collide_wall(self, level):
        
        back = np.array([self.x - self.vel[0], self.y - self.vel[1]],
            dtype=int)
        rr, cc = draw.line(int(self.x), int(self.y), back[0], back[1])
        points = np.array(list(zip(rr, cc)))

        colliding = level[points]
        self.collided = np.any(colliding)
        if self.collided:
            center = min(points[level[points] > 0],
                key=lambda p: np.linalg.norm(p - back))
            level.set_at(self.get_explosion(center), 0)

        return self.collided


# Characters

# Minotaur
# Follows the last sent bullet as long as the player is holding right-click
# If the player releases right-click, the minotaur will stop following

class Minotaur(Player):

    def __init__(self, pos, id):
        super().__init__(pos, id)

        self.ride = None
    
    def do_action(self, matrix, frame, bullets, level):
        # current setup is four actions:
        # 0: mouse position x from center
        # 1: mouse position y from center
        # 2: stop moving
        # 3: shoot
        actions = matrix[self.id][frame]

        # if right-click is lifted, stop following the bullet
        if self.ride and (not actions[3] or not self.ride.is_alive()):
            if self.ride.collided and isinstance(self.ride.collided, Unit):
                self.ride.collided.reload += 30
            self.ride = None

        # if distance > Unit.SIDE/2, use full speed.
        # else, use speed based on distance
        distance = np.sqrt(actions[0]**2 + actions[1]**2) + 1e-8
        if distance > Unit.SIDE/2:
            speed = self.speed
        else:
            speed = self.speed * distance / Unit.SIDE
        
        # heal speed
        if self.speed < self.max_speed:
            self.speed += 0.1
            if self.speed > self.max_speed:
                self.speed = self.max_speed
        
        # get unit vector of the direction
        u_dir = (actions[0] / distance, actions[1] / distance)
        
        # move the character
        if self.ride:
            self.x, self.y = self.ride.get_pos()
        elif distance > 4 and not actions[2]:
            self.x += speed * u_dir[0]
            self.y += speed * u_dir[1]
        
        # set cursor location to where the unit is aiming
        self.cursor_loc = (u_dir[0] * 0.55 * Unit.SIDE,
            u_dir[1] * 0.55 * Unit.SIDE)

        # if shooting, reload
        if self.reload > 0 and not self.ride:
            self.reload -= 1
            return
        if actions[3] and self.reload <= 0:
            self.reload = self.reload_time
            dx = Bullet.SPEED * u_dir[0]
            dy = Bullet.SPEED * u_dir[1]
            self.shoot(bullets, (dx, dy))
            if not self.ride and not actions[2]:
                self.ride = bullets[-1]

# Blood-bender
# Summons bullets from in-range corpses

# Reloader
# Saves the game at a certain position and time and reloads it when the player
# clicks on the character

# Echo
# Spawns an echo of the character when the player gets a kill

# Trapper
# Spawns a bomb that explodes into 8 bullets after a certain time


# Weapons

class Gun:
    
    def shoot(self, bullets, pos, vel, parent, color, damage, **argv):
        bullets.append(Bullet(pos, vel, parent, color, damage))

# Vaporized Soup
# Each bullet applies the "burn" effect to the unit it hits, causing additional
# damage over time.

class SoupBullet(Bullet):

    def __init__(self, pos, vel, parent, color, damage):
        super().__init__(pos, vel, parent, color, 1)
        self.burn = damage
    
    @staticmethod
    def do_burn(unit):
        unit.color = (255, 150, 0)
        unit.get_hurt(1)
        unit.burn -= 1
        if unit.burn <= 0:
            return True
        return False

    def on_hit(self, unit):
        unit.burn = self.burn
        unit.add_effect(SoupBullet.do_burn)

class VaporizedSoup(Gun):

    def shoot(self, bullets, pos, vel, parent, color, damage, **argv):
        bullets.append(SoupBullet(pos, vel, parent, color, damage))

# Crossbow
# The player charges the crossbow and shoots a bullet with high damage

# Laser
# The bullet travels its full distance instantly

# Heat-seeker
# The bullet swerves towards enemies and explodes on contact

# BB-Gun
# The bullet rebounds off of the first enemy it hits

# Drill
# The bullet moves through and destroys walls

weapon_dict = {
    'Vaporized Soup': VaporizedSoup
}