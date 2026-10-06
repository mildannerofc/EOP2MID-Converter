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

## How to use

### Option 1: Drag and drop

1. Save your file as `.eop`
2. Drag the file onto `eop_to_midi.py`
3. The converter will create a `.mid` file next to the source file

### Option 2: Command line

```bash
python eop_to_midi.py your_file.eop
```

You can also convert multiple files at once:

```bash
python eop_to_midi.py song1.eop song2.eop song3.eop
```

## Example

```bash
python eop_to_midi.py example/demo.eop
```

This produces a MIDI file such as:

```text
example/demo.mid
```

## Project structure

```text
EOP2MID-Converter/
├── eop_to_midi.py
├── converter.png
├── README.md
├── LICENSE
├── package.json
└── example/
```

## Notes

- The script reads the EOP data structure and reconstructs note events into MIDI timing.
- MIDI tempo is based on the metadata found in the source EOP file.
- Output files are created without overwriting existing files; numbered alternatives are generated when needed.

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
