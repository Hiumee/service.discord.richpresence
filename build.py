#!/usr/bin/env python3
"""
Build script for Discord Rich Presence addon.
Creates a zip file with the addon packaged in a 'service.discord.richpresence' folder.
"""

import os
import zipfile
from pathlib import Path

def build_addon():
    """Create a zip file with the addon structure."""
    
    # Get the script directory
    script_dir = Path(__file__).parent
    
    # Define the addon folder name and output zip
    addon_name = "service.discord.richpresence"
    zip_filename = script_dir / f"{addon_name}.zip"
    
    # Files and folders to include
    files_to_include = [
        "License.txt",
        "addon.xml",
        "default.py",
        "icon.png",
        "README.md"
    ]
    
    folders_to_include = [
        "lib",
        "resources"
    ]
    
    print(f"Building {addon_name}.zip...")
    
    try:
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            
            # Add the root addon directory entry
            root_entry = zipfile.ZipInfo(f"{addon_name}/")
            zipf.writestr(root_entry, '')
            
            # Add individual files
            for file in files_to_include:
                file_path = script_dir / file
                if file_path.exists():
                    arcname = f"{addon_name}/{file}"
                    zipf.write(file_path, arcname)
                    print(f"  Added: {arcname}")
                elif file in ["License.txt", "addon.xml", "default.py"]:
                    print(f"  WARNING: Required file not found: {file}")
            
            # Add folders recursively with directory entries
            for folder in folders_to_include:
                folder_path = script_dir / folder
                if folder_path.exists():
                    # Add directory entry for the folder
                    arcname = f"{addon_name}/{folder}/"
                    dir_entry = zipfile.ZipInfo(arcname)
                    zipf.writestr(dir_entry, '')
                    
                    for root, dirs, files in os.walk(folder_path):
                        # Add directory entries for subdirectories
                        for dir_name in dirs:
                            dir_path = Path(root) / dir_name
                            rel_path = dir_path.relative_to(script_dir)
                            dir_arcname = f"{addon_name}/{rel_path}/".replace("\\", "/")
                            dir_entry = zipfile.ZipInfo(dir_arcname)
                            zipf.writestr(dir_entry, '')
                        
                        # Add files
                        for file in files:
                            file_path = Path(root) / file
                            rel_path = file_path.relative_to(script_dir)
                            arcname = f"{addon_name}/{rel_path}".replace("\\", "/")
                            zipf.write(file_path, arcname)
                            print(f"  Added: {arcname}")
                else:
                    print(f"  WARNING: Folder not found: {folder}")
        
        print(f"\nSuccessfully created: {zip_filename}")
        print(f"File size: {zip_filename.stat().st_size / 1024:.2f} KB")
        
    except Exception as e:
        print(f"Error creating zip file: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = build_addon()
    exit(0 if success else 1)
