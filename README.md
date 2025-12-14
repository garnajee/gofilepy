# GofilePy

[![Build and Release](https://github.com/garnajee/gofilepy/actions/workflows/build_release.yml/badge.svg)](https://github.com/garnajee/gofilepy/actions/workflows/build_release.yml)

A Python library and CLI tool for [Gofile.io](https://gofile.io). 
It supports the free API tiers, streaming uploads (low memory usage for large files), and script-friendly JSON output.

## Features

- **Streaming Uploads**: Upload 100GB+ files without loading them into RAM.
- **Download Support**: Download files from Gofile URLs or content IDs.
- **Folder Management**: Upload to specific folders or create new ones automatically.
- **Script Ready**: JSON output mode for easy parsing in pipelines.
- **Free Tier Support**: Handles Guest accounts and Standard tokens.
- **Progress Bar**: Visual feedback for long uploads and downloads.

## Installation

### With pip

You can install the library directly from the source without cloning the repository manually:
```bash
pip install git+https://github.com/garnajee/gofilepy.git
```

### From Source

1. Clone the repository:
```bash
git clone https://github.com/garnajee/gofilepy.git && cd gofilepy
```

2. Install via [uv](https://docs.astral.sh/uv/getting-started/installation/):
```bash
uv sync
```

3. Running the CLI
```bash
uv run gofilepy --help
```

4. (Optional) Install the package in your environment
```bash
uv pip install .
```

## Usage (CLI)

### Basic Upload
Upload a single file. A new public folder will be created automatically if you don't provide one.

```bash
gofilepy video.mp4
```

### Upload with Token
Export your token (Get it from your Gofile Profile) to access your account storage.

```bash
export GOFILE_TOKEN="your_token_here"
gofilepy my_file.zip
```

### Upload to a Specific Folder
If you have an existing folder ID:

```bash
gofilepy -f "folder-uuid-123" image.png
```

### Group Upload (Single Folder)
Upload multiple files. The first file creates a folder, and the rest are uploaded into it.

```bash
gofilepy -s part1.rar part2.rar part3.rar
```

### Download Files
Download files from a Gofile URL or content ID.

Download from URL:
```bash
gofilepy -d https://gofile.io/d/GxHNKL
```

Download from content ID:
```bash
gofilepy -d GxHNKL
```

Download to specific directory
```bash
gofilepy -d GxHNKL -o ./downloads
```

### Scripting Mode (JSON Output)
Use `--json` to suppress human-readable text and output a JSON array.

```bash
gofilepy --json file.txt
# Output: [{"file": "file.txt", "status": "success", "downloadPage": "...", ...}]
```

### Verbose Mode
Debug connection issues or API responses.

```bash
gofilepy -vv big_file.iso
```

## Usage (Library)

You can use `gofilepy` in your own Python scripts.

### Upload Files

```python
from gofilepy import GofileClient

client = GofileClient()
# client = GofileClient(token="YOUR_TOKEN_HERE")  # Optional token for private uploads
file = client.upload(file=open("./test.py", "rb"))
print(file.name)
print(file.page_link)  # View and download file at this link
```

### Download Files

```python
from gofilepy import GofileClient

client = GofileClient()
contents = client.get_contents("GxHNKL")
print("Folder contents:")
print(contents)
```

## Development

For contributors and developers:

1. Install with development dependencies:
```bash
uv sync --extra dev
```

2. Run pylint to check code quality:
```bash
uv run pylint src/gofilepy
```

3. Install in editable mode for development:
```bash
uv pip install -e .
```

## Building for Release

To build a `.whl` (Wheel) file and a source distribution:

1. Install build tools:
   ```bash
   pip install build
   ```
2. Run build:
   ```bash
   python -m build
   ```
3. Artifacts will be in `dist/`.

## License

This project is licensed under the [MIT](LICENSE) License.
