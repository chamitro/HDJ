import os
import pygame
from pygame.locals import *
import time
import sys
import librosa
import soundfile as sf

# Config
FADE_DURATION = 15000
DEFAULT_BPM = 120

# Init
pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2)
screen = pygame.display.set_mode((800, 800))
pygame.display.set_caption("H-Dj Mixer")
pause_for_bpm_choice = True
font = pygame.font.SysFont(None, 32)
clock = pygame.time.Clock()
popup_font = pygame.font.SysFont("comicsansms", 28)

background_img = pygame.image.load("vinyl.jpg").convert()
background_img = pygame.transform.scale(background_img, screen.get_size())
overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
overlay.fill((0, 0, 0, 120))

songs = []
channels = [pygame.mixer.Channel(i) for i in range(2)]
current_channel = 0
current_song_idx = 0
last_fade_start = 0
music_folder = None
loading_messages = []
bpm_analysis_enabled = False


def get_beat_interval(bpm):
    return (60 / bpm) * 1000


def show_drag_in_message():
    screen.blit(background_img, (0, 0))
    screen.blit(overlay, (0, 0))
    title = font.render("---> Drop your music folder here", True, (255, 255, 255))
    screen.blit(title, (180, 370))
    pygame.display.flip()


def ask_bpm_analysis():
    global bpm_analysis_enabled
    screen.blit(background_img, (0, 0))
    screen.blit(overlay, (0, 0))
    msg = popup_font.render("Analyze BPM automatically? (Y/N)", True, (255, 255, 255))
    screen.blit(msg, (140, 370))
    pygame.display.flip()

    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == KEYDOWN:
                if event.unicode.lower() == 'y':
                    bpm_analysis_enabled = True
                    waiting = False
                elif event.unicode.lower() == 'n':
                    bpm_analysis_enabled = False
                    waiting = False

    screen.blit(background_img, (0, 0))
    screen.blit(overlay, (0, 0))
    pygame.display.flip()


def show_loading_screen(messages):
    screen.blit(background_img, (0, 0))
    screen.blit(overlay, (0, 0))
    title = font.render("<...> Loading Songs...", True, (255, 255, 255))
    screen.blit(title, (30, 30))
    for i, msg in enumerate(messages[-15:]):
        line = font.render(msg, True, (180, 220, 255))
        screen.blit(line, (50, 80 + i * 30))
    pygame.display.flip()


def detect_bpm(path):
    try:
        y, sr = librosa.load(path, sr=None, mono=True, duration=120.0)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        tempo = librosa.beat.tempo(onset_envelope=onset_env, sr=sr)
        if len(tempo) > 0:
            return round(tempo[0])
        else:
            return DEFAULT_BPM
    except Exception as e:
        return DEFAULT_BPM


def load_music_folder(folder_path):
    global songs, loading_messages
    songs = []
    loading_messages = []

    for file in sorted(os.listdir(folder_path)):
        if file.lower().endswith(".mp3"):
            full_path = os.path.join(folder_path, file)
            try:
                loading_messages.append(f"~ Analyzing: {file}")
                show_loading_screen(loading_messages)
                pygame.event.pump()
                pygame.display.flip()

                sound = pygame.mixer.Sound(full_path)
                bpm = DEFAULT_BPM
                if bpm_analysis_enabled:
                    bpm = detect_bpm(full_path)

                songs.append({
                    'file': file,
                    'sound': sound,
                    'bpm': bpm
                })

                loading_messages.append(f"✅ {file} (BPM: {bpm})")
                show_loading_screen(loading_messages)
                pygame.event.pump()
                pygame.display.flip()
                time.sleep(0.2)

            except Exception as e:
                msg = f"❌ {file}: {str(e)}"
                loading_messages.append(msg)
                show_loading_screen(loading_messages)
                pygame.event.pump()
                pygame.display.flip()
                time.sleep(0.5)

    # Sort songs by BPM ascending after loading
    songs.sort(key=lambda s: s['bpm'])


state = "waiting"
running = True

while running:
    now = pygame.time.get_ticks()

    if state == "waiting":
        show_drag_in_message()

    for event in pygame.event.get():
        if event.type == QUIT:
            running = False

        elif event.type == DROPFILE and state == "waiting":
            dropped_path = event.file
            if os.path.isdir(dropped_path):
                music_folder = dropped_path
                ask_bpm_analysis()
                state = "loading"
                load_music_folder(music_folder)
                if songs:
                    channels[current_channel].play(songs[current_song_idx]['sound'], loops=0)
                    channels[current_channel].set_volume(1.0)
                    state = "playing"
                else:
                    state = "waiting"

        if state == "playing":
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

    if state == "playing" and last_fade_start > 0:
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

    if state == "playing":
        screen.blit(background_img, (0, 0))
        screen.blit(overlay, (0, 0))

        title_font = pygame.font.SysFont("comicsansms", 42)
        title_text = title_font.render("H-DJ Mixer", True, (255, 200, 50))
        screen.blit(title_text, (50, 20))

        song_font = pygame.font.SysFont("arialblack", 28)
        label_text = song_font.render("Now Playing:", True, (255, 255, 0))
        screen.blit(label_text, (60, 100))

        current_song = songs[current_song_idx]['file']
        current_text = font.render(current_song, True, (255, 255, 255))
        screen.blit(current_text, (60, 140))

        next_idx = (current_song_idx + 1) % len(songs)
        next_song = songs[next_idx]['file']
        next_label = song_font.render("Up Next:", True, (100, 255, 255))
        screen.blit(next_label, (60, 190))

        next_text = font.render(next_song, True, (255, 255, 255))
        screen.blit(next_text, (60, 230))

        bar_x, bar_y, bar_w, bar_h = 60, 640, 680, 30
        pygame.draw.rect(screen, (255, 255, 255), (bar_x, bar_y, bar_w, bar_h), 3, border_radius=15)

        if last_fade_start > 0:
            progress = min((now - last_fade_start) / FADE_DURATION, 1.0)
            fill_width = int(bar_w * progress)
            pygame.draw.rect(screen, (255, 100, 200), (bar_x, bar_y, fill_width, bar_h), border_radius=15)
            pygame.draw.rect(screen, (255, 180, 255), (bar_x, bar_y, fill_width, bar_h), 2, border_radius=15)

        next_button_rect = pygame.Rect(600, 700, 160, 50)
        mouse_hover = next_button_rect.collidepoint(pygame.mouse.get_pos())
        button_color = (255, 80, 120) if mouse_hover else (255, 50, 100)
        pygame.draw.rect(screen, button_color, next_button_rect, border_radius=20)
        pygame.draw.rect(screen, (255, 255, 255), next_button_rect, 3, border_radius=20)

        next_button_text = font.render("> Next Track", True, (255, 255, 255))
        screen.blit(next_button_text, (next_button_rect.x + 15, next_button_rect.y + 12))

        pygame.display.flip()

        if pygame.mouse.get_pressed()[0] and mouse_hover and last_fade_start == 0:
            pygame.event.post(pygame.event.Event(KEYDOWN, key=K_SPACE))
            time.sleep(0.2)

    clock.tick(60)

pygame.quit()

