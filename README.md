# Pamuk
![Pamuk](pamuk.svg)
</br>
Python script to connect to an android device via ADB and filter out the adware away.

## Requirements
- Python 3.x
- ADB (Android Debug Bridge)

## Installation
1. Get the code:
   - Clone the repository:
   ```bash
   git clone https://github.com/tiel/pamuk.git
   cd pamuk
   ```
   - Or download the ZIP file from the GitHub repository and extract it

2. Install the required Python packages:
```bash
pip install -r requirements.txt
```

## Usage
1. Make sure you have ADB installed and added to your PATH.
2. Connect your android device to your computer via USB and enable USB debugging.
3. Run the script with the following command:
```bash
python pamuk.py
```
4. Choose your preferred mode:
   - **Catalogue Mode (1)**: Checks your device against a known list of adware packages
   - **Hunter Mode (2)**: Actively monitors running apps and allows immediate uninstallation
### For Catalogue Mode:
   - The script will scan for known adware packages
   - If matches are found, you can choose to uninstall them
   - If no matches are found, you'll be offered to switch to Hunter Mode
### For Hunter Mode:
   - The script will show you the current running app in real-time
   - For each new app that comes into focus, you can choose to uninstall it
   - When you uninstall an app, it's automatically added to the catalogue for future reference
   - Press Ctrl+C to exit Hunter Mode


## Contributing
If you encounter any issues or would like to suggest a package name to be added to the list, please submit an issue or a pull request on the GitHub repository. Include the package name and a brief description of why it should be added.

## License
This project is licensed under the MIT License. See the LICENSE file for more details.

## Contributing
Contributions are welcome! If you would like to contribute to this project, please fork the repository and submit a pull request. Make sure to follow the code style.