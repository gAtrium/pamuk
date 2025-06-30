#!/usr/bin/env python3

import yaml
import subprocess
import sys
import os
import time
import datetime
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

def get_package_details(device, package):
    """Get detailed information about a package including installation date."""
    try:
        # Get package info using dumpsys
        result = subprocess.run(
            ['adb', '-s', device, 'shell', 'dumpsys', 'package', package],
            capture_output=True,
            text=True,
            check=True
        )
        
        details = {
            'package': package,
            'label': package,  # Default to package name
            'version': 'Unknown',
            'install_time': None,
            'update_time': None,
            'size': 'Unknown'
        }
        
        lines = result.stdout.splitlines()
        for line in lines:
            line = line.strip()
            if line.startswith('versionName='):
                details['version'] = line.split('=', 1)[1]
            elif line.startswith('firstInstallTime='):
                timestamp = line.split('=', 1)[1]
                try:
                    # Parse timestamp (format: 2024-01-15 10:30:45)
                    details['install_time'] = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    # Try alternative timestamp format (milliseconds since epoch)
                    try:
                        timestamp_ms = int(timestamp)
                        details['install_time'] = datetime.datetime.fromtimestamp(timestamp_ms / 1000)
                    except (ValueError, OSError):
                        pass
            elif line.startswith('lastUpdateTime='):
                timestamp = line.split('=', 1)[1]
                try:
                    details['update_time'] = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    try:
                        timestamp_ms = int(timestamp)
                        details['update_time'] = datetime.datetime.fromtimestamp(timestamp_ms / 1000)
                    except (ValueError, OSError):
                        pass
        
        # Try to get human-readable app name
        try:
            label_result = subprocess.run(
                ['adb', '-s', device, 'shell', 'pm', 'list', 'packages', '-f', package],
                capture_output=True,
                text=True,
                check=True
            )
            # Extract APK path and get label
            if label_result.stdout:
                apk_line = label_result.stdout.strip()
                if '=' in apk_line:
                    apk_path = apk_line.split('=')[0].replace('package:', '')
                    # Get app label
                    aapt_result = subprocess.run(
                        ['adb', '-s', device, 'shell', 'aapt', 'dump', 'badging', apk_path],
                        capture_output=True,
                        text=True
                    )
                    if aapt_result.returncode == 0:
                        for aapt_line in aapt_result.stdout.splitlines():
                            if aapt_line.startswith('application-label:'):
                                label = aapt_line.split("'")[1] if "'" in aapt_line else package
                                details['label'] = label
                                break
        except (subprocess.CalledProcessError, IndexError):
            pass  # Keep default package name as label
        
        return details
        
    except subprocess.CalledProcessError:
        return None

def get_all_apps_with_details(device):
    """Get all installed apps with their details, sorted by installation date."""
    print("Fetching installed packages...")
    installed_packages = get_installed_packages(device)
    
    print(f"Getting details for {len(installed_packages)} packages...")
    apps_with_details = []
    
    # Filter out system packages that are likely not user-installed apps
    user_packages = [pkg for pkg in installed_packages if not pkg.startswith(('com.android.', 'com.google.android.', 'android.'))]
    
    for i, package in enumerate(user_packages):
        print(f"Processing {i+1}/{len(user_packages)}: {package}", end='\r')
        details = get_package_details(device, package)
        if details and details['install_time']:
            apps_with_details.append(details)
    
    print()  # New line after progress
    
    # Sort by installation date (newest first)
    apps_with_details.sort(key=lambda x: x['install_time'], reverse=True)
    
    return apps_with_details

def list_apps_by_install_date(device):
    """List user-installed apps sorted by installation date with pagination."""
    print("\n=== User-Installed Apps Sorted by Installation Date (Newest First) ===\n")
    
    apps = get_all_apps_with_details(device)
    
    if not apps:
        print("No user-installed apps found with installation dates.")
        return
    
    print(f"Found {len(apps)} user-installed apps.\n")
    
    # Pagination settings
    items_per_page = 10
    total_pages = (len(apps) + items_per_page - 1) // items_per_page
    current_page = 1
    
    while True:
        # Calculate page boundaries
        start_idx = (current_page - 1) * items_per_page
        end_idx = min(start_idx + items_per_page, len(apps))
        
        # Display header
        print(f"--- Page {current_page} of {total_pages} ---")
        print(f"Showing apps {start_idx + 1}-{end_idx} of {len(apps)} (newest first)\n")
        
        # Display apps for current page
        for i in range(start_idx, end_idx):
            app = apps[i]
            install_date = app['install_time'].strftime('%Y-%m-%d %H:%M:%S')
            update_date = app['update_time'].strftime('%Y-%m-%d %H:%M:%S') if app['update_time'] else 'N/A'
            
            print(f"{i+1:3d}. {app['label']}")
            print(f"     Package: {app['package']}")
            print(f"     Version: {app['version']}")
            print(f"     Installed: {install_date}")
            print(f"     Updated: {update_date}")
            print()
        
        # Navigation and action options
        options = []
        if current_page > 1:
            options.append("p - Previous page")
        if current_page < total_pages:
            options.append("n - Next page")
        options.append("u - Uninstall app")
        options.append("b - Backup APK and uninstall app")
        options.append("q - Quit")
        
        print(f"Options: {' | '.join(options)}")
        choice = input("Enter your choice: ").strip().lower()
        
        if choice == 'n' and current_page < total_pages:
            current_page += 1
            print("\n" + "="*60 + "\n")
        elif choice == 'p' and current_page > 1:
            current_page -= 1
            print("\n" + "="*60 + "\n")
        elif choice == 'u':
            # Uninstall functionality
            try:
                app_num = int(input(f"Enter app number to uninstall (1-{len(apps)}): "))
                if 1 <= app_num <= len(apps):
                    selected_app = apps[app_num - 1]
                    confirm = input(f"Uninstall '{selected_app['label']}' ({selected_app['package']})? (y/N): ").lower()
                    if confirm == 'y':
                        print(f"Uninstalling {selected_app['package']}...", end=' ')
                        if uninstall_package(device, selected_app['package']):
                            print("Success")
                            # Add to catalogue
                            update_catalogue(selected_app['package'])
                            # Remove from list and adjust pagination if needed
                            apps.pop(app_num - 1)
                            total_pages = (len(apps) + items_per_page - 1) // items_per_page
                            if current_page > total_pages and total_pages > 0:
                                current_page = total_pages
                            print(f"App uninstalled. {len(apps)} apps remaining.")
                        else:
                            print("Failed")
                    else:
                        print("Cancelled.")
                else:
                    print(f"Invalid number. Please enter 1-{len(apps)}.")
            except ValueError:
                print("Invalid input. Please enter a valid number.")
            print()
        elif choice == 'b':
            # Backup APK and uninstall functionality
            try:
                app_num = int(input(f"Enter app number to backup and uninstall (1-{len(apps)}): "))
                if 1 <= app_num <= len(apps):
                    selected_app = apps[app_num - 1]
                    confirm = input(f"Backup APK and uninstall '{selected_app['label']}' ({selected_app['package']})? (y/N): ").lower()
                    if confirm == 'y':
                        # First, backup the APK
                        apk_path = pull_apk(device, selected_app['package'])
                        if apk_path:
                            # Then uninstall
                            print(f"Uninstalling {selected_app['package']}...", end=' ')
                            if uninstall_package(device, selected_app['package']):
                                print("Success")
                                # Add to catalogue
                                update_catalogue(selected_app['package'])
                                # Remove from list and adjust pagination if needed
                                apps.pop(app_num - 1)
                                total_pages = (len(apps) + items_per_page - 1) // items_per_page
                                if current_page > total_pages and total_pages > 0:
                                    current_page = total_pages
                                print(f"App backed up and uninstalled. {len(apps)} apps remaining.")
                            else:
                                print("Failed to uninstall (APK was backed up)")
                        else:
                            print("Failed to backup APK. Uninstall cancelled.")
                    else:
                        print("Cancelled.")
                else:
                    print(f"Invalid number. Please enter 1-{len(apps)}.")
            except ValueError:
                print("Invalid input. Please enter a valid number.")
            print()
        elif choice == 'q':
            break
        else:
            print("Invalid choice. Available options:")
            print("  n - Next page (if available)")
            print("  p - Previous page (if available)")
            print("  u - Uninstall app")
            print("  b - Backup APK and uninstall app")
            print("  q - Quit")
            print()

def pull_apk(device, package, output_dir="apk_backups"):
    """Pull APK file from device before uninstalling."""
    try:
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Get APK path on device
        result = subprocess.run(
            ['adb', '-s', device, 'shell', 'pm', 'path', package],
            capture_output=True,
            text=True,
            check=True
        )
        
        if not result.stdout.strip():
            print(f"Could not find APK path for {package}")
            return False
        
        # Extract APK path (format: package:/path/to/app.apk)
        apk_path = result.stdout.strip()
        if apk_path.startswith('package:'):
            apk_path = apk_path[8:]  # Remove 'package:' prefix
        
        # Create output filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"{package}_{timestamp}.apk"
        output_path = os.path.join(output_dir, output_filename)
        
        # Pull the APK file
        print(f"Pulling APK from {apk_path}...", end=' ')
        pull_result = subprocess.run(
            ['adb', '-s', device, 'pull', apk_path, output_path],
            capture_output=True,
            text=True,
            check=True
        )
        
        if os.path.exists(output_path):
            print(f"Success! Saved to {output_path}")
            return output_path
        else:
            print("Failed - file not created")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"Failed - {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

def uninstall_package_with_backup(device, package, backup=False):
    """Uninstall a package with optional APK backup."""
    if backup:
        print(f"Backing up {package}...")
        backup_path = pull_apk(device, package)
        if not backup_path:
            confirm = input("Backup failed. Continue with uninstall anyway? (y/N): ").lower()
            if confirm != 'y':
                print("Uninstall cancelled.")
                return False
    
    return uninstall_package(device, package)

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
    print("3. List all apps by installation date")
    
    mode = input("Enter mode (1/2/3): ").strip()
    
    if mode == "2":
        hunter_mode(device)
        sys.exit(0)
    elif mode == "3":
        list_apps_by_install_date(device)
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