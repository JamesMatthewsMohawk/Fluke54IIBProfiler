# Superba Tunnel Profiler

## About

Superba Tunnel Profiler is a desktop application (PySide6) that connects to a **Fluke 54 II B** thermometer to pull temperature readings and build thermal profiles of **Superba tunnels**. It logs data over time, stores it in a local database, and lets you chart, review, and export the resulting profiles.

## Getting Started

Download the latest standalone Windows build from the [Releases](https://github.com/JamesMatthewsMohawk/Fluke54IIBProfiler/releases) page, extract the folder anywhere, and run `SuperbaTunnelProfiler.exe` from inside it — no Python install required. Keep the whole folder together; the app stores its database next to the .exe.

See [docs/Superba Tunnel Profiler - How To Use.pdf](docs/Superba%20Tunnel%20Profiler%20-%20How%20To%20Use.pdf) for a full walkthrough.

**You'll need:** a Fluke 54 II B thermometer with logged readings, the Fluke IRUSB Rev. II cable, Windows, and an activated license (see below).

**Licensing:** meter downloads require a machine-locked license key, activated from the Settings tab. See `tools/generate_license.py` for issuing keys.

## Features

- Communicates with the Fluke 54 II B over its IR/USB interface to pull logged temperature data
- Automatically detects when a download bundles more than one logged run (e.g. the meter was started/stopped twice before connecting) and splits them into separate runs, prompting for a tunnel name for each
- Builds tunnel thermal profiles from logged readings
- Overlays multiple runs on one graph, each in its own color, to compare them directly
- Hovering the graph shows a dot on each curve at the current time, with live temperature and time values in the legend
- Drag any plotted curve left/right to shift it in time and line up start/end points across runs with different logging start times; double-click a curve to reset it
- Stores collected data in a local SQLite database (`superba_profiler.db`)
- Chart, Database, Download, and Settings tabs for reviewing and exporting data
- Exports plotted data (PNG, CSV, Excel) and prints one-page run reports
- Machine-locked license activation gates meter downloads
- Packaged as a standalone Windows build via PyInstaller
