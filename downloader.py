import requests
import json
import os
import sys
import yt_dlp
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import customtkinter as ctk
from PIL import Image, ImageTk
import urllib.parse
import shutil
import time
import pyperclip
import re
import base64
import pickle
from datetime import timedelta
import webbrowser
import subprocess

# Tool version
VERSION = "2.5.3"  # Updated version number

# Server URL for License Verification
SERVER_URL = "https://raw.githubusercontent.com/aziztech1234/License-Keys/main/keys.json"
# GitHub URL for updates
UPDATE_URL = "https://raw.githubusercontent.com/aziztech1234/UltraFastVideoDownloader/main/downloader.py"

# Global variables
root = None
download_queue = []
current_downloads = {}
downloading = False
paused = False
settings = None
progress_info = {}  # Store progress information for each download
video_table = None  # Table to display video information
download_button = None  # Global reference to the download button
start_bulk_button = None  # Global reference to bulk download button
header_label = None
status_label = None
right_click_menu = None
context_menu_row = None

# Set theme appearance
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("green")

# Function to center windows relative to root window
def center_window(window, width, height):
    if root:
        # Get root window position and size
        root_x = root.winfo_x()
        root_y = root.winfo_y()
        root_width = root.winfo_width()
        root_height = root.winfo_height()
        
        # Calculate position for centering
        x = root_x + (root_width // 2) - (width // 2)
        y = root_y + (root_height // 2) - (height // 2)
        
        # Set geometry
        window.geometry(f"{width}x{height}+{x}+{y}")
    else:
        # Center on screen if root not available
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")

# License Key Verification Function
def is_key_valid(user_key):
    try:
        response = requests.get(SERVER_URL, headers={"Cache-Control": "no-cache"})
        if response.status_code == 200:
            license_data = json.loads(response.text)
            valid_keys = license_data.get("valid_keys", [])
            disabled_keys = license_data.get("disabled_keys", [])
            
            # Check if key is valid and not disabled
            return user_key.strip() in valid_keys and user_key.strip() not in disabled_keys
        return False  
    except:
        # If we can't check online, use cached data
        return verify_cached_license(user_key)

# Function to save license key securely
def save_license_key(key):
    try:
        # Create a more secure storage by encoding the key
        encoded = base64.b64encode(key.encode()).decode()
        license_data = {"key": encoded, "timestamp": time.time()}
        
        # Save to multiple locations for redundancy
        license_file = os.path.join(os.path.expanduser("~"), ".video_downloader_license")
        with open(license_file, "w") as f:
            f.write(encoded)
        
        # Also save as pickled data with more info
        license_data_file = os.path.join(os.path.expanduser("~"), ".video_downloader_data")
        with open(license_data_file, "wb") as f:
            pickle.dump(license_data, f)
            
        return True
    except Exception as e:
        print(f"Error saving license: {str(e)}")
        return False

# Function to load and verify cached license
def verify_cached_license(key=None):
    try:
        license_data_file = os.path.join(os.path.expanduser("~"), ".video_downloader_data")
        if os.path.exists(license_data_file):
            with open(license_data_file, "rb") as f:
                license_data = pickle.load(f)
                
            # If key is provided, verify it matches the stored key
            if key:
                stored_key = base64.b64decode(license_data["key"].encode()).decode()
                return stored_key == key
            
            # If no key provided, just return the stored key
            return base64.b64decode(license_data["key"].encode()).decode()
        
        # Fallback to the old method
        license_file = os.path.join(os.path.expanduser("~"), ".video_downloader_license")
        if os.path.exists(license_file):
            with open(license_file, "r") as f:
                encoded_key = f.read().strip()
                return base64.b64decode(encoded_key.encode()).decode()
        
        return None if key is None else False
    except Exception as e:
        print(f"Error verifying license: {str(e)}")
        return None if key is None else False

# Function to detect platform from URL
def detect_platform(url):
    domain = urllib.parse.urlparse(url).netloc
    if 'youtube' in domain or 'youtu.be' in domain:
        return "YouTube"
    elif 'tiktok' in domain:
        return "TikTok"
    elif 'instagram' in domain:
        return "Instagram"
    elif 'facebook' in domain or 'fb.com' in domain or 'fb.watch' in domain:
        return "Facebook"
    else:
        return "Other"

# Function to clean up filename
def clean_filename(filename):
    if filename is None:
        return "Unknown"
    # Remove illegal characters for filenames
    filename = re.sub(r'[\\/*?:"<>|]', "", filename)
    # Remove extra spaces
    filename = re.sub(r'\s+', " ", filename).strip()
    # Limit filename length
    if len(filename) > 150:
        filename = filename[:147] + "..."
    return filename

# Function to format file size
def format_size(size_bytes):
    if size_bytes is None:
        return "Unknown"
    # Convert bytes to human-readable format
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

# Function to format duration
def format_duration(duration_seconds):
    if duration_seconds is None:
        return "Unknown"
    return str(timedelta(seconds=int(duration_seconds)))

# Updates a status message (now uses status_label instead of header)
def update_header_message(message, color="#FFFFFF"):
    """Updates the status message in a given color - now uses status_label"""
    if status_label:
        # Update the status label with the message instead of the header
        status_label.configure(text=message)

# Get video output path from a row_id
def get_video_output_path(row_id):
    """Get the expected output path for a video based on its URL and title with more robust path detection"""
    try:
        if not video_table or not row_id:
            return None
            
        values = video_table.item(row_id, "values")
        title = values[3] if len(values) > 3 else "Unknown"
        
        # Get URL from either table row or tags
        url = values[1] if len(values) > 1 else None
        tags = video_table.item(row_id, "tags")
        
        # If URL wasn't in values, try to get from tags
        if not url:
            for tag in tags:
                if tag != "url" and tag != "completed" and tag != "failed" and tag != "editing":
                    url = tag
                    break
                    
        if not url:
            return None
            
        # Get platform
        platform = detect_platform(url)
        
        # Get download path
        download_dir = download_path.get() or settings.get("default_download_path", 
                                                         os.path.join(os.path.expanduser("~"), "Downloads"))
        platform_path = os.path.join(download_dir, platform)
        
        # Debug message - useful for troubleshooting path issues
        print(f"Looking for video in {platform_path} with title: {title}")
        
        # Check if the folder exists
        if not os.path.exists(platform_path):
            return None
            
        # For Facebook and TikTok, use a more thorough search approach
        # Since these platforms often have more complex filenames
        if platform in ["Facebook", "TikTok", "Instagram"]:
            # List all video files in the directory
            video_files = []
            for file in os.listdir(platform_path):
                if file.lower().endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov')):
                    video_files.append(file)
                    
            # Sort by modification time (newest first)
            video_files.sort(key=lambda x: os.path.getmtime(os.path.join(platform_path, x)), reverse=True)
            
            # First, check if we have any files at all
            if video_files:
                # For Facebook, the newest file is probably the one we want
                newest_file = video_files[0]
                print(f"Found newest video file: {newest_file}")
                return os.path.join(platform_path, newest_file)
        
        # For other platforms, try to match by title
        simplified_title = clean_filename(title.lower())
        
        # Check if we have the direct output file path in progress_info
        for info_url, info in progress_info.items():
            if url == info_url and 'output_file' in info and info['output_file']:
                if os.path.exists(info['output_file']):
                    print(f"Found exact file via progress_info: {info['output_file']}")
                    return info['output_file']
        
        # Search for files with title in the name
        matching_files = []
        for file in os.listdir(platform_path):
            file_lower = file.lower()
            if file_lower.endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov')):
                if simplified_title in file_lower:
                    matching_files.append(file)
                    
        if matching_files:
            # Sort by modification time (newest first)
            matching_files.sort(key=lambda x: os.path.getmtime(os.path.join(platform_path, x)), reverse=True)
            newest_match = matching_files[0]
            print(f"Found matching file by title: {newest_match}")
            return os.path.join(platform_path, newest_match)
            
        # If still not found, try searching for any part of the URL in the filename
        url_parts = url.split('/')
        for part in url_parts:
            if len(part) > 5:  # Only consider meaningful parts (not just "www" etc)
                for file in os.listdir(platform_path):
                    file_lower = file.lower()
                    if file_lower.endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov')):
                        if part.lower() in file_lower:
                            print(f"Found file by URL part: {file}")
                            return os.path.join(platform_path, file)
        
        # If we still haven't found it, just return the most recent video file
        video_files = []
        for file in os.listdir(platform_path):
            if file.lower().endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov')):
                video_files.append(file)
                
        if video_files:
            # Sort by modification time (newest first)
            video_files.sort(key=lambda x: os.path.getmtime(os.path.join(platform_path, x)), reverse=True)
            newest_file = video_files[0]
            print(f"Found newest video file as last resort: {newest_file}")
            return os.path.join(platform_path, newest_file)
        
        return None
    except Exception as e:
        print(f"Error getting video path: {str(e)}")
        return None

# Progress Hook Function
class ProgressManager:
    def __init__(self, url, row_id):
        self.url = url
        self.row_id = row_id
        self.start_time = time.time()
        self.title = None
        self.author = None
        self.duration = None
        self.filesize = None
        self.output_file = None
        self.hashtags = None
        
    def update_progress(self, d):
        global progress_info
        
        if d['status'] == 'downloading':
            try:
                # Get percentage and speed
                percentage = d.get('_percent_str', '0%').strip()
                speed = d.get('_speed_str', 'N/A').strip()
                eta = d.get('_eta_str', '').strip()
                
                # Track output filename if available
                if 'filename' in d:
                    self.output_file = d['filename']
                
                # Get video metadata if available
                if not self.title and 'info_dict' in d:
                    info = d['info_dict']
                    self.title = info.get('title', 'Unknown Title')
                    self.author = info.get('uploader', info.get('channel', 'Unknown Author'))
                    self.duration = info.get('duration')
                    self.filesize = info.get('filesize')
                    
                    # Get hashtags if available (for Instagram and TikTok)
                    if 'hashtags' in info:
                        self.hashtags = info.get('hashtags', [])
                    elif 'tags' in info:
                        self.hashtags = info.get('tags', [])
                    
                    # Update the table with metadata
                    root.after(0, lambda: update_video_metadata(self.row_id, self.title, self.author, self.duration, self.filesize))
                
                # Store progress info for status bar
                progress_info[self.url] = {
                    'percentage': percentage,
                    'speed': speed,
                    'eta': eta,
                    'title': self.title,
                    'hashtags': self.hashtags,
                    'output_file': self.output_file
                }
                
                # Update overall progress in status bar
                update_overall_progress()
                
                # Update table with progress
                root.after(0, lambda: update_video_status(self.row_id, f"Downloading {percentage}", speed))
                
                # Update status with current download info
                platform = detect_platform(self.url)
                status_text = f"Downloading {platform}: {percentage} | {self.title if self.title else 'Unknown'}"
                root.after(0, lambda: update_header_message(status_text))
                
            except Exception as e:
                print(f"Progress update error: {str(e)}")
                
        elif d['status'] == 'finished':
            # The download part is finished, now it's post-processing
            elapsed = time.time() - self.start_time
            root.after(0, lambda: update_video_status(self.row_id, f"Processing...", f"{elapsed:.1f}s"))
            
            # Store output file if set
            if self.output_file and self.url in progress_info:
                progress_info[self.url]['output_file'] = self.output_file
            
        elif d['status'] == 'error':
            # An error occurred during download
            error_msg = d.get('error', 'Unknown error')
            print(f"Download error: {error_msg}")
            root.after(0, lambda: update_video_status(self.row_id, "Failed", str(error_msg)[:20]))
            
            # Remove from progress tracking
            if self.url in progress_info:
                del progress_info[self.url]
                update_overall_progress()

def update_video_status(row_id, status, extra_info=""):
    """Update the status column in the video table"""
    try:
        if not video_table:
            return
            
        values = list(video_table.item(row_id, "values"))
        values[2] = status  # Update status column (third column)
        if extra_info:
            # Add extra info to the time column for speed or processing time
            values[5] = extra_info
        video_table.item(row_id, values=values)
        
        # Update the row style based on status
        if "Completed" in status:
            # Preserve the URL in tags when marking as completed
            url = values[1] if len(values) > 1 else None
            video_table.item(row_id, values=values, tags=("completed", url))
        elif "Failed" in status:
            # Keep the URL in tags when marking as failed
            url = values[1] if len(values) > 1 else None
            video_table.item(row_id, tags=("failed", url))
        elif "Paused" in status:
            # Keep the URL in tags when marking as paused
            url = values[1] if len(values) > 1 else None
            video_table.item(row_id, tags=("paused", url))
    except Exception as e:
        print(f"Update video status error: {str(e)}")

def update_video_metadata(row_id, title, author, duration, filesize):
    """Update video metadata in the table"""
    try:
        if not video_table:
            return
            
        values = list(video_table.item(row_id, "values"))
        # Update title, author, time, size columns
        values[3] = clean_filename(title) if title else "Unknown"  # Titles (4th column)
        values[4] = author if author else "Unknown"  # Author (5th column)
        values[5] = format_duration(duration) if values[5] == "Unknown" else values[5]  # Time (6th column)
        values[6] = format_size(filesize)  # Size (7th column)
        video_table.item(row_id, values=values)
    except Exception as e:
        print(f"Update video metadata error: {str(e)}")

# Update overall progress in status bar
def update_overall_progress():
    if not status_label or not progress_bar:
        return
        
    if not progress_info:
        status_label.configure(text="Waiting for download...")
        progress_bar.set(0)
        return
    
    # Calculate average progress
    total_percentage = 0
    total_items = 0
    active_downloads = []
    
    for url, info in progress_info.items():
        try:
            percentage = info['percentage'].strip('%')
            if percentage and percentage != 'N/A':
                total_percentage += float(percentage)
                total_items += 1
            active_downloads.append(f"{os.path.basename(url)[:15]}... ({info['percentage']} @ {info['speed']})")
        except:
            pass
    
    # Update progress bar
    if total_items > 0:
        avg_percentage = total_percentage / total_items / 100
        progress_bar.set(avg_percentage)
        
        # Update status text
        if len(active_downloads) <= 2:
            status_text = " | ".join(active_downloads)
        else:
            status_text = f"{len(active_downloads)} files downloading at {sum([float(info.get('speed', '0 MiB/s').split(' ')[0]) for info in progress_info.values() if info.get('speed', '0 MiB/s').split(' ')[0].replace('.', '', 1).isdigit()]):.1f} MiB/s"
        
        status_label.configure(text=status_text)

# Get optimized format options based on platform - ENHANCED VERSION
def get_format_options(platform, quality):
    """
    Returns optimized format selection strings for different platforms.
    Updated to fix issues with YouTube, Instagram, and TikTok.
    """
    if platform == "YouTube":
        # Updated YouTube format selection to work with recent changes
        if quality == "Max Quality":
            return 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4] / bv*+ba/b'
        else:
            return f'bv*[height<={quality}][ext=mp4]+ba[ext=m4a]/b[height<={quality}][ext=mp4] / bv*[height<={quality}]+ba/b[height<={quality}]'
    elif platform == "Facebook":
        # Facebook format selection - works fine, kept as is
        return 'best[ext=mp4]/dash_sd_src/dash_hd_src/hd_src/sd_src'
    elif platform == "TikTok":
        # Enhanced TikTok format to avoid HEVC issues completely
        return 'bv*[vcodec!*=hevc][vcodec!*=h265]+ba/b[vcodec!*=hevc][vcodec!*=h265]/b'
    elif platform == "Instagram":
        # Improved Instagram format selection for better metadata
        return 'best/dash_hd/dash_sd'
    else:
        # Default improved format for other platforms
        if quality == "Max Quality":
            return 'bv*+ba/b'
        else:
            return f'bv*[height<={quality}]+ba/b[height<={quality}]'

# Enhanced platform-specific user agents
def get_platform_user_agent(platform):
    """
    Returns optimized user agents for different platforms.
    Updated with more modern user agent strings.
    """
    # Modern desktop user agent
    common_desktop = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    if platform == "YouTube":
        # Modern Chrome user agent for YouTube
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    elif platform == "TikTok":
        # TikTok works better with mobile user agents
        return "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    elif platform == "Instagram":
        # Updated Instagram app-like user agent
        return "Instagram 271.0.0.16.108 Android (33/13; 420dpi; 1080x2210; Google/google; Pixel 7; panther; armv8l; en_US; 429794285)"
    elif platform == "Facebook":
        # Updated Facebook user agent
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
    else:
        return common_desktop

# Video Download Function - ENHANCED VERSION WITH PLATFORM FIXES
def download_video(url, download_path, quality, thread_count, row_id):
    """
    Main download function, updated to fix issues with all platforms.
    """
    platform = detect_platform(url)
    
    # Create platform-specific folder
    platform_path = os.path.join(download_path, platform)
    if not os.path.exists(platform_path):
        os.makedirs(platform_path)
    
    # Get optimized format selection for this platform
    format_option = get_format_options(platform, quality)
    
    # Create progress manager
    progress_manager = ProgressManager(url, row_id)
    
    # Setup output template based on settings
    if settings.get("use_original_title", False) and settings.get("use_tags", False):
        # If original title with hashtags is enabled
        output_template = '%(title)s %(hashtags)s.%(ext)s'
    elif settings.get("use_original_title", False):
        # Just original title
        output_template = '%(title)s.%(ext)s'
    else:
        # Standard output format
        output_template = '%(title)s.%(ext)s'
    
    # Prepare base download options
    ydl_opts = {
        'format': format_option,
        'outtmpl': os.path.join(platform_path, output_template),
        'merge_output_format': 'mp4',
        'progress_hooks': [progress_manager.update_progress],
        'noplaylist': True,
        'quiet': False,
        'writeinfojson': settings.get("create_backup", False),
        'writedescription': settings.get("create_backup", False),
        'writesubtitles': settings.get("write_subtitles", False),
        'subtitleslangs': ['en'] if settings.get("write_subtitles", False) else None,
        'embedsubtitles': settings.get("embed_subtitles", False),
        'nooverwrites': False,
        'retries': settings.get("retries", 5),
        'fragment_retries': 15,
        'skip_unavailable_fragments': False,
        'keepvideo': False,  # Changed to False to avoid keeping separate files
        'overwrites': True,
        'ignoreerrors': True,
        'prefer_ffmpeg': True,
        'socket_timeout': 60,
        'writethumbnail': True,  # Always download thumbnail
        # Common user agent
        'http_headers': {
            'User-Agent': get_platform_user_agent(platform),
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        }
    }
    
    # YouTube-specific options for better merging
    if platform == "YouTube":
        ydl_opts.update({
            'merge_output_format': 'mp4',
            'postprocessors': [
                {
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4'
                },
                {
                    'key': 'FFmpegMetadata',
                    'add_metadata': True
                },
                {
                    'key': 'EmbedThumbnail',  # Add thumbnail to video
                    'already_have_thumbnail': False
                },
                {
                    'key': 'MoveFiles',
                    'dest_dir': platform_path
                }
            ],
            'postprocessor_args': {
                'ffmpeg': [
                    '-c:v', 'libx264',  # Force H.264 codec
                    '-c:a', 'aac',
                    '-strict', 'experimental',
                    '-movflags', '+faststart'
                ]
            },
            # YouTube-specific browser headers
            'http_headers': {
                'User-Agent': get_platform_user_agent("YouTube"),
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Referer': 'https://www.youtube.com/',
                'Origin': 'https://www.youtube.com'
            }
        })
    
    # TikTok-specific options
    elif platform == "TikTok":
        ydl_opts.update({
            'format': 'bv*[vcodec!*=hevc][vcodec!*=h265]+ba/b[vcodec!*=hevc][vcodec!*=h265]/b',
            'merge_output_format': 'mp4',
            'postprocessors': [
                {
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4'
                },
                {
                    # Force conversion to H.264 for all TikTok videos
                    'key': 'FFmpegVideoRemuxer',
                    'preferedformat': 'mp4'
                },
                {
                    'key': 'FFmpegMetadata',
                    'add_metadata': True
                }
            ],
            'postprocessor_args': {
                'ffmpeg': [
                    '-c:v', 'libx264',  # Force H.264 codec
                    '-c:a', 'aac',
                    '-strict', 'experimental',
                    '-movflags', '+faststart'
                ]
            },
            'http_headers': {
                'User-Agent': get_platform_user_agent("TikTok"),
                'Referer': 'https://www.tiktok.com/',
                'Origin': 'https://www.tiktok.com'
            }
        })
    
    # Facebook-specific options
    elif platform == "Facebook":
        ydl_opts.update({
            'format': 'best[ext=mp4]/dash_sd_src/dash_hd_src/hd_src/sd_src',
            'merge_output_format': 'mp4',
            'http_headers': {
                'User-Agent': get_platform_user_agent("Facebook"),
                'Referer': 'https://www.facebook.com/',
                'Origin': 'https://www.facebook.com'
            }
        })
    
    # Instagram-specific options
    elif platform == "Instagram":
        ydl_opts.update({
            'format': 'best/dash_hd/dash_sd',
            'merge_output_format': 'mp4',
            'extract_flat': False,
            'writeinfojson': True,  # Always save info for Instagram
            'postprocessors': [
                {
                    'key': 'FFmpegMetadata',
                    'add_metadata': True
                },
                {
                    'key': 'EmbedThumbnail',
                    'already_have_thumbnail': False
                }
            ],
            'http_headers': {
                'User-Agent': get_platform_user_agent("Instagram"),
                'Referer': 'https://www.instagram.com/',
                'Origin': 'https://www.instagram.com'
            },
            'cookiefile': os.path.join(os.path.expanduser("~"), ".ig_cookies.txt")
        })
        
        # Try to find or create Instagram cookie file
        cookie_file = os.path.join(os.path.expanduser("~"), ".ig_cookies.txt")
        if not os.path.exists(cookie_file):
            # Create empty cookie file
            with open(cookie_file, 'w') as f:
                f.write("# Instagram cookies file\n")
    
    # Add aria2c support with thread count if enabled
    if thread_count > 1:
        ydl_opts['external_downloader'] = 'aria2c'
        ydl_opts['external_downloader_args'] = [
            f'-x{thread_count}',
            f'-j{thread_count}',
            f'-s{thread_count}',
            '--min-split-size=1M',
            '--max-connection-per-server=16',
            '--stream-piece-selector=inorder',
            '-c',
            '--file-allocation=none',
            '--auto-file-renaming=false'
        ]
    
    # Debug output
    print(f"Downloading {platform} video with format: {format_option}")
    print(f"Output template: {output_template}")
    
    try:
        # Enhanced download process with multiple attempts
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # First try to extract info
            try:
                info = ydl.extract_info(url, download=False)
                
                # Pre-update the table with available metadata
                if info and isinstance(info, dict):
                    title = clean_filename(info.get('title', 'Unknown Title'))
                    author = info.get('uploader', info.get('channel', 'Unknown Author'))
                    duration = info.get('duration')
                    filesize = info.get('filesize')
                    
                    # Update metadata in the table
                    root.after(0, lambda: update_video_metadata(row_id, title, author, duration, filesize))
                    
                    # Debug output
                    print(f"Video info: Title: {title}, Author: {author}, Duration: {duration}, Size: {filesize}")
            except Exception as e:
                print(f"Info extraction error: {str(e)}")
                # Continue with download even if metadata extraction fails
            
            # Start actual download
            ydl.download([url])
        
        # After download, verify the file exists
        video_path = get_video_output_path(row_id)
        if video_path and os.path.exists(video_path):
            print(f"Download successful, file saved at: {video_path}")
            # Mark download as complete
            root.after(0, lambda: update_video_status(row_id, "Completed", "Done"))
            root.after(0, lambda: update_header_message(f"Download Completed: {os.path.basename(video_path)}", "#00FF00"))
            return True
        else:
            print("Download might have failed, file not found at expected location")
            root.after(0, lambda: update_video_status(row_id, "Failed", "File not found"))
            root.after(0, lambda: update_header_message("Download failed: File not found", "#FF0000"))
            return False
            
    except Exception as e:
        error_msg = str(e)
        print(f"Download error: {error_msg}")
        root.after(0, lambda: update_video_status(row_id, "Failed", error_msg[:20] + "..."))
        root.after(0, lambda: update_header_message(f"Download Failed: {error_msg[:50]}", "#FF0000"))
        return False
        
      # Folder Selection Function
def browse_folder():
    folder_selected = filedialog.askdirectory()
    if folder_selected:
        download_path.set(folder_selected)
        folder_entry.delete(0, tk.END)
        folder_entry.insert(0, folder_selected)
        # Save the selected path to settings
        settings["default_download_path"] = folder_selected
        save_settings_to_file()

# Add URL to list
def add_url():
    # Check if clipboard contains URL and auto-paste
    clipboard_content = pyperclip.paste().strip()
    url = ""
    
    # Common URL prefixes to detect
    url_prefixes = ['http://', 'https://', 'www.', 'youtube.com', 'youtu.be', 'tiktok.com', 'instagram.com', 'facebook.com']
    
    # Check if clipboard contains URL and auto-paste is enabled
    if settings.get("auto_paste", True) and any(prefix in clipboard_content.lower() for prefix in url_prefixes):
        url = clipboard_content
    
    if url:
        add_url_to_table(url)
    else:
        # If no URL in clipboard or auto-paste disabled, show manual entry dialog
        url_window = ctk.CTkToplevel(root)
        url_window.title("Add URL")
        url_window.geometry("500x150")
        url_window.resizable(False, False)
        url_window.grab_set()  # Make the window modal
        
        # Center window relative to root
        center_window(url_window, 500, 150)
        
        ctk.CTkLabel(url_window, text="Enter Video URL:").pack(pady=(15, 5))
        
        url_input = ctk.CTkEntry(url_window, width=400)
        url_input.pack(pady=5)
        url_input.focus()
        
        def add_to_list():
            url = url_input.get().strip()
            if url:
                add_url_to_table(url)
                url_window.destroy()
        
        button_frame = ctk.CTkFrame(url_window, fg_color="transparent")
        button_frame.pack(pady=10)
        
        ctk.CTkButton(button_frame, text="Add", command=add_to_list, width=100).pack(side=tk.LEFT, padx=5)
        ctk.CTkButton(button_frame, text="Cancel", command=url_window.destroy, width=100).pack(side=tk.LEFT, padx=5)
        
        # Bind Enter key to add URL
        url_input.bind("<Return>", lambda event: add_to_list())

def add_url_to_table(url):
    """Add a URL to the table with initial values"""
    try:
        # Count existing items to determine the row number
        count = len(video_table.get_children()) + 1
        
        # Insert new row with default values
        row_id = video_table.insert("", "end", values=(
            count,              # Row number
            url,                # URL
            "Pending",          # Status
            "Fetching...",      # Title
            "Unknown",          # Author
            "Unknown",          # Duration
            "Unknown"           # Size
        ), tags=("url", url))   # Store URL in tags
        
        # Update count in footer
        update_link_count()
        
        # Update header with new link count
        platform = detect_platform(url)
        update_header_message(f"Link Count: {count} | Added {platform} URL")
    except Exception as e:
        print(f"Error adding URL to table: {str(e)}")

def update_link_count():
    """Update the link count in the footer"""
    count = len(video_table.get_children())
    link_count_label.configure(text=f"Link Count: {count}")

# Function to pause all downloads - FIXED
def pause_all_downloads():
    global paused
    paused = True
    update_header_message("Downloads paused. Click Resume to continue.")
    
    # Update status for all active downloads
    for item_id in video_table.get_children():
        values = video_table.item(item_id, "values")
        status = values[2] if len(values) > 2 else ""
        
        # Only change status for currently downloading items
        if "Downloading" in status:
            # Preserve the URL in tags when marking as paused
            url = values[1] if len(values) > 1 else None
            update_video_status(item_id, "Paused", "")
            video_table.item(item_id, tags=("paused", url))

# Function to resume all downloads - FIXED
def resume_all_downloads():
    global paused
    paused = False
    update_header_message("Downloads resumed.")
    
    # Update status for all paused downloads
    for item_id in video_table.get_children():
        values = video_table.item(item_id, "values")
        status = values[2] if len(values) > 2 else ""
        
        if status == "Paused":
            # Preserve the URL in tags when updating status
            url = values[1] if len(values) > 1 else None
            update_video_status(item_id, "Pending", "")
            video_table.item(item_id, tags=("url", url))
    
    # Restart downloads if they were active before
    if downloading:
        start_download()

# Reset URL table and stop ongoing downloads
def reset_urls():
    global downloading, download_queue, progress_info
    
    if len(video_table.get_children()) > 0:
        # Add more clear warning if downloads are in progress
        warning_message = "Are you sure you want to clear all URLs?"
        if downloading:
            warning_message = "Downloads are in progress! Stopping all downloads and clearing URLs. Continue?"
            
        if messagebox.askyesno("Reset URLs", warning_message):
            # First stop any ongoing downloads
            if downloading:
                # Clear download queue to prevent new tasks from starting
                download_queue.clear()
                
                # Set downloading flag to false
                downloading = False
                
                # Clear progress tracking
                progress_info.clear()
                
                # Re-enable download buttons
                if download_button:
                    download_button.configure(state="normal")
                if start_bulk_button:
                    start_bulk_button.configure(state="normal")
                
                # Reset progress bar
                progress_bar.set(0)
                
                # Update status
                status_label.configure(text="Downloads stopped and reset")
                
                # Force kill any active download threads after a short delay
                def terminate_threads():
                    # Identify and interrupt download worker threads
                    for thread in threading.enumerate():
                        if thread != threading.current_thread() and "download_worker" in thread.name:
                            try:
                                # We can't actually terminate threads in Python, but we've set the 
                                # downloading flag to False which should cause them to exit
                                pass
                            except:
                                pass
                
                # Schedule the thread termination after a short delay
                root.after(200, terminate_threads)
            
            # Now clear all URLs from the table
            for item in video_table.get_children():
                video_table.delete(item)
                
            # Update link count
            update_link_count()
            
            # Update header message
            if downloading:
                update_header_message("All downloads stopped and URLs cleared")
            else:
                update_header_message("All URLs cleared")

# Start Bulk Download
def start_download():
    global downloading, download_queue, download_button, start_bulk_button
    
    if downloading:
        messagebox.showinfo("Download in Progress", "Download is already in progress!")
        return
    
    # Get all URLs from the table
    items = video_table.get_children()
    if not items:
        messagebox.showwarning("Warning", "Please add at least one video URL!")
        return
    
    path = download_path.get().strip()
    if not path:
        messagebox.showwarning("Warning", "Please select a download folder!")
        return
    
    quality = quality_var.get()
    thread_count = int(thread_count_var.get())
    
    downloading = True
    
    # Make sure we reference the global buttons
    if download_button:
        download_button.configure(state="disabled")
    if start_bulk_button:
        start_bulk_button.configure(state="disabled")
        
    status_label.configure(text="Starting downloads...")
    update_header_message(f"Starting downloads for {len(items)} videos")
    
    # Clear download queue and add all items
    download_queue.clear()
    
    for item in items:
        # Get URL from tags and skip already downloading/completed items
        tags = video_table.item(item, "tags")
        values = video_table.item(item, "values")
        
        if len(tags) > 1 and tags[0] == "url":
            url = tags[1]
            status = values[2]  # Status is the 3rd column (index 2)
            
            # Only queue items that are pending or failed
            if status in ["Pending", "Failed", "Paused"]:
                download_queue.append((item, url))
    
    # Start worker threads based on configuration
    for _ in range(min(thread_count, len(download_queue))):
        t = threading.Thread(target=download_worker, args=(path, quality, thread_count), daemon=True)
        t.start()

# Download worker function
def download_worker(path, quality, thread_count):
    global downloading, download_queue, download_button, start_bulk_button, paused
    
    while download_queue:
        # Check if downloads are paused
        if paused:
            time.sleep(1)  # Wait before checking again
            continue
            
        # Check if downloading flag is still set
        if not downloading:
            break  # Exit if downloads have been stopped
            
        try:
            # Get next URL from queue
            row_id, url = download_queue.pop(0)
            
            # Update status in table
            root.after(0, lambda r=row_id: update_video_status(r, "Starting", ""))
            
            # Update status label
            platform = detect_platform(url)
            root.after(0, lambda: status_label.configure(
                text=f"Downloading {platform}: {url[:30]}..." if len(url) > 30 else f"Downloading {platform}: {url}"))
            
            # Download the video
            success = download_video(url, path, quality, thread_count, row_id)
        except Exception as e:
            print(f"Error in download worker: {str(e)}")
    
    # Check if all downloads are complete
    download_queue_empty = len(download_queue) == 0
    
    if download_queue_empty:
        # Use a safer method to count active download workers
        active_workers = 0
        for t in threading.enumerate():
            if t != threading.current_thread() and t.is_alive() and "download_worker" in t.name:
                active_workers += 1
        
        if active_workers == 0:
            # This is the last thread, reset everything
            root.after(0, lambda: status_label.configure(text="All downloads completed!"))
            root.after(0, lambda: progress_bar.set(1.0))  # Set progress to 100%
            
            # Re-enable download buttons - guaranteed to run
            root.after(100, enable_download_buttons)  # Small delay to ensure UI updates
            root.after(0, lambda: update_header_message("All downloads completed successfully!", "#00FF00"))
            root.after(150, set_downloading_false)  # Set this after enabling buttons

def enable_download_buttons():
    global download_button, start_bulk_button
    
    # Use root.after to ensure this runs in the main thread
    def _enable():
        if download_button:
            download_button.configure(state="normal")
        if start_bulk_button:
            start_bulk_button.configure(state="normal")
    
    # Run in main thread if we're not already there
    if threading.current_thread() is not threading.main_thread():
        root.after(0, _enable)
    else:
        _enable()

# Helper function to safely set the downloading flag to False
def set_downloading_false():
    global downloading
    downloading = False
    # Double check that buttons are enabled
    enable_download_buttons()

# Function to install YouTube packages
def install_yt_packages():
    try:
        # Create a popup window with options
        install_window = ctk.CTkToplevel(root)
        install_window.title("Install YouTube Packages")
        install_window.geometry("500x350")
        install_window.resizable(False, False)
        install_window.grab_set()
        
        # Center window relative to root
        center_window(install_window, 500, 350)
        
        ctk.CTkLabel(install_window, text="Install Additional Packages", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(20, 5))
        
        info_text = """The video downloader requires additional packages to function correctly with YouTube.
        
This will install/update the following packages:
- yt-dlp (main downloader)
- ffmpeg (video processor)
- aria2c (multi-threaded downloader)

Select an installation method below:"""
        
        info_label = ctk.CTkLabel(install_window, text=info_text, wraplength=450, justify="left")
        info_label.pack(pady=15, padx=20)
        
        # Installation methods
        def install_pip():
            install_window.destroy()
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"])
                messagebox.showinfo("Installation", "YouTube packages installed successfully via pip!")
            except Exception as e:
                messagebox.showerror("Installation Error", f"Failed to install packages: {str(e)}")
        
        def open_instructions():
            install_window.destroy()
            webbrowser.open("https://github.com/yt-dlp/yt-dlp/wiki/Installation")
        
        # Buttons for installation methods
        button_frame = ctk.CTkFrame(install_window, fg_color="transparent")
        button_frame.pack(pady=20)
        
        ctk.CTkButton(button_frame, text="Install with pip", command=install_pip, 
                    width=200, height=40, fg_color="#2ecc71", hover_color="#27ae60").pack(pady=10)
        
        ctk.CTkButton(button_frame, text="Open Installation Instructions", command=open_instructions,
                    width=200, height=40, fg_color="#3498db", hover_color="#2980b9").pack(pady=10)
        
        ctk.CTkButton(button_frame, text="Cancel", command=install_window.destroy,
                    width=200, height=40, fg_color="#e74c3c", hover_color="#c0392b").pack(pady=10)
        
    except Exception as e:
        messagebox.showerror("Error", f"Error opening installation window: {str(e)}")

# Function to open Aziz YouTube channel
def open_youtube_channel():
    webbrowser.open("https://www.youtube.com/@AzizKhan077")

# Function to open Aziz Facebook page
def open_facebook_page():
    webbrowser.open("https://www.facebook.com/princeaziz011")

# Function to check for updates
def check_for_updates():
    try:
        # Show checking message
        update_header_message("Checking for updates...", "#2980B9")
        
        # Fetch the latest script from GitHub
        response = requests.get(UPDATE_URL, timeout=10)
        
        if response.status_code == 200:
            # Extract version from the fetched script
            script_content = response.text
            latest_version_match = re.search(r'VERSION\s*=\s*["\']([\d\.]+)["\']', script_content)
            
            if latest_version_match:
                latest_version = latest_version_match.group(1)
                
                # Compare versions
                if latest_version > VERSION:
                    # New version available
                    update_header_message(f"New version {latest_version} available!", "#2ECC71")
                    
                    # Ask user if they want to update
                    if messagebox.askyesno("Update Available", 
                                         f"A new version ({latest_version}) is available. Your current version is {VERSION}.\n\nWould you like to update now?"):
                        # Update the script
                        try:
                            # Get the path to the current script
                            if hasattr(sys, 'frozen'):
                                # If running as executable
                                script_path = sys.executable
                                messagebox.showinfo("Update Error", 
                                                 "Automatic updates are not supported for the executable version.\n\nPlease download the latest version manually from the GitHub repository.")
                                return
                            else:
                                # If running as script
                                script_path = sys.argv[0]
                                
                                # Create backup
                                backup_path = script_path + ".backup"
                                shutil.copy2(script_path, backup_path)
                                
                                # Write the new version
                                with open(script_path, 'w', encoding='utf-8') as f:
                                    f.write(script_content)
                                
                                # Show success message
                                if messagebox.askyesno("Update Successful", 
                                                    f"The application has been updated to version {latest_version}.\n\nThe application needs to restart to apply the update. Restart now?"):
                                    # Restart the application
                                    python = sys.executable
                                    os.execl(python, python, *sys.argv)
                        except Exception as e:
                            messagebox.showerror("Update Error", f"Failed to update: {str(e)}")
                else:
                    # Already up to date
                    update_header_message("You have the latest version!", "#2ECC71")
                    messagebox.showinfo("Up to Date", f"You are already running the latest version ({VERSION}).")
            else:
                # Couldn't find version in script
                update_header_message("Update check failed: Version not found", "#E74C3C")
                messagebox.showwarning("Update Check Failed", "Couldn't determine the latest version from the repository.")
        else:
            # Failed to fetch script
            update_header_message("Update check failed: Couldn't connect to GitHub", "#E74C3C")
            messagebox.showwarning("Update Check Failed", f"Failed to fetch update information. Status code: {response.status_code}")
    except Exception as e:
        # Error occurred
        update_header_message(f"Update check error: {str(e)[:50]}", "#E74C3C")
        messagebox.showerror("Update Error", f"An error occurred while checking for updates:\n\n{str(e)}")

# Global variables to store icon references (to prevent garbage collection)
menu_icons = {}

# Load menu icons function
def load_menu_icons():
    global menu_icons
    
    try:
        # Define icon paths
        icon_paths = {
            "remove": "E:\\Remove From List.png",
            "delete": "E:\\Delete Video.png",
            "play": "E:\\Play Video.png",
            "folder": "E:\\Open Folder.png",
            "copy": "E:\\Copy Url.png"
        }
        
        # Load each icon
        for key, path in icon_paths.items():
            if os.path.exists(path):
                # Load and resize the image to appropriate menu size (16x16 or 20x20)
                img = Image.open(path)
                img = img.resize((16, 16), Image.Resampling.LANCZOS)
                menu_icons[key] = ImageTk.PhotoImage(img)
            else:
                print(f"Warning: Icon not found at {path}")
    except Exception as e:
        print(f"Error loading menu icons: {str(e)}")

# Function to handle right-click context menu events
def show_context_menu(event):
    global right_click_menu, context_menu_row, video_table, menu_icons
    
    # Only show context menu if video_table exists
    if not video_table:
        return
    
    # Load icons if not already loaded
    if not menu_icons:
        load_menu_icons()
    
    # Get the item that was clicked
    try:
        # Identify the row that was clicked
        row_id = video_table.identify_row(event.y)
        if not row_id:
            return  # No row was clicked
            
        # Select the row that was clicked
        video_table.selection_set(row_id)
        
        # Store the row id for later use
        context_menu_row = row_id
        
        # Get the status and URL of the row
        values = video_table.item(row_id, "values")
        status = values[2] if len(values) > 2 else ""
        url = values[1] if len(values) > 1 else ""
        
        # Create a new context menu with enhanced styling
        right_click_menu = tk.Menu(root, tearoff=0, font=('Segoe UI', 11), 
                                  relief="flat", borderwidth=2,
                                  activebackground="#4a86e8", 
                                  activeforeground="white",  # White text on hover
                                  background="#ffffff")
        
        # Configure menu padding and size
        right_click_menu.config(bd=0)
        
        # FIXED COLORS: Using consistent blue hover with white text for better contrast
        hover_bg = "#2980B9"      # Consistent dark blue background on hover
        hover_fg = "#FFFFFF"      # White text on hover for maximum contrast
        
        # Add menu items based on status in the specified order
        # 1. Remove From List
        right_click_menu.add_command(
            label="Remove From List", 
            command=remove_from_list,
            font=('Segoe UI', 11),
            background="#ffffff",
            foreground="#000000",           # Black text normally
            activebackground=hover_bg,      # Blue when hovering
            activeforeground=hover_fg,      # White text when hovering
            image=menu_icons.get("remove"),
            compound=tk.LEFT)
        
        # 2. Delete Video (only if completed)
        if "Completed" in status:
            right_click_menu.add_command(
                label="Delete Video", 
                command=delete_video,
                font=('Segoe UI', 11),
                background="#ffffff",
                foreground="#000000",
                activebackground=hover_bg,
                activeforeground=hover_fg,
                image=menu_icons.get("delete"),
                compound=tk.LEFT)
        
        # 3. Play Video (only if completed)
        if "Completed" in status:
            right_click_menu.add_command(
                label="Play Video", 
                command=play_video,
                font=('Segoe UI', 11),
                background="#ffffff",
                foreground="#000000",
                activebackground=hover_bg,
                activeforeground=hover_fg,
                image=menu_icons.get("play"),
                compound=tk.LEFT)
            
            # 4. Open Folder (only if completed)
            right_click_menu.add_command(
                label="Open Folder", 
                command=open_video_folder,
                font=('Segoe UI', 11),
                background="#ffffff",
                foreground="#000000",
                activebackground=hover_bg,
                activeforeground=hover_fg,
                image=menu_icons.get("folder"),
                compound=tk.LEFT)
        
        # 5. Copy URL (always available)
        right_click_menu.add_command(
            label="Copy URL", 
            command=copy_video_url,
            font=('Segoe UI', 11),
            background="#ffffff",
            foreground="#000000",
            activebackground=hover_bg,
            activeforeground=hover_fg,
            image=menu_icons.get("copy"),
            compound=tk.LEFT)
        
        # Add "Retry Download" option if download failed
        if "Failed" in status:
            right_click_menu.add_separator()
            # We don't have a retry icon, so we'll reuse another icon or skip the image
            retry_icon = menu_icons.get("play")  # Reuse play icon or could use None
            right_click_menu.add_command(
                label="Retry Download", 
                command=retry_download,
                font=('Segoe UI', 11, 'bold'),
                background="#ffffff",
                foreground="#000000",
                activebackground=hover_bg,
                activeforeground=hover_fg,
                image=retry_icon,
                compound=tk.LEFT)
        
        # Show the context menu
        right_click_menu.tk_popup(event.x_root, event.y_root)
    except Exception as e:
        print(f"Error showing context menu: {str(e)}")
        if right_click_menu:
            right_click_menu.destroy()

# Enhanced get_video_output_path function to handle more cases
def get_video_output_path(row_id):
    """Get the expected output path for a video based on its URL and title with improved platform handling"""
    try:
        if not video_table or not row_id:
            return None

        # Get the values from the table row
        values = video_table.item(row_id, "values")
        title = values[3] if len(values) > 3 else "Unknown"
        
        # Extract URL with better error handling
        url = None
        
        # First try to get URL from values
        if len(values) > 1 and values[1] and values[1] != "None" and values[1] != "Unknown":
            url = values[1]
        
        # If not found in values, try to get from tags
        if not url or url == "":
            tags = video_table.item(row_id, "tags")
            for tag in tags:
                if tag != "url" and tag != "completed" and tag != "failed" and tag != "editing":
                    url = tag
                    break
        
        # If still no URL, we can't proceed
        if not url:
            print(f"Could not find URL for row {row_id}")
            return None
            
        # Determine platform with improved detection
        platform = detect_platform(url)
        print(f"Platform detected for URL {url}: {platform}")
        
        # Get download path
        download_dir = download_path.get() or settings.get("default_download_path", 
                                                       os.path.join(os.path.expanduser("~"), "Downloads"))
        platform_path = os.path.join(download_dir, platform)
        
        # Debug message
        print(f"Looking for video in {platform_path} with title: {title}")
        
        # Check if the platform folder exists
        if not os.path.exists(platform_path):
            print(f"Platform path does not exist: {platform_path}")
            return None
        
        # First check if we have the direct output file path in progress_info
        for info_url, info in progress_info.items():
            if url == info_url and 'output_file' in info and info['output_file']:
                if os.path.exists(info['output_file']):
                    print(f"Found exact file via progress_info: {info['output_file']}")
                    return info['output_file']
        
        # Clean title for file matching
        simplified_title = clean_filename(title.lower())
        
        # Search for files with title or URL components in the name
        matching_files = []
        
        # List all video files in the platform directory
        if os.path.exists(platform_path):
            for file in os.listdir(platform_path):
                file_lower = file.lower()
                if file_lower.endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov')):
                    # Match by title
                    if simplified_title != "unknown" and simplified_title in file_lower:
                        matching_files.append((file, 10))  # Higher priority for title match
                        continue
                    
                    # Match by URL components
                    url_parts = url.split('/')
                    for part in url_parts:
                        if len(part) > 5 and part.lower() in file_lower:
                            matching_files.append((file, 5))  # Medium priority for URL part match
                            break
        
        # If we found matching files, return the highest priority match
        if matching_files:
            # Sort by priority (highest first) and then by modification time (newest first)
            matching_files.sort(key=lambda x: (-x[1], -os.path.getmtime(os.path.join(platform_path, x[0]))))
            best_match = matching_files[0][0]
            print(f"Found best matching file: {best_match}")
            return os.path.join(platform_path, best_match)
        
        # If no specific matches, get the most recent video file in the platform folder
        video_files = []
        for file in os.listdir(platform_path):
            if file.lower().endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov')):
                video_files.append(file)
                
        if video_files:
            # Sort by modification time (newest first)
            video_files.sort(key=lambda x: os.path.getmtime(os.path.join(platform_path, x)), reverse=True)
            newest_file = video_files[0]
            print(f"Found newest video file as last resort: {newest_file}")
            return os.path.join(platform_path, newest_file)
        
        # If we couldn't find any file, return None
        print(f"No matching video files found in {platform_path}")
        return None
    except Exception as e:
        print(f"Error getting video path: {str(e)}")
        return None

# Improved open_video_folder function
def open_video_folder():
    global context_menu_row, video_table
    
    if not context_menu_row or not video_table:
        return
        
    try:
        # First try to get status to determine if download is complete
        values = video_table.item(context_menu_row, "values")
        status = values[2] if len(values) > 2 else ""
        
        # Get the URL from the row
        url = values[1] if len(values) > 1 else None
        if not url:
            tags = video_table.item(context_menu_row, "tags")
            for tag in tags:
                if tag != "url" and tag != "completed" and tag != "failed" and tag != "editing":
                    url = tag
                    break
        
        if not url:
            messagebox.showwarning("Open Folder Failed", "Could not determine the video URL.")
            return
            
        # Get the platform for this URL
        platform = detect_platform(url)
        
        # Get download directory
        download_dir = download_path.get() or settings.get("default_download_path", 
                                                         os.path.join(os.path.expanduser("~"), "Downloads"))
        # Construct platform folder path
        platform_path = os.path.join(download_dir, platform)
        
        # Check if the platform folder exists - create it if not
        if not os.path.exists(platform_path):
            os.makedirs(platform_path)
        
        # First attempt: Try to find the specific video file
        if "Completed" in status:
            file_path = get_video_output_path(context_menu_row)
            
            if file_path and os.path.isfile(file_path):
                # We found the specific file
                folder_path = os.path.dirname(file_path)
                
                # Check if folder exists
                if not os.path.exists(folder_path):
                    folder_path = platform_path  # Fallback to platform folder
                
                # Open folder and select the file if possible
                if sys.platform == "win32":
                    # On Windows, use explorer to open and select the file
                    subprocess.run(['explorer', '/select,', file_path])
                    return
                else:
                    # On other platforms, just open the folder
                    if sys.platform == "darwin":  # macOS
                        subprocess.call(["open", folder_path])
                    else:  # Linux
                        subprocess.call(["xdg-open", folder_path])
                    return
        
        # Second attempt: Just open the platform folder
        if os.path.exists(platform_path):
            if sys.platform == "win32":
                os.startfile(platform_path)
            elif sys.platform == "darwin":  # macOS
                subprocess.call(["open", platform_path])
            else:  # Linux
                subprocess.call(["xdg-open", platform_path])
            return
        
        # If we get here, both attempts failed
        messagebox.showwarning("Open Folder", 
                               f"Opened downloads folder: {download_dir}\nVideos are organized by platform.")
        
        # Open the main downloads folder as a last resort
        if os.path.exists(download_dir):
            if sys.platform == "win32":
                os.startfile(download_dir)
            elif sys.platform == "darwin":  # macOS
                subprocess.call(["open", download_dir])
            else:  # Linux
                subprocess.call(["xdg-open", download_dir])
            
    except Exception as e:
        print(f"Error opening folder: {str(e)}")
        messagebox.showerror("Open Folder Failed", f"Error opening folder: {str(e)}")
        
        # Try to open the downloads folder directly as a last resort
        try:
            download_dir = download_path.get() or settings.get("default_download_path", 
                                                            os.path.join(os.path.expanduser("~"), "Downloads"))
            if os.path.exists(download_dir):
                if sys.platform == "win32":
                    os.startfile(download_dir)
                elif sys.platform == "darwin":  # macOS
                    subprocess.call(["open", download_dir])
                else:  # Linux
                    subprocess.call(["xdg-open", download_dir])
        except:
            pass

# Function to copy video URL to clipboard
def copy_video_url():
    global context_menu_row, video_table
    
    if not context_menu_row or not video_table:
        return
        
    try:
        # Get the URL from the table
        values = video_table.item(context_menu_row, "values")
        url = values[1] if len(values) > 1 else ""
        
        if url:
            # Copy URL to clipboard
            pyperclip.copy(url)
            
            # Show brief confirmation
            update_header_message("URL copied to clipboard", "#00FF00")
        else:
            messagebox.showwarning("Copy Failed", "Could not find URL to copy.")
    except Exception as e:
        print(f"Error copying URL: {str(e)}")
        messagebox.showerror("Copy Failed", f"Error copying URL: {str(e)}")

# Function to remove a row from the list
def remove_from_list():
    global context_menu_row, video_table
    
    if not context_menu_row or not video_table:
        return
        
    try:
        # Remove the row from the table
        video_table.delete(context_menu_row)
        
        # Renumber remaining rows
        for i, item in enumerate(video_table.get_children(), 1):
            values = list(video_table.item(item, "values"))
            values[0] = i  # Update row number
            video_table.item(item, values=values)
            
        # Update link count
        update_link_count()
        
        # Reset context menu row
        context_menu_row = None
    except Exception as e:
        print(f"Error removing from list: {str(e)}")

# Function to delete a video
def delete_video():
    global context_menu_row, video_table
    
    if not context_menu_row or not video_table:
        return
        
    try:
        # Get the path to the video
        video_path = get_video_output_path(context_menu_row)
        
        if video_path and os.path.exists(video_path):
            # Confirm deletion
            if messagebox.askyesno("Delete Video", 
                                 f"Are you sure you want to delete this video?\n\n{os.path.basename(video_path)}"):
                # Delete the video
                os.remove(video_path)
                messagebox.showinfo("Video Deleted", "The video has been deleted successfully.")
                
                # Update status to reflect deletion
                values = list(video_table.item(context_menu_row, "values"))
                values[2] = "Deleted"  # Update status
                video_table.item(context_menu_row, values=values)
        else:
            messagebox.showwarning("Delete Failed", "Could not find the video file to delete.")
            
        # Reset context menu row
        context_menu_row = None
    except Exception as e:
        print(f"Error deleting video: {str(e)}")
        messagebox.showerror("Delete Failed", f"Error deleting video: {str(e)}")

# Function to play a video
def play_video():
    global context_menu_row, video_table
    
    if not context_menu_row or not video_table:
        return
        
    try:
        # Get the path to the video
        video_path = get_video_output_path(context_menu_row)
        print(f"Attempting to play video at: {video_path}")
        
        if video_path and os.path.exists(video_path):
            print(f"Video file exists, opening with default player")
            # Open the video with the default player
            if sys.platform == "win32":
                os.startfile(video_path)
            elif sys.platform == "darwin":  # macOS
                subprocess.call(["open", video_path])
            else:  # Linux
                subprocess.call(["xdg-open", video_path])
        else:
            # If not found by the function, let's try a more direct approach for debugging
            values = video_table.item(context_menu_row, "values")
            title = values[3] if len(values) > 3 else "Unknown"
            url = values[1] if len(values) > 1 else None
            
            platform = detect_platform(url) if url else "Unknown"
            download_dir = download_path.get() or settings.get("default_download_path", 
                                                              os.path.join(os.path.expanduser("~"), "Downloads"))
            platform_path = os.path.join(download_dir, platform)
            
            messagebox.showwarning("Play Failed", 
                                  f"Could not find the video file to play.\n\nLooking in: {platform_path}\n\nTry using 'Open Folder' and playing the file manually.")
            
    except Exception as e:
        print(f"Error playing video: {str(e)}")
        messagebox.showerror("Play Failed", f"Error playing video: {str(e)}")

# Function to retry a failed download
def retry_download():
    global context_menu_row, video_table
    
    if not context_menu_row or not video_table:
        return
        
    try:
        # Get the URL from the row
        tags = video_table.item(context_menu_row, "tags")
        url = None
        for tag in tags:
            if tag != "url" and tag != "failed":
                url = tag
                break
                
        if not url:
            messagebox.showwarning("Retry Failed", "Could not find the URL to retry.")
            return
            
        # Update status to pending
        values = list(video_table.item(context_menu_row, "values"))
        values[2] = "Pending"  # Update status
        video_table.item(context_menu_row, values=values, tags=("url", url))
        
        # Add to download queue if downloading is active
        if downloading:
            download_queue.append((context_menu_row, url))
        else:
            # Start download if not already downloading
            path = download_path.get().strip()
            if path:
                quality = quality_var.get()
                thread_count = int(thread_count_var.get())
                t = threading.Thread(target=lambda: download_video(url, path, quality, thread_count, context_menu_row), daemon=True)
                t.start()
            
        # Reset context menu row
        context_menu_row = None
    except Exception as e:
        print(f"Error retrying download: {str(e)}")
        messagebox.showerror("Retry Failed", f"Error retrying download: {str(e)}")

# New combined settings function with REDUCED SIZE
def show_combined_settings():
    global settings
    
    settings_window = ctk.CTkToplevel(root)
    settings_window.title("Settings")
    settings_window.geometry("500x580")  # REDUCED size from 600x700
    settings_window.resizable(False, False)
    settings_window.grab_set()
    
    # Center window relative to root
    center_window(settings_window, 500, 580)
    
    # Create a tabview to separate basic and advanced settings
    tab_view = ctk.CTkTabview(settings_window)
    tab_view.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)  # Reduced padding
    
    # Create tabs
    basic_tab = tab_view.add("Basic Settings")
    advanced_tab = tab_view.add("Advanced Settings")
    
    # === BASIC SETTINGS TAB - MORE COMPACT ===
    
    # Main content area for basic tab
    basic_area = ctk.CTkScrollableFrame(basic_tab)
    basic_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)  # Reduced padding
    
    # Title for basic settings - More compact
    title_label = ctk.CTkLabel(basic_area, text="⚙️ Basic Settings", 
                              font=ctk.CTkFont(size=18, weight="bold"))
    title_label.pack(anchor=tk.CENTER, pady=(0, 15))
    
    # Video Backup Option
    backup_var = tk.BooleanVar(value=settings.get("create_backup", False))
    backup_check = ctk.CTkCheckBox(basic_area, text="Save Video Backups (JSON, Description)",
                                   variable=backup_var)
    backup_check.pack(anchor=tk.W, pady=5)  # Reduced padding
    
    # Subtitle Options Section
    subtitle_label = ctk.CTkLabel(basic_area, text="Save Captions Options:", 
                                font=ctk.CTkFont(size=14, weight="bold"))
    subtitle_label.pack(anchor=tk.W, pady=(5, 2))  # Reduced padding
    
    # Subtitles Options - More compact 
    subtitles_var = tk.BooleanVar(value=settings.get("write_subtitles", False))
    embed_subtitles_var = tk.BooleanVar(value=settings.get("embed_subtitles", False))
    auto_subtitles_var = tk.BooleanVar(value=settings.get("write_auto_subtitles", False))
    
    subtitles_check = ctk.CTkCheckBox(basic_area, text="Download as Separate SRT File",
                                     variable=subtitles_var)
    subtitles_check.pack(anchor=tk.W, padx=15, pady=2)  # Reduced padding
    
    embed_subtitles_check = ctk.CTkCheckBox(basic_area, text="Embed Inside Video",
                                           variable=embed_subtitles_var)
    embed_subtitles_check.pack(anchor=tk.W, padx=15, pady=2)  # Reduced padding
    
    auto_subtitles_check = ctk.CTkCheckBox(basic_area, text="Include Auto-Generated Captions",
                                          variable=auto_subtitles_var)
    auto_subtitles_check.pack(anchor=tk.W, padx=15, pady=2)  # Reduced padding
    
    # File naming options section
    naming_label = ctk.CTkLabel(basic_area, text="Save Videos With:", 
                              font=ctk.CTkFont(size=14, weight="bold"))
    naming_label.pack(anchor=tk.W, pady=(10, 2))  # Reduced padding
    
    # File naming options
    original_title_var = tk.BooleanVar(value=settings.get("use_original_title", True))
    tags_var = tk.BooleanVar(value=settings.get("use_tags", False))
    
    original_title_check = ctk.CTkCheckBox(basic_area, text="Original Title",
                                          variable=original_title_var)
    original_title_check.pack(anchor=tk.W, padx=15, pady=2)  # Reduced padding
    
    tags_check = ctk.CTkCheckBox(basic_area, text="Include Tags/Hashtags",
                                variable=tags_var)
    tags_check.pack(anchor=tk.W, padx=15, pady=2)  # Reduced padding
    
    # Auto-paste Option
    autopaste_var = tk.BooleanVar(value=settings.get("auto_paste", True))
    autopaste_check = ctk.CTkCheckBox(basic_area, text="Auto-paste URL from Clipboard",
                                     variable=autopaste_var)
    autopaste_check.pack(anchor=tk.W, pady=5)  # Reduced padding
    
    # === ADVANCED SETTINGS TAB - MORE COMPACT ===
    
    # Main content area for advanced tab
    adv_area = ctk.CTkScrollableFrame(advanced_tab)
    adv_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)  # Reduced padding
    
    # Title for advanced settings - More compact
    adv_title_label = ctk.CTkLabel(adv_area, text="🛠️ Advanced Settings", 
                                 font=ctk.CTkFont(size=18, weight="bold"))
    adv_title_label.pack(anchor=tk.CENTER, pady=(0, 15))
    
    # Application Theme Section
    theme_label = ctk.CTkLabel(adv_area, text="Application Theme:", 
                             font=ctk.CTkFont(size=14, weight="bold"))
    theme_label.pack(anchor=tk.W, pady=(5, 2))  # Reduced padding
    
    theme_var = tk.StringVar(value=settings.get("theme", "light"))
    theme_frame = ctk.CTkFrame(adv_area, fg_color="transparent")
    theme_frame.pack(fill=tk.X, pady=(0, 5))  # Reduced padding
    
    light_radio = ctk.CTkRadioButton(theme_frame, text="Light Mode", variable=theme_var, value="light")
    light_radio.pack(side=tk.LEFT, padx=(0, 20))
    
    dark_radio = ctk.CTkRadioButton(theme_frame, text="Dark Mode", variable=theme_var, value="dark")
    dark_radio.pack(side=tk.LEFT)
    
    # Cache Management Section
    cache_label = ctk.CTkLabel(adv_area, text="Cache Management:", 
                             font=ctk.CTkFont(size=14, weight="bold"))
    cache_label.pack(anchor=tk.W, pady=(10, 5))  # Reduced padding
    
    def clear_cache():
        cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "yt-dlp")
        if os.path.exists(cache_dir):
            try:
                shutil.rmtree(cache_dir)
                messagebox.showinfo("Success", "Cache cleared successfully!")
                update_header_message("Cache cleared successfully", "#00FF00")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear cache: {str(e)}")
                update_header_message(f"Cache clear failed: {str(e)}", "#FF0000")
        else:
            messagebox.showinfo("Info", "No cache found to clear.")
            update_header_message("No cache found to clear", "#FFFF00")
    
    cache_btn = ctk.CTkButton(adv_area, text="Clear Download Cache", command=clear_cache, 
                             fg_color="#2ecc71", hover_color="#27ae60")
    cache_btn.pack(anchor=tk.W, pady=3)  # Reduced padding
    
    # Multithreading Settings Section
    threading_label = ctk.CTkLabel(adv_area, text="Multithreading Settings:", 
                                 font=ctk.CTkFont(size=14, weight="bold"))
    threading_label.pack(anchor=tk.W, pady=(10, 2))  # Reduced padding
    
    thread_count_label = ctk.CTkLabel(adv_area, text="Default Thread Count:")
    thread_count_label.pack(anchor=tk.W, pady=(2, 0))  # Reduced padding
    
    default_thread_var = tk.StringVar(value=settings.get("default_threads", "4"))
    thread_dropdown = ctk.CTkOptionMenu(adv_area, variable=default_thread_var,
                                      values=["1", "2", "3", "4", "6", "8"],
                                      fg_color="#2ecc71", button_color="#27ae60", button_hover_color="#219652",
                                      width=100)
    thread_dropdown.pack(anchor=tk.W, pady=3)  # Reduced padding
    
    # Download Retries Section
    retries_label = ctk.CTkLabel(adv_area, text="Download Retries:", 
                               font=ctk.CTkFont(size=14, weight="bold"))
    retries_label.pack(anchor=tk.W, pady=(10, 2))  # Reduced padding
    
    retry_var = tk.IntVar(value=settings.get("retries", 3))
    
    retry_frame = ctk.CTkFrame(adv_area, fg_color="transparent")
    retry_frame.pack(fill=tk.X, pady=3)  # Reduced padding
    
    retry_slider = ctk.CTkSlider(retry_frame, from_=0, to=10, number_of_steps=10, variable=retry_var)
    retry_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
    
    retry_value = ctk.CTkLabel(retry_frame, text=f"Value: {retry_var.get()}")
    retry_value.pack(side=tk.RIGHT)
    
    def update_retry_label(event):
        retry_value.configure(text=f"Value: {int(retry_var.get())}")
    
    retry_slider.bind("<Motion>", update_retry_label)
    retry_slider.bind("<ButtonRelease-1>", update_retry_label)
    
    # Buttons at the bottom - More compact
    button_frame = ctk.CTkFrame(settings_window, height=50)  # Reduced height
    button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=15, pady=15)  # Reduced padding
    
    # Cancel button
    def cancel_settings():
        settings_window.destroy()
    
    cancel_button = ctk.CTkButton(
        button_frame, 
        text="Cancel", 
        command=cancel_settings,
        fg_color="#E74C3C", 
        hover_color="#C0392B",
        width=100,  # Reduced width
        height=32   # Reduced height
    )
    cancel_button.pack(side=tk.LEFT, padx=(0, 10))
    
    # Save button
    def save_all_settings():
        # Save basic settings
        settings["create_backup"] = backup_var.get()
        settings["write_subtitles"] = subtitles_var.get()
        settings["embed_subtitles"] = embed_subtitles_var.get()
        settings["write_auto_subtitles"] = auto_subtitles_var.get()
        settings["auto_paste"] = autopaste_var.get()
        settings["use_original_title"] = original_title_var.get()
        settings["use_tags"] = tags_var.get()
        
        # Save advanced settings
        settings["theme"] = theme_var.get()
        settings["retries"] = int(retry_var.get())
        settings["default_threads"] = default_thread_var.get()
        
        # Apply theme change
        ctk.set_appearance_mode(settings["theme"])
        
        # Update thread count in dropdown if it's set
        if thread_count_var:
            thread_count_var.set(default_thread_var.get())
            
        save_settings_to_file()
        settings_window.destroy()
        update_header_message("Settings saved successfully", "#00FF00")
    
    save_button = ctk.CTkButton(
        button_frame, 
        text="Save All Settings", 
        command=save_all_settings,
        fg_color="#2ecc71", 
        hover_color="#27ae60",
        width=120,  # Adjusted width
        height=32   # Reduced height
    )
    save_button.pack(side=tk.RIGHT)
    
    # Set the default tab
    tab_view.set("Basic Settings")

# Settings management
def load_settings():
    global settings
    
    settings_file = os.path.join(os.path.expanduser("~"), ".video_downloader_settings.json")
    
    try:
        if os.path.exists(settings_file):
            with open(settings_file, 'r') as f:
                settings = json.load(f)
        else:
            # Default settings
            settings = {
                "theme": "light",
                "auto_paste": True,
                "create_backup": False,
                "write_subtitles": False,
                "embed_subtitles": False,
                "write_auto_subtitles": False,
                "retries": 3,
                "use_original_title": True,
                "use_tags": False,
                "default_threads": "4",
                "default_download_path": os.path.join(os.path.expanduser("~"), "Downloads")
            }
    except Exception as e:
        print(f"Error loading settings: {str(e)}")
        settings = {
            "theme": "light",
            "auto_paste": True,
            "create_backup": False,
            "write_subtitles": False,
            "embed_subtitles": False,
            "write_auto_subtitles": False,
            "retries": 3,
            "use_original_title": True,
            "use_tags": False,
            "default_threads": "4",
            "default_download_path": os.path.join(os.path.expanduser("~"), "Downloads")
        }

def save_settings_to_file():
    settings_file = os.path.join(os.path.expanduser("~"), ".video_downloader_settings.json")
    
    try:
        with open(settings_file, 'w') as f:
            json.dump(settings, f)
    except Exception as e:
        print(f"Error saving settings: {str(e)}")

# Cloud Key Verification Function
def check_cloud_status(license_key):
    try:
        response = requests.get(SERVER_URL, headers={"Cache-Control": "no-cache"})
        if response.status_code == 200:
            license_data = json.loads(response.text)
            disabled_keys = license_data.get("disabled_keys", [])
            
            if license_key in disabled_keys:
                # Key has been disabled
                messagebox.showerror("License Revoked", 
                                     "Your license has been revoked by the administrator. The application will now close.")
                root.quit()
                return False
        return True
    except:
        # If we can't check, continue (benefit of doubt)
        return True

# Periodic cloud key verification
def schedule_key_verification(license_key):
    if check_cloud_status(license_key):
        # Schedule next check in 10 minutes
        root.after(600000, lambda: schedule_key_verification(license_key))

# License Verification Window - Modern Dark Theme
def verify_license():
    import webbrowser
    
    license_window = tk.Tk()
    license_window.title("Tool by Aziz Tech")
    license_window.geometry("360x280")
    license_window.resizable(False, False)
    license_window.configure(bg="#222222")  # Dark background
    
    # Center window on screen
    screen_width = license_window.winfo_screenwidth()
    screen_height = license_window.winfo_screenheight()
    x = (screen_width // 2) - (360 // 2)
    y = (screen_height // 2) - (280 // 2)
    license_window.geometry(f"360x280+{x}+{y}")
    
    # Try to set window icon
    try:
        icon_path = "icon.ico"
        if os.path.exists(icon_path):
            license_window.iconbitmap(icon_path)
    except:
        pass
    
    # Title text with red color
    title_label = tk.Label(
        license_window, 
        text="Tool by Aziz Tech", 
        font=("Arial", 18, "bold"), 
        bg="#222222", 
        fg="#FF3B30"  # Bright red
    )
    title_label.pack(pady=(20, 5))
    
    # WhatsApp info with green text
    whatsapp_label = tk.Label(
        license_window, 
        text="Whatsapp: +923060124361", 
        font=("Arial", 12), 
        bg="#222222", 
        fg="#4CD964"  # Bright green
    )
    whatsapp_label.pack(pady=(0, 20))
    
    # License entry with dark styling
    key_entry = tk.Entry(
        license_window, 
        width=30, 
        font=("Arial", 11),
        justify="center",
        bg="#333333",  # Slightly lighter than background
        fg="#FFFFFF",  # White text
        insertbackground="#FFFFFF",  # White cursor
        relief=tk.FLAT,
        bd=0
    )
    key_entry.pack(pady=10, ipady=8)  # Add internal padding for height
    key_entry.insert(0, "Enter your license key")
    key_entry.config(fg="#999999")  # Gray placeholder text
    
    # Add focus/unfocus events for placeholder behavior
    def on_entry_click(event):
        """Function to clear placeholder text when clicked"""
        if key_entry.get() == "Enter your license key":
            key_entry.delete(0, tk.END)
            key_entry.config(fg="#FFFFFF")  # Change text color to white
    
    def on_focus_out(event):
        """Function to restore placeholder text if empty"""
        if key_entry.get() == "":
            key_entry.insert(0, "Enter your license key")
            key_entry.config(fg="#999999")  # Change text color to gray
    
    key_entry.bind("<FocusIn>", on_entry_click)
    key_entry.bind("<FocusOut>", on_focus_out)
    
    # Status message (hidden by default)
    status_var = tk.StringVar(value="")
    status_label = tk.Label(
        license_window,
        textvariable=status_var,
        font=("Arial", 10),
        bg="#222222",
        fg="#FF3B30"  # Red text for errors
    )
    status_label.pack(pady=(5, 5))
    
    # Login button (white)
    login_button = tk.Button(
        license_window, 
        text="Login", 
        font=("Arial", 12, "bold"),
        bg="#FFFFFF", 
        fg="#333333",  # Dark text
        width=30,
        relief=tk.FLAT,
        cursor="hand2",
        bd=0
    )
    login_button.pack(pady=10)
    
    # Button frame for Purchase and Tutorials
    button_frame = tk.Frame(license_window, bg="#222222")
    button_frame.pack(fill=tk.X, pady=5)
    
    # Function to open WhatsApp link
    def open_whatsapp():
        webbrowser.open("https://wa.me/03060124361")
    
    # Function to open Facebook tutorials
    def open_facebook():
        webbrowser.open("https://www.facebook.com/princeaziz011")
    
    # Purchase button (dark)
    purchase_button = tk.Button(
        button_frame, 
        text="Purchase", 
        font=("Arial", 11),
        bg="#333333", 
        fg="#FFFFFF",
        width=15,
        relief=tk.FLAT,
        cursor="hand2",
        command=open_whatsapp,
        bd=0
    )
    purchase_button.pack(side=tk.LEFT, padx=(40, 20))
    
    # Tutorials button (dark)
    tutorials_button = tk.Button(
        button_frame, 
        text="Tutorials", 
        font=("Arial", 11),
        bg="#333333", 
        fg="#FFFFFF",
        width=15,
        relief=tk.FLAT,
        cursor="hand2",
        command=open_facebook,
        bd=0
    )
    tutorials_button.pack(side=tk.RIGHT, padx=(20, 40))
    
    # Instructions text
    instructions_label = tk.Label(
        license_window, 
        text="Press Login To Continue Using Tool", 
        font=("Arial", 10), 
        bg="#222222", 
        fg="#BBBBBB"  # Light gray
    )
    instructions_label.pack(pady=(10, 0))
    
    # Login function - Check key validity and proceed only if valid
    def validate_and_login():
        user_key = key_entry.get().strip()
        
        # If it's the placeholder, treat as empty
        if user_key == "Enter your license key":
            user_key = ""
        
        # Clear any previous error messages
        status_var.set("")
        
        if not user_key:
            status_var.set("Please enter a license key")
            return
            
        # Show a "checking" message
        status_var.set("Verifying license key...")
        license_window.update()  # Force UI update
        
        # Add a small delay to show the checking message
        license_window.after(200)
        
        if is_key_valid(user_key):
            # Save the key securely
            save_license_key(user_key)
            license_window.destroy()
            open_downloader(user_key)
        else:
            # Show error and keep window open
            status_var.set("Invalid license key. Please try again.")
    
    # Connect login button to validation function
    login_button.config(command=validate_and_login)
    
    # Bind Enter key to login function
    key_entry.bind("<Return>", lambda event: validate_and_login())
    
    # Check for cached license and pre-fill if available
    cached_license = verify_cached_license()
    if cached_license:
        # Pre-fill with cached license
        key_entry.delete(0, tk.END)
        key_entry.insert(0, cached_license)
        key_entry.config(fg="#FFFFFF")  # White text for actual license
    
    # Focus the window
    license_window.focus_force()
    key_entry.focus_set()
    
    license_window.mainloop()

# Class for handling inline editing directly in the treeview
class TreeviewEditor:
    def __init__(self, treeview):
        self.treeview = treeview
        self.editing = False
        self.edit_widget = None
        self.edit_item = None
        self.edit_column = None
        self.original_value = None
        
        # Bind events for inline editing
        self.treeview.bind('<Double-1>', self.on_double_click)
        self.treeview.bind('<Return>', self.on_return_pressed)
        self.treeview.bind('<Escape>', self.cancel_edit)
        self.treeview.bind('<Delete>', self.delete_selected)
    
    def on_double_click(self, event):
        """Start editing on double click"""
        region = self.treeview.identify_region(event.x, event.y)
        if region != "cell":
            return
        
        item = self.treeview.identify_row(event.y)
        if not item:
            return
            
        column = self.treeview.identify_column(event.x)
        if column != "#2":  # Only edit the URLs column
            return
            
        # Get column index (remove # from column identifier)
        column_index = int(column[1:]) - 1
        
        # Start editing
        self.edit_item = item
        self.edit_column = column
        self.original_value = self.treeview.item(item, "values")[column_index]
        
        # Create text entry for editing
        self.setup_edit_widget(item, column, column_index)
    
    def setup_edit_widget(self, item, column, column_index):
        """Create an entry widget for editing"""
        self.editing = True
        
        # Get cell dimensions and position
        bbox = self.treeview.bbox(item, column)
        if not bbox:
            self.editing = False
            return
            
        x, y, width, height = bbox
        
        # Create entry widget
        self.edit_widget = tk.Entry(self.treeview)
        self.edit_widget.place(x=x, y=y, width=width, height=height, anchor="nw")
        self.edit_widget.insert(0, self.original_value)
        self.edit_widget.select_range(0, tk.END)
        self.edit_widget.focus_set()
        
        # Bind events to the entry widget
        self.edit_widget.bind("<Return>", self.save_edit)
        self.edit_widget.bind("<Escape>", self.cancel_edit)
        self.edit_widget.bind("<FocusOut>", self.save_edit)
        
        # Add highlighting to the edited row
        self.treeview.item(item, tags=("editing",))
    
    def save_edit(self, event=None):
        """Save the edited value"""
        if not self.editing or not self.edit_widget:
            return
            
        # Get the new value
        new_value = self.edit_widget.get().strip()
        
        if new_value and new_value != self.original_value:
            # Update value in treeview
            values = list(self.treeview.item(self.edit_item, "values"))
            column_index = int(self.edit_column[1:]) - 1
            values[column_index] = new_value
            
            # Update tags to store URL
            self.treeview.item(self.edit_item, values=values, tags=("url", new_value))
            
            # Reset status if URL was changed
            update_video_status(self.edit_item, "Pending", "")
            
        # Cleanup
        self.cleanup_edit_widget()
        
    def cancel_edit(self, event=None):
        """Cancel editing"""
        self.cleanup_edit_widget()
    
    def cleanup_edit_widget(self):
        """Remove edit widget and reset state"""
        if self.edit_widget:
            self.edit_widget.destroy()
            self.edit_widget = None
            
        # Remove editing highlight
        if self.edit_item:
            current_tags = self.treeview.item(self.edit_item, "tags")
            # Restore original tags
            url = None
            for tag in current_tags:
                if tag != "editing":
                    url = tag
            if url:
                self.treeview.item(self.edit_item, tags=("url", url))
            
        self.editing = False
        self.edit_item = None
        self.edit_column = None
        self.original_value = None
    
    def on_return_pressed(self, event):
        """Handle Return key press when no active edit"""
        if self.editing:
            return
            
        # Start editing the selected item
        selected = self.treeview.selection()
        if not selected:
            return
            
        item = selected[0]
        column = "#2"  # Links column
        column_index = 1
        
        self.edit_item = item
        self.edit_column = column
        self.original_value = self.treeview.item(item, "values")[column_index]
        
        self.setup_edit_widget(item, column, column_index)
    
    def delete_selected(self, event=None):
        """Delete selected items when Delete key is pressed"""
        selected = self.treeview.selection()
        if not selected:
            return
            
        # Delete all selected items
        for item in selected:
            self.treeview.delete(item)
            
        # Renumber remaining rows
        for i, item in enumerate(self.treeview.get_children(), 1):
            values = list(self.treeview.item(item, "values"))
            values[0] = i  # Update row number
            self.treeview.item(item, values=values)
            
        # Update link count
        update_link_count()
        
        # Update status message
        count = len(self.treeview.get_children())
        update_header_message(f"Link Count: {count} | Removed selected URLs")

def setup_inline_editing(treeview):
    """Setup the inline editing for the treeview"""
    editor = TreeviewEditor(treeview)
    # Store editor reference on treeview to prevent garbage collection
    treeview.editor = editor

# Main Downloader GUI
def open_downloader(license_key):
    global root, download_path, folder_entry, download_button, status_label
    global quality_var, thread_count_var, progress_bar, start_bulk_button
    global link_count_label, tool_version_label, footer_label, video_table, header_label
    
    # Load settings
    load_settings()
    
    # Apply theme from settings
    ctk.set_appearance_mode(settings.get("theme", "light"))
    
    root = ctk.CTk()
    root.title("Ultra Fast Video Downloader by Aziz Tech")
    root.geometry("900x600")
    root.resizable(True, True)
    
    # Variables
    download_path = tk.StringVar(value=settings.get("default_download_path", os.path.join(os.path.expanduser("~"), "Downloads")))
    quality_var = tk.StringVar(value="1080")
    thread_count_var = tk.StringVar(value=settings.get("default_threads", "4"))
    
    # Create menu bar with INCREASED SIZE
    menu_bar = tk.Menu(root, font=('Segoe UI', 11))  # Increased font size
    root.config(menu=menu_bar)
    
    # Custom style for menus with more padding
    root.option_add('*Menu.borderWidth', 2)
    root.option_add('*Menu.activeBorderWidth', 2)
    root.option_add('*Menu.relief', 'raised')
    root.option_add('*Menu.activeBackground', '#e0e0e0')
    root.option_add('*Menu.padY', 6)  # Increased padding
    
    # Create Files menu
    file_menu = tk.Menu(menu_bar, tearoff=0, font=('Segoe UI', 11))
    menu_bar.add_cascade(label="  Files  ", menu=file_menu)  # Added spaces for padding
    file_menu.add_command(label="Install YT PKGs", command=install_yt_packages)
    
    # Create Help menu with Check for Updates
    help_menu = tk.Menu(menu_bar, tearoff=0, font=('Segoe UI', 11))
    menu_bar.add_cascade(label="  Help  ", menu=help_menu)  # Added spaces for padding
    help_menu.add_command(label="Check for Updates", command=check_for_updates)
    help_menu.add_separator()
    help_menu.add_command(label="YouTube Channel", command=open_youtube_channel)
    help_menu.add_command(label="Facebook Page", command=open_facebook_page)
    
    # Main frame with padding
    main_frame = ctk.CTkFrame(root, fg_color="transparent")
    main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    
    # URL Section
    url_section = ctk.CTkFrame(main_frame, fg_color="transparent")
    url_section.pack(fill=tk.X, pady=(5, 10))
    
    # Create an empty/hidden header label for status updates only
    header_label = tk.Label(main_frame, text="", fg="white")
    header_label.pack_forget()
    
    ctk.CTkLabel(url_section, text="Enter Video URLs (One per line in Listbox):", font=ctk.CTkFont(size=14)).pack(anchor=tk.W)
    
    # Button row for URL management
    button_frame = ctk.CTkFrame(url_section, fg_color="transparent")
    button_frame.pack(fill=tk.X, pady=(5, 0))
    
    # Buttons with exact styling from the reference image
    add_button = ctk.CTkButton(button_frame, text="➕ Add Links", command=add_url, width=120, height=36, 
                              fg_color="#2ecc71", hover_color="#27ae60")
    add_button.pack(side=tk.LEFT, padx=(0, 12))
    
    # Add Start Bulk Download button right after Add Links
    start_bulk_button = ctk.CTkButton(button_frame, text="▶️ Start Bulk Download", command=start_download, 
                                     width=180, height=36, fg_color="#2980B9", hover_color="#3498DB")
    start_bulk_button.pack(side=tk.LEFT, padx=(0, 12))
    
    # Add Pause All button
    pause_button = ctk.CTkButton(button_frame, text="⏸️ Pause All", command=pause_all_downloads, 
                               width=120, height=36, fg_color="#F39C12", hover_color="#E67E22")
    pause_button.pack(side=tk.LEFT, padx=(0, 12))
    
    # Add Resume All button
    resume_button = ctk.CTkButton(button_frame, text="▶️ Resume All", command=resume_all_downloads, 
                                width=120, height=36, fg_color="#2ecc71", hover_color="#27ae60")
    resume_button.pack(side=tk.LEFT, padx=(0, 12))
    
    reset_button = ctk.CTkButton(button_frame, text="🗑️ Reset All", command=reset_urls, 
                               width=120, height=36, fg_color="#E74C3C", hover_color="#C0392B")
    reset_button.pack(side=tk.LEFT, padx=(0, 12))
    
    # Add settings button 
    settings_button = ctk.CTkButton(button_frame, text="⚙️ Settings", command=show_combined_settings, 
                                   width=120, height=36, fg_color="#2ecc71", hover_color="#27ae60")
    settings_button.pack(side=tk.LEFT)
    
    # Folder and Quality Selection Row
    options_row = ctk.CTkFrame(main_frame, fg_color="transparent")
    options_row.pack(fill=tk.X, pady=(10, 10))
    
    ctk.CTkLabel(options_row, text="Download Folder:", font=ctk.CTkFont(size=14)).pack(side=tk.LEFT, padx=(0, 10))
    
    # Create a single row for folder and quality
    folder_entry = ctk.CTkEntry(options_row, placeholder_text="Select download location...", width=400, height=38)
    folder_entry.pack(side=tk.LEFT, padx=(0, 15))
    folder_entry.insert(0, download_path.get())
    
    browse_button = ctk.CTkButton(options_row, text="📂 Browse", command=browse_folder, 
                                 width=120, height=38, fg_color="#2ecc71", hover_color="#27ae60")
    browse_button.pack(side=tk.LEFT, padx=(0, 20))
    
    # Quality selector - adjusted spacing
    ctk.CTkLabel(options_row, text="Quality:", font=ctk.CTkFont(size=14)).pack(side=tk.LEFT, padx=(10, 8))
    quality_menu = ctk.CTkOptionMenu(options_row, variable=quality_var, 
                                    values=["720", "1080", "1440", "2160", "Max Quality"],
                                    height=38, width=140, 
                                    fg_color="#2ecc71", button_color="#27ae60", button_hover_color="#219652")
    quality_menu.pack(side=tk.LEFT)
    
    # Create the table container
    table_container = ctk.CTkFrame(main_frame, fg_color="transparent")
    table_container.pack(fill=tk.BOTH, expand=True, pady=10)
    
    # Create the Treeview with black headers
    style = ttk.Style()
    
    # Configure the styles
    style.theme_use('default')
    style.configure("Treeview.Heading",
                   background="black",
                   foreground="white",
                   relief="flat",
                   font=('Segoe UI', 10, 'bold'))
    
    style.configure("Treeview", 
                   rowheight=25,
                   font=('Segoe UI', 9))
                   
    style.map('Treeview', 
             background=[('selected', '#2ecc71')],
             foreground=[('selected', 'black')])
    
    # Create frame for treeview and scrollbars
    tree_frame = tk.Frame(table_container, bg="black", bd=2)
    tree_frame.pack(fill=tk.BOTH, expand=True)
    
    # Scrollbars
    vsb = ttk.Scrollbar(tree_frame, orient="vertical")
    hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
    
    # Create an editable Treeview
    video_table = ttk.Treeview(tree_frame, columns=("#", "Links", "Status", "Titles", "Author", "Time", "Size"),
                             show="headings", height=12,
                             yscrollcommand=vsb.set,
                             xscrollcommand=hsb.set)
    
    # Configure column headings
    for col in ("#", "Links", "Status", "Titles", "Author", "Time", "Size"):
        video_table.heading(col, text=col)
    
    # NOW we can configure tags AFTER creating the video_table
    video_table.tag_configure("completed", background="#E8F8F5")
    video_table.tag_configure("failed", background="#FADBD8")
    video_table.tag_configure("editing", background="#FEF9E7")  # Highlight for editing
    
    # Configure scrollbars
    vsb.config(command=video_table.yview)
    hsb.config(command=video_table.xview)
    
    # Add scrollbars
    vsb.pack(side=tk.RIGHT, fill=tk.Y)
    hsb.pack(side=tk.BOTTOM, fill=tk.X)
    
    # Configure column widths
    video_table.column("#", width=30, anchor=tk.CENTER)
    video_table.column("Links", width=250, anchor=tk.W)  # Wider for better editing
    video_table.column("Status", width=80, anchor=tk.W)
    video_table.column("Titles", width=150, anchor=tk.W)
    video_table.column("Author", width=100, anchor=tk.W)
    video_table.column("Time", width=70, anchor=tk.CENTER)
    video_table.column("Size", width=70, anchor=tk.CENTER)
    
    # Pack the treeview
    video_table.pack(fill=tk.BOTH, expand=True)
    
    # Create black footer for the table with 3 sections
    footer_frame = tk.Frame(table_container, bg="black", height=30)  # Increased height
    footer_frame.pack(fill=tk.X)
    
    # Create the label frames inside the black footer
    link_frame = tk.Frame(footer_frame, bg="black")
    link_frame.pack(side=tk.LEFT, fill=tk.Y)
    
    tool_frame = tk.Frame(footer_frame, bg="black")
    tool_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    author_frame = tk.Frame(footer_frame, bg="black")
    author_frame.pack(side=tk.RIGHT, fill=tk.Y)
    
    # The three labels in the footer - UPDATED to display tool version
    link_count_label = tk.Label(link_frame, text="Link Count: 0", bg="black", fg="white", font=('Segoe UI', 10))
    link_count_label.pack(side=tk.LEFT, padx=12, pady=5)
    
    tool_version_label = tk.Label(tool_frame, text=f"Version {VERSION}", bg="black", fg="white", font=('Segoe UI', 10))
    tool_version_label.pack(pady=5)
    
    footer_label = tk.Label(author_frame, text="Tool by Aziz Tech", bg="black", fg="white", font=('Segoe UI', 10))
    footer_label.pack(side=tk.RIGHT, padx=12, pady=5)
    
    # Progress Status Frame - now directly after the table
    progress_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    progress_frame.pack(fill=tk.X, pady=(10, 5))
    
    # Progress Bar 
    progress_bar = ctk.CTkProgressBar(progress_frame, height=15)
    progress_bar.pack(fill=tk.X, pady=(0, 5))
    progress_bar.set(0)  # Initialize at 0%
    
    # Status Label
    status_label = ctk.CTkLabel(progress_frame, text="Waiting for download...", 
                              font=ctk.CTkFont(size=14),
                              height=30,
                              fg_color=("#f0f0f0", "#2d2d2d"),
                              corner_radius=6)
    status_label.pack(fill=tk.X)
    
    # Initialize link count
    update_link_count()
    
    # Create a general purpose download button (reference only)
    download_button = ctk.CTkButton(main_frame, text="Download", command=start_download)
    download_button.pack_forget()  # Hide it, we just need the reference
    
    # Setup inline editing for the treeview
    setup_inline_editing(video_table)
    
    # Setup right-click menu for the treeview - ADD CONTEXT MENU
    video_table.bind("<Button-3>", show_context_menu)
    
    # Start cloud key verification
    schedule_key_verification(license_key)
    
    # Set window icon
    try:
        icon_path = "icon.ico"
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except:
        pass
    
    # Initialize header with empty message
    update_header_message("")
    
    # Center the window on the screen
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width // 2) - (900 // 2)
    y = (screen_height // 2) - (600 // 2)
    root.geometry(f"900x600+{x}+{y}")
    
    root.mainloop()

# Main execution function
def main():
    # Always show license verification window first
    verify_license()

if __name__ == "__main__":
    main()  
