# GofilePy

A Python library and CLI tool for [Gofile.io](https://gofile.io). 
It supports the free API tiers, streaming uploads (low memory usage for large files), and script-friendly JSON output.

## Features

- 🚀 **Streaming Uploads**: Upload 100GB+ files without loading them into RAM.
- 📂 **Folder Management**: Upload to specific folders or create new ones automatically.
- 🤖 **Script Ready**: JSON output mode for easy parsing in pipelines.
- 🆓 **Free Tier Support**: Handles Guest accounts and Standard tokens.
- 📊 **Progress Bar**: Visual feedback for long uploads.

## Installation

### From Source

1. Clone the repository.
2. Install via pip:

```bash
pip install .
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

```python
from gofilepy import GofileClient

# Initialize (Token optional for guest upload)
client = GofileClient(token="your_token")

# Simple Callback for progress
def my_progress(bytes_read):
    print(f"Read: {bytes_read} bytes")

# Upload (Streaming)
try:
    response = client.upload_file(
        file_path="/path/to/movie.mkv", 
        folder_id=None, # None = Create new folder
        callback=my_progress
    )
    print(f"Uploaded! Download here: {response['downloadPage']}")
except Exception as e:
    print(f"Error: {e}")
```

## Building for Release

To build a `.whl` (Wheel) file and a source distribution:

1. Install build tools:
   ```bash
   pip install build twine
   ```
2. Run build:
   ```bash
   python -m build
   ```
3. Artifacts will be in `dist/`.

## License

This project is licensed under the [MIT](LICENSE) License.
