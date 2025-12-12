# GofilePy

[![Build and Release](https://github.com/garnajee/gofilepy/actions/workflows/build_release.yml/badge.svg)](https://github.com/garnajee/gofilepy/actions/workflows/build_release.yml)

A Python library and CLI tool for [Gofile.io](https://gofile.io). 
It supports the free API tiers, streaming uploads (low memory usage for large files), and script-friendly JSON output.

## Features

- **Streaming Uploads**: Upload 100GB+ files without loading them into RAM.
- **Folder Management**: Upload to specific folders or create new ones automatically.
- **Script Ready**: JSON output mode for easy parsing in pipelines.
- **Free Tier Support**: Handles Guest accounts and Standard tokens.
- **Progress Bar**: Visual feedback for long uploads.

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
import os
from gofilepy import GofileClient
from tqdm import tqdm

TOKEN = os.environ.get("GOFILE_TOKEN") # in .env file, or put it here
FILES_TO_UPLOAD = [
    "/path/to/video1.mp4",
    "/path/to/image.jpg"
]
FOLDER_ID = None # None to create new folder, or put folder ID here

def upload_files():
    client = GofileClient(token=TOKEN)
    
    print(f"Starting upload... {len(FILES_TO_UPLOAD)}")

    for file_path in FILES_TO_UPLOAD:
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            continue

        filename = os.path.basename(file_path)
        filesize = os.path.getsize(file_path)

        with tqdm(total=filesize, unit='B', unit_scale=True, desc=filename) as pbar:
            
            def progress_callback(bytes_read):
                uploaded_so_far = pbar.n
                pbar.update(bytes_read - uploaded_so_far)

            try:
                response = client.upload_file(
                    file_path=file_path, 
                    folder_id=FOLDER_ID, 
                    callback=progress_callback
                )
                
                global FOLDER_ID
                if FOLDER_ID is None and 'parentFolder' in response:
                    FOLDER_ID = response['parentFolder']
                
                pbar.update(filesize - pbar.n)
                
                tqdm.write(f"✅ Success : {response.get('downloadPage')}")

            except Exception as e:
                tqdm.write(f"❌ Error, {filename}: {e}")

if __name__ == "__main__":
    upload_files()
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
