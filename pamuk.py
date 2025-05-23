#!/usr/bin/env python3

import yaml
import subprocess
import sys
import os
import time
from shutil import which

def check_adb():
    """Check if ADB is available in PATH."""
    if which('adb') is None:
        print("Error: ADB is not found in PATH")
        sys.exit(1)
    return True

def load_catalogue(filename='catalogue.yaml'):
    """Load package names from catalogue file."""
    try:
        with open(filename, 'r') as file:
            data = yaml.safe_load(file)
            return data.get('catalogue', {})
    except Exception as e:
        print(f"Error loading catalogue: {e}")
        sys.exit(1)

def wait_for_device():
    """Wait for an Android device to be connected."""
    print("Waiting for Android device...")
    try:
        subprocess.run(['adb', 'wait-for-device'], check=True)
        # Get device info
        result = subprocess.run(['adb', 'devices'], capture_output=True, text=True, check=True)
        devices = [line.split()[0] for line in result.stdout.splitlines()[1:] if line.strip()]
        
        if not devices:
            print("No devices found after connection")
            sys.exit(1)
            
        return devices[0]  # Return the first connected device
    except subprocess.CalledProcessError as e:
        print(f"Error connecting to device: {e}")
        sys.exit(1)

def get_installed_packages(device):
    """Get list of installed packages on the device."""
    try:
        result = subprocess.run(
            ['adb', '-s', device, 'shell', 'pm', 'list', 'packages'],
            capture_output=True,
            text=True,
            check=True
        )
        return [line.split(':')[1].strip() for line in result.stdout.splitlines()]
    except subprocess.CalledProcessError as e:
        print(f"Error getting installed packages: {e}")
        sys.exit(1)

def uninstall_package(device, package):
    """Uninstall a package from the device."""
    try:
        subprocess.run(['adb', '-s', device, 'shell', 'pm', 'uninstall', package], check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def get_android_version(device):
    """Get the Android version of the device."""
    try:
        result = subprocess.run(
            ['adb', '-s', device, 'shell', 'getprop', 'ro.build.version.release'],
            capture_output=True,
            text=True,
            check=True
        )
        return int(result.stdout.split('.')[0])
    except (subprocess.CalledProcessError, ValueError, IndexError):
        return 0

def get_current_app(device):
    """Get the current foreground app based on Android version."""
    android_version = get_android_version(device)
    try:
        if android_version >= 10:
            cmd = f"adb -s {device} shell 'dumpsys window displays | grep mCurrentFocus'"
        else:
            cmd = f"adb -s {device} shell 'dumpsys window | grep mCurrentFocus'"
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=True
        )
        
        if result.stdout:
            # Parse the output to get package name
            output = result.stdout.strip()
            # Format: mCurrentFocus=Window{hash u0 package/activity}
            if 'mCurrentFocus=' in output:
                # Extract content between last space before package and /
                parts = output.split()
                for part in parts:
                    if '/' in part:
                        package = part.split('/')[0]
                        return package
            return None
        return None
    except (subprocess.CalledProcessError, IndexError):
        return None

def update_catalogue(package, category='hunter'):
    """Update catalogue.yaml with a new package."""
    try:
        with open('catalogue.yaml', 'r') as file:
            data = yaml.safe_load(file)
        
        if category not in data['catalogue']:
            data['catalogue'][category] = []
        
        if package not in data['catalogue'][category]:
            data['catalogue'][category].append(package)
            
            with open('catalogue.yaml', 'w') as file:
                yaml.dump(data, file, default_flow_style=False, sort_keys=False)
            
            print(f"\nPackage {package} has been added to the catalogue under '{category}'")
            print("Please consider opening an issue at github.com/gAtrium/pamuk")
            print("to help include this package in the official repository.")
    except Exception as e:
        print(f"Error updating catalogue: {e}")

def hunter_mode(device):
    """Monitor top app and allow immediate uninstallation."""
    print("Entering hunter mode (Press Ctrl+C to exit)...")
    print("Monitoring current app...")
    
    last_package = None
    try:
        while True:
            current_package = get_current_app(device)
            if current_package and current_package != last_package:
                last_package = current_package
                print(f"\nCurrent app: {current_package}")
                if input("Uninstall this app? (y/N): ").lower() == 'y':
                    if uninstall_package(device, current_package):
                        print("Successfully uninstalled.")
                        update_catalogue(current_package)
                    else:
                        print("Failed to uninstall.")
                else:
                    print("Continuing the watch...")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting hunter mode...")

def main():
    # Check if ADB is available
    check_adb()
    
    # Load catalogue
    catalogue = load_catalogue()
    
    # Wait for device
    device = wait_for_device()
    print(f"Connected to device: {device}")
    
    # Ask for mode
    print("\nSelect mode:")
    print("1. Catalogue mode (check against known packages)")
    print("2. Hunter mode (monitor current app)")
    
    mode = input("Enter mode (1/2): ").strip()
    
    if mode == "2":
        hunter_mode(device)
        sys.exit(0)
    
    # Continue with catalogue mode
    installed_packages = get_installed_packages(device)
    
    # Check for matches
    matches = []
    for category, packages in catalogue.items():
        for package in packages:
            if package in installed_packages:
                print(f"[{category}] {package}")
                matches.append((category, package))
    
    if not matches:
        print("No matching packages found.")
        response = input("Would you like to switch to hunter mode to detect running apps? (y/N): ").lower()
        if response == 'y':
            hunter_mode(device)
        sys.exit(0)
    
    # Ask for confirmation
    response = input("\nDo you want to uninstall these packages? (y/N): ").lower()
    if response != 'y':
        print("Operation cancelled.")
        sys.exit(0)
    
    # Uninstall packages
    print("\nUninstalling packages...")
    for category, package in matches:
        print(f"Uninstalling [{category}] {package}...", end=' ')
        if uninstall_package(device, package):
            print("Success")
        else:
            print("Failed")

if __name__ == "__main__":
    main()