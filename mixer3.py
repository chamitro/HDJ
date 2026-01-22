import os
import pygame
from pygame.locals import *
import time
import sys
import librosa
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from dataclasses import dataclass
from typing import List, Optional
import threading
import math

# ==================== CONFIG ====================
FADE_DURATION = 15000
DEFAULT_BPM = 120
DEFAULT_KEY = "Unknown"
CACHE_FILE = "song_cache.json"
MAX_WORKERS = 4

# Camelot Wheel
CAMELOT_WHEEL = {
    'C': '8B', 'Cm': '5A', 'C#': '3B', 'C#m': '12A',
    'D': '10B', 'Dm': '7A', 'D#': '5B', 'D#m': '2A',
    'E': '12B', 'Em': '9A', 'F': '7B', 'Fm': '4A',
    'F#': '2B', 'F#m': '11A', 'G': '9B', 'Gm': '6A',
    'G#': '4B', 'G#m': '1A', 'A': '11B', 'Am': '8A',
    'A#': '6B', 'A#m': '3A', 'B': '1B', 'Bm': '10A'
}

def calculate_key_distance(key1: str, key2: str) -> int:
    """Calculate harmonic distance between keys"""
    if key1 == "Unknown" or key2 == "Unknown":
        return 999
    if key1 == key2:
        return 0
    
    key_map = {
        'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5,
        'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11
    }
    
    def parse_key(key):
        if key.endswith('m'):
            return key_map.get(key[:-1], 0), 'minor'
        else:
            return key_map.get(key, 0), 'major'
    
    root1, mode1 = parse_key(key1)
    root2, mode2 = parse_key(key2)
    
    semitone_dist = min(abs(root1 - root2), 12 - abs(root1 - root2))
    mode_penalty = 0 if mode1 == mode2 else 3
    
    return semitone_dist + mode_penalty

def get_compatible_keys(camelot):
    """Get harmonically compatible keys"""
    if camelot == "?":
        return []
    try:
        num = int(camelot[:-1])
        letter = camelot[-1]
        compatible = [camelot]
        compatible.append(f"{num}{('A' if letter == 'B' else 'B')}")
        compatible.append(f"{(num % 12) + 1}{letter}")
        compatible.append(f"{((num - 2) % 12) + 1}{letter}")
        return compatible
    except:
        return [camelot]

@dataclass
class Song:
    file: str
    path: str
    bpm: float
    key: str
    camelot: str
    energy: float
    waveform: list
    duration: float
    
    def is_compatible(self, other: 'Song') -> bool:
        bpm_diff = abs(self.bpm - other.bpm)
        key_compatible = other.camelot in get_compatible_keys(self.camelot)
        return bpm_diff <= 6 and key_compatible

class SongCache:
    @staticmethod
    def load():
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    @staticmethod
    def save(cache):
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f)

class MusicAnalyzer:
    @staticmethod
    def analyze_song(file_path: str) -> Optional[dict]:
        try:
            y, sr = librosa.load(file_path, sr=22050, mono=True, duration=60.0)
            
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            tempo = librosa.beat.tempo(onset_envelope=onset_env, sr=sr)
            bpm = round(tempo[0]) if len(tempo) > 0 else DEFAULT_BPM
            
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
            chroma_avg = np.mean(chroma, axis=1)
            key_index = np.argmax(chroma_avg)
            key_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            key = key_names[key_index]
            
            harmonic = librosa.effects.harmonic(y)
            tonnetz = librosa.feature.tonnetz(y=harmonic, sr=sr)
            is_minor = tonnetz.mean(axis=1)[0] < 0
            full_key = key + ("m" if is_minor else "")
            camelot = CAMELOT_WHEEL.get(full_key, "?")
            
            rms = librosa.feature.rms(y=y)
            energy = float(np.mean(rms))
            
            waveform_data = librosa.util.normalize(y)
            waveform_data = waveform_data[::int(len(waveform_data) / 800)]
            waveform = waveform_data.tolist()
            
            return {
                'bpm': bpm,
                'key': full_key,
                'camelot': camelot,
                'energy': energy,
                'waveform': waveform,
                'duration': None
            }
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
            return None
    
    @staticmethod
    def extract_waveform_fast(path: str) -> list:
        try:
            y, sr = librosa.load(path, sr=11025, mono=True)
            y = librosa.util.normalize(y)
            y = y[::int(len(y) / 800)] if len(y) > 800 else y
            return y.tolist()
        except:
            return []

class SmartPlaylist:
    def __init__(self, songs: List[Song]):
        self.songs = songs
        self.current_index = 0
    
    def sort_by_energy(self):
        self.songs.sort(key=lambda s: s.energy)
    
    def sort_by_bpm_and_key(self):
        self.songs.sort(key=lambda s: s.bpm)
        from itertools import groupby
        sorted_songs = []
        for bpm, group in groupby(self.songs, key=lambda s: round(s.bpm)):
            group_list = list(group)
            if len(group_list) <= 1:
                sorted_songs.extend(group_list)
            else:
                bpm_sorted = [group_list[0]]
                remaining = group_list[1:]
                while remaining:
                    current = bpm_sorted[-1]
                    best = min(remaining, key=lambda s: calculate_key_distance(current.key, s.key))
                    bpm_sorted.append(best)
                    remaining.remove(best)
                sorted_songs.extend(bpm_sorted)
        self.songs = sorted_songs
    
    def sort_by_bpm(self):
        self.songs.sort(key=lambda s: s.bpm)
    
    def get_next(self):
        self.current_index = (self.current_index + 1) % len(self.songs)
        return self.songs[self.current_index]
    
    def get_current(self):
        return self.songs[self.current_index]

# ==================== PROFESSIONAL DJ UI ====================
class ProfessionalDJUI:
    """Ultra-professional DJ interface inspired by Serato/Traktor"""
    
    def __init__(self, width=1400, height=900):
        pygame.init()
        pygame.mixer.init(frequency=44100, size=-16, channels=2)
        
        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("HDJ PRO")
        
        # Professional Typography (inspired by DJ software)
        self.logo_font = pygame.font.SysFont("impact", 48, bold=True)
        self.title_font = pygame.font.SysFont("arial", 28, bold=True)
        self.header_font = pygame.font.SysFont("arial", 20, bold=True)
        self.font = pygame.font.SysFont("arial", 16)
        self.small_font = pygame.font.SysFont("arial", 14)
        self.tiny_font = pygame.font.SysFont("arial", 11)
        
        # Professional Color Scheme (Dark theme like real DJ software)
        self.bg_main = (18, 18, 22)          # Almost black
        self.bg_panel = (25, 25, 30)         # Dark panels
        self.bg_deck = (30, 30, 36)          # Deck background
        self.bg_highlight = (40, 40, 48)     # Highlighted areas
        
        # Accent colors (vibrant but professional)
        self.deck_a_color = (0, 200, 255)    # Cyan for Deck A
        self.deck_b_color = (255, 80, 120)   # Pink for Deck B
        self.accent_green = (0, 255, 150)    # Success/compatible
        self.accent_orange = (255, 160, 0)   # Warning
        self.accent_red = (255, 60, 60)      # Error/active
        
        # UI colors
        self.text_primary = (240, 240, 245)
        self.text_secondary = (160, 160, 170)
        self.text_dim = (100, 100, 110)
        
        # Grid and lines
        self.line_color = (45, 45, 52)
        self.grid_color = (35, 35, 40)
        
        try:
            self.background = pygame.image.load("vinyl.jpg").convert()
            self.background = pygame.transform.scale(self.background, (width, height))
        except:
            self.background = None
        
        self.clock = pygame.time.Clock()
    
    def draw_glow(self, x, y, radius, color, alpha=100):
        """Draw glowing effect"""
        glow_surf = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
        for i in range(radius, 0, -2):
            current_alpha = int(alpha * (radius - i) / radius)
            pygame.draw.circle(glow_surf, (*color, current_alpha), (radius, radius), i)
        self.screen.blit(glow_surf, (x - radius, y - radius))
    
    def draw_panel(self, x, y, w, h, title="", border_color=None):
        """Draw professional panel with title bar"""
        # Main panel
        pygame.draw.rect(self.screen, self.bg_panel, (x, y, w, h))
        
        # Title bar if provided
        if title:
            title_h = 32
            pygame.draw.rect(self.screen, self.bg_highlight, (x, y, w, title_h))
            
            title_text = self.header_font.render(title, True, self.text_primary)
            self.screen.blit(title_text, (x + 12, y + 8))
            
            # Title bar accent line
            if border_color:
                pygame.draw.line(self.screen, border_color, (x, y + title_h - 1), (x + w, y + title_h - 1), 2)
        
        # Border
        border_col = border_color if border_color else self.line_color
        pygame.draw.rect(self.screen, border_col, (x, y, w, h), 2)
    
    def draw_waveform_pro(self, waveform, x, y, width, height, play_position, deck_color):
        """Professional waveform like Serato/Traktor"""
        if not waveform:
            return
        
        # Dark background
        pygame.draw.rect(self.screen, (20, 20, 24), (x, y, width, height))
        
        # Grid lines
        for i in range(5):
            grid_y = y + (height // 4) * i
            pygame.draw.line(self.screen, self.grid_color, (x, grid_y), (x + width, grid_y), 1)
        
        # Waveform bars
        bar_width = max(1, width // len(waveform))
        center_y = y + height // 2
        
        for i, sample in enumerate(waveform):
            bar_x = x + i * bar_width
            bar_h = int(abs(sample) * height * 0.48)
            
            # Determine color based on playback position
            progress = i / len(waveform)
            
            if progress < play_position:
                # Played - bright deck color
                color = deck_color
                alpha = 255
            else:
                # Unplayed - dim gray
                color = (60, 60, 70)
                alpha = 180
            
            # Draw mirrored waveform (top and bottom)
            pygame.draw.rect(self.screen, color, (bar_x, center_y - bar_h, bar_width, bar_h))
            pygame.draw.rect(self.screen, color, (bar_x, center_y, bar_width, bar_h))
        
        # Center line
        pygame.draw.line(self.screen, (80, 80, 90), (x, center_y), (x + width, center_y), 2)
        
        # Playhead with glow
        playhead_x = x + int(play_position * width)
        self.draw_glow(playhead_x, center_y, 15, (255, 255, 255), 120)
        pygame.draw.line(self.screen, (255, 255, 255), (playhead_x, y), (playhead_x, y + height), 3)
        
        # Beat markers every 4 beats (estimated)
        if hasattr(self, 'current_bpm'):
            beats_per_bar = 4
            # Draw some beat markers
            for beat in range(0, int(len(waveform) / 16), 1):
                marker_x = x + int((beat * 16 / len(waveform)) * width)
                pygame.draw.line(self.screen, (80, 80, 100), (marker_x, y), (marker_x, y + 5), 2)
        
        # Border
        pygame.draw.rect(self.screen, self.line_color, (x, y, width, height), 2)
    
    def draw_deck_display(self, x, y, w, h, song_info, deck_color, is_active=False):
        """Professional deck display"""
        # Panel
        self.draw_panel(x, y, w, h, "", deck_color if is_active else None)
        
        # Deck indicator
        deck_label = "A" if deck_color == self.deck_a_color else "B"
        label_size = 40
        pygame.draw.circle(self.screen, deck_color if is_active else self.bg_highlight, 
                          (x + 30, y + 30), label_size // 2)
        deck_text = self.logo_font.render(deck_label, True, self.text_primary)
        deck_rect = deck_text.get_rect(center=(x + 30, y + 30))
        self.screen.blit(deck_text, deck_rect)
        
        # Track title
        track_text = self.title_font.render(song_info['Track'][:35], True, self.text_primary)
        self.screen.blit(track_text, (x + 70, y + 15))
        
        # BPM - Large and prominent
        bpm_text = self.logo_font.render(f"{song_info['BPM']}", True, deck_color)
        self.screen.blit(bpm_text, (x + 70, y + 45))
        
        bpm_label = self.small_font.render("BPM", True, self.text_secondary)
        self.screen.blit(bpm_label, (x + 145, y + 60))
        
        # Key with Camelot
        key_str = f"{song_info['Key']}"
        key_text = self.header_font.render(key_str, True, self.text_primary)
        self.screen.blit(key_text, (x + 220, y + 50))
        
        # Energy bar
        energy_val = float(song_info['Energy'])
        energy_x = x + w - 120
        energy_w = 100
        energy_h = 8
        
        pygame.draw.rect(self.screen, self.bg_main, (energy_x, y + 50, energy_w, energy_h))
        fill_w = int(energy_val * energy_w * 2)  # Scale energy
        fill_w = min(fill_w, energy_w)
        
        # Gradient energy bar
        for i in range(fill_w):
            blend = i / energy_w
            color = tuple(int(self.accent_green[j] * (1-blend) + self.accent_red[j] * blend) 
                         for j in range(3))
            pygame.draw.line(self.screen, color, (energy_x + i, y + 50), (energy_x + i, y + 50 + energy_h))
        
        pygame.draw.rect(self.screen, self.line_color, (energy_x, y + 50, energy_w, energy_h), 1)
        
        energy_label = self.tiny_font.render("ENERGY", True, self.text_dim)
        self.screen.blit(energy_label, (energy_x, y + 62))
    
    def draw_fader_professional(self, x, y, width, height, value, label, color):
        """Professional vertical fader like Pioneer DJM"""
        # Fader track
        track_w = 8
        track_x = x + (width - track_w) // 2
        
        # Track background
        pygame.draw.rect(self.screen, self.bg_main, (track_x, y, track_w, height))
        
        # Fill from bottom
        fill_h = int(value * height)
        fill_y = y + height - fill_h
        
        # Gradient fill
        for i in range(fill_h):
            blend = i / height
            grad_color = tuple(int(c * (0.3 + 0.7 * blend)) for c in color)
            pygame.draw.line(self.screen, grad_color, (track_x, fill_y + i), (track_x + track_w, fill_y + i))
        
        pygame.draw.rect(self.screen, self.line_color, (track_x, y, track_w, height), 1)
        
        # Fader handle
        handle_y = fill_y
        handle_w = 28
        handle_h = 12
        handle_x = x + (width - handle_w) // 2
        
        pygame.draw.rect(self.screen, color, (handle_x, handle_y - handle_h//2, handle_w, handle_h), border_radius=2)
        pygame.draw.rect(self.screen, self.text_primary, (handle_x, handle_y - handle_h//2, handle_w, handle_h), 1, border_radius=2)
        
        # Label
        label_text = self.small_font.render(label, True, self.text_secondary)
        label_rect = label_text.get_rect(center=(x + width // 2, y - 15))
        self.screen.blit(label_text, label_rect)
        
        # Value display
        value_text = self.font.render(f"{int(value * 100)}", True, self.text_primary)
        value_rect = value_text.get_rect(center=(x + width // 2, y + height + 15))
        self.screen.blit(value_text, value_rect)
        
        return self.handle_fader_input(track_x, y, track_w, height)
    
    def handle_fader_input(self, x, y, w, h):
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()[0]
        
        if mouse_pressed and (x - 20 <= mouse_pos[0] <= x + w + 20 and 
                             y - 20 <= mouse_pos[1] <= y + h + 20):
            relative_y = mouse_pos[1] - y
            value = 1.0 - (relative_y / h)
            return max(0, min(1, value))
        return None
    
    def draw_button_pro(self, text, x, y, w, h, color, icon=None):
        """Professional button"""
        mouse_pos = pygame.mouse.get_pos()
        mouse_clicked = pygame.mouse.get_pressed()[0]
        
        is_hover = (x <= mouse_pos[0] <= x + w and y <= mouse_pos[1] <= y + h)
        
        # Button background
        if is_hover:
            btn_color = tuple(min(255, c + 30) for c in color)
            pygame.draw.rect(self.screen, btn_color, (x, y, w, h), border_radius=4)
        else:
            pygame.draw.rect(self.screen, color, (x, y, w, h), border_radius=4)
        
        # Border
        pygame.draw.rect(self.screen, self.text_primary if is_hover else self.line_color, 
                        (x, y, w, h), 2, border_radius=4)
        
        # Text
        text_surf = self.font.render(text, True, self.text_primary)
        text_rect = text_surf.get_rect(center=(x + w // 2, y + h // 2))
        self.screen.blit(text_surf, text_rect)
        
        return is_hover and mouse_clicked
    
    def draw_time_display(self, elapsed_sec, total_sec, x, y):
        """Large professional time display"""
        time_str = f"{elapsed_sec // 60:02d}:{elapsed_sec % 60:02d}"
        total_str = f"{total_sec // 60:02d}:{total_sec % 60:02d}"
        
        # Time box
        box_w, box_h = 180, 60
        pygame.draw.rect(self.screen, self.bg_panel, (x, y, box_w, box_h))
        pygame.draw.rect(self.screen, self.line_color, (x, y, box_w, box_h), 2)
        
        # Elapsed time (large)
        time_text = self.logo_font.render(time_str, True, self.text_primary)
        self.screen.blit(time_text, (x + 15, y + 5))
        
        # Total time (small)
        total_text = self.small_font.render(f"/ {total_str}", True, self.text_secondary)
        self.screen.blit(total_text, (x + 15, y + 42))
    
    def draw_loading_screen(self, progress, total, current_file=""):
        self.screen.fill(self.bg_main)
        
        # Title
        title = self.logo_font.render("HDJ PRO", True, self.deck_a_color)
        title_rect = title.get_rect(center=(self.width // 2, 200))
        self.screen.blit(title, title_rect)
        
        subtitle = self.header_font.render("Professional DJ Software", True, self.text_secondary)
        subtitle_rect = subtitle.get_rect(center=(self.width // 2, 250))
        self.screen.blit(subtitle, subtitle_rect)
        
        # Progress bar
        bar_w, bar_h = 600, 8
        bar_x = (self.width - bar_w) // 2
        bar_y = 350
        
        pygame.draw.rect(self.screen, self.bg_panel, (bar_x, bar_y, bar_w, bar_h))
        
        if total > 0:
            progress_w = int((progress / total) * bar_w)
            pygame.draw.rect(self.screen, self.deck_a_color, (bar_x, bar_y, progress_w, bar_h))
        
        pygame.draw.rect(self.screen, self.line_color, (bar_x, bar_y, bar_w, bar_h), 1)
        
        # Progress text
        percent = int((progress / total) * 100) if total > 0 else 0
        progress_text = self.header_font.render(f"Loading: {progress}/{total} ({percent}%)", 
                                               True, self.text_primary)
        progress_rect = progress_text.get_rect(center=(self.width // 2, bar_y + 30))
        self.screen.blit(progress_text, progress_rect)
        
        if current_file:
            file_text = self.small_font.render(current_file[:60], True, self.text_secondary)
            file_rect = file_text.get_rect(center=(self.width // 2, bar_y + 60))
            self.screen.blit(file_text, file_rect)
        
        pygame.display.flip()
    
    def draw_drag_screen(self):
        self.screen.fill(self.bg_main)
        
        # Logo
        logo = self.logo_font.render("HDJ PRO", True, self.deck_a_color)
        logo_rect = logo.get_rect(center=(self.width // 2, 200))
        self.screen.blit(logo, logo_rect)
        
        subtitle = self.header_font.render("Professional DJ Mixing Software", True, self.text_secondary)
        subtitle_rect = subtitle.get_rect(center=(self.width // 2, 250))
        self.screen.blit(subtitle, subtitle_rect)
        
        # Drop zone
        drop_w, drop_h = 600, 200
        drop_x = (self.width - drop_w) // 2
        drop_y = 320
        
        pygame.draw.rect(self.screen, self.bg_panel, (drop_x, drop_y, drop_w, drop_h))
        pygame.draw.rect(self.screen, self.deck_a_color, (drop_x, drop_y, drop_w, drop_h), 3)
        
        inst = self.title_font.render("DROP MUSIC FOLDER HERE", True, self.text_primary)
        inst_rect = inst.get_rect(center=(self.width // 2, drop_y + 80))
        self.screen.blit(inst, inst_rect)
        
        inst2 = self.font.render("MP3 Format | Auto BPM & Key Detection", True, self.text_secondary)
        inst2_rect = inst2.get_rect(center=(self.width // 2, drop_y + 120))
        self.screen.blit(inst2, inst2_rect)
        
        # Features
        features = ["Harmonic Mixing", "Smart Sorting", "Professional Waveforms", "Auto Crossfade"]
        y = 580
        for i, feat in enumerate(features):
            x_pos = 200 + i * 250
            pygame.draw.rect(self.screen, self.bg_panel, (x_pos - 80, y - 10, 160, 40))
            pygame.draw.rect(self.screen, self.line_color, (x_pos - 80, y - 10, 160, 40), 1)
            
            feat_text = self.small_font.render(feat, True, self.text_primary)
            feat_rect = feat_text.get_rect(center=(x_pos, y + 10))
            self.screen.blit(feat_text, feat_rect)
        
        pygame.display.flip()

# Continue in next part...

# ==================== MAIN APPLICATION ====================
class DJMixerApp:
    def __init__(self):
        self.ui = ProfessionalDJUI()
        self.playlist = None
        
        print("=" * 70)
        print("HDJ PRO - Professional DJ Software")
        print("=" * 70)
        
        self.cache = SongCache.load()
        
        if self.cache:
            print(f"Cache loaded: {len(self.cache)} songs")
        else:
            print("No cache - analyzing tracks...")
        
        print("=" * 70)
        print()
        
        self.channels = [pygame.mixer.Channel(i) for i in range(2)]
        self.current_channel = 0
        self.volumes = [1.0, 1.0]
        self.channel_song_index = [0, 0]
        
        self.state = "waiting"
        self.is_paused = False
        self.pause_position = 0
        self.fade_start = 0
        self.track_start_time = 0
        
        self.sort_mode = "bpm_key"
    
    def load_folder_parallel(self, folder_path):
        self.state = "loading"
        
        mp3_files = [f for f in os.listdir(folder_path) 
                     if f.lower().endswith('.mp3')]
        
        if not mp3_files:
            self.state = "waiting"
            return
        
        songs = []
        processed = 0
        total = len(mp3_files)
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_file = {}
            
            for file in mp3_files:
                full_path = os.path.join(folder_path, file)
                
                if full_path in self.cache:
                    try:
                        cached = self.cache[full_path]
                        sound = pygame.mixer.Sound(full_path)
                        real_duration = sound.get_length()
                        
                        song = Song(
                            file=file, path=full_path, bpm=cached['bpm'],
                            key=cached['key'], camelot=cached['camelot'],
                            energy=cached['energy'], waveform=cached['waveform'],
                            duration=real_duration
                        )
                        songs.append((song, sound))
                        
                        if cached.get('duration') != real_duration:
                            cached['duration'] = real_duration
                            self.cache[full_path] = cached
                        
                        processed += 1
                        self.ui.draw_loading_screen(processed, total, file)
                        pygame.event.pump()
                        continue
                    except:
                        pass
                
                future = executor.submit(MusicAnalyzer.analyze_song, full_path)
                future_to_file[future] = (file, full_path)
            
            for future in as_completed(future_to_file):
                file, full_path = future_to_file[future]
                result = future.result()
                
                if result:
                    try:
                        sound = pygame.mixer.Sound(full_path)
                        real_duration = sound.get_length()
                        
                        song = Song(
                            file=file, path=full_path, bpm=result['bpm'],
                            key=result['key'], camelot=result['camelot'],
                            energy=result['energy'], waveform=result['waveform'],
                            duration=real_duration
                        )
                        songs.append((song, sound))
                        
                        result['duration'] = real_duration
                        self.cache[full_path] = result
                    except Exception as e:
                        print(f"Error loading {file}: {e}")
                
                processed += 1
                self.ui.draw_loading_screen(processed, total, file)
                pygame.event.pump()
        
        SongCache.save(self.cache)
        
        if songs:
            song_objects = [s[0] for s in songs]
            self.sounds = {s[0].file: s[1] for s in songs}
            
            self.playlist = SmartPlaylist(song_objects)
            self.apply_sort()
            
            current_song = self.playlist.get_current()
            self.channels[self.current_channel].play(self.sounds[current_song.file])
            self.channels[self.current_channel].set_volume(self.volumes[self.current_channel])
            self.track_start_time = pygame.time.get_ticks()
            self.pause_position = 0
            self.channel_song_index[self.current_channel] = self.playlist.current_index
            self.state = "playing"
            
            print("\nGenerating full waveforms in background...")
            threading.Thread(target=self.generate_full_waveforms, daemon=True).start()
        else:
            self.state = "waiting"
    
    def generate_full_waveforms(self):
        for song in self.playlist.songs:
            try:
                if song.duration > 70:
                    full_waveform = MusicAnalyzer.extract_waveform_fast(song.path)
                    if full_waveform:
                        song.waveform = full_waveform
                        if song.path in self.cache:
                            self.cache[song.path]['waveform'] = full_waveform
            except:
                pass
        SongCache.save(self.cache)
        print("Full waveforms generated!")
    
    def apply_sort(self):
        if self.sort_mode == "bpm_key":
            self.playlist.sort_by_bpm_and_key()
        elif self.sort_mode == "bpm":
            self.playlist.sort_by_bpm()
        elif self.sort_mode == "energy":
            self.playlist.sort_by_energy()
    
    def trigger_crossfade(self):
        if self.fade_start > 0:
            return
        
        next_song_idx = (self.playlist.current_index + 1) % len(self.playlist.songs)
        next_song = self.playlist.songs[next_song_idx]
        next_channel = (self.current_channel + 1) % 2
        
        self.channels[next_channel].play(self.sounds[next_song.file])
        self.channels[next_channel].set_volume(0.0)
        self.channel_song_index[next_channel] = next_song_idx
        
        self.fade_start = pygame.time.get_ticks()
        self.track_start_time = pygame.time.get_ticks()
        self.pause_position = 0
        self.is_paused = False
    
    def update_crossfade(self):
        if self.fade_start == 0:
            return
        
        elapsed = pygame.time.get_ticks() - self.fade_start
        
        if elapsed <= FADE_DURATION:
            progress = elapsed / FADE_DURATION
            self.channels[self.current_channel].set_volume(
                (1 - progress) * self.volumes[self.current_channel]
            )
            self.channels[(self.current_channel + 1) % 2].set_volume(
                progress * self.volumes[(self.current_channel + 1) % 2]
            )
        else:
            self.channels[self.current_channel].stop()
            self.current_channel = (self.current_channel + 1) % 2
            self.playlist.current_index = self.channel_song_index[self.current_channel]
            self.fade_start = 0
    
    def draw_playing_screen(self):
        """Professional DJ interface"""
        self.ui.screen.fill(self.ui.bg_main)
        
        current_song_idx = self.channel_song_index[self.current_channel]
        current_song = self.playlist.songs[current_song_idx]
        
        next_song_idx = (current_song_idx + 1) % len(self.playlist.songs)
        next_song = self.playlist.songs[next_song_idx]
        
        # Top bar
        logo = self.ui.logo_font.render("HDJ", True, self.ui.deck_a_color)
        self.ui.screen.blit(logo, (20, 15))
        
        pro_text = self.ui.small_font.render("PRO", True, self.ui.text_secondary)
        self.ui.screen.blit(pro_text, (80, 35))
        
        # Track counter
        counter_text = self.ui.font.render(
            f"Track {current_song_idx + 1}/{len(self.playlist.songs)}", 
            True, self.ui.text_secondary
        )
        self.ui.screen.blit(counter_text, (self.ui.width - 180, 30))
        
        # Deck A (current)
        current_info = {
            'Track': current_song.file[:35],
            'BPM': f"{current_song.bpm:.0f}",
            'Key': f"{current_song.key} ({current_song.camelot})",
            'Energy': f"{current_song.energy:.2f}"
        }
        self.ui.draw_deck_display(20, 70, 660, 90, current_info, self.ui.deck_a_color, True)
        
        # Deck B (next)
        next_info = {
            'Track': next_song.file[:35],
            'BPM': f"{next_song.bpm:.0f}",
            'Key': f"{next_song.key} ({next_song.camelot})",
            'Energy': f"{next_song.energy:.2f}"
        }
        self.ui.draw_deck_display(720, 70, 660, 90, next_info, self.ui.deck_b_color, False)
        
        # Compatibility
        is_compat = current_song.is_compatible(next_song)
        compat_text = "COMPATIBLE" if is_compat else "CHECK MIX"
        compat_color = self.ui.accent_green if is_compat else self.ui.accent_orange
        compat = self.ui.small_font.render(compat_text, True, compat_color)
        self.ui.screen.blit(compat, (730, 145))
        
        # Waveform
        if self.is_paused:
            elapsed = self.pause_position
        else:
            elapsed = pygame.time.get_ticks() - self.track_start_time
        
        duration_ms = current_song.duration * 1000
        play_pos = min(elapsed / duration_ms, 1.0) if duration_ms > 0 else 0
        
        self.ui.draw_waveform_pro(current_song.waveform, 20, 180, 1360, 160, 
                                 play_pos, self.ui.deck_a_color)
        
        # Time display
        elapsed_sec = elapsed // 1000
        total_sec = int(current_song.duration)
        self.ui.draw_time_display(elapsed_sec, total_sec, 610, 360)
        
        # Crossfade progress
        if self.fade_start > 0:
            fade_elapsed = pygame.time.get_ticks() - self.fade_start
            fade_progress = min(fade_elapsed / FADE_DURATION, 1.0)
            
            bar_x, bar_y, bar_w, bar_h = 20, 450, 1360, 20
            pygame.draw.rect(self.ui.screen, self.ui.bg_panel, (bar_x, bar_y, bar_w, bar_h))
            
            fill_w = int(fade_progress * bar_w)
            # Gradient crossfade bar
            for i in range(fill_w):
                blend = i / bar_w
                color = tuple(int(self.ui.deck_a_color[j] * (1-blend) + self.ui.deck_b_color[j] * blend) 
                            for j in range(3))
                pygame.draw.line(self.ui.screen, color, (bar_x + i, bar_y), (bar_x + i, bar_y + bar_h))
            
            pygame.draw.rect(self.ui.screen, self.ui.line_color, (bar_x, bar_y, bar_w, bar_h), 1)
            
            fade_text = self.ui.small_font.render(f"CROSSFADE {int(fade_progress * 100)}%", 
                                                  True, self.ui.text_primary)
            self.ui.screen.blit(fade_text, (bar_x + 10, bar_y + 3))
        
        # Volume faders
        new_vol_a = self.ui.draw_fader_professional(
            120, 500, 50, 250, self.volumes[0], "DECK A", self.ui.deck_a_color
        )
        if new_vol_a is not None:
            self.volumes[0] = new_vol_a
            self.channels[0].set_volume(self.volumes[0])
        
        new_vol_b = self.ui.draw_fader_professional(
            1230, 500, 50, 250, self.volumes[1], "DECK B", self.ui.deck_b_color
        )
        if new_vol_b is not None:
            self.volumes[1] = new_vol_b
            self.channels[1].set_volume(self.volumes[1])
        
        # Control buttons
        button_y = 790
        button_h = 50
        
        pause_label = "PAUSE" if not self.is_paused else "PLAY"
        if self.ui.draw_button_pro(pause_label, 300, button_y, 150, button_h, 
                                   self.ui.bg_highlight):
            if not self.is_paused:
                self.pause_position = pygame.time.get_ticks() - self.track_start_time
                self.channels[self.current_channel].pause()
                self.is_paused = True
            else:
                self.track_start_time = pygame.time.get_ticks() - self.pause_position
                self.channels[self.current_channel].unpause()
                self.is_paused = False
            time.sleep(0.1)
        
        if self.ui.draw_button_pro("NEXT", 480, button_y, 150, button_h, self.ui.bg_highlight):
            if self.fade_start == 0:
                self.trigger_crossfade()
            time.sleep(0.1)
        
        # Sort modes
        sort_colors = {"bpm_key": (80, 150, 80), "bpm": (80, 120, 180), "energy": (180, 120, 80)}
        sort_labels = {"bpm_key": "BPM+KEY", "bpm": "BPM", "energy": "ENERGY"}
        
        if self.ui.draw_button_pro(f"SORT: {sort_labels[self.sort_mode]}", 
                                   770, button_y, 180, button_h, sort_colors[self.sort_mode]):
            modes = ["bpm_key", "bpm", "energy"]
            current_idx = modes.index(self.sort_mode)
            self.sort_mode = modes[(current_idx + 1) % len(modes)]
            self.apply_sort()
            time.sleep(0.1)
        
        # Status info
        status_y = 855
        status_items = [
            (f"BPM: {current_song.bpm:.0f}", 30),
            (f"KEY: {current_song.key} ({current_song.camelot})", 180),
            (f"ENERGY: {current_song.energy:.2f}", 420),
            (f"SORT: {sort_labels[self.sort_mode]}", 620)
        ]
        
        for text, x_pos in status_items:
            status_text = self.ui.tiny_font.render(text, True, self.ui.text_dim)
            self.ui.screen.blit(status_text, (x_pos, status_y))
        
        pygame.display.flip()
    
    def run(self):
        running = True
        
        while running:
            for event in pygame.event.get():
                if event.type == QUIT:
                    running = False
                
                elif event.type == DROPFILE and self.state == "waiting":
                    dropped_path = event.file
                    if os.path.isdir(dropped_path):
                        threading.Thread(
                            target=self.load_folder_parallel,
                            args=(dropped_path,),
                            daemon=True
                        ).start()
                
                elif event.type == KEYDOWN:
                    if event.key == K_SPACE and self.state == "playing":
                        if self.fade_start == 0:
                            self.trigger_crossfade()
                    elif event.key == K_ESCAPE:
                        running = False
            
            if (self.state == "playing" and self.fade_start == 0 and 
                not self.channels[self.current_channel].get_busy()):
                self.trigger_crossfade()
            
            if self.state == "playing":
                self.update_crossfade()
            
            if self.state == "waiting":
                self.ui.draw_drag_screen()
            elif self.state == "playing":
                self.draw_playing_screen()
            
            self.ui.clock.tick(60)
        
        pygame.quit()

if __name__ == "__main__":
    app = DJMixerApp()
    app.run()
