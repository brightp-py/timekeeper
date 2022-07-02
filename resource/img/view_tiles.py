import pygame

img = pygame.image.load("resource/img/grass_tileset.png")
w, h = img.get_size()

screen = pygame.display.set_mode((500, 500))
clock = pygame.time.Clock()

img = pygame.transform.scale(img, (500 * w // 16, 500 * h // 16))
w, h = img.get_size()

x, y = 0, 0

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:
                x -= 500
                if x < 0:
                    x = w - 500
            elif event.key == pygame.K_RIGHT:
                x += 500
                if x >= w:
                    x = 0
            elif event.key == pygame.K_UP:
                y -= 500
                if y < 0:
                    y = h - 500
            elif event.key == pygame.K_DOWN:
                y += 500
                if y >= h:
                    y = 0
    screen.fill((0, 0, 0))
    screen.blit(img, (-x, -y))
    pygame.display.flip()
    clock.tick(60)