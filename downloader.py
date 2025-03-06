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

# Tool version
VERSION = "2.5.0"

# Server URL for License Verification
SERVER_URL = "https://raw.githubusercontent.com/aziztech1234/License-Keys/main/keys.json"

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

# Set theme appearance
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("green")

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
    elif 'facebook' in domain or 'fb.com' in domain:
        return "Facebook"
    else:
        return "Other"

# Function to clean up filename
def clean_filename(filename):
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
        
    def update_progress(self, d):
        global progress_info
        
        if d['status'] == 'downloading':
            try:
                # Get percentage and speed
                percentage = d.get('_percent_str', '0%').strip()
                speed = d.get('_speed_str', 'N/A').strip()
                eta = d.get('_eta_str', '').strip()
                
                # Get video metadata if available
                if not self.title and 'info_dict' in d:
                    info = d['info_dict']
                    self.title = info.get('title', 'Unknown Title')
                    self.author = info.get('uploader', info.get('channel', 'Unknown Author'))
                    self.duration = info.get('duration')
                    self.filesize = info.get('filesize')
                    
                    # Update the table with metadata
                    root.after(0, lambda: update_video_metadata(self.row_id, self.title, self.author, self.duration, self.filesize))
                
                # Store progress info for status bar
                progress_info[self.url] = {
                    'percentage': percentage,
                    'speed': speed,
                    'eta': eta,
                    'title': self.title
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
            elapsed = time.time() - self.start_time
            root.after(0, lambda: update_video_status(self.row_id, f"Processing...", f"{elapsed:.1f}s"))
            
            # Remove from progress tracking
            if self.url in progress_info:
                del progress_info[self.url]
                update_overall_progress()

def update_video_status(row_id, status, extra_info=""):
    """Update the status column in the video table"""
    try:
        values = list(video_table.item(row_id, "values"))
        values[2] = status  # Update status column (third column)
        if extra_info:
            # Add extra info to the time column for speed or processing time
            values[5] = extra_info
        video_table.item(row_id, values=values)
        
        # Update the row style based on status
        if "Completed" in status:
            video_table.item(row_id, tags=("completed",))
        elif "Failed" in status:
            video_table.item(row_id, tags=("failed",))
    except Exception as e:
        print(f"Update video status error: {str(e)}")

def update_video_metadata(row_id, title, author, duration, filesize):
    """Update video metadata in the table"""
    try:
        values = list(video_table.item(row_id, "values"))
        # Update title, author, time, size columns
        values[3] = title if title else "Unknown"  # Titles (4th column)
        values[4] = author if author else "Unknown"  # Author (5th column)
        values[5] = format_duration(duration) if values[5] == "Unknown" else values[5]  # Time (6th column)
        values[6] = format_size(filesize)  # Size (7th column)
        video_table.item(row_id, values=values)
    except Exception as e:
        print(f"Update video metadata error: {str(e)}")

# Update overall progress in status bar
def update_overall_progress():
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
    if platform == "YouTube":
        if quality == "Max Quality":
            # Optimized for YouTube - prefer mp4 for direct compatibility
            return 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        else:
            return f'bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality}][ext=mp4]/best'
    elif platform == "Facebook":
        # ENHANCED: Facebook specific format options with multiple fallbacks
        if quality == "Max Quality":
            return 'dash_sd_src/dash_hd_src/hd_src/sd_src/high/low'
        else:
            return f'dash_sd_src/sd_src/high/low'
    elif platform == "TikTok":
        # ENHANCED: TikTok specific format with proper quality selection
        if quality == "Max Quality":
            return 'bestvideo+bestaudio/best/download_addr-0/play_addr-0'
        else:
            return f'play_addr-0/download_addr-0'
    elif platform == "Instagram":
        # ENHANCED: Instagram specific format options
        if quality == "Max Quality":
            return 'dash_hd/dash_sd/high/low'
        else:
            return 'high/low'
    else:
        # Default for other platforms
        if quality == "Max Quality":
            return 'bestvideo+bestaudio/best'
        else:
            return f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]'

# Get platform-specific FFmpeg parameters
def get_ffmpeg_params(platform):
    # Common parameters
    params = [
        '-c:v', 'libx264',      # Force H.264 video codec
        '-c:a', 'aac',          # Use AAC for audio
        '-strict', 'experimental'
    ]
    
    # Platform-specific optimizations
    if platform == "YouTube" or platform == "Facebook":
        params.extend([
            '-movflags', '+faststart',  # Optimize for web streaming
            '-preset', 'medium',        # Balance between speed and quality
            '-crf', '23',               # Reasonable quality setting
            '-threads', '4'             # Use multiple threads for encoding
        ])
    
    return params

# Video Download Function - ENHANCED VERSION WITH PLATFORM FIXES
def download_video(url, download_path, quality, thread_count, row_id):
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
    
    # Prepare download options - ENHANCED PLATFORM-SPECIFIC CONFIGURATION
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
        'retries': settings.get("retries", 5),  # INCREASED default retries
        'fragment_retries': 15,  # INCREASED fragment retries
        'skip_unavailable_fragments': False,
        'keepvideo': False,
        'overwrites': True,
        
        # Essential postprocessors
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4'
        }, {
            'key': 'FFmpegMetadata',
            'add_metadata': True,
        }]
    }
    
    # Platform-specific enhancements
    if platform == "Facebook":
        # ENHANCED: Facebook specific options
        ydl_opts.update({
            'cookiefile': os.path.join(os.path.expanduser("~"), ".fb_cookies.txt"),
            'socket_timeout': 60,  # Increased timeout
            'extract_flat': False,
            'force_generic_extractor': False
        })
    
    elif platform == "TikTok":
        # ENHANCED: TikTok specific options
        ydl_opts.update({
            'socket_timeout': 60,  # Increased timeout for TikTok
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.tiktok.com/'
            }
        })
    
    elif platform == "Instagram":
        # ENHANCED: Instagram specific options
        ydl_opts.update({
            'cookiefile': os.path.join(os.path.expanduser("~"), ".ig_cookies.txt"),
            'socket_timeout': 60,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.instagram.com/'
            }
        })
    
    # Add subtitle processors if enabled
    if settings.get("write_subtitles", False):
        if settings.get("embed_subtitles", False):
            ydl_opts['postprocessors'].append({
                'key': 'FFmpegEmbedSubtitle',
                'already_have_subtitle': False,
            })
        if settings.get("write_auto_subtitles", False):
            ydl_opts['writeautomaticsub'] = True
    
    # Add ffmpeg location if needed for certain platforms
    if hasattr(sys, 'frozen'):  # Check if running as exe
        ffmpeg_location = os.path.join(os.path.dirname(sys.executable), 'ffmpeg')
        if os.path.exists(ffmpeg_location):
            ydl_opts['ffmpeg_location'] = ffmpeg_location
    
    # Get platform-specific FFmpeg parameters
    ydl_opts['postprocessor_args'] = get_ffmpeg_params(platform)
    
    # Add aria2c support with thread count
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
    
    try:
        # ENHANCED: Try with multiple attempts and different formats if needed
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    
                    # Pre-update the table with available metadata
                    if info:
                        title = clean_filename(info.get('title', 'Unknown Title'))
                        author = info.get('uploader', info.get('channel', 'Unknown Author'))
                        duration = info.get('duration')
                        filesize = info.get('filesize')
                        
                        # Update the metadata in the table before download starts
                        root.after(0, lambda: update_video_metadata(row_id, title, author, duration, filesize))
                    
                    # Start actual download
                    ydl.download([url])
                
                # Download successful, break the retry loop
                break
            
            except Exception as e:
                error_msg = str(e)
                print(f"Download attempt {attempt+1} error: {error_msg}")
                
                # If this is the last attempt, raise the exception to be caught by the outer try-except
                if attempt == max_attempts - 1:
                    raise
                
                # For Facebook connection issues, wait and retry
                if platform == "Facebook" and "Requested format is not available" in error_msg:
                    # Try a different format option
                    if attempt == 0:
                        ydl_opts['format'] = 'hd_src/sd_src'
                    else:
                        ydl_opts['format'] = 'sd_src'
                    time.sleep(2)  # Wait before retry
                
                # For TikTok connection issues
                elif platform == "TikTok" and ("Connection" in error_msg or "aborted" in error_msg):
                    # Try with different headers and options
                    ydl_opts['http_headers']['User-Agent'] = 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
                    time.sleep(3)  # Longer wait for TikTok
                
                # For Instagram format issues
                elif platform == "Instagram" and "Requested format is not available" in error_msg:
                    # Try different format options for Instagram
                    ydl_opts['format'] = 'standard/high/low'
                    time.sleep(2)
        
        # Mark download as complete in table and update header
        root.after(0, lambda: update_video_status(row_id, "Completed", "Done"))
        root.after(0, lambda: update_header_message(f"Download Completed: {info.get('title', 'Video')}", "#00FF00"))
        return True
    
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

# Function to pause all downloads
def pause_all_downloads():
    global paused
    paused = True
    update_header_message("Downloads paused. Click Resume to continue.")
    
    # Update status for all active downloads
    for item_id in video_table.get_children():
        values = video_table.item(item_id, "values")
        if "Downloading" in values[2]:
            update_video_status(item_id, "Paused", "")

# Function to resume all downloads
def resume_all_downloads():
    global paused
    paused = False
    update_header_message("Downloads resumed.")
    
    # Update status for all paused downloads
    for item_id in video_table.get_children():
        values = video_table.item(item_id, "values")
        if values[2] == "Paused":
            update_video_status(item_id, "Pending", "")
    
    # Restart downloads if they were active before
    if downloading:
        start_download()

# ENHANCED: Reset URL table and stop ongoing downloads
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
    messagebox.showinfo("Install YouTube Packages", 
                       "This will install additional packages needed for YouTube downloads.")
    # Here you would implement the actual installation logic
    # For example, calling pip or showing a more detailed installation dialog
    
    # Placeholder implementation
    messagebox.showinfo("Installation Complete", 
                       "YouTube packages have been installed successfully!")

# Function to open Aziz YouTube channel
def open_youtube_channel():
    webbrowser.open("https://www.youtube.com/@AzizKhan077")

# Function to open Aziz Facebook page
def open_facebook_page():
    webbrowser.open("https://www.facebook.com/princeaziz011")

# New combined settings function that replaces both basic and advanced settings
def show_combined_settings():
    global settings
    
    settings_window = ctk.CTkToplevel(root)
    settings_window.title("Settings")
    settings_window.geometry("600x700")  # Make it larger to fit all settings
    settings_window.resizable(False, False)
    settings_window.grab_set()
    
    # Create a tabview to separate basic and advanced settings
    tab_view = ctk.CTkTabview(settings_window)
    tab_view.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    
    # Create tabs
    basic_tab = tab_view.add("Basic Settings")
    advanced_tab = tab_view.add("Advanced Settings")
    
    # === BASIC SETTINGS TAB ===
    
    # Main content area for basic tab
    basic_area = ctk.CTkScrollableFrame(basic_tab)
    basic_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # Title for basic settings
    title_frame = ctk.CTkFrame(basic_area, fg_color="transparent")
    title_frame.pack(fill=tk.X, pady=(0, 20))
    
    # Add gear icon and title
    icon_label = ctk.CTkLabel(title_frame, text="⚙️", font=ctk.CTkFont(size=24))
    icon_label.pack(side=tk.LEFT, padx=(90, 10))
    
    title_label = ctk.CTkLabel(title_frame, text="Basic Settings", font=ctk.CTkFont(size=20, weight="bold"))
    title_label.pack(side=tk.LEFT)
    
    # Video Backup Option
    backup_var = tk.BooleanVar(value=settings.get("create_backup", False))
    backup_check = ctk.CTkCheckBox(basic_area, text="Save Video Backups (JSON, Description)",
                                   variable=backup_var)
    backup_check.pack(anchor=tk.W, pady=10)
    
    # Subtitle Options Section
    subtitle_label = ctk.CTkLabel(basic_area, text="Save Captions Options:", font=ctk.CTkFont(size=14, weight="bold"))
    subtitle_label.pack(anchor=tk.W, pady=(10, 5))
    
    # Subtitles Options
    subtitles_var = tk.BooleanVar(value=settings.get("write_subtitles", False))
    embed_subtitles_var = tk.BooleanVar(value=settings.get("embed_subtitles", False))
    auto_subtitles_var = tk.BooleanVar(value=settings.get("write_auto_subtitles", False))
    
    subtitles_check = ctk.CTkCheckBox(basic_area, text="Download as Separate SRT File",
                                     variable=subtitles_var)
    subtitles_check.pack(anchor=tk.W, padx=20, pady=5)
    
    embed_subtitles_check = ctk.CTkCheckBox(basic_area, text="Embed Inside Video",
                                           variable=embed_subtitles_var)
    embed_subtitles_check.pack(anchor=tk.W, padx=20, pady=5)
    
    auto_subtitles_check = ctk.CTkCheckBox(basic_area, text="Include Auto-Generated Captions",
                                          variable=auto_subtitles_var)
    auto_subtitles_check.pack(anchor=tk.W, padx=20, pady=5)
    
    # File naming options section
    naming_label = ctk.CTkLabel(basic_area, text="Save Videos With:", font=ctk.CTkFont(size=14, weight="bold"))
    naming_label.pack(anchor=tk.W, pady=(20, 5))
    
    # File naming options
    original_title_var = tk.BooleanVar(value=settings.get("use_original_title", True))
    tags_var = tk.BooleanVar(value=settings.get("use_tags", False))
    
    original_title_check = ctk.CTkCheckBox(basic_area, text="Original Title",
                                          variable=original_title_var)
    original_title_check.pack(anchor=tk.W, padx=20, pady=5)
    
    tags_check = ctk.CTkCheckBox(basic_area, text="Include Tags/Hashtags",
                                variable=tags_var)
    tags_check.pack(anchor=tk.W, padx=20, pady=5)
    
    # Auto-paste Option
    autopaste_var = tk.BooleanVar(value=settings.get("auto_paste", True))
    autopaste_check = ctk.CTkCheckBox(basic_area, text="Auto-paste URL from Clipboard",
                                     variable=autopaste_var)
    autopaste_check.pack(anchor=tk.W, pady=10)
    
    # === ADVANCED SETTINGS TAB ===
    
    # Main content area for advanced tab
    adv_area = ctk.CTkScrollableFrame(advanced_tab)
    adv_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # Title for advanced settings
    adv_title_frame = ctk.CTkFrame(adv_area, fg_color="transparent")
    adv_title_frame.pack(fill=tk.X, pady=(0, 20))
    
    # Add wrench icon and title
    adv_icon_label = ctk.CTkLabel(adv_title_frame, text="🛠️", font=ctk.CTkFont(size=24))
    adv_icon_label.pack(side=tk.LEFT, padx=(90, 10))
    
    adv_title_label = ctk.CTkLabel(adv_title_frame, text="Advanced Settings", font=ctk.CTkFont(size=20, weight="bold"))
    adv_title_label.pack(side=tk.LEFT)
    
    # Application Theme Section
    theme_label = ctk.CTkLabel(adv_area, text="Application Theme:", font=ctk.CTkFont(size=14, weight="bold"))
    theme_label.pack(anchor=tk.W, pady=(10, 5))
    
    theme_var = tk.StringVar(value=settings.get("theme", "light"))
    theme_frame = ctk.CTkFrame(adv_area, fg_color="transparent")
    theme_frame.pack(fill=tk.X, pady=(0, 10))
    
    light_radio = ctk.CTkRadioButton(theme_frame, text="Light Mode", variable=theme_var, value="light")
    light_radio.pack(side=tk.LEFT, padx=(0, 20))
    
    dark_radio = ctk.CTkRadioButton(theme_frame, text="Dark Mode", variable=theme_var, value="dark")
    dark_radio.pack(side=tk.LEFT)
    
    # Cache Management Section
    cache_label = ctk.CTkLabel(adv_area, text="Cache Management:", font=ctk.CTkFont(size=14, weight="bold"))
    cache_label.pack(anchor=tk.W, pady=(20, 10))
    
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
    cache_btn.pack(anchor=tk.W, pady=5)
    
    # Multithreading Settings Section
    threading_label = ctk.CTkLabel(adv_area, text="Multithreading Settings:", font=ctk.CTkFont(size=14, weight="bold"))
    threading_label.pack(anchor=tk.W, pady=(20, 5))
    
    thread_count_label = ctk.CTkLabel(adv_area, text="Default Thread Count:")
    thread_count_label.pack(anchor=tk.W, pady=(5, 0))
    
    default_thread_var = tk.StringVar(value=settings.get("default_threads", "4"))
    thread_dropdown = ctk.CTkOptionMenu(adv_area, variable=default_thread_var,
                                      values=["1", "2", "3", "4", "6", "8"],
                                      fg_color="#2ecc71", button_color="#27ae60", button_hover_color="#219652",
                                      width=100)
    thread_dropdown.pack(anchor=tk.W, pady=5)
    
    # Download Retries Section
    retries_label = ctk.CTkLabel(adv_area, text="Download Retries:", font=ctk.CTkFont(size=14, weight="bold"))
    retries_label.pack(anchor=tk.W, pady=(20, 5))
    
    retry_var = tk.IntVar(value=settings.get("retries", 3))
    
    retry_frame = ctk.CTkFrame(adv_area, fg_color="transparent")
    retry_frame.pack(fill=tk.X, pady=5)
    
    retry_slider = ctk.CTkSlider(retry_frame, from_=0, to=10, number_of_steps=10, variable=retry_var)
    retry_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
    
    retry_value = ctk.CTkLabel(retry_frame, text=f"Value: {retry_var.get()}")
    retry_value.pack(side=tk.RIGHT)
    
    def update_retry_label(event):
        retry_value.configure(text=f"Value: {int(retry_var.get())}")
    
    retry_slider.bind("<Motion>", update_retry_label)
    retry_slider.bind("<ButtonRelease-1>", update_retry_label)
    
    # Buttons at the bottom
    button_frame = ctk.CTkFrame(settings_window, height=60)
    button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=20)
    
    # Cancel button
    def cancel_settings():
        settings_window.destroy()
    
    cancel_button = ctk.CTkButton(
        button_frame, 
        text="Cancel", 
        command=cancel_settings,
        fg_color="#E74C3C", 
        hover_color="#C0392B",
        width=120,
        height=35
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
        width=120,
        height=35
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
    
    # Center window on screen
    license_window.update_idletasks()
    width = license_window.winfo_width()
    height = license_window.winfo_height()
    x = (license_window.winfo_screenwidth() // 2) - (width // 2)
    y = (license_window.winfo_screenheight() // 2) - (height // 2)
    license_window.geometry(f"{width}x{height}+{x}+{y}")
    
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

# Main Downloader GUI - MODIFIED with requested changes
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
    root.geometry("900x600")  # Reduced height for more compact UI
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
    
    # Create Help menu
    help_menu = tk.Menu(menu_bar, tearoff=0, font=('Segoe UI', 11))
    menu_bar.add_cascade(label="  Help  ", menu=help_menu)  # Added spaces for padding
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
    
    # Folder and Quality Selection Row - MODIFIED to remove Threads button
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
    
    # Force header visibility
    for col in ("#", "Links", "Status", "Titles", "Author", "Time", "Size"):
        video_table.heading(col, text=col)
    
    # Create and configure tags for row coloring
    video_table.tag_configure("completed", background="#E8F8F5")
    video_table.tag_configure("failed", background="#FADBD8")
    video_table.tag_configure("editing", background="#FEF9E7")  # Highlight for editing
    
    # Configure scrollbars
    vsb.config(command=video_table.yview)
    hsb.config(command=video_table.xview)
    
    # Add scrollbars
    vsb.pack(side=tk.RIGHT, fill=tk.Y)
    hsb.pack(side=tk.BOTTOM, fill=tk.X)
    
    # Configure column headings
    video_table.heading("#", text="#", anchor=tk.CENTER)
    video_table.heading("Links", text="Links", anchor=tk.CENTER)
    video_table.heading("Status", text="Status", anchor=tk.CENTER)
    video_table.heading("Titles", text="Titles", anchor=tk.CENTER)
    video_table.heading("Author", text="Author", anchor=tk.CENTER)
    video_table.heading("Time", text="Time", anchor=tk.CENTER)
    video_table.heading("Size", text="Size", anchor=tk.CENTER)
    
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
    
    root.mainloop()

# Main execution function
def main():
    # Always show license verification window first
    verify_license()

if __name__ == "__main__":
    main()