import os
import pygame
from pygame.locals import *
import time
import sys

# Get folder from command line
if len(sys.argv) < 2:
    print("Usage: python3 mixer3.py /path/to/music_folder")
    sys.exit(1)

MUSIC_FOLDER = sys.argv[1]
FADE_DURATION = 15000  # 15 seconds in milliseconds
MANUAL_BPM = {
    "song1.mp3": 128,
    "song2.mp3": 124,
    "song3.mp3": 130
}

# Initialize Pygame
pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2)
screen = pygame.display.set_mode((800, 800))
pygame.display.set_caption("H-Dj Set")
font = pygame.font.SysFont(None, 32)
clock = pygame.time.Clock()

# Load background image
background_img = pygame.image.load("./vinyl.png").convert()
background_img = pygame.transform.scale(background_img, screen.get_size())

# Preload overlay
overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
overlay.fill((0, 0, 0, 120))

# Song loading with UI feedback
def show_loading_screen(messages):
    screen.blit(background_img, (0, 0))
    screen.blit(overlay, (0, 0))

    title = font.render("🎧 Loading Songs...", True, (255, 255, 255))
    screen.blit(title, (30, 30))

    for i, msg in enumerate(messages[-15:]):
        line = font.render(msg, True, (180, 220, 255))
        screen.blit(line, (50, 80 + i * 30))

    pygame.display.flip()

def load_music_folder(folder_path):
    music_files = []
    messages = []
    for file in sorted(os.listdir(folder_path)):
        if file.lower().endswith(".mp3"):
            full_path = os.path.join(folder_path, file)
            try:
                sound = pygame.mixer.Sound(full_path)
                bpm = MANUAL_BPM.get(file, 120)
                music_files.append({
                    'file': file,
                    'sound': sound,
                    'bpm': bpm
                })
                msg = f"✅ Loaded: {file} (BPM: {bpm})"
                messages.append(msg)
                show_loading_screen(messages)
                time.sleep(0.2)
            except Exception as e:
                msg = f"❌ Error loading {file}: {str(e)}"
                messages.append(msg)
                show_loading_screen(messages)
                time.sleep(0.5)
    return music_files

songs = load_music_folder(MUSIC_FOLDER)
if not songs:
    show_loading_screen(["❌ No valid MP3 files found!"])
    time.sleep(2)
    pygame.quit()
    sys.exit()

# Setup audio
channels = [pygame.mixer.Channel(i) for i in range(2)]
current_channel = 0
current_song_idx = 0
last_fade_start = 0

def get_beat_interval(bpm):
    return (60 / bpm) * 1000

# Start first song
channels[current_channel].play(songs[current_song_idx]['sound'], loops=0)
channels[current_channel].set_volume(1.0)

# Main loop
running = True
while running:
    now = pygame.time.get_ticks()

    for event in pygame.event.get():
        if event.type == QUIT:
            running = False

        if (event.type == KEYDOWN and event.key == K_SPACE and last_fade_start == 0) or \
           (last_fade_start == 0 and not channels[current_channel].get_busy()):

            next_song_idx = (current_song_idx + 1) % len(songs)
            next_channel = (current_channel + 1) % 2
            current_song = songs[current_song_idx]
            next_song = songs[next_song_idx]

            current_bpm = current_song['bpm']
            beat_interval = get_beat_interval(current_bpm)

            channels[next_channel].play(next_song['sound'], loops=0)
            channels[next_channel].set_volume(0.0)
            last_fade_start = now

    # Handle fading
    if last_fade_start > 0:
        elapsed = now - last_fade_start
        if elapsed <= FADE_DURATION:
            progress = elapsed / FADE_DURATION
            channels[current_channel].set_volume(1.0 - progress)
            channels[(current_channel + 1) % 2].set_volume(progress)
        else:
            channels[current_channel].stop()
            current_channel = (current_channel + 1) % 2
            current_song_idx = (current_song_idx + 1) % len(songs)
            last_fade_start = 0

    # === UI Drawing ===
    # === Fancy UI Drawing ===
    screen.blit(background_img, (0, 0))
    screen.blit(overlay, (0, 0))

    # 🎛️ Title
    title_font = pygame.font.SysFont("comicsansms", 42)
    title_shadow = title_font.render(" H-DJ Mixer", True, (0, 0, 0))
    title_text = title_font.render("H-DJ Mixer", True, (255, 200, 50))
    screen.blit(title_shadow, (52, 22))
    screen.blit(title_text, (50, 20))

    # 🎵 Now Playing
    song_font = pygame.font.SysFont("arialblack", 28)
    label_shadow = song_font.render("Now Playing:", True, (0, 0, 0))
    label_text = song_font.render("Now Playing:", True, (255, 255, 0))
    screen.blit(label_shadow, (60 + 2, 100 + 2))
    screen.blit(label_text, (60, 100))

    current_song = songs[current_song_idx]['file']
    current_text = font.render(current_song, True, (255, 255, 255))
    current_shadow = font.render(current_song, True, (0, 0, 0))
    screen.blit(current_shadow, (60 + 2, 140 + 2))
    screen.blit(current_text, (60, 140))

    # ⏭️ Next
    next_idx = (current_song_idx + 1) % len(songs)
    next_song = songs[next_idx]['file']
    next_label = song_font.render("Up Next:", True, (100, 255, 255))
    next_shadow = song_font.render("Up Next:", True, (0, 0, 0))
    screen.blit(next_shadow, (60 + 2, 190 + 2))
    screen.blit(next_label, (60, 190))

    next_text = font.render(next_song, True, (255, 255, 255))
    next_shadow = font.render(next_song, True, (0, 0, 0))
    screen.blit(next_shadow, (60 + 2, 230 + 2))
    screen.blit(next_text, (60, 230))

    # Progress bar background
    bar_x, bar_y, bar_w, bar_h = 60, 300, 680, 30
    pygame.draw.rect(screen, (255, 255, 255), (bar_x, bar_y, bar_w, bar_h), 3, border_radius=15)

    # Progress bar fill
    if last_fade_start > 0:
        progress = min((now - last_fade_start) / FADE_DURATION, 1.0)
        fill_width = int(bar_w * progress)
        pygame.draw.rect(screen, (255, 100, 200), (bar_x, bar_y, fill_width, bar_h), border_radius=15)
        # Neon glow edge
        pygame.draw.rect(screen, (255, 180, 255), (bar_x, bar_y, fill_width, bar_h), 2, border_radius=15)

    # Next Button
    next_button_rect = pygame.Rect(600, 700, 160, 50)
    mouse_hover = next_button_rect.collidepoint(pygame.mouse.get_pos())
    button_color = (255, 80, 120) if mouse_hover else (255, 50, 100)
    pygame.draw.rect(screen, button_color, next_button_rect, border_radius=20)
    pygame.draw.rect(screen, (255, 255, 255), next_button_rect, 3, border_radius=20)

    next_button_text = font.render("▶ Next Track", True, (255, 255, 255))
    screen.blit(next_button_text, (next_button_rect.x + 15, next_button_rect.y + 12))

    pygame.display.flip()

    # Handle mouse click on button
    if pygame.mouse.get_pressed()[0] and mouse_hover and last_fade_start == 0:
        pygame.event.post(pygame.event.Event(KEYDOWN, key=K_SPACE))
        time.sleep(0.2)


pygame.quit()

