<div align="center">
  <img src="converter.png" alt="EOP to MIDI Converter logo" width="300">
  
  # EOP2MID Converter
  
  Convert EveryonePiano files (.EOP) into standard MIDI files (.MID) with Python.
</div>

A lightweight converter for EveryonePiano sheet music and demo files. It extracts note data from `.EOP` files and writes MIDI output that can be opened in DAWs, MIDI editors, or notation software.

## Why this project exists

Many users want to take music created in EveryonePiano and continue working with it in a standard MIDI workflow. This project focuses on converting `.EOP` files back into MIDI without needing external dependencies.

It is especially useful for:

- music reverse engineering
- soundfont recreation
- MIDI editing and arrangement
- preserving original note timing and tempo data

## Features

- Converts EveryonePiano `.EOP` files to MIDI
- No external Python packages required
- Supports EOP 2.00, 2.01, and 3.01
- Preserves left/right hand separation for EOP 2.00 files
- Generates standard MIDI Format 1 output
- Accepts drag-and-drop usage on Windows or direct CLI execution

## Supported formats

This project supports these EveryonePiano versions:

- EOP 2.00
- EOP 2.01
- EOP 3.01

For EOP 2.00, left and right hand information is preserved as separate MIDI tracks. For EOP 2.01 and 3.01 files, notes are mapped into a single piano track because the corresponding hand metadata is not available in the format.

## Installation

### Prerequisites

You need Python 3.6 or higher installed on your system. If you don't have Python yet, download it from:

- https://www.python.org/downloads/

### Clone the repository

Open a terminal or command prompt and run:

```bash
git clone https://github.com/mildannerofc/EOP2MID-Converter.git
```

Navigate into the project directory:

```bash
cd EOP2MID-Converter
```

### Verify the installation

Check that the Python script is present:

```bash
ls -la eop_to_midi.py
```

On Windows, use:

```cmd
dir eop_to_midi.py
```

## How to use

### Option 1: Drag and drop (Windows)

1. Save your file as `.eop`
2. Drag the file onto `eop_to_midi.py`
3. The converter will create a `.mid` file next to the source file

### Option 2: Command line

Navigate to the directory where you cloned the repository, then run:

```bash
python eop_to_midi.py your_file.eop
```

You can also convert multiple files at once:

```bash
python eop_to_midi.py song1.eop song2.eop song3.eop
```

### Option 3: Using the example

The repository includes an example directory with demo files. To test the converter:

```bash
python eop_to_midi.py example/demo.eop
```

This produces a MIDI file such as:

```text
example/demo.mid
```

## Compiling to an executable (Optional)

If you want to create a standalone `.exe` file on Windows, you can use PyInstaller:

### Install PyInstaller

```bash
pip install pyinstaller
```

### Build the executable

From the project directory, run:

```bash
pyinstaller --onefile eop_to_midi.py
```

This creates a standalone executable in the `dist/` folder:

```text
dist/eop_to_midi.exe
```

You can then use this `.exe` file directly on other Windows machines without needing Python installed.

### After building

Once compiled, you can:

1. Drag and drop `.eop` files onto `eop_to_midi.exe`
2. Or run it from the command line: `eop_to_midi.exe your_file.eop`

## Project structure

```text
EOP2MID-Converter/
├── eop_to_midi.py
├── converter.png
├── README.md
├── LICENSE
├── package.json
├── example/
│   └── (demo EOP files)
└── dist/
    └── (compiled executable, after running PyInstaller)
```

## Notes

- The script reads the EOP data structure and reconstructs note events into MIDI timing.
- MIDI tempo is based on the metadata found in the source EOP file.
- Output files are created without overwriting existing files; numbered alternatives are generated when needed.
- The converter requires no internet connection or external dependencies to run.

## Download original EveryonePiano

The original software can be downloaded from:

- https://www.everyonepiano.com/

## AI disclosure

This project is written in Python and was developed with the help of ChatGPT. The visual assets and the project concept remain my own.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contributing

Issues, bug reports, and feature ideas are welcome. If you have a file that fails to convert, feel free to open an issue and include the `.EOP` file if possible.

## Disclaimer

This tool is intended for educational and personal use. Please respect copyright and licensing of the original music files you convert.
