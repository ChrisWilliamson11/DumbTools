"""
Standalone Batch Render GUI for Blender
Allows selecting multiple .blend files and rendering them via command-line
"""

import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
import subprocess
import threading
import os
import json
from pathlib import Path

class BatchRenderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Batch Render Animation")
        self.root.geometry("800x600")
        
        # Load settings
        self.settings_file = Path(__file__).parent / "batch_render_settings.json"
        self.settings = self.load_settings()
        
        # Blender path
        path_frame = tk.Frame(root, padx=10, pady=10)
        path_frame.pack(fill=tk.X)
        
        tk.Label(path_frame, text="Blender Executable:").pack(side=tk.LEFT)
        self.blender_path = tk.StringVar(value=self.settings.get("blender_path", ""))
        tk.Entry(path_frame, textvariable=self.blender_path, width=50).pack(side=tk.LEFT, padx=5)
        tk.Button(path_frame, text="Browse", command=self.browse_blender).pack(side=tk.LEFT)
        
        # File list
        list_frame = tk.Frame(root, padx=10, pady=10)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(list_frame, text="Blend Files to Render:").pack(anchor=tk.W)
        
        # Listbox with scrollbar
        listbox_frame = tk.Frame(list_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.file_listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set, selectmode=tk.EXTENDED)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.file_listbox.yview)
        
        # Buttons for file list
        button_frame = tk.Frame(list_frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        tk.Button(button_frame, text="Add Files", command=self.add_files).pack(side=tk.LEFT, padx=2)
        tk.Button(button_frame, text="Add Folder", command=self.add_folder).pack(side=tk.LEFT, padx=2)
        tk.Button(button_frame, text="Remove Selected", command=self.remove_selected).pack(side=tk.LEFT, padx=2)
        tk.Button(button_frame, text="Clear All", command=self.clear_all).pack(side=tk.LEFT, padx=2)
        
        # Console output
        console_frame = tk.Frame(root, padx=10, pady=10)
        console_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(console_frame, text="Console Output:").pack(anchor=tk.W)
        self.console = scrolledtext.ScrolledText(console_frame, height=10, state=tk.DISABLED)
        self.console.pack(fill=tk.BOTH, expand=True)
        
        # Render button
        render_frame = tk.Frame(root, padx=10, pady=10)
        render_frame.pack(fill=tk.X)
        
        self.render_button = tk.Button(render_frame, text="Start Batch Render", 
                                       command=self.start_render, bg="green", fg="white", 
                                       font=("Arial", 12, "bold"))
        self.render_button.pack(fill=tk.X)
        
        # Progress
        self.progress_label = tk.Label(render_frame, text="")
        self.progress_label.pack()
        
        self.rendering = False
        self.blend_files = []
    
    def load_settings(self):
        """Load settings from JSON file"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def save_settings(self):
        """Save settings to JSON file"""
        self.settings["blender_path"] = self.blender_path.get()
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except:
            pass
    
    def browse_blender(self):
        """Browse for Blender executable"""
        filename = filedialog.askopenfilename(
            title="Select Blender Executable",
            filetypes=[("Executable", "*.exe"), ("All Files", "*.*")]
        )
        if filename:
            self.blender_path.set(filename)
            self.save_settings()
    
    def add_files(self):
        """Add blend files to the list"""
        filenames = filedialog.askopenfilenames(
            title="Select Blend Files",
            filetypes=[("Blender Files", "*.blend"), ("All Files", "*.*")]
        )
        for filename in filenames:
            if filename not in self.blend_files:
                self.blend_files.append(filename)
                self.file_listbox.insert(tk.END, filename)
    
    def add_folder(self):
        """Add all blend files from a folder"""
        folder = filedialog.askdirectory(title="Select Folder Containing Blend Files")
        if folder:
            for file in Path(folder).glob("*.blend"):
                filepath = str(file)
                if filepath not in self.blend_files:
                    self.blend_files.append(filepath)
                    self.file_listbox.insert(tk.END, filepath)
    
    def remove_selected(self):
        """Remove selected files from the list"""
        selected = self.file_listbox.curselection()
        for index in reversed(selected):
            self.file_listbox.delete(index)
            del self.blend_files[index]
    
    def clear_all(self):
        """Clear all files from the list"""
        self.file_listbox.delete(0, tk.END)
        self.blend_files.clear()
    
    def log(self, message):
        """Add message to console"""
        self.console.config(state=tk.NORMAL)
        self.console.insert(tk.END, message + "\n")
        self.console.see(tk.END)
        self.console.config(state=tk.DISABLED)
        self.root.update()
    
    def start_render(self):
        """Start the batch render process"""
        if self.rendering:
            messagebox.showwarning("Already Rendering", "A render is already in progress!")
            return
        
        blender_exe = self.blender_path.get()
        if not blender_exe or not os.path.exists(blender_exe):
            messagebox.showerror("Error", "Please select a valid Blender executable!")
            return
        
        if not self.blend_files:
            messagebox.showerror("Error", "Please add at least one blend file!")
            return
        
        # Save settings
        self.save_settings()
        
        # Start rendering in a separate thread
        self.rendering = True
        self.render_button.config(state=tk.DISABLED, text="Rendering...")
        thread = threading.Thread(target=self.render_files, args=(blender_exe,))
        thread.daemon = True
        thread.start()
    
    def render_files(self, blender_exe):
        """Render all files in the list"""
        total = len(self.blend_files)
        success = 0
        failed = 0
        
        self.log(f"\n{'='*60}")
        self.log(f"Starting batch render for {total} file(s)")
        self.log(f"{'='*60}\n")
        
        for idx, filepath in enumerate(self.blend_files, 1):
            self.progress_label.config(text=f"Rendering {idx}/{total}: {os.path.basename(filepath)}")
            
            if not os.path.exists(filepath):
                self.log(f"[{idx}/{total}] ✗ File not found: {filepath}")
                failed += 1
                continue
            
            self.log(f"[{idx}/{total}] Processing: {os.path.basename(filepath)}")
            self.log(f"  → Starting render...")
            
            # Build command
            cmd = [
                blender_exe,
                "--background",
                filepath,
                "--render-anim"
            ]
            
            try:
                # Run the command and capture output in real-time
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                # Read output line by line
                for line in process.stdout:
                    line = line.strip()
                    if line:
                        # Filter to show only important lines
                        if any(keyword in line for keyword in ["Fra:", "Saved:", "Error", "Warning", "Time:"]):
                            self.log(f"    {line}")
                
                process.wait()
                
                if process.returncode == 0:
                    self.log(f"  ✓ Render complete\n")
                    success += 1
                else:
                    self.log(f"  ✗ Render failed with return code {process.returncode}\n")
                    failed += 1
                    
            except Exception as e:
                self.log(f"  ✗ Error: {str(e)}\n")
                failed += 1
        
        self.log(f"\n{'='*60}")
        self.log(f"Batch render complete!")
        self.log(f"Success: {success}, Failed: {failed}")
        self.log(f"{'='*60}\n")
        
        self.rendering = False
        self.render_button.config(state=tk.NORMAL, text="Start Batch Render")
        self.progress_label.config(text=f"Complete! {success}/{total} rendered successfully")
        
        messagebox.showinfo("Render Complete", 
                          f"Batch render finished!\n\nSuccess: {success}\nFailed: {failed}")



root = tk.Tk()
app = BatchRenderGUI(root)
root.mainloop()

