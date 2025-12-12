#!/usr/bin/env python3

import argparse
import os
import json
import logging
from tqdm import tqdm
from dotenv import load_dotenv
from .client import GofileClient

# Configure Logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger("gofilepy")

def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Gofile.io CLI Uploader (HTTPX Edition)")
    
    parser.add_argument("files", nargs='+', help="Files to upload")
    
    parser.add_argument("-s", "--to-single-folder", action="store_true",
                        help="Upload multiple files to the same folder.")
    
    parser.add_argument("-f", "--folder-id", type=str, default=None,
                        help="ID of an existing Gofile folder.")
    
    parser.add_argument("-vv", "--verbose", action="store_true",
                        help="Show detailed debug info.")
    
    parser.add_argument("--json", action="store_true",
                        help="Output result as JSON for scripts.")

    args = parser.parse_args()

    # Log Level Handling
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        # HTTPX can be verbose, enable if needed
        # logging.getLogger("httpx").setLevel(logging.DEBUG) 
    else:
        logger.setLevel(logging.INFO)
        logging.getLogger("httpx").setLevel(logging.WARNING)

    # Token Logic
    token = os.environ.get("GOFILE_TOKEN")
    if token:
        masked_token = f"{token[:4]}..."
        if not args.json:
            logger.info(f"🔑 Token loaded: {masked_token}")
    else:
        if not args.json:
            logger.warning("⚠️ No GOFILE_TOKEN found in .env or environment. Running as Guest.")

    client = GofileClient(token=token)
    
    target_folder_id = args.folder_id
    results = []

    for file_path in args.files:
        if not os.path.exists(file_path):
            res_err = {"file": file_path, "status": "error", "message": "File not found"}
            results.append(res_err)
            if not args.json:
                logger.error(f"File not found: {file_path}")
            continue

        file_size = os.path.getsize(file_path)
        filename = os.path.basename(file_path)
        
        # Init Progress Bar (Only if not JSON mode)
        pbar = None
        if not args.json:
            pbar = tqdm(total=file_size, unit='B', unit_scale=True, desc=f"Uploading {filename}")

        def progress_update(chunk_size):
            if pbar:
                pbar.update(chunk_size)

        try:
            data = client.upload_file(
                file_path=file_path, 
                folder_id=target_folder_id,
                callback=progress_update
            )
            
            # --- Auto-Folder Management for Guests ---
            # If we are in single folder mode and it's the first upload
            if args.to_single_folder and target_folder_id is None:
                if 'parentFolder' in data:
                    target_folder_id = data['parentFolder']
                    logger.debug(f"Parent folder set to: {target_folder_id}")
                
                # If guest, capture the guestToken to write to the same folder next time
                if 'guestToken' in data and not client.token:
                    client.token = data['guestToken']
                    # Re-auth client with new token
                    client.client.headers.update({"Authorization": f"Bearer {client.token}"})
                    logger.debug(f"Guest token applied: {client.token}")

            results.append({
                "file": filename,
                "status": "success",
                "downloadPage": data.get("downloadPage"),
                "directLink": data.get("directLink", "N/A"), # Sometimes available
                "parentFolder": data.get("parentFolder")
            })

        except Exception as e:
            err_msg = str(e)
            results.append({"file": filename, "status": "error", "message": err_msg})
            if not args.json:
                logger.error(f"Upload failed: {err_msg}")
        finally:
            if pbar:
                pbar.close()

    # Output
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("\n--- Summary ---")
        for res in results:
            if res['status'] == 'success':
                print(f"✅ {res['file']} -> {res['downloadPage']}")
            else:
                print(f"❌ {res['file']} -> {res['message']}")

if __name__ == "__main__":
    main()
