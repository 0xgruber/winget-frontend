#!/usr/bin/env python3
"""
Build script for compiling winget-frontend to a portable Windows executable.
Uses PyInstaller to bundle everything into a single exe.
"""

import subprocess
import sys
from pathlib import Path


def main():
    # Ensure we're in the project directory
    project_dir = Path(__file__).parent
    
    # Output directory
    dist_dir = project_dir / "dist"
    dist_dir.mkdir(exist_ok=True)
    
    # PyInstaller command
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        
        # Single file output
        "--onefile",
        
        # Console mode (required for TUI)
        "--console",
        
        # Output configuration
        f"--distpath={dist_dir}",
        "--name=winget-frontend",
        
        # Clean build
        "--clean",
        
        # Include the winget_client module
        "--hidden-import=winget_client",
        
        # Include textual and its dependencies
        "--hidden-import=textual",
        "--hidden-import=textual.app",
        "--hidden-import=textual.widgets",
        "--hidden-import=textual.containers",
        "--hidden-import=textual.binding",
        "--hidden-import=rich",
        "--collect-all=textual",
        
        # Add additional data files (winget_client.py)
        f"--add-data={project_dir / 'winget_client.py'};.",
        
        # Main entry point
        "main.py",
    ]
    
    print("=" * 60)
    print("Building winget-frontend with PyInstaller")
    print("=" * 60)
    print(f"Command: {' '.join(cmd)}")
    print()
    
    # Run PyInstaller
    result = subprocess.run(cmd, cwd=project_dir)
    
    if result.returncode == 0:
        exe_path = dist_dir / "winget-frontend.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print()
            print("=" * 60)
            print(f"Build successful!")
            print(f"Output: {exe_path}")
            print(f"Size: {size_mb:.1f} MB")
            print("=" * 60)
        else:
            print("Build completed but exe not found at expected location.")
            print(f"Check {dist_dir} for output files.")
    else:
        print()
        print("=" * 60)
        print(f"Build failed with return code: {result.returncode}")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
