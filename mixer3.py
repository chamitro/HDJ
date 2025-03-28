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
    "song1.mp3": 128,  # Replace with your actual filenames and BPM values
    "song2.mp3": 124,
    "song3.mp3": 130
}

# Initialize Pygame
pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2)
screen = pygame.display.set_mode((300, 100))
pygame.display.set_caption("Manual BPM Player")

def load_music_folder(folder_path):
    music_files = []
    for file in sorted(os.listdir(folder_path)):
        if file.lower().endswith(".mp3"):
            full_path = os.path.join(folder_path, file)
            try:
                sound = pygame.mixer.Sound(full_path)
                bpm = MANUAL_BPM.get(file, 120)  # Default to 120 BPM if not specified
                music_files.append({
                    'file': file,
                    'sound': sound,
                    'bpm': bpm
                })
                print(f"Loaded: {file} (BPM: {bpm})")
            except Exception as e:
                print(f"Error loading {file}: {str(e)}")
    return music_files

# Load songs
songs = load_music_folder(MUSIC_FOLDER)
if not songs:
    print("No valid MP3 files found!")
    pygame.quit()
    exit()

# Create channels and initialize state
channels = [pygame.mixer.Channel(i) for i in range(2)]
current_channel = 0
current_song_idx = 0
last_fade_start = 0

# Calculate beat interval in milliseconds
def get_beat_interval(bpm):
    return (60 / bpm) * 1000  # Convert BPM to milliseconds per beat

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
    
    # Prepare next song
            next_song_idx = (current_song_idx + 1) % len(songs)
            next_channel = (current_channel + 1) % 2
            current_song = songs[current_song_idx]
            next_song = songs[next_song_idx]

    # Calculate beat-synced start time
            current_bpm = current_song['bpm']
            next_bpm = next_song['bpm']
            beat_interval = get_beat_interval(current_bpm)
    
    # Start next song on beat
            channels[next_channel].play(next_song['sound'], loops=0)
            channels[next_channel].set_volume(0.0)
            last_fade_start = now
            print(f"Transitioning to: {next_song['file']} (auto: {event.type != KEYDOWN})")


    # Rest of the fade handling remains the same
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

    pygame.display.update()
    time.sleep(0.01)

pygame.quit()
