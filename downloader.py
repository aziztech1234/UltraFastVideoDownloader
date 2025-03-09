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
VERSION = "2.8.1"  # Updated version number with fixes

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
extraction_progress_window = None  # Global reference to extraction progress window
extraction_cancel = False  # Flag to cancel extraction
loading_animation_index = 0  # For loading animation
active_download_threads = []  # Track active download threads for proper termination

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
    elif 'instagram' in domain or 'ig.me' in domain:
        return "Instagram"
    elif 'facebook' in domain or 'fb.com' in domain or 'fb.watch' in domain or 'fbwat.ch' in domain:
        return "Facebook"
    else:
        return "Other"

# IMPROVED: Function to detect profile URLs with better pattern matching
def is_profile_url(url):
    """Improved check for profiles/channels with enhanced pattern matching for Facebook and Instagram"""
    domain = urllib.parse.urlparse(url).netloc.lower()
    path = urllib.parse.urlparse(url).path.lower()
    query = urllib.parse.urlparse(url).query.lower()
    
    # YouTube channel or user URLs
    if ('youtube.com' in domain or 'youtu.be' in domain):
        if ('/channel/' in path or '/user/' in path or '/c/' in path or '@' in path):
            return True
        # YouTube playlist URLs
        if '/playlist' in path:
            return True
    
    # TikTok profile URLs - improved pattern matching
    elif 'tiktok.com' in domain:
        # TikTok profiles have format @username or just /username
        if re.match(r'^/(@[\w\.]+)/?$', path) or path.count('/') <= 1:
            # Exclude specific video pattern
            if not '/video/' in path:
                return True
    
    # FIXED: Instagram profile URLs - improved detection
    elif 'instagram.com' in domain or 'ig.me' in domain:
        # Instagram profiles are just /username without any specific content indicators
        # Exclude known content patterns
        if not any(content_type in path for content_type in ['/p/', '/reel/', '/stories/', '/tv/']):
            # Typical profile URL pattern
            if re.match(r'^/([\w\.]+)/?$', path) or path.startswith('/@'):
                return True
    
    # FIXED: Facebook profile/page URLs - much more comprehensive detection
    elif 'facebook.com' in domain or 'fb.com' in domain or 'fb.watch' in domain:
        # Exclude specific video patterns
        if not any(video_pattern in path for video_pattern in ['/watch/', '/videos/', '/video_redirect/']):
            # Profile patterns
            if re.match(r'^/([\w\.]+)/?$', path) or '/pg/' in path or '/pages/' in path:
                return True
            # Groups with video content
            if '/groups/' in path and not '/permalink/' in path:
                return True
        # Special case: profiles that include video tabs but are still profiles
        if '/videos/' in path and path.count('/') <= 2:
            return True
    
    return False

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

# IMPROVED version of get_video_output_path to fix YouTube folder issue
def get_video_output_path(row_id):
    """Enhanced function to get video output path with fixes for YouTube and other platforms"""
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
        
        # Create platform folder if it doesn't exist (this ensures the folder exists for Open Folder)
        if not os.path.exists(platform_path):
            try:
                os.makedirs(platform_path)
                print(f"Created platform path: {platform_path}")
            except Exception as e:
                print(f"Error creating platform directory: {str(e)}")
                return platform_path  # Return the platform path even if creation fails
        
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
        
        # IMPROVED VIDEO FILE SEARCH - better handling of YouTube files
        if os.path.exists(platform_path):
            # Get all video files in platform directory, sorted by modification time (newest first)
            video_files = []
            for file in os.listdir(platform_path):
                file_path = os.path.join(platform_path, file)
                if os.path.isfile(file_path) and file.lower().endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov')):
                    video_files.append((file, os.path.getmtime(file_path)))
            
            # Sort by modification time, newest first
            video_files.sort(key=lambda x: x[1], reverse=True)
            
            # First try to match by title
            if simplified_title and simplified_title != "unknown":
                for file, _ in video_files:
                    if simplified_title in file.lower():
                        print(f"Found file matching title: {file}")
                        return os.path.join(platform_path, file)
            
            # If no match by title, try to match by URL components
            if url:
                url_parts = url.split('/')
                for part in url_parts:
                    if len(part) > 5:  # Only use meaningful parts
                        for file, _ in video_files:
                            if part.lower() in file.lower():
                                print(f"Found file matching URL part: {file}")
                                return os.path.join(platform_path, file)
            
            # If we still haven't found a match, just return the most recent video
            if video_files:
                newest_file = video_files[0][0]
                print(f"Returning most recent video file: {newest_file}")
                return os.path.join(platform_path, newest_file)
        
        # If we couldn't find any file, still return the platform path for "Open Folder" functionality
        print(f"No matching video files found, returning platform directory: {platform_path}")
        return platform_path
    except Exception as e:
        print(f"Error getting video path: {str(e)}")
        download_dir = download_path.get() or settings.get("default_download_path", 
                                                      os.path.join(os.path.expanduser("~"), "Downloads"))
        if url:
            platform = detect_platform(url)
            platform_path = os.path.join(download_dir, platform)
            return platform_path
        return download_dir  # Fall back to main download directory

# Progress Hook Function - IMPROVED VERSION
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
        self.last_update_time = 0
        self.update_interval = 0.2  # Update UI every 200ms to avoid UI freezing
        
    def update_progress(self, d):
        global progress_info
        
        current_time = time.time()
        
        # Throttle UI updates to prevent GUI freezing
        should_update_ui = (current_time - self.last_update_time) >= self.update_interval
        
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
                    
                    # Get hashtags if available
                    if 'hashtags' in info:
                        self.hashtags = info.get('hashtags', [])
                    elif 'tags' in info:
                        self.hashtags = info.get('tags', [])
                    
                    # Always update metadata on first receive
                    root.after(0, lambda: update_video_metadata(
                        self.row_id, self.title, self.author, self.duration, self.filesize))
                
                # Store progress info for status bar
                progress_info[self.url] = {
                    'percentage': percentage,
                    'speed': speed,
                    'eta': eta,
                    'title': self.title,
                    'hashtags': self.hashtags,
                    'output_file': self.output_file
                }
                
                # Update overall progress in status bar - always do this
                update_overall_progress()
                
                # Only update UI at throttled intervals to prevent freezing
                if should_update_ui:
                    # Update table with progress
                    root.after(0, lambda: update_video_status(
                        self.row_id, f"Downloading {percentage}", speed))
                    
                    # Update status with current download info
                    platform = detect_platform(self.url)
                    title_display = self.title if self.title else 'Unknown'
                    if len(title_display) > 30:
                        title_display = title_display[:27] + "..."
                        
                    status_text = f"Downloading {platform}: {percentage} | {title_display} | {speed}"
                    root.after(0, lambda: update_header_message(status_text))
                    
                    # Update last update time
                    self.last_update_time = current_time
                    
            except Exception as e:
                print(f"Progress update error: {str(e)}")
                
        elif d['status'] == 'finished':
            # The download part is finished, now it's post-processing
            elapsed = time.time() - self.start_time
            root.after(0, lambda: update_video_status(
                self.row_id, f"Processing...", f"{elapsed:.1f}s"))
            
            # Store output file if set
            if self.output_file and self.url in progress_info:
                progress_info[self.url]['output_file'] = self.output_file
            
        elif d['status'] == 'error':
            # An error occurred during download
            error_msg = d.get('error', 'Unknown error')
            print(f"Download error: {error_msg}")
            root.after(0, lambda: update_video_status(
                self.row_id, "Failed", str(error_msg)[:20]))
            
            # Remove from progress tracking
            if self.url in progress_info:
                del progress_info[self.url]
                update_overall_progress()

# Update video status in the table
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

# IMPROVED FORMAT SELECTION FUNCTION
def get_format_options(platform, quality):
    """
    Returns optimized format selection strings for different platforms.
    Completely rewritten to address recent yt-dlp changes and ensure reliability.
    """
    if platform == "YouTube":
        # Completely redesigned YouTube format selection
        if quality == "Max Quality":
            return 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        else:
            return f'bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality}][ext=mp4]/best[height<={quality}]'
    elif platform == "Facebook":
        # Improved Facebook format selection with better compatibility
        return 'best[ext=mp4]/dash_sd_src/dash_hd_src/hd_src/sd_src'
    elif platform == "TikTok":
        # Completely redone TikTok format to handle all cases reliably
        return 'best[vcodec!*=hevc][vcodec!*=h265]/best'
    elif platform == "Instagram":
        # Fixed Instagram format selection for both Reels and normal posts
        return 'best/dash_hd/dash_sd'
    else:
        # More robust default format for other platforms
        if quality == "Max Quality":
            return 'bestvideo+bestaudio/best'
        else:
            return f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]'

# IMPROVED USER AGENT FUNCTION
def get_platform_user_agent(platform):
    """
    Returns optimized user agents for different platforms.
    Updated with more modern and reliable user agent strings.
    """
    # Modern Chrome user agent that works well across platforms
    common_desktop = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    if platform == "YouTube":
        return common_desktop
    elif platform == "TikTok":
        # TikTok works better with mobile user agents
        return "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    elif platform == "Instagram":
        # Instagram app-like user agent
        return "Instagram 271.0.0.16.108 Android (33/13; 420dpi; 1080x2210; Google/google; Pixel 7; panther; armv8l; en_US; 429794285)"
    elif platform == "Facebook":
        # Facebook-specific user agent
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
    else:
        return common_desktop

# Helper functions for improved download
def get_referer_for_platform(platform):
    """Get appropriate referer for each platform"""
    if platform == "YouTube":
        return "https://www.youtube.com/"
    elif platform == "TikTok":
        return "https://www.tiktok.com/"
    elif platform == "Instagram":
        return "https://www.instagram.com/"
    elif platform == "Facebook":
        return "https://www.facebook.com/"
    else:
        return "https://google.com/"

def get_alternate_user_agent(platform, attempt):
    """Get alternate user agents for retries"""
    # List of user agents to cycle through
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1"
    ]
    
    # Return different user agent based on attempt number
    return user_agents[attempt % len(user_agents)]

def get_ffmpeg_path():
    """Try to find ffmpeg in the system"""
    # Check common paths
    common_paths = [
        "",  # empty string will use system PATH
        os.path.join(os.path.dirname(sys.executable), "ffmpeg"),
        os.path.join(os.path.dirname(sys.executable), "ffmpeg.exe"),
        "/usr/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "C:\\ffmpeg\\bin\\ffmpeg.exe"
    ]
    
    for path in common_paths:
        try:
            if not path:  # empty path means rely on system PATH
                subprocess.run(["ffmpeg", "-version"], capture_output=True, check=False)
                return None  # Return None to use system PATH
            elif os.path.exists(path):
                return path
        except:
            continue
    
    return None  # Let yt-dlp find ffmpeg
    
# COMPLETELY REWRITTEN DOWNLOAD FUNCTION WITH FIX FOR THUMBNAIL ISSUE
def download_video(url, download_path, quality, thread_count, row_id):
    """
    Enhanced download function with better error handling and reliability.
    Fixed thumbnail downloading issues for TikTok and Instagram.
    """
    global active_download_threads
    
    # Add current thread to active download threads tracker
    current_thread = threading.current_thread()
    if current_thread not in active_download_threads:
        active_download_threads.append(current_thread)
    
    platform = detect_platform(url)
    
    # Create platform-specific folder
    platform_path = os.path.join(download_path, platform)
    if not os.path.exists(platform_path):
        os.makedirs(
  platform_path)
    
    # Get optimized format selection for this platform
    format_option = get_format_options(platform, quality)
    
    # Create progress manager
    progress_manager = ProgressManager(url, row_id)
    
    # Setup output template based on settings
    if settings.get("use_original_title", False) and settings.get("use_tags", False):
        output_template = '%(title)s %(hashtags)s.%(ext)s'
    elif settings.get("use_original_title", False):
        output_template = '%(title)s.%(ext)s'
    else:
        output_template = '%(title)s.%(ext)s'
    
    # Prepare base download options with better defaults - DISABLE THUMBNAIL DOWNLOAD FOR ALL PLATFORMS
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
        'retries': settings.get("retries", 10),  # Increased retries
        'fragment_retries': 15,
        'skip_unavailable_fragments': False,
        'keepvideo': False,
        'overwrites': True,
        'ignoreerrors': True,
        'prefer_ffmpeg': True,
        'socket_timeout': 60,
        'writethumbnail': False,  # FIXED: Disable thumbnail download for all platforms
        'http_headers': {
            'User-Agent': get_platform_user_agent(platform),
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': get_referer_for_platform(platform),
        },
        'noprogress': False,
        'ffmpeg_location': get_ffmpeg_path(),
        'extractor_retries': 5,
        'concurrent_fragment_downloads': thread_count,
    }
    
    # Platform-specific optimizations
    if platform == "YouTube":
        # For YouTube, we'll enable thumbnail only if embedding is desired
        youtube_postprocessors = [
            {'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'},
            {'key': 'FFmpegMetadata', 'add_metadata': True},
        ]
        
        # Only enable thumbnail embedding if specifically requested
        if settings.get("embed_thumbnail", False):
            # Enable thumbnail download for YouTube only if embedding is requested
            ydl_opts['writethumbnail'] = True
            youtube_postprocessors.append({'key': 'EmbedThumbnail'})
            
        ydl_opts.update({
            'postprocessors': youtube_postprocessors,
        })
    elif platform == "TikTok":
        ydl_opts.update({
            'postprocessors': [
                {'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'},
                {'key': 'FFmpegMetadata', 'add_metadata': True},
            ],
            # Extra options to prevent thumbnail downloads for TikTok
            'writeautomaticsub': False,
            'writewebp': False,
            'writejpg': False,
            'writepng': False,
        })
    elif platform == "Instagram":
        # Create cookie file if it doesn't exist
        cookie_file = os.path.join(os.path.expanduser("~"), ".ig_cookies.txt")
        if not os.path.exists(cookie_file):
            with open(cookie_file, 'w') as f:
                f.write("# Instagram cookies file\n")
        
        ydl_opts.update({
            'cookiefile': cookie_file,
            'extract_flat': 'in_playlist',  # Better for profile pages
            'postprocessors': [
                {'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'},
                {'key': 'FFmpegMetadata', 'add_metadata': True},
            ],
            # Extra options to prevent thumbnail downloads for Instagram
            'writeautomaticsub': False,
            'writewebp': False,
            'writejpg': False,
            'writepng': False,
        })
    elif platform == "Facebook":
        cookie_file = os.path.join(os.path.expanduser("~"), ".fb_cookies.txt")
        if not os.path.exists(cookie_file):
            with open(cookie_file, 'w') as f:
                f.write("# Facebook cookies file\n")
                
        ydl_opts.update({
            'cookiefile': cookie_file,
        })
    
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
        ]
    
    try:
        # Enhanced download process with better error handling
        attempts = 0
        max_attempts = 3
        success = False
        
        while attempts < max_attempts and not success and downloading:  # Check global download flag
            attempts += 1
            
            try:
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
                            
                            # Check if this is a playlist or channel
                            if 'entries' in info:
                                # This is a playlist, channel or profile page
                                return handle_playlist_or_profile(info, download_path, quality, thread_count, row_id, url, platform)
                    except Exception as e:
                        print(f"Info extraction warning (will try direct download): {str(e)}")
                    
                    # Check if downloading was cancelled before starting actual download
                    if not downloading:
                        root.after(0, lambda: update_video_status(row_id, "Cancelled", ""))
                        return False
                    
                    # Start actual download
                    ydl.download([url])
                
                # After download, verify the file exists
                video_path = get_video_output_path(row_id)
                if video_path and os.path.exists(video_path) and os.path.isfile(video_path):
                    print(f"Download successful, file saved at: {video_path}")
                    # Mark download as complete
                    root.after(0, lambda: update_video_status(row_id, "Completed", "Done"))
                    root.after(0, lambda: update_header_message(f"Download Completed: {os.path.basename(video_path)}", "#00FF00"))
                    success = True
                    
                    # Clean up any remaining thumbnail files
                    try:
                        cleanup_thumbnail_files(platform_path)
                    except:
                        pass  # Ignore errors in cleanup
                        
                    return True
                else:
                    # If file not found but no exception was raised, try with different options
                    print(f"Download attempt {attempts} - File not found at expected location, retrying with different options")
                    # Modify options for next attempt
                    if attempts < max_attempts:
                        if platform == "YouTube":
                            # Try with different format on retry
                            ydl_opts['format'] = 'best/bestvideo+bestaudio'
                        elif platform == "Facebook":
                            # Try with different Facebook format
                            ydl_opts['format'] = 'best'
                        elif platform == "TikTok":
                            # TikTok fallback
                            ydl_opts['format'] = 'best'
                            
            except Exception as e:
                error_msg = str(e)
                print(f"Download attempt {attempts} error: {error_msg}")
                
                if attempts < max_attempts and downloading:  # Check if downloading is still active
                    # Log retry
                    root.after(0, lambda: update_video_status(row_id, f"Retry {attempts}/{max_attempts}", error_msg[:20] + "..."))
                    root.after(0, lambda: update_header_message(f"Retrying download... Attempt {attempts}/{max_attempts}", "#FFCC00"))
                    
                    # Change options based on error
                    if "HTTP Error 403" in error_msg:
                        # Permission error - try with different user agent
                        ydl_opts['http_headers']['User-Agent'] = get_alternate_user_agent(platform, attempts)
                    elif "requested format not available" in error_msg.lower():
                        # Format issue - fallback to simpler format
                        ydl_opts['format'] = 'best'
                    
                    # Small delay before retry
                    time.sleep(1)
                
        # If we get here, all attempts failed or downloads were cancelled
        if not downloading:
            root.after(0, lambda: update_video_status(row_id, "Cancelled", ""))
            return False
        elif not success:
            error_msg = "Maximum retry attempts reached"
            root.after(0, lambda: update_video_status(row_id, "Failed", error_msg))
            root.after(0, lambda: update_header_message(f"Download Failed after {max_attempts} attempts", "#FF0000"))
            return False
                
    except Exception as e:
        error_msg = str(e)
        print(f"Critical download error: {error_msg}")
        root.after(0, lambda: update_video_status(row_id, "Failed", error_msg[:20] + "..."))
        root.after(0, lambda: update_header_message(f"Download Failed: {error_msg[:50]}", "#FF0000"))
        return False
    finally:
        # Remove thread from active threads list
        if threading.current_thread() in active_download_threads:
            active_download_threads.remove(threading.current_thread())

# ENHANCED FUNCTION: To clean up thumbnail files - more thorough cleanup
def cleanup_thumbnail_files(directory):
    """Clean up any remaining thumbnail files in the directory"""
    thumbnail_extensions = ['.jpg', '.jpeg', '.webp', '.png', '.thumb']
    
    try:
        # Only proceed if directory exists
        if not os.path.exists(directory) or not os.path.isdir(directory):
            return
            
        # Get all files in the directory
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath):
                # Check if this is a thumbnail file
                is_thumbnail = False
                
                # Check extension first
                if any(filename.lower().endswith(ext) for ext in thumbnail_extensions):
                    is_thumbnail = True
                
                # Also delete any .jpg files with matching video names
                # For example, if "video.mp4" exists, delete "video.mp4.jpg"
                base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
                if not is_thumbnail:
                    for ext in thumbnail_extensions:
                        thumb_name = f"{filename}{ext}"
                        thumb_path = os.path.join(directory, thumb_name)
                        if os.path.isfile(thumb_path):
                            try:
                                os.remove(thumb_path)
                                print(f"Removed thumbnail file: {thumb_path}")
                            except Exception as e:
                                print(f"Error removing thumbnail file {thumb_path}: {str(e)}")
                elif is_thumbnail:
                    # This is a thumbnail file, check if we should delete it
                    # If file ends with .mp4.jpg or similar pattern, it's definitely a thumbnail
                    if any(f".{vext}.{text}" in filename.lower() for vext in ['mp4', 'webm', 'mkv'] for text in ['jpg', 'jpeg', 'webp', 'png']):
                        try:
                            os.remove(filepath)
                            print(f"Removed thumbnail file: {filepath}")
                        except Exception as e:
                            print(f"Error removing thumbnail file {filepath}: {str(e)}")
    except Exception as e:
        print(f"Error during thumbnail cleanup: {str(e)}")

# IMPROVED LOADING ANIMATION FOR EXTRACTION PROGRESS
def update_loading_animation():
    """Update the loading animation in the extraction progress window"""
    global loading_animation_index, extraction_progress_window
    
    if extraction_progress_window and hasattr(extraction_progress_window, 'animation_label'):
        # Animation frames
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        
        # Update animation index
        loading_animation_index = (loading_animation_index + 1) % len(frames)
        
        # Update animation label
        extraction_progress_window.animation_label.configure(text=frames[loading_animation_index])
        
        # Schedule next update
        extraction_progress_window.after(100, update_loading_animation)

# COMPLETELY REDESIGNED EXTRACTION PROGRESS WINDOW
def create_extraction_progress_window(title="Extracting Videos", profile_url=""):
    """Create an improved window to show extraction progress with animation"""
    global extraction_progress_window, extraction_cancel, loading_animation_index
    
    # Reset cancel flag and animation index
    extraction_cancel = False
    loading_animation_index = 0
    
    # Close existing window if open
    if extraction_progress_window and extraction_progress_window.winfo_exists():
        extraction_progress_window.destroy()
    
    # Create new window
    extraction_progress_window = ctk.CTkToplevel(root)
    extraction_progress_window.title(title)
    extraction_progress_window.geometry("450x270")  # Slightly larger for better layout
    extraction_progress_window.resizable(False, False)
    extraction_progress_window.grab_set()  # Make modal
    extraction_progress_window.transient(root)  # Make window appear on top of main window
    
    # Center the window
    center_window(extraction_progress_window, 450, 270)
    
    # Header frame with title and animation
    header_frame = ctk.CTkFrame(extraction_progress_window, fg_color="transparent")
    header_frame.pack(fill="x", padx=20, pady=(20, 5))
    
    # Animation label (spinner)
    animation_label = ctk.CTkLabel(header_frame, text="⠋", font=ctk.CTkFont(size=24))
    animation_label.pack(side="left", padx=(0, 10))
    
    # Store reference to animation label
    extraction_progress_window.animation_label = animation_label
    
    # Title label
    title_label = ctk.CTkLabel(
        header_frame, 
        text="Extracting Videos from Profile",
        font=ctk.CTkFont(size=16, weight="bold")
    )
    title_label.pack(side="left", fill="x", expand=True)
    
    # URL display with truncation if needed
    url_display = profile_url
    if len(url_display) > 60:
        url_display = url_display[:57] + "..."
    
    # URL frame
    url_frame = ctk.CTkFrame(extraction_progress_window, fg_color="transparent")
    url_frame.pack(fill="x", padx=20, pady=5)
    
    # URL label (showing the profile being processed)
    url_label = ctk.CTkLabel(
        url_frame, 
        text=f"URL: {url_display}",
        font=ctk.CTkFont(size=12),
        fg_color="#f0f0f0",  # Light background
        corner_radius=4,
        width=410
    )
    url_label.pack(pady=5, ipady=3)  # Inner padding for better appearance
    
    # Progress information section
    info_frame = ctk.CTkFrame(extraction_progress_window, fg_color="transparent")
    info_frame.pack(fill="x", padx=20, pady=5)
    
    # Status label
    status_label_title = ctk.CTkLabel(info_frame, text="Status:", width=80)
    status_label_title.grid(row=0, column=0, sticky="w", pady=2)
    
    status_value = ctk.CTkLabel(info_frame, text="Initializing...", width=300)
    status_value.grid(row=0, column=1, sticky="w", pady=2)
    
    # Count label
    count_label_title = ctk.CTkLabel(info_frame, text="Found:", width=80)
    count_label_title.grid(row=1, column=0, sticky="w", pady=2)
    
    count_value = ctk.CTkLabel(info_frame, text="0 videos")
    count_value.grid(row=1, column=1, sticky="w", pady=2)
    
    # Progress label
    progress_label_title = ctk.CTkLabel(info_frame, text="Progress:", width=80) 
    progress_label_title.grid(row=2, column=0, sticky="w", pady=2)
    
    progress_value = ctk.CTkLabel(info_frame, text="0 of 0 videos (0%)")
    progress_value.grid(row=2, column=1, sticky="w", pady=2)
    
    # Progress bar
    progress_bar_frame = ctk.CTkFrame(extraction_progress_window, fg_color="transparent")
    progress_bar_frame.pack(fill="x", padx=20, pady=10)
    
    progress = ctk.CTkProgressBar(progress_bar_frame, width=410, height=15)
    progress.pack(pady=5)
    progress.set(0)
    
    # Cancel button with improved styling
    button_frame = ctk.CTkFrame(extraction_progress_window, fg_color="transparent") 
    button_frame.pack(pady=15)
    
    def cancel_extraction():
        global extraction_cancel
        extraction_cancel = True
        status_value.configure(text="Cancelling extraction...")
    
    cancel_button = ctk.CTkButton(
        button_frame, 
        text="Cancel Extraction", 
        command=cancel_extraction,
        fg_color="#e74c3c", 
        hover_color="#c0392b",
        width=150,
        height=32  # Reduced height for more compact look
    )
    cancel_button.pack()
    
    # Store references to widgets that need to be updated
    extraction_progress_window.status_label = status_value
    extraction_progress_window.count_label = count_value
    extraction_progress_window.progress_label = progress_value
    extraction_progress_window.progress_bar = progress
    
    # Start the loading animation
    update_loading_animation()
    
    return extraction_progress_window

# Function to update extraction progress with better formatting
def update_extraction_progress(status, current=0, total=0, count=None):
    """Update the extraction progress window with improved formatting"""
    global extraction_progress_window
    
    if extraction_progress_window and extraction_progress_window.winfo_exists():
        if status:
            extraction_progress_window.status_label.configure(text=status)
        
        if count is not None:
            extraction_progress_window.count_label.configure(text=f"{count} videos")
        
        # Calculate and format progress percentage
        if total > 0:
            percent = (current / total) * 100
            extraction_progress_window.progress_bar.set(percent / 100)
            extraction_progress_window.progress_label.configure(
                text=f"{current} of {total} videos ({percent:.1f}%)"
            )
        
        # Force window update
        extraction_progress_window.update_idletasks()
        extraction_progress_window.update()

# Check if extraction was cancelled
def is_extraction_cancelled():
    """Check if the extraction process was cancelled by user"""
    global extraction_cancel
    return extraction_cancel
    
# IMPROVED PROFILE/CHANNEL DOWNLOAD WITH PROGRESS WINDOW
def handle_playlist_or_profile(info, download_path, quality, thread_count, row_id, url, platform):
    """
    Enhanced function to handle playlist/profile downloads with improved progress window.
    """
    global download_queue, video_table, extraction_progress_window
    
    try:
        # Create progress window with profile URL
        extraction_window = create_extraction_progress_window(
            f"Extracting {platform} Videos",
            url
        )
        
        if 'entries' not in info or not info['entries']:
            # Not a playlist or empty playlist
            update_video_status(row_id, "Failed", "No videos found")
            update_header_message("No videos found in playlist/profile", "#FF0000")
            
            # Close progress window
            if extraction_window and extraction_window.winfo_exists():
                extraction_window.destroy()
                
            return False
            
        # Get all potential entries
        all_entries = list(info['entries'])
        entry_count = len(all_entries)
        
        # Update progress window
        update_extraction_progress(
            f"Found {entry_count} videos in {platform} profile/playlist",
            0, entry_count, entry_count
        )
        
        # First update the original row to indicate this is a playlist/profile
        playlist_title = info.get('title', 'Unknown Playlist')
        update_video_metadata(row_id, f"[Collection] {playlist_title}", 
                            info.get('uploader', info.get('channel', 'Unknown')),
                            None, None)
        update_video_status(row_id, f"Profile: {entry_count} videos", "")
        
        # Add all videos to the queue
        videos_added = 0
        
        # Loop through entries with improved progress tracking
        for i, entry in enumerate(all_entries):
            # Check if extraction was cancelled
            if is_extraction_cancelled():
                update_header_message(f"Extraction cancelled. Added {videos_added} videos.", "#FFCC00")
                
                # Close progress window
                if extraction_window and extraction_window.winfo_exists():
                    extraction_window.destroy()
                    
                # Start downloads for videos that were already added
                if videos_added > 0 and not downloading:
                    start_downloads()
                    
                return True
            
            # Update progress
            update_extraction_progress(
                f"Processing video {i+1} of {entry_count}",
                i+1, entry_count, videos_added
            )
            
            if not entry:
                continue
                
            # Get video URL with enhanced handling
            video_url = None
            
            # First try to get direct URL
            if 'url' in entry:
                video_url = entry['url']
            elif 'webpage_url' in entry:
                video_url = entry['webpage_url']
            elif 'id' in entry:
                # Construct URL based on platform and ID
                if platform == "YouTube":
                    video_url = f"https://www.youtube.com/watch?v={entry['id']}"
                elif platform == "TikTok" and 'webpage_url' in entry:
                    video_url = entry['webpage_url']
                elif platform == "Instagram" and 'webpage_url' in entry:
                    video_url = entry['webpage_url']
                elif platform == "Facebook" and 'id' in entry:
                    # For Facebook, we may need to construct a watch URL
                    video_url = f"https://www.facebook.com/watch/?v={entry['id']}"
                    
            if not video_url:
                continue
            
            # Get video title with fallback
            video_title = entry.get('title', f'Video {i+1}')
            
            # Add to UI and queue
            new_row_id = add_url_to_table(video_url, f"[{i+1}/{entry_count}] {video_title}")
            download_queue.append((new_row_id, video_url))
            videos_added += 1
            
            # Update progress for added videos
            update_extraction_progress(
                f"Added {videos_added} videos so far",
                i+1, entry_count, videos_added
            )
            
            # Short sleep to prevent UI freeze and allow cancellation
            time.sleep(0.05)
            
        # Close progress window
        if extraction_window and extraction_window.winfo_exists():
            extraction_window.destroy()
            
        # Update status
        update_header_message(f"Added {videos_added} videos from {platform} profile/playlist", "#00FF00")
        
        # Start downloads if not already downloading
        if videos_added > 0 and not downloading:
            start_downloads()
            
        return True
        
    except Exception as e:
        print(f"Error handling playlist/profile: {str(e)}")
        update_video_status(row_id, "Failed", "Error processing profile")
        update_header_message(f"Error processing profile: {str(e)[:50]}", "#FF0000")
        
        # Close progress window if it exists
        if extraction_progress_window and extraction_progress_window.winfo_exists():
            extraction_progress_window.destroy()
            
        return False

# IMPROVED: Function to extract videos from profile/channel with better platform support
def extract_videos_from_profile(url, parent_row_id=None):
    """
    Enhanced function to extract videos from profiles with better Facebook and Instagram support.
    This runs in a background thread to avoid UI freezing.
    """
    global extraction_progress_window
    
    # Create extraction progress window
    platform = detect_platform(url)
    extraction_window = create_extraction_progress_window(
        f"Extracting videos from {platform} profile",
        url
    )
    
    # Set up yt-dlp options for extraction with platform-specific optimizations
    ydl_opts = {
        'quiet': True,
        'extract_flat': 'in_playlist',
        'skip_download': True,
        'ignoreerrors': True,
        'http_headers': {
            'User-Agent': get_platform_user_agent(platform)
        }
    }
    
    # Platform-specific extraction optimizations
    if platform == "Facebook":
        # Enhanced Facebook extraction options
        cookie_file = os.path.join(os.path.expanduser("~"), ".fb_cookies.txt")
        if os.path.exists(cookie_file):
            ydl_opts['cookiefile'] = cookie_file
        # Facebook needs additional options
        ydl_opts.update({
            'extract_flat': True,  # Better for Facebook profiles
            'dump_single_json': True,  # Get all data
            'playlistend': 50,  # Limit to 50 videos to prevent timeouts
            'extractor_args': {
                'facebook': ['webpage_url_prefix=https://m.facebook.com/'],
                'generic': ['webpage_url_prefix=https://m.facebook.com/']
            }
        })
    elif platform == "Instagram":
        # Enhanced Instagram extraction options
        cookie_file = os.path.join(os.path.expanduser("~"), ".ig_cookies.txt")
        if os.path.exists(cookie_file):
            ydl_opts['cookiefile'] = cookie_file
        
        # Instagram needs specific options
        ydl_opts.update({
            'extract_flat': True,
            'playlistend': 30,  # Limit to 30 videos to prevent timeouts
            'max_sleep_interval': 5,  # Reduce waiting time
            'http_headers': {
                'User-Agent': "Instagram 243.1.0.14.111 Android (31/12; 480dpi; 1080x2340; samsung; SM-G973F; beyond1; exynos9820; en_US; 382290498)",
                'Accept': '*/*',
                'Accept-Language': 'en-US',
                'Accept-Encoding': 'gzip, deflate',
                'Origin': 'https://www.instagram.com',
                'Referer': 'https://www.instagram.com/'
            }
        })
    
    try:
        # Update progress window
        update_extraction_progress("Connecting to platform...", 0, 1, 0)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract video information
            try:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    # No information found
                    update_extraction_progress("Failed to extract videos: No information found", 0, 1, 0)
                    time.sleep(2)
                    if extraction_window and extraction_window.winfo_exists():
                        extraction_window.destroy()
                        
                    # Update parent row if provided
                    if parent_row_id:
                        root.after(0, lambda: update_video_status(parent_row_id, "Failed", "No videos found"))
                    return
                
                # Check if this is a playlist or profile with entries
                if 'entries' not in info or not info['entries']:
                    # Special case for Facebook/Instagram - try alternate extractor
                    if platform in ["Facebook", "Instagram"] and not info.get('entries'):
                        update_extraction_progress("Trying alternate extraction method...", 0, 1, 0)
                        time.sleep(1)
                        
                        # Change settings for second attempt
                        ydl_opts['force_generic_extractor'] = True
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl2:
                            info = ydl2.extract_info(url, download=False)
                            if not info or 'entries' not in info or not info['entries']:
                                # Still no entries
                                update_extraction_progress("No videos found in profile/playlist", 0, 1, 0)
                                time.sleep(2)
                                if extraction_window and extraction_window.winfo_exists():
                                    extraction_window.destroy()

# Update parent row if provided
                                if parent_row_id:
                                    root.after(0, lambda: update_video_status(parent_row_id, "Failed", "No videos found"))
                                return
                    else:
                        # Not a playlist or empty playlist
                        update_extraction_progress("No videos found in profile/playlist", 0, 1, 0)
                        time.sleep(2)
                        if extraction_window and extraction_window.winfo_exists():
                            extraction_window.destroy()
                            
                        # Update parent row if provided
                        if parent_row_id:
                            root.after(0, lambda: update_video_status(parent_row_id, "Failed", "No videos found"))
                        return
                    
                # Get all potential entries
                all_entries = list(info['entries'])
                entry_count = len(all_entries)
                
                # Update progress window
                update_extraction_progress(
                    f"Found {entry_count} videos in {platform} profile/playlist",
                    0, entry_count, entry_count
                )
                
                # Update parent row if provided
                if parent_row_id:
                    playlist_title = info.get('title', 'Unknown Profile')
                    root.after(0, lambda: update_video_metadata(parent_row_id, 
                                                               f"[Collection] {playlist_title}",
                                                               info.get('uploader', info.get('channel', 'Unknown')),
                                                               None, None))
                    root.after(0, lambda: update_video_status(parent_row_id, f"Profile: {entry_count} videos", ""))
                
                # Add videos to the table
                videos_added = 0
                
                # Loop through entries with progress tracking
                for i, entry in enumerate(all_entries):
                    # Check if extraction was cancelled
                    if is_extraction_cancelled():
                        update_header_message(f"Extraction cancelled. Added {videos_added} videos.", "#FFCC00")
                        
                        # Close progress window
                        if extraction_window and extraction_window.winfo_exists():
                            extraction_window.destroy()
                        return
                    
                    # Update progress
                    update_extraction_progress(
                        f"Processing video {i+1} of {entry_count}",
                        i+1, entry_count, videos_added
                    )
                    
                    if not entry:
                        continue
                        
                    # Get video URL with enhanced handling for all platforms
                    video_url = None
                    
                    # First try to get direct URL
                    if 'url' in entry:
                        video_url = entry['url']
                    elif 'webpage_url' in entry:
                        video_url = entry['webpage_url']
                    elif 'original_url' in entry:
                        video_url = entry['original_url']
                    elif 'id' in entry:
                        # Construct URL based on platform and ID
                        if platform == "YouTube":
                            video_url = f"https://www.youtube.com/watch?v={entry['id']}"
                        elif platform == "TikTok" and 'id' in entry:
                            video_url = f"https://www.tiktok.com/@tiktok/video/{entry['id']}"
                        elif platform == "Instagram" and 'id' in entry:
                            video_url = f"https://www.instagram.com/p/{entry['id']}/"
                        elif platform == "Facebook" and 'id' in entry:
                            # For Facebook, we need to construct a watch URL
                            video_url = f"https://www.facebook.com/watch/?v={entry['id']}"
                            
                    # For Facebook and Instagram, extract the direct URL if possible
                    if platform in ["Facebook", "Instagram"] and (not video_url or "generic" in video_url):
                        # Try to extract URL from other fields
                        for field in ['url', 'webpage_url', 'id', 'ie_key']:
                            if field in entry and entry[field]:
                                field_value = entry[field]
                                if isinstance(field_value, str) and ("facebook.com" in field_value or "instagram.com" in field_value):
                                    video_url = field_value
                                    break
                    
                    if not video_url:
                        print(f"Could not determine URL for entry {i+1}")
                        continue
                    
                    # Get video title with fallback
                    video_title = entry.get('title', f'Video {i+1}')
                    if not video_title or video_title == "NA":
                        video_title = f"{platform} Video {i+1}"
                    
                    # Create a function to add the URL to the table (for threading safety)
                    def add_video_safely(url, title):
                        add_url_to_table(url, title)
                    
                    # Add to UI table (using root.after for thread safety)
                    root.after(0, lambda u=video_url, t=video_title: add_video_safely(u, f"[{i+1}/{entry_count}] {t}"))
                    videos_added += 1
                    
                    # Update progress for added videos
                    update_extraction_progress(
                        f"Added {videos_added} videos so far",
                        i+1, entry_count, videos_added
                    )
                    
                    # Short sleep to prevent UI freeze and allow cancellation
                    time.sleep(0.05)
                    
                # Update status message
                update_header_message(f"Added {videos_added} videos from {platform} profile/playlist", "#00FF00")
                
                # Close progress window after a short delay
                time.sleep(1)
                if extraction_window and extraction_window.winfo_exists():
                    extraction_window.destroy()
            except Exception as e:
                print(f"Error during extraction: {str(e)}")
                update_extraction_progress(f"Extraction error: {str(e)[:50]}...", 0, 1, 0)
                time.sleep(3)
                if extraction_window and extraction_window.winfo_exists():
                    extraction_window.destroy()
                # Update parent row if provided
                if parent_row_id:
                    root.after(0, lambda: update_video_status(parent_row_id, "Failed", f"Error: {str(e)[:20]}"))
    
    except Exception as e:
        print(f"Error extracting videos from profile: {str(e)}")
        update_extraction_progress(f"Error: {str(e)}", 0, 1, 0)
        
        # Update parent row if provided
        if parent_row_id:
            root.after(0, lambda: update_video_status(parent_row_id, "Failed", f"Error: {str(e)[:20]}"))
        
        # Close progress window after error display
        time.sleep(3)
        if extraction_window and extraction_window.winfo_exists():
            extraction_window.destroy()

# ENHANCED ADD URL FUNCTION WITH PROFILE DETECTION
def add_url_to_table(url, title=None):
    """Enhanced function to add URL to table with optional title and profile detection"""
    try:
        # Count existing items to determine the row number
        count = len(video_table.get_children()) + 1
        
        # For profile URLs, add a special entry and start extraction
        if is_profile_url(url):
            platform = detect_platform(url)
            
            # Insert profile row with special status
            row_id = video_table.insert("", "end", values=(
                count,              # Row number
                url,                # URL
                f"{platform} Profile",  # Status showing it's a profile
                title or f"Extracting videos from {platform} profile...",  # Title
                "Multiple creators",  # Author
                "Various",          # Duration
                "Multiple"          # Size
            ), tags=("profile_url", url))
            
            # Update count in footer
            update_link_count()
            
            # Update header with new profile
            update_header_message(f"Added {platform} profile: {url}")
            
            # Start extraction in background thread
            threading.Thread(
                target=lambda: extract_videos_from_profile(url, row_id), 
                daemon=True,
                name=f"profile_extractor_{count}"
            ).start()
            
            return row_id
        
        # Standard URL handling (non-profile)
        row_id = video_table.insert("", "end", values=(
            count,              # Row number
            url,                # URL
            "Pending",          # Status
            title or "Fetching...",  # Title (if provided)
            "Unknown",          # Author
            "Unknown",          # Duration
            "Unknown"           # Size
        ), tags=("url", url))   # Store URL in tags
        
        # Update count in footer
        update_link_count()
        
        # Update header with new link count
        platform = detect_platform(url)
        update_header_message(f"Link Count: {count} | Added {platform} URL")
        
        return row_id
    except Exception as e:
        print(f"Error adding URL to table: {str(e)}")
        return None

# Function to add URL with profile detection
def add_url():
    """Enhanced function to add URL with profile detection"""
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
        
        ctk.CTkLabel(url_window, text="Enter Video or Profile URL:").pack(pady=(15, 5))
        
        url_input = ctk.CTkEntry(url_window, placeholder_text="Paste URL here...", width=400)
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

# REDESIGNED BULK URL INPUT WINDOW
def add_bulk_urls():
    """Redesigned function to add multiple URLs at once with profile detection"""
    bulk_window = ctk.CTkToplevel(root)
    bulk_window.title("Add Multiple URLs")
    bulk_window.geometry("500x350")  # Reduced size for compact layout
    bulk_window.resizable(True, True)
    bulk_window.grab_set()
    
    # Center window
    center_window(bulk_window, 500, 350)
    
    # Main frame
    main_frame = ctk.CTkFrame(bulk_window, fg_color="transparent")
    main_frame.pack(fill="both", expand=True, padx=15, pady=15)
    
    # Instructions
    ctk.CTkLabel(
        main_frame,
        text="Enter Multiple URLs (one per line):",
        font=ctk.CTkFont(size=14, weight="bold")
    ).pack(pady=(0, 5))
    
    # Help text
    help_text = "Each line should contain one URL (video or profile/channel URL)"
    ctk.CTkLabel(
        main_frame,
        text=help_text,
        font=ctk.CTkFont(size=12),
        text_color="#666666"
    ).pack(pady=(0, 5))
    
    # Text area for URLs
    url_text = ctk.CTkTextbox(main_frame, width=470, height=200)
    url_text.pack(pady=10, fill="both", expand=True)
    url_text.focus_set()
    
    # Button frame
    button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    button_frame.pack(fill="x", pady=(10, 0))
    
    # Process function
    def process_urls():
        urls_text = url_text.get("1.0", "end-1c")
        urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
        
        added_count = 0
        for url in urls:
            if url:
                add_url_to_table(url)
                added_count += 1
        
        bulk_window.destroy()
        update_header_message(f"Added {added_count} URLs in bulk", "#00FF00")
    
    # Paste from clipboard function
    def paste_clipboard():
        clipboard_content = pyperclip.paste()
        if clipboard_content:
            url_text.delete("1.0", "end")
            url_text.insert("1.0", clipboard_content)
    
    # Add URLs button
    ctk.CTkButton(
        button_frame,
        text="Add URLs",
        command=process_urls,
        width=100,
        height=32,
        fg_color="#2ecc71",
        hover_color="#27ae60"
    ).pack(side="left", padx=(0, 5))
    
    # Cancel button
    ctk.CTkButton(
        button_frame,
        text="Cancel",
        command=bulk_window.destroy,
        width=100,
        height=32,
        fg_color="#e74c3c",
        hover_color="#c0392b"
    ).pack(side="left", padx=5)
    
    # Paste clipboard button
    ctk.CTkButton(
        button_frame,
        text="Paste from Clipboard",
        command=paste_clipboard,
        width=150,
        height=32,
        fg_color="#3498db",
        hover_color="#2980b9"
    ).pack(side="right", padx=(5, 0))

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

def update_link_count():
    """Update the link count in the footer"""
    count = len(video_table.get_children())
    link_count_label.configure(text=f"Link Count: {count}")

# IMPROVED OPEN FOLDER FUNCTION WITH YOUTUBE FIX
def open_video_folder():
    """Fixed open folder function to properly handle YouTube folders"""
    global context_menu_row, video_table
    
    if not context_menu_row or not video_table:
        return
        
    try:
        # Get values from the selected row
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
        
        # Ensure the platform folder exists - create it if not
        if not os.path.exists(platform_path):
            try:
                os.makedirs(platform_path)
                print(f"Created platform folder: {platform_path}")
            except Exception as e:
                print(f"Error creating folder: {str(e)}")
        
        # Try to get the video file path
        video_path = get_video_output_path(context_menu_row)
        
        # If the path is a file, open its containing folder
        if video_path and os.path.isfile(video_path):
            folder_path = os.path.dirname(video_path)
            
            # Check if folder exists
            if not os.path.exists(folder_path):
                folder_path = platform_path  # Fallback to platform folder
            
            # Open folder and select the file if possible
            if sys.platform == "win32":
                # On Windows, use explorer to open and select the file
                try:
                    subprocess.run(['explorer', '/select,', video_path])
                    return
                except Exception as e:
                    print(f"Error using explorer select: {str(e)}")
                    # Fallback to just opening the folder
                    os.startfile(folder_path)
            else:
                # On other platforms, just open the folder
                if sys.platform == "darwin":  # macOS
                    subprocess.call(["open", folder_path])
                else:  # Linux
                    subprocess.call(["xdg-open", folder_path])
                return
        
        # If can't find specific file, just open the platform folder
        print(f"Opening platform folder: {platform_path}")
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
        
        if video_path and os.path.exists(video_path) and os.path.isfile(video_path):
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
        
        if video_path and os.path.exists(video_path) and os.path.isfile(video_path):
            print(f"Video file exists, opening with default player")
            # Open the video with the default player
            if sys.platform == "win32":
                os.startfile(video_path)
            elif sys.platform == "darwin":  # macOS
                subprocess.call(["open", video_path])
            else:  # Linux
                subprocess.call(["xdg-open", video_path])
        else:
            # If not found by the function, show error message
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
            values = video_table.item(context_menu_row, "values")
            if len(values) > 1:
                url = values[1]
                
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

# FIXED DOWNLOAD STARTER FUNCTION (renamed to start_downloads from start_download)
def start_downloads():
    """Enhanced function to start downloads with better thread management"""
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
    
    # Set downloading flag before modifying UI
    downloading = True
    
    # Disable buttons safely
    try:
        if download_button:
            download_button.configure(state="disabled")
        if start_bulk_button:
            start_bulk_button.configure(state="disabled")
    except Exception as e:
        print(f"Error disabling buttons: {str(e)}")
    
    status_label.configure(text="Starting downloads...")
    update_header_message(f"Starting downloads for {len(items)} videos")
    
    # Clear download queue and add all items
    download_queue.clear()
    
    for item in items:
        # Get URL from tags and skip already downloading/completed items
        tags = video_table.item(item, "tags")
        values = video_table.item(item, "values")
        
        if len(values) > 2:  # Make sure we have enough values
            status = values[2]  # Status is the 3rd column (index 2)
            
            # Only queue items that are pending or failed
            if status in ["Pending", "Failed", "Paused"]:
                url = None
                
                # Try to get URL from tags first
                if len(tags) > 1:
                    for tag in tags:
                        if tag != "url" and tag != "completed" and tag != "failed" and tag != "paused":
                            url = tag
                            break
                
                # If URL not in tags, try to get from values
                if not url and len(values) > 1:
                    url = values[1]
                
                if url:
                    download_queue.append((item, url))
    
    # Start worker threads based on configuration - limit to available items
    worker_count = min(thread_count, len(download_queue), 8)  # Max 8 workers
    
    for i in range(worker_count):
        t = threading.Thread(target=download_worker, 
                           args=(path, quality, thread_count),
                           name=f"download_worker_{i}",
                           daemon=True)
        t.start()
        print(f"Started worker thread {i}")
    
    # If somehow no threads started and no items in queue
    if worker_count == 0 and downloading:
        print("No workers started - enabling buttons and resetting state")
        downloading = False
        enable_download_buttons()

# Function to pause all downloads - IMPROVED
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

# Function to resume all downloads - IMPROVED
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
        start_downloads()

# IMPROVED: Restart application and reset all state - FIXED Issue #1
def restart_app():
    """Completely restart the application, clearing all URLs and instantly stopping all active downloads"""
    global downloading, download_queue, progress_info, extraction_progress_window, active_download_threads
    
    # Close extraction progress window if open
    if extraction_progress_window and extraction_progress_window.winfo_exists():
        try:
            extraction_progress_window.destroy()
        except:
            pass
    
    # Prepare warning message
    warning_message = "Are you sure you want to restart the application? This will clear all URLs and reset all settings."
    if downloading:
        warning_message = "Downloads are in progress! Restarting will stop all downloads and clear everything. Continue?"
        
    if messagebox.askyesno("Restart Application", warning_message):
        # First stop any ongoing downloads - FIXED: More aggressive termination
        if downloading:
            # Clear download queue immediately to prevent new tasks from starting
            download_queue.clear()
            
            # Set downloading flag to false immediately 
            downloading = False
            
            # Mark all active downloads as cancelled in UI
            for item in video_table.get_children():
                values = list(video_table.item(item, "values"))
                status = values[2] if len(values) > 2 else ""
                
                # Only update downloads in progress
                if "Downloading" in status or status == "Pending" or status == "Paused":
                    values[2] = "Cancelled"
                    video_table.item(item, values=values)
            
            # Clear progress tracking
            progress_info.clear()
            
            # Re-enable download buttons immediately
            if download_button:
                download_button.configure(state="normal")
            if start_bulk_button:
                start_bulk_button.configure(state="normal")
            
            # Reset progress bar
            progress_bar.set(0)
            
            # Update status to show restart happened
            status_label.configure(text="All downloads stopped and application reset")
            update_header_message("Downloads stopped and application reset", "#FF9900")
        
        # Now clear all URLs from the table
        for item in video_table.get_children():
            video_table.delete(item)
            
        # Update link count
        update_link_count()
        
        # Reset paused state if needed
        global paused
        paused = False
        
        # Reset any folder path to default
        default_path = settings.get("default_download_path", os.path.join(os.path.expanduser("~"), "Downloads"))
        download_path.set(default_path)
        if folder_entry:
            folder_entry.delete(0, tk.END)
            folder_entry.insert(0, default_path)
        
        # Reset quality to default
        quality_var.set("1080")
        
        # Reset thread count to default from settings
        thread_count_var.set(settings.get("default_threads", "4"))
        
        # Clear any progress info
        progress_info.clear()
        
        # Reset progress bar
        progress_bar.set(0)
        
        # Update header message with restart confirmation
        update_header_message("Application restarted - all settings and URLs have been reset", "#00FF00")

# IMPROVED DOWNLOAD WORKER WITH BETTER THREAD MANAGEMENT
def download_worker(path, quality, thread_count):
    """Improved download worker with better thread management"""
    global downloading, download_queue, paused, active_download_threads
    
    worker_name = threading.current_thread().name
    print(f"Worker started: {worker_name}")
    
    # Add this thread to the active download threads list
    if threading.current_thread() not in active_download_threads:
        active_download_threads.append(threading.current_thread())
    
    try:
        while download_queue and downloading:
            # Check if downloads are paused
            if paused:
                time.sleep(1)  # Wait before checking again
                continue
                
            try:
                # Get next URL from queue safely
                row_id, url = None, None
                with threading.Lock():  # Use lock to safely get from queue
                    if download_queue:
                        row_id, url = download_queue.pop(0)
                
                if not row_id or not url:
                    time.sleep(0.5)
                    continue
                
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
                time.sleep(1)  # Prevent rapid failures
    except Exception as e:
        print(f"Fatal error in worker {worker_name}: {str(e)}")
    finally:
        print(f"Worker exiting: {worker_name}")
        
        # Remove this thread from active threads list
        if threading.current_thread() in active_download_threads:
            active_download_threads.remove(threading.current_thread())
            
        # Check if this is the last worker and if the queue is empty
        check_if_all_downloads_complete()

# Function to check if all downloads are complete
def check_if_all_downloads_complete():
    """Check if all downloads are complete and safely reset UI"""
    global downloading, download_queue
    
    # Count active workers
    active_workers = sum(1 for t in threading.enumerate() 
                      if t != threading.current_thread() and t.is_alive() 
                      and "download_worker" in t.name)
    
    download_queue_empty = len(download_queue) == 0
    
    if download_queue_empty and active_workers <= 1:  # ≤1 because current thread might be counted
        # This is the last thread - safely reset everything
        # Use after to ensure this runs in the main thread
        root.after(0, lambda: status_label.configure(text="All downloads completed!"))
        root.after(0, lambda: progress_bar.set(1.0))  # Set progress to 100%
        root.after(0, lambda: update_header_message("All downloads completed successfully!", "#00FF00"))
        
        # Reset downloading flag FIRST
        root.after(0, set_downloading_false)
        
        # THEN enable buttons
        root.after(50, enable_download_buttons)

# IMPROVED BUTTON ENABLING FUNCTION
def enable_download_buttons():
    """Improved function to reliably enable download buttons"""
    global download_button, start_bulk_button
    
    # Define a function to ensure this runs on the main thread
    def _enable():
        try:
            if download_button:
                download_button.configure(state="normal")
            if start_bulk_button:
                start_bulk_button.configure(state="normal")
            print("Download buttons enabled successfully")
        except Exception as e:
            print(f"Error enabling buttons: {str(e)}")
    
    # Run directly if we're in the main thread, otherwise use after
    if threading.current_thread() is threading.main_thread():
        _enable()
    else:
        try:
            root.after(0, _enable)
        except Exception as e:
            print(f"Error scheduling button enable: {str(e)}")

# SAFER FUNCTION TO SET DOWNLOADING FALSE
def set_downloading_false():
    """Safely set the downloading flag to False"""
    global downloading
    try:
        downloading = False
        print("Download state reset successfully")
    except Exception as e:
        print(f"Error resetting download state: {str(e)}")

# Function to install YouTube packages
def install_yt_packages():
    try:
        # Create a popup window with options
        install_window = ctk.CTkToplevel(root)
        install_window.title("Install YouTube Packages")
        install_window.geometry("450x300")  # Reduced size
        install_window.resizable(False, False)
        install_window.grab_set()
        
        # Center window relative to root
        center_window(install_window, 450, 300)
        
        ctk.CTkLabel(install_window, text="Install Additional Packages", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(20, 5))
        
        info_text = """The video downloader requires additional packages to function correctly with YouTube.
        
This will install/update the following packages:
- yt-dlp (main downloader)
- ffmpeg (video processor)
- aria2c (multi-threaded downloader)

Select an installation method below:"""
        
        info_label = ctk.CTkLabel(install_window, text=info_text, wraplength=400, justify="left")
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
        button_frame.pack(pady=10)
        
        ctk.CTkButton(button_frame, text="Install with pip", command=install_pip, 
                    width=180, height=36, fg_color="#2ecc71", hover_color="#27ae60").pack(pady=8)
        
        ctk.CTkButton(button_frame, text="Open Installation Instructions", command=open_instructions,
                    width=180, height=36, fg_color="#3498db", hover_color="#2980b9").pack(pady=8)
        
        ctk.CTkButton(button_frame, text="Cancel", command=install_window.destroy,
                    width=180, height=36, fg_color="#e74c3c", hover_color="#c0392b").pack(pady=8)
        
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

# FIXED: Load menu icons function to load from application directory
def load_menu_icons():
    """
    Enhanced function to load menu icons from the application directory
    - Fixes Issue #3: Context menu icons not showing for other users
    """
    global menu_icons
    
    try:
        # Determine the application directory - works with both script and executable
        if hasattr(sys, 'frozen'):  # Running as compiled exe
            app_dir = os.path.dirname(sys.executable)
        else:  # Running as script
            app_dir = os.path.dirname(os.path.abspath(__file__))
            
        # If app_dir is empty (when run from current directory), use current directory
        if not app_dir:
            app_dir = os.getcwd()
            
        print(f"Looking for icons in: {app_dir}")
        
        # Define icon filenames
        icon_filenames = {
            "remove": "Remove From List.png",
            "delete": "Delete Video.png",
            "play": "Play Video.png",
            "folder": "Open Folder.png",
            "copy": "Copy Url.png",
            "retry": "Retry Download.png"  # Added retry icon
        }
        
        # Try to load each icon from the application directory
        for key, filename in icon_filenames.items():
            # Full path to the icon
            icon_path = os.path.join(app_dir, filename)
            
            if os.path.exists(icon_path):
                # Load and resize the image to appropriate menu size
                img = Image.open(icon_path)
                img = img.resize((16, 16), Image.Resampling.LANCZOS)
                menu_icons[key] = ImageTk.PhotoImage(img)
                print(f"Loaded icon: {filename}")
            else:
                # Icon not found, try alternative locations
                print(f"Icon not found at {icon_path}, trying alternatives")
                # Try in an 'icons' subdirectory
                alt_path = os.path.join(app_dir, "icons", filename)
                if os.path.exists(alt_path):
                    img = Image.open(alt_path)
                    img = img.resize((16, 16), Image.Resampling.LANCZOS)
                    menu_icons[key] = ImageTk.PhotoImage(img)
                    print(f"Loaded icon from alternative path: {alt_path}")
                else:
                    print(f"Warning: Icon {filename} not found")
    except Exception as e:
        print(f"Error loading menu icons: {str(e)}")
        # Don't stop the application if icons can't be loaded
        # The menu will still work without icons

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
            # Use proper retry icon if available
            retry_icon = menu_icons.get("retry") if "retry" in menu_icons else menu_icons.get("play")
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
                "default_download_path": os.path.join(os.path.expanduser("~"), "Downloads"),
                "embed_thumbnail": False  # NEW SETTING: To control thumbnail embedding
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
            "default_download_path": os.path.join(os.path.expanduser("~"), "Downloads"),
            "embed_thumbnail": False
        }

def save_settings_to_file():
    settings_file = os.path.join(os.path.expanduser("~"), ".video_downloader_settings.json")
    
    try:
        with open(settings_file, 'w') as f:
            json.dump(settings, f)
    except Exception as e:
        print(f"Error saving settings: {str(e)}")

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

# UPDATED SETTINGS DIALOG WITH THUMBNAIL OPTION
def show_combined_settings():
    global settings
    
    settings_window = ctk.CTkToplevel(root)
    settings_window.title("Settings")
    settings_window.geometry("450x520")  # Reduced size for compact layout
    settings_window.resizable(False, False)
    settings_window.grab_set()
    
    # Center window relative to root
    center_window(settings_window, 450, 520)
    
    # Create a tabview to separate basic and advanced settings
    tab_view = ctk.CTkTabview(settings_window)
    tab_view.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
    
    # Create tabs
    basic_tab = tab_view.add("Basic Settings")
    advanced_tab = tab_view.add("Advanced Settings")
    
    # === BASIC SETTINGS TAB ===
    
    # Main content area for basic tab
    basic_area = ctk.CTkScrollableFrame(basic_tab)
    basic_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    # Title for basic settings
    title_label = ctk.CTkLabel(basic_area, text="⚙️ Basic Settings", 
                              font=ctk.CTkFont(size=16, weight="bold"))
    title_label.pack(anchor=tk.CENTER, pady=(0, 10))
    
    # Video Backup Option
    backup_var = tk.BooleanVar(value=settings.get("create_backup", False))
    backup_check = ctk.CTkCheckBox(basic_area, text="Save Video Backups (JSON, Description)",
                                   variable=backup_var)
    backup_check.pack(anchor=tk.W, pady=4)
    
    # Subtitle Options Section
    subtitle_label = ctk.CTkLabel(basic_area, text="Save Captions Options:", 
                                font=ctk.CTkFont(size=14, weight="bold"))
    subtitle_label.pack(anchor=tk.W, pady=(5, 2))
    
    # Subtitles Options
    subtitles_var = tk.BooleanVar(value=settings.get("write_subtitles", False))
    embed_subtitles_var = tk.BooleanVar(value=settings.get("embed_subtitles", False))
    auto_subtitles_var = tk.BooleanVar(value=settings.get("write_auto_subtitles", False))
    
    subtitles_check = ctk.CTkCheckBox(basic_area, text="Download as Separate SRT File",
                                     variable=subtitles_var)
    subtitles_check.pack(anchor=tk.W, padx=15, pady=2)
    
    embed_subtitles_check = ctk.CTkCheckBox(basic_area, text="Embed Inside Video",
                                           variable=embed_subtitles_var)
    embed_subtitles_check.pack(anchor=tk.W, padx=15, pady=2)
    
    auto_subtitles_check = ctk.CTkCheckBox(basic_area, text="Include Auto-Generated Captions",
                                          variable=auto_subtitles_var)
    auto_subtitles_check.pack(anchor=tk.W, padx=15, pady=2)
    
    # NEW: Thumbnail Option - only for YouTube
    embed_thumbnail_var = tk.BooleanVar(value=settings.get("embed_thumbnail", False))
    embed_thumbnail_check = ctk.CTkCheckBox(basic_area, text="Embed Thumbnail in YouTube Videos",
                                     variable=embed_thumbnail_var)
    embed_thumbnail_check.pack(anchor=tk.W, padx=15, pady=5)
    
    # File naming options section
    naming_label = ctk.CTkLabel(basic_area, text="Save Videos With:", 
                              font=ctk.CTkFont(size=14, weight="bold"))
    naming_label.pack(anchor=tk.W, pady=(10, 2))
    
    # File naming options
    original_title_var = tk.BooleanVar(value=settings.get("use_original_title", True))
    tags_var = tk.BooleanVar(value=settings.get("use_tags", False))
    
    original_title_check = ctk.CTkCheckBox(basic_area, text="Original Title",
                                          variable=original_title_var)
    original_title_check.pack(anchor=tk.W, padx=15, pady=2)
    
    tags_check = ctk.CTkCheckBox(basic_area, text="Include Tags/Hashtags",
                                variable=tags_var)
    tags_check.pack(anchor=tk.W, padx=15, pady=2)
    
    # Auto-paste Option
    autopaste_var = tk.BooleanVar(value=settings.get("auto_paste", True))
    autopaste_check = ctk.CTkCheckBox(basic_area, text="Auto-paste URL from Clipboard",
                                     variable=autopaste_var)
    autopaste_check.pack(anchor=tk.W, pady=5)
    
    # === ADVANCED SETTINGS TAB ===
    
    # Main content area for advanced tab
    adv_area = ctk.CTkScrollableFrame(advanced_tab)
    adv_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    # Title for advanced settings
    adv_title_label = ctk.CTkLabel(adv_area, text="🛠️ Advanced Settings", 
                                 font=ctk.CTkFont(size=16, weight="bold"))
    adv_title_label.pack(anchor=tk.CENTER, pady=(0, 10))
    
    # Application Theme Section
    theme_label = ctk.CTkLabel(adv_area, text="Application Theme:", 
                             font=ctk.CTkFont(size=14, weight="bold"))
    theme_label.pack(anchor=tk.W, pady=(5, 2))
    
    theme_var = tk.StringVar(value=settings.get("theme", "light"))
    theme_frame = ctk.CTkFrame(adv_area, fg_color="transparent")
    theme_frame.pack(fill=tk.X, pady=(0, 5))
    
    light_radio = ctk.CTkRadioButton(theme_frame, text="Light Mode", variable=theme_var, value="light")
    light_radio.pack(side=tk.LEFT, padx=(0, 20))
    
    dark_radio = ctk.CTkRadioButton(theme_frame, text="Dark Mode", variable=theme_var, value="dark")
    dark_radio.pack(side=tk.LEFT)
    
    # Cache Management Section
    cache_label = ctk.CTkLabel(adv_area, text="Cache Management:", 
                             font=ctk.CTkFont(size=14, weight="bold"))
    cache_label.pack(anchor=tk.W, pady=(10, 5))
    
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
                             fg_color="#2ecc71", hover_color="#27ae60", height=32)
    cache_btn.pack(anchor=tk.W, pady=3)
    
    # Multithreading Settings Section
    threading_label = ctk.CTkLabel(adv_area, text="Multithreading Settings:", 
                                 font=ctk.CTkFont(size=14, weight="bold"))
    threading_label.pack(anchor=tk.W, pady=(10, 2))
    
    thread_count_label = ctk.CTkLabel(adv_area, text="Default Thread Count:")
    thread_count_label.pack(anchor=tk.W, pady=(2, 0))
    
    default_thread_var = tk.StringVar(value=settings.get("default_threads", "4"))
    thread_dropdown = ctk.CTkOptionMenu(adv_area, variable=default_thread_var,
                                      values=["1", "2", "3", "4", "6", "8"],
                                      fg_color="#2ecc71", button_color="#27ae60", button_hover_color="#219652",
                                      width=100, height=32)
    thread_dropdown.pack(anchor=tk.W, pady=3)
    
    # Download Retries Section
    retries_label = ctk.CTkLabel(adv_area, text="Download Retries:", 
                               font=ctk.CTkFont(size=14, weight="bold"))
    retries_label.pack(anchor=tk.W, pady=(10, 2))
    
    retry_var = tk.IntVar(value=settings.get("retries", 3))
    
    retry_frame = ctk.CTkFrame(adv_area, fg_color="transparent")
    retry_frame.pack(fill=tk.X, pady=3)
    
    retry_slider = ctk.CTkSlider(retry_frame, from_=0, to=10, number_of_steps=10, variable=retry_var)
    retry_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
    
    retry_value = ctk.CTkLabel(retry_frame, text=f"Value: {retry_var.get()}")
    retry_value.pack(side=tk.RIGHT)
    
    def update_retry_label(event):
        retry_value.configure(text=f"Value: {int(retry_var.get())}")
    
    retry_slider.bind("<Motion>", update_retry_label)
    retry_slider.bind("<ButtonRelease-1>", update_retry_label)
    
    # Buttons at the bottom
    button_frame = ctk.CTkFrame(settings_window, height=40)  # Reduced height
    button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=15, pady=10)  # Reduced padding
    
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
        height=30   # Reduced height
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
        settings["embed_thumbnail"] = embed_thumbnail_var.get()  # Save thumbnail setting
        
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
        height=30   # Reduced height
    )
    save_button.pack(side=tk.RIGHT)
    
    # Set the default tab
    tab_view.set("Basic Settings")

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

# License Verification Window
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

# REDESIGNED MAIN DOWNLOADER GUI WITH COMPACT LAYOUT
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
    root.geometry("850x550")  # Reduced size for more compact layout
    root.resizable(True, True)
    
    # Variables
    download_path = tk.StringVar(value=settings.get("default_download_path", os.path.join(os.path.expanduser("~"), "Downloads")))
    quality_var = tk.StringVar(value="1080")
    thread_count_var = tk.StringVar(value=settings.get("default_threads", "4"))
    
    # Create menu bar with proper sizing
    menu_bar = tk.Menu(root, font=('Segoe UI', 10))  # Reduced font size
    root.config(menu=menu_bar)
    
    # Custom style for menus
    root.option_add('*Menu.borderWidth', 1)
    root.option_add('*Menu.activeBorderWidth', 1)
    root.option_add('*Menu.relief', 'flat')
    root.option_add('*Menu.activeBackground', '#e0e0e0')
    root.option_add('*Menu.padY', 4)  # Reduced padding
    
    # Create Files menu
    file_menu = tk.Menu(menu_bar, tearoff=0, font=('Segoe UI', 10))
    menu_bar.add_cascade(label="Files", menu=file_menu)  # Removed extra spaces
    file_menu.add_command(label="Install YT PKGs", command=install_yt_packages)
    file_menu.add_command(label="Add Bulk URLs", command=add_bulk_urls)  # New bulk URL option
    
    # Create Help menu with Check for Updates
    help_menu = tk.Menu(menu_bar, tearoff=0, font=('Segoe UI', 10))
    menu_bar.add_cascade(label="Help", menu=help_menu)  # Removed extra spaces
    help_menu.add_command(label="Check for Updates", command=check_for_updates)
    help_menu.add_separator()
    help_menu.add_command(label="YouTube Channel", command=open_youtube_channel)
    help_menu.add_command(label="Facebook Page", command=open_facebook_page)
    
    # Main frame with reduced padding
    main_frame = ctk.CTkFrame(root, fg_color="transparent")
    main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)  # Reduced padding
    
    # URL Section
    url_section = ctk.CTkFrame(main_frame, fg_color="transparent")
    url_section.pack(fill=tk.X, pady=(5, 8))  # Reduced padding
    
    # Create an empty/hidden header label for status updates only
    header_label = tk.Label(main_frame, text="", fg="white")
    header_label.pack_forget()
    
    # URL section header
    ctk.CTkLabel(url_section, text="Video URLs:", font=ctk.CTkFont(size=13)).pack(anchor=tk.W)
    
    # Button row for URL management - COMPACT LAYOUT
    button_frame = ctk.CTkFrame(url_section, fg_color="transparent")
    button_frame.pack(fill=tk.X, pady=(5, 0))
    
    # Buttons with reduced sizes
    add_button = ctk.CTkButton(button_frame, text="➕ Add Links", command=add_url, width=120, height=36, 
                              fg_color="#2ecc71", hover_color="#27ae60")
    add_button.pack(side=tk.LEFT, padx=(0, 12))  # Original padding
    
    # Bulk download button - FIXED: Changed command from start_download to start_downloads
    start_bulk_button = ctk.CTkButton(button_frame, text="▶️ Start Download", command=start_downloads, 
                                     width=140, height=32, fg_color="#2980B9", hover_color="#3498DB")
    start_bulk_button.pack(side=tk.LEFT, padx=(0, 8))  # Reduced padding
    
    # Pause button
    pause_button = ctk.CTkButton(button_frame, text="⏸️ Pause", command=pause_all_downloads, 
                               width=90, height=32, fg_color="#F39C12", hover_color="#E67E22")
    pause_button.pack(side=tk.LEFT, padx=(0, 8))  # Reduced padding
    
    # Resume button
    resume_button = ctk.CTkButton(button_frame, text="▶️ Resume", command=resume_all_downloads, 
                                width=90, height=32, fg_color="#2ecc71", hover_color="#27ae60")
    resume_button.pack(side=tk.LEFT, padx=(0, 8))  # Reduced padding
    
    # CHANGED: Renamed Reset to Restart with updated command
    restart_button = ctk.CTkButton(button_frame, text="🔄 Restart", command=restart_app, 
                               width=90, height=32, fg_color="#E74C3C", hover_color="#C0392B")
    restart_button.pack(side=tk.LEFT, padx=(0, 8))  # Reduced padding
    
    # Settings button
    settings_button = ctk.CTkButton(button_frame, text="⚙️ Settings", command=show_combined_settings, 
                                   width=90, height=32, fg_color="#2ecc71", hover_color="#27ae60")
    settings_button.pack(side=tk.LEFT)
    
    # Folder and Quality Selection Row - COMPACT LAYOUT
    options_row = ctk.CTkFrame(main_frame, fg_color="transparent")
    options_row.pack(fill=tk.X, pady=(8, 8))  # Reduced padding
    
    ctk.CTkLabel(options_row, text="Save to:", font=ctk.CTkFont(size=13)).pack(side=tk.LEFT, padx=(0, 8))
    
    # Folder entry with reduced size
    folder_entry = ctk.CTkEntry(options_row, placeholder_text="Select download location...", width=360, height=32)
    folder_entry.pack(side=tk.LEFT, padx=(0, 8))
    folder_entry.insert(0, download_path.get())
    
    # Browse button with reduced size
    browse_button = ctk.CTkButton(options_row, text="📂 Browse", command=browse_folder, 
                                 width=90, height=32, fg_color="#2ecc71", hover_color="#27ae60")
    browse_button.pack(side=tk.LEFT, padx=(0, 15))
    
    # Quality selector with reduced size
    ctk.CTkLabel(options_row, text="Quality:", font=ctk.CTkFont(size=13)).pack(side=tk.LEFT, padx=(5, 5))
    quality_menu = ctk.CTkOptionMenu(options_row, variable=quality_var, 
                                    values=["720", "1080", "1440", "2160", "Max Quality"],
                                    height=32, width=120,  # Reduced size
                                    fg_color="#2ecc71", button_color="#27ae60", button_hover_color="#219652")
    quality_menu.pack(side=tk.LEFT)
    
    # Create the table container
    table_container = ctk.CTkFrame(main_frame, fg_color="transparent")
    table_container.pack(fill=tk.BOTH, expand=True, pady=8)  # Reduced padding
    
    # Create the Treeview with black headers
    style = ttk.Style()
    
    # Configure the styles
    style.theme_use('default')
    style.configure("Treeview.Heading",
                   background="black",
                   foreground="white",
                   relief="flat",
                   font=('Segoe UI', 9, 'bold'))  # Reduced font size
    
    style.configure("Treeview", 
                   rowheight=22,  # Reduced row height
                   font=('Segoe UI', 8))  # Reduced font size   

    style.map('Treeview', 
             background=[('selected', '#2ecc71')],
             foreground=[('selected', 'black')])
    
    # Create frame for treeview and scrollbars
    tree_frame = tk.Frame(table_container, bg="black", bd=1)  # Reduced border
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
    
    # Configure tags AFTER creating the video_table
    video_table.tag_configure("completed", background="#E8F8F5")
    video_table.tag_configure("failed", background="#FADBD8")
    video_table.tag_configure("editing", background="#FEF9E7")  # Highlight for editing
    
    # Configure scrollbars
    vsb.config(command=video_table.yview)
    hsb.config(command=video_table.xview)
    
    # Add scrollbars
    vsb.pack(side=tk.RIGHT, fill=tk.Y)
    hsb.pack(side=tk.BOTTOM, fill=tk.X)
    
    # Configure column widths - more compact
    video_table.column("#", width=25, anchor=tk.CENTER)
    video_table.column("Links", width=200, anchor=tk.W)
    video_table.column("Status", width=80, anchor=tk.W)
    video_table.column("Titles", width=150, anchor=tk.W)
    video_table.column("Author", width=90, anchor=tk.W)
    video_table.column("Time", width=60, anchor=tk.CENTER)
    video_table.column("Size", width=60, anchor=tk.CENTER)
    
    # Pack the treeview
    video_table.pack(fill=tk.BOTH, expand=True)
    
    # Create black footer for the table with 3 sections
    footer_frame = tk.Frame(table_container, bg="black", height=24)  # Reduced height
    footer_frame.pack(fill=tk.X)
    
    # Create the label frames inside the black footer
    link_frame = tk.Frame(footer_frame, bg="black")
    link_frame.pack(side=tk.LEFT, fill=tk.Y)
    
    tool_frame = tk.Frame(footer_frame, bg="black")
    tool_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    author_frame = tk.Frame(footer_frame, bg="black")
    author_frame.pack(side=tk.RIGHT, fill=tk.Y)
    
    # The three labels in the footer with reduced font size
    link_count_label = tk.Label(link_frame, text="Link Count: 0", bg="black", fg="white", font=('Segoe UI', 9))
    link_count_label.pack(side=tk.LEFT, padx=8, pady=3)  # Reduced padding
    
    tool_version_label = tk.Label(tool_frame, text=f"Version {VERSION}", bg="black", fg="white", font=('Segoe UI', 9))
    tool_version_label.pack(pady=3)  # Reduced padding
    
    footer_label = tk.Label(author_frame, text="Tool by Aziz Tech", bg="black", fg="white", font=('Segoe UI', 9))
    footer_label.pack(side=tk.RIGHT, padx=8, pady=3)  # Reduced padding
    
    # Progress Status Frame - now directly after the table
    progress_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    progress_frame.pack(fill=tk.X, pady=(8, 5))  # Reduced padding
    
    # Progress Bar with reduced height
    progress_bar = ctk.CTkProgressBar(progress_frame, height=12)  # Reduced height
    progress_bar.pack(fill=tk.X, pady=(0, 5))
    progress_bar.set(0)  # Initialize at 0%
    
    # Status Label with reduced height
    status_label = ctk.CTkLabel(progress_frame, text="Waiting for download...", 
                              font=ctk.CTkFont(size=12),  # Reduced font size
                              height=25,  # Reduced height
                              fg_color=("#f0f0f0", "#2d2d2d"),
                              corner_radius=4)  # Reduced corner radius
    status_label.pack(fill=tk.X)
    
    # Initialize link count
    update_link_count()
    
    # Create a general purpose download button (reference only)
    download_button = ctk.CTkButton(main_frame, text="Download", command=start_downloads)
    download_button.pack_forget()  # Hide it, we just need the reference
    
    # Setup inline editing for the treeview
    setup_inline_editing(video_table)
    
    # Setup right-click menu for the treeview
    video_table.bind("<Button-3>", show_context_menu)
    
    # Start cloud key verification
    schedule_key_verification(license_key)
    
    # Set window icon
    try:
        # Look for icon in application directory
        if hasattr(sys, 'frozen'):  # Running as compiled exe
            app_dir = os.path.dirname(sys.executable)
        else:  # Running as script
            app_dir = os.path.dirname(os.path.abspath(__file__))
        
        # If app_dir is empty (when run from current directory), use current directory
        if not app_dir:
            app_dir = os.getcwd()
            
        # Check multiple possible icon locations
        icon_paths = [
            os.path.join(app_dir, "icon.ico"),
            os.path.join(app_dir, "icons", "icon.ico"),
            "icon.ico"  # Fallback to current directory
        ]
        
        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                root.iconbitmap(icon_path)
                break
    except Exception as e:
        print(f"Error setting window icon: {str(e)}")
    
    # Initialize header with empty message
    update_header_message("")
    
    # Center the window on the screen
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width // 2) - (425)  # Half of 850
    y = (screen_height // 2) - (275)  # Half of 550
    root.geometry(f"850x550+{x}+{y}")
    
    # Load menu icons for context menu
    load_menu_icons()
    
    root.mainloop()

# Main execution function
def main():
    # Always show license verification window first
    verify_license()

if __name__ == "__main__":
    main()
        
        
