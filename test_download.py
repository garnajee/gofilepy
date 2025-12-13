#!/usr/bin/env python3
"""Test script for download functionality."""

from gofilepy import GofileClient

# Test downloading from the folder URL
client = GofileClient()

# Get folder contents
contents = client.get_contents("QUo3a5")
print("Folder contents:")
print(contents)

# You can also download programmatically like this:
# client.download_file(
#     download_url="https://store-eu-par-6.gofile.io/download/web/folder-id/file.py",
#     output_path="./downloaded_test.py"
# )
