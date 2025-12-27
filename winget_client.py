"""
WingetClient - A helper class to interact with Windows Package Manager (winget) CLI.
Handles subprocess calls and parses winget output into structured data.
"""

import subprocess
import re
from typing import List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class Package:
    """Represents a winget package."""
    name: str
    id: str
    version: str
    source: str = ""
    available_version: str = ""


class WingetClient:
    """Client for interacting with winget CLI commands."""
    
    def __init__(self):
        self.winget_exe = "winget"
    
    def _run_command(self, args: List[str], timeout: int = 60) -> Tuple[str, int]:
        """
        Run a winget command and return stdout and return code.
        
        Args:
            args: List of command arguments
            timeout: Command timeout in seconds
            
        Returns:
            Tuple of (stdout, return_code)
        """
        try:
            result = subprocess.run(
                [self.winget_exe] + args,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='replace'
            )
            # If returncode is non-zero and stderr has content, include it
            if result.returncode != 0 and result.stderr:
                return f"{result.stdout}\nSTDERR: {result.stderr}", result.returncode
            return result.stdout, result.returncode
        except subprocess.TimeoutExpired:
            return "Command timed out", 1
        except FileNotFoundError:
            return "winget command not found. Is Windows Package Manager installed?", 1
        except PermissionError:
            return "Permission denied. Administrator privileges may be required.", 1
        except Exception as e:
            return f"Error: {str(e)}", 1
    
    def _parse_list_output(self, output: str) -> List[Package]:
        """
        Parse the output of 'winget list' into a list of Package objects.
        """
        packages = []
        lines = output.strip().split('\n')
        
        # Find the separator line (starts with dashes)
        separator_idx = -1
        for idx, line in enumerate(lines):
            if line.strip().startswith('---'):
                separator_idx = idx
                break
        
        if separator_idx == -1:
            return packages
        
        # Skip everything up to and including the separator line
        data_lines = lines[separator_idx + 1:]
        
        # Pattern to match: Name (variable spaces) Id (variable spaces) Version (variable spaces) Available? (variable spaces) Source?
        pattern = r'^(.+?)\s{2,}(.+?)\s{2,}(.+?)(?:\s{2,}(.+?))?(?:\s{2,}(.+?))?$'
        
        for line in data_lines:
            line = line.strip()
            if not line:
                continue
            
            # Skip lines that look like progress indicators or non-data lines
            if len(line) < 10 or line.startswith('-') or line.startswith('\\') or line.startswith('|') or line.startswith('/'):
                continue
            
            match = re.match(pattern, line)
            
            if match:
                name = match.group(1).strip()
                package_id = match.group(2).strip()
                version = match.group(3).strip()
                
                group4 = match.group(4).strip() if match.group(4) else ""
                group5 = match.group(5).strip() if match.group(5) else ""
                
                if group5:
                    source = group5
                    available_version = group4
                elif group4 and ("winget" in group4.lower() or "msstore" in group4.lower() or len(group4) < 20):
                    source = group4
                    available_version = ""
                else:
                    source = "winget"
                    available_version = group4
                
                packages.append(Package(
                    name=name,
                    id=package_id,
                    version=version,
                    source=source,
                    available_version=available_version
                ))
        
        return packages
    
    def list_installed(self) -> Tuple[List[Package], Optional[str]]:
        """
        Fetch list of installed packages.
        
        Returns:
            Tuple of (list of Package objects, error message if any)
        """
        stdout, return_code = self._run_command(["list"])
        
        if return_code != 0:
            error_msg = stdout if "Error" in stdout or "Permission" in stdout else f"Command failed with return code {return_code}"
            return [], error_msg
        
        packages = self._parse_list_output(stdout)
        return packages, None
    
    def _parse_search_output(self, output: str) -> List[Package]:
        """
        Parse the output of 'winget search' into a list of Package objects.
        """
        packages = []
        lines = output.strip().split('\n')
        
        # Find the separator line (starts with dashes)
        separator_idx = -1
        for idx, line in enumerate(lines):
            if line.strip().startswith('---'):
                separator_idx = idx
                break
        
        if separator_idx == -1:
            return packages
        
        # Skip everything up to and including the separator line
        data_lines = lines[separator_idx + 1:]
        
        pattern = r'^(.+?)\s{2,}(.+?)\s{2,}(.+?)(?:\s{2,}(.+?))?(?:\s{2,}(.+?))?$'
        
        for line in data_lines:
            line = line.strip()
            if not line:
                continue
            
            if len(line) < 10 or line.startswith('-') or line.startswith('\\') or line.startswith('|') or line.startswith('/'):
                continue
            
            match = re.match(pattern, line)
            
            if match:
                name = match.group(1).strip()
                package_id = match.group(2).strip()
                version = match.group(3).strip()
                
                group4 = match.group(4).strip() if match.group(4) else ""
                group5 = match.group(5).strip() if match.group(5) else ""
                
                if group5:
                    source = group5
                    available_version = group4 if group4 and group4 not in ["Command:", "Tag:", "Tag"] else ""
                elif group4 and ("winget" in group4.lower() or "msstore" in group4.lower() or len(group4) < 20):
                    source = group4
                    available_version = ""
                else:
                    source = "winget"
                    available_version = group4
                
                packages.append(Package(
                    name=name,
                    id=package_id,
                    version=version,
                    source=source,
                    available_version=available_version
                ))
        
        return packages
    
    def search(self, query: str) -> Tuple[List[Package], Optional[str]]:
        """
        Search for packages.
        
        Args:
            query: Search query string
            
        Returns:
            Tuple of (list of Package objects, error message if any)
        """
        stdout, return_code = self._run_command(["search", query])
        
        if return_code != 0:
            error_msg = stdout if "Error" in stdout or "Permission" in stdout else f"Command failed with return code {return_code}"
            return [], error_msg
        
        packages = self._parse_search_output(stdout)
        return packages, None
    
    def _parse_upgrade_output(self, output: str) -> List[Package]:
        """
        Parse the output of 'winget upgrade' (with no arguments) into a list of Package objects.
        """
        packages = []
        lines = output.strip().split('\n')
        
        # Find the separator line (starts with dashes)
        separator_idx = -1
        for idx, line in enumerate(lines):
            if line.strip().startswith('---'):
                separator_idx = idx
                break
        
        if separator_idx == -1:
            return packages
        
        # Skip everything up to and including the separator line
        data_lines = lines[separator_idx + 1:]
        
        # Pattern: Name Id Version Available Source
        pattern = r'^(.+?)\s{2,}(.+?)\s{2,}(.+?)\s{2,}(.+?)\s{2,}(.+?)$'
        
        for line in data_lines:
            line = line.strip()
            if not line:
                continue
            
            if len(line) < 10 or line.startswith('-') or line.startswith('\\') or line.startswith('|') or line.startswith('/'):
                continue
            
            match = re.match(pattern, line)
            
            if match:
                name = match.group(1).strip()
                package_id = match.group(2).strip()
                current_version = match.group(3).strip()
                available_version = match.group(4).strip()
                source = match.group(5).strip()
                
                packages.append(Package(
                    name=name,
                    id=package_id,
                    version=current_version,
                    source=source,
                    available_version=available_version
                ))
        
        return packages
    
    def check_for_updates(self) -> Tuple[List[Package], Optional[str]]:
        """
        Check for available package updates.
        
        Returns:
            Tuple of (list of Package objects with updates available, error message if any)
        """
        stdout, return_code = self._run_command(["upgrade"])
        
        if return_code != 0:
            error_msg = stdout if "Error" in stdout or "Permission" in stdout else f"Command failed with return code {return_code}"
            return [], error_msg
        
        packages = self._parse_upgrade_output(stdout)
        return packages, None
    
    def install(self, package_id: str, user_context: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Install a package.
        
        Args:
            package_id: The package ID to install
            user_context: If True, install for current user only. If False, install system-wide (requires admin).
            
        Returns:
            Tuple of (success, error message if any)
        """
        cmd = ["install", "--id", package_id, "--accept-package-agreements", "--accept-source-agreements", "--silent"]
        if user_context:
            cmd.extend(["--scope", "user"])
        else:
            cmd.extend(["--scope", "machine"])
        
        stdout, return_code = self._run_command(cmd)
        
        if return_code != 0:
            error_msg = stdout if "Error" in stdout or "Permission" in stdout else f"Installation failed with return code {return_code}"
            return False, error_msg
        
        return True, None
    
    def uninstall(self, package_id: str) -> Tuple[bool, Optional[str]]:
        """
        Uninstall a package.
        
        Args:
            package_id: The package ID to uninstall
            
        Returns:
            Tuple of (success, error message if any)
        """
        stdout, return_code = self._run_command(["uninstall", "--id", package_id, "--silent"])
        
        if return_code != 0:
            error_msg = stdout if "Error" in stdout or "Permission" in stdout else f"Uninstallation failed with return code {return_code}"
            return False, error_msg
        
        return True, None
    
    def upgrade(self, package_id: str) -> Tuple[bool, Optional[str]]:
        """
        Upgrade a package.
        
        Args:
            package_id: The package ID to upgrade
            
        Returns:
            Tuple of (success, error message if any)
        """
        stdout, return_code = self._run_command(["upgrade", "--id", package_id, "--accept-package-agreements", "--accept-source-agreements", "--silent"])
        
        if return_code != 0:
            error_msg = stdout if "Error" in stdout or "Permission" in stdout else f"Upgrade failed with return code {return_code}"
            return False, error_msg
        
        return True, None
