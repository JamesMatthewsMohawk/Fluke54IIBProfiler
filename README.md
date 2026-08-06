# Superba Tunnel Profiler

## About

Superba Tunnel Profiler is a desktop application (PySide6) that connects to a **Fluke 54 II B** thermometer to pull temperature readings and build thermal profiles of **Superba tunnels**. It logs data over time, stores it in a local database, and lets you chart, review, and export the resulting profiles.

## Features

- Communicates with the Fluke 54 II B over its IR/USB interface to pull live and logged temperature data
- Builds tunnel thermal profiles from logged readings
- Stores collected data in a local SQLite database (`superba_profiler.db`)
- Chart, Database, Download, and Settings tabs for reviewing and exporting data
- Exports plotted data for further analysis
- Packaged as a standalone Windows build via PyInstaller
