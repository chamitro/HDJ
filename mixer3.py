import os
import pygame
from pygame.locals import *
import time
import sys
import librosa
import soundfile as sf
import numpy as np

# Config
FADE_DURATION = 15000
DEFAULT_BPM = 120
DEFAULT_KEY = "Unknown"

# Camelot Wheel (basic mapping)
CAMELT_KEYS = {
    'C': '8B', 'C#': '3B', 'D': '10B', 'D#': '5B', 'E': '12B', 'F': '7B',
    'F#': '2B', 'G': '9B', 'G#': '4B', 'A': '11B', 'A#': '6B', 'B': '1B'
}

# Init
pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2)
screen = pygame.display.set_mode((800, 800))
pygame.display.set_caption("H-Dj Mixer")
font = pygame.font.SysFont(None, 32)
popup_font = pygame.font.SysFont("comicsansms", 28)
clock = pygame.time.Clock()

background_img = pygame.image.load("vinyl.jpg").convert()
background_img = pygame.transform.scale(background_img, screen.get_size())
overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
overlay.fill((0, 0, 0, 120))

songs = []
channels = [pygame.mixer.Channel(i) for i in range(2)]
current_channel = 0
current_song_idx = 0
last_fade_start = 0
is_paused = False
bpm_analysis_enabled = False
state = "waiting"
running = True
volumes = [1.0, 1.0]  # Initial volume for both decks A and B

def get_beat_interval(bpm):
    return (60 / bpm) * 1000

def extract_waveform(path):
    try:
        y, sr = librosa.load(path, sr=None, mono=True)
        y = librosa.util.normalize(y)
        y = y[::int(len(y) / 400)] if len(y) > 400 else y
        return y
    except:
        return []

def draw_waveform(data, y_base, height, color):
    if len(data) == 0:
        return
    bar_width = screen.get_width() // len(data)
    for i, sample in enumerate(data):
        x = i * bar_width
        h = int(sample * height)
        pygame.draw.line(screen, color, (x, y_base), (x, y_base - h), 1)
        pygame.draw.line(screen, (255, 255, 255, 40), (x, y_base), (x, y_base + h // 4), 1)
    pygame.draw.line(screen, (255, 255, 255), (0, y_base), (screen.get_width(), y_base), 1)

def show_pause_button():
    pause_button_rect = pygame.Rect(40, 700, 160, 50)  # ⬅️ Left-down corner
    mouse_hover = pause_button_rect.collidepoint(pygame.mouse.get_pos())
    button_color = (80, 80, 255) if mouse_hover else (50, 50, 200)
    pygame.draw.rect(screen, button_color, pause_button_rect, border_radius=20)
    pygame.draw.rect(screen, (255, 255, 255), pause_button_rect, 3, border_radius=20)
    label = "Pause ⏸️" if not is_paused else "Play ▶️"
    text = font.render(label, True, (255, 255, 255))
    screen.blit(text, (pause_button_rect.x + 15, pause_button_rect.y + 12))
    return pause_button_rect

def draw_play_time():
    if state != "playing":
        return
    elapsed_ms = pygame.time.get_ticks() - track_start_time
    seconds = (elapsed_ms // 1000) % 60
    minutes = (elapsed_ms // 1000) // 60
    time_text = font.render(f"⏱️ {minutes:02}:{seconds:02}", True, (255, 255, 255))
    screen.blit(time_text, (360, 740))

def draw_volume_sliders():
    slider_width = 120
    slider_height = 10

    for i in range(2):
        x = 60 if i == 0 else 620
        y = 600
        pygame.draw.rect(screen, (180, 180, 180), (x, y, slider_width, slider_height))
        fill = int(volumes[i] * slider_width)
        pygame.draw.rect(screen, (0, 255, 180), (x, y, fill, slider_height))
        pygame.draw.rect(screen, (255, 255, 255), (x, y, slider_width, slider_height), 2)
        label = font.render(f"Track {'A' if i == 0 else 'B'}", True, (255, 255, 255))
        screen.blit(label, (x, y - 25))

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
                pygame.quit(); sys.exit()
            elif event.type == KEYDOWN:
                if event.unicode.lower() == 'y':
                    bpm_analysis_enabled = True
                    waiting = False
                elif event.unicode.lower() == 'n':
                    bpm_analysis_enabled = False
                    waiting = False

def show_loading_screen(messages):
    screen.blit(background_img, (0, 0))
    screen.blit(overlay, (0, 0))
    title = font.render("<...> Loading Songs...", True, (255, 255, 255))
    screen.blit(title, (30, 30))
    for i, msg in enumerate(messages[-15:]):
        line = font.render(msg, True, (180, 220, 255))
        screen.blit(line, (50, 80 + i * 30))
    pygame.display.flip()

def detect_bpm_and_key(path):
    try:
        y, sr = librosa.load(path, sr=22050, mono=True, duration=30.0, offset=15.0)
        # BPM detection
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        tempo = librosa.beat.tempo(onset_envelope=onset_env, sr=sr)
        bpm = round(tempo[0]) if len(tempo) > 0 else DEFAULT_BPM

        # Key detection
        chroma_cq = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_avg = np.mean(chroma_cq, axis=1)
        key_index = np.argmax(chroma_avg)
        key_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        key = key_names[key_index]

        # Determine if it's minor
        is_minor = librosa.feature.tonnetz(y=librosa.effects.harmonic(y), sr=sr).mean(axis=1)[0] < 0
        full_key = key + ("m" if is_minor else "")

        # Camelot notation map
        CAMELT_KEYS_EXTENDED = {
            'C':  '8B', 'C#': '3B', 'D':  '10B', 'D#': '5B', 'E':  '12B', 'F':  '7B',
            'F#': '2B', 'G':  '9B', 'G#': '4B', 'A':  '11B', 'A#': '6B', 'B':  '1B',
            'Cm':  '5A', 'C#m': '12A', 'Dm':  '7A', 'D#m': '2A', 'Em':  '9A', 'Fm':  '4A',
            'F#m': '11A', 'Gm':  '6A', 'G#m': '1A', 'Am':  '8A', 'A#m': '3A', 'Bm':  '10A'
        }

        camelot = CAMELT_KEYS_EXTENDED.get(full_key, "?")
        return bpm, full_key, camelot

    except Exception as e:
        print(f"[ERROR] Key detection failed for {path}: {e}")
        return DEFAULT_BPM, DEFAULT_KEY, "?"


def load_music_folder(folder_path):
    global songs
    songs = []
    messages = []
    for file in sorted(os.listdir(folder_path)):
        if file.lower().endswith(".mp3"):
            full_path = os.path.join(folder_path, file)
            try:
                messages.append(f"~ Analyzing: {file}")
                show_loading_screen(messages); pygame.event.pump()
                sound = pygame.mixer.Sound(full_path)
                bpm, key, camelot = DEFAULT_BPM, DEFAULT_KEY, "?"
                if bpm_analysis_enabled:
                    bpm, key, camelot = detect_bpm_and_key(full_path)
                waveform = extract_waveform(full_path)
                songs.append({
                    'file': file, 'sound': sound, 'bpm': bpm, 'key': key,
                    'camelot': camelot, 'waveform': waveform
                })
                messages.append(f"\/ {file} (BPM: {bpm}, Key: {key}, Camelot: {camelot})")
                show_loading_screen(messages)
                pygame.event.pump(); time.sleep(0.2)
            except Exception as e:
                messages.append(f"❌ {file}: {e}")
                show_loading_screen(messages); pygame.event.pump(); time.sleep(0.5)
    songs.sort(key=lambda s: (s['bpm'], s['key']))

# ========== Main Loop ==========
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
                ask_bpm_analysis()
                state = "loading"
                load_music_folder(dropped_path)
                if songs:
                    channels[current_channel].play(songs[current_song_idx]['sound'])
                    channels[current_channel].set_volume(volumes[current_channel])
                    track_start_time = now
                    state = "playing"
                else:
                    state = "waiting"

        if state == "playing":
            if (event.type == KEYDOWN and event.key == K_SPACE and last_fade_start == 0) or \
               (last_fade_start == 0 and not channels[current_channel].get_busy()):

                next_idx = (current_song_idx + 1) % len(songs)
                next_channel = (current_channel + 1) % 2
                channels[next_channel].play(songs[next_idx]['sound'])
                channels[next_channel].set_volume(0.0)
                track_start_time = now
                last_fade_start = now

    if state == "playing" and last_fade_start > 0:
        elapsed = now - last_fade_start
        if elapsed <= FADE_DURATION:
            progress = elapsed / FADE_DURATION
            channels[current_channel].set_volume((1.0 - progress) * volumes[current_channel])
            channels[(current_channel + 1) % 2].set_volume(progress * volumes[(current_channel + 1) % 2])
        else:
            channels[current_channel].stop()
            current_channel = (current_channel + 1) % 2
            current_song_idx = (current_song_idx + 1) % len(songs)
            last_fade_start = 0

    if state == "playing":
        # Background
        screen.blit(background_img, (0, 0))
        screen.blit(overlay, (0, 0))

        # Titles
        title_font = pygame.font.SysFont("comicsansms", 42)
        screen.blit(title_font.render("H-DJ Mixer", True, (255, 200, 50)), (50, 20))

        song_font = pygame.font.SysFont("arialblack", 28)
        screen.blit(song_font.render("Now Playing:", True, (255, 255, 0)), (60, 100))
        screen.blit(font.render(songs[current_song_idx]['file'], True, (255, 255, 255)), (60, 140))

        screen.blit(song_font.render("Up Next:", True, (100, 255, 255)), (60, 190))
        next_idx = (current_song_idx + 1) % len(songs)
        screen.blit(font.render(songs[next_idx]['file'], True, (255, 255, 255)), (60, 230))

        # Waveform
        current_waveform = songs[current_song_idx].get('waveform', [])
        draw_waveform(current_waveform, y_base=520, height=40, color=(0, 255, 200))

        # Pause Button (bottom left)
        pause_button_rect = pygame.Rect(40, 700, 160, 50)
        mouse_hover = pause_button_rect.collidepoint(pygame.mouse.get_pos())
        button_color = (80, 80, 255) if mouse_hover else (50, 50, 200)
        pygame.draw.rect(screen, button_color, pause_button_rect, border_radius=20)
        pygame.draw.rect(screen, (255, 255, 255), pause_button_rect, 3, border_radius=20)
        pause_label = "Pause ||" if not is_paused else "Play ▶️"
        screen.blit(font.render(pause_label, True, (255, 255, 255)), (pause_button_rect.x + 20, pause_button_rect.y + 12))

        if pygame.mouse.get_pressed()[0] and mouse_hover:
            if not is_paused:
                channels[current_channel].pause(); is_paused = True
            else:
                channels[current_channel].unpause(); is_paused = False
            time.sleep(0.2)

        # Progress Bar
        bar_x, bar_y, bar_w, bar_h = 60, 640, 680, 30
        pygame.draw.rect(screen, (255, 255, 255), (bar_x, bar_y, bar_w, bar_h), 3, border_radius=15)
        if last_fade_start > 0:
            progress = min((now - last_fade_start) / FADE_DURATION, 1.0)
            fill_width = int(bar_w * progress)
            pygame.draw.rect(screen, (255, 100, 200), (bar_x, bar_y, fill_width, bar_h), border_radius=15)

        # Volume Sliders
        for i in range(2):
            x = 60 if i == 0 else 620
            y = 600
            pygame.draw.rect(screen, (180, 180, 180), (x, y, 120, 10))
            fill = int(volumes[i] * 120)
            pygame.draw.rect(screen, (0, 255, 180), (x, y, fill, 10))
            pygame.draw.rect(screen, (255, 255, 255), (x, y, 120, 10), 2)
            screen.blit(font.render(f"Track {'A' if i == 0 else 'B'}", True, (255, 255, 255)), (x, y - 25))

        # Volume click handler
        if pygame.mouse.get_pressed()[0]:
            mx, my = pygame.mouse.get_pos()
            for i in range(2):
                slider_x = 60 if i == 0 else 620
                slider_y = 600
                if slider_x <= mx <= slider_x + 120 and slider_y <= my <= slider_y + 10:
                    volumes[i] = (mx - slider_x) / 120
                    channels[i].set_volume(volumes[i])
                    time.sleep(0.1)

        # Play Time
        elapsed = pygame.time.get_ticks() - track_start_time
        mm = (elapsed // 1000) // 60
        ss = (elapsed // 1000) % 60
        time_text = font.render(f"Time: {mm:02}:{ss:02}", True, (255, 255, 255))
        screen.blit(time_text, (370, 740))

        # Next Button (bottom right)
        next_button_rect = pygame.Rect(600, 700, 160, 50)
        hover = next_button_rect.collidepoint(pygame.mouse.get_pos())
        next_color = (255, 80, 120) if hover else (255, 50, 100)
        pygame.draw.rect(screen, next_color, next_button_rect, border_radius=20)
        pygame.draw.rect(screen, (255, 255, 255), next_button_rect, 3, border_radius=20)
        screen.blit(font.render("> Next Track", True, (255, 255, 255)), (next_button_rect.x + 15, next_button_rect.y + 12))

        if pygame.mouse.get_pressed()[0] and hover and last_fade_start == 0:
            pygame.event.post(pygame.event.Event(KEYDOWN, key=K_SPACE))
            time.sleep(0.2)

        # Final display
        pygame.display.flip()

    clock.tick(60)

pygame.quit()

