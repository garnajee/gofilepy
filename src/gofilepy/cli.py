"""Command-line interface for uploading files to Gofile."""

from __future__ import annotations

import argparse
import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from tqdm import tqdm

from .client import GofileClient, GofileError

LOG_FORMAT = "[%(levelname)s] %(message)s"
logger = logging.getLogger("gofilepy")


def parse_arguments() -> argparse.Namespace:
    """Return parsed CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Gofile.io CLI Uploader (HTTPX Edition)",
    )
    parser.add_argument("files", nargs="*", help="Files to upload")
    parser.add_argument(
        "-d",
        "--download",
        type=str,
        metavar="URL",
        help="Download files from a Gofile URL (folder or content ID).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=".",
        help="Output directory for downloads (default: current directory).",
    )
    parser.add_argument(
        "-s",
        "--to-single-folder",
        action="store_true",
        help="Upload multiple files to the same folder.",
    )
    parser.add_argument(
        "-f",
        "--folder-id",
        type=str,
        default=None,
        help="ID of an existing Gofile folder.",
    )
    parser.add_argument(
        "-vv",
        "--verbose",
        action="store_true",
        help="Show detailed debug info.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON for scripts.",
    )
    return parser.parse_args()


def configure_logging(verbose: bool) -> None:
    """Configure logging for the CLI session."""

    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format=LOG_FORMAT)
    logger.setLevel(level)
    httpx_logger = logging.getLogger("httpx")
    httpx_logger.setLevel(logging.DEBUG if verbose else logging.WARNING)


def _log_token_state(token: Optional[str], json_mode: bool) -> None:
    """Log whether a token was discovered for informational output."""

    if json_mode:
        return
    if token:
        masked_token = f"{token[:4]}..."
        logger.info("🔑 Token loaded: %s", masked_token)
    else:
        logger.warning("⚠️ No GOFILE_TOKEN found in .env or environment. Running as Guest.")


def _progress_callback_factory(progress_bar: Optional[tqdm]) -> Callable[[int], None]:
    """Return a callback that updates the provided progress bar."""

    def update(chunk_size: int, active_bar: Optional[tqdm] = progress_bar) -> None:
        if active_bar:
            active_bar.update(chunk_size)

    return update


def _create_progress_bar(
    filename: str, total: int, quiet: bool, mode: str = "Uploading"
) -> Optional[tqdm]:
    """Create a tqdm progress bar unless JSON mode is requested."""

    if quiet:
        return None
    return tqdm(total=total, unit="B", unit_scale=True, desc=f"{mode} {filename}")


def _handle_upload_success(
    data: Dict[str, object],
    filename: str,
) -> Dict[str, object]:
    """Normalize the success payload for presentation."""

    return {
        "file": filename,
        "status": "success",
        "downloadPage": data.get("downloadPage"),
        "directLink": data.get("directLink", "N/A"),
        "parentFolder": data.get("parentFolder"),
    }


def _handle_upload_error(filename: str, error: Exception) -> Dict[str, object]:
    """Normalize the error payload for presentation."""

    return {
        "file": filename,
        "status": "error",
        "message": str(error),
        "errorType": error.__class__.__name__,
    }


def _apply_guest_token(client: GofileClient, data: Dict[str, object]) -> None:
    """Capture a guest token from the response so future uploads reuse the folder."""

    guest_token = data.get("guestToken")
    if guest_token and not client.token:
        client.token = str(guest_token)
        client.client.headers.update({"Authorization": f"Bearer {client.token}"})
        logger.debug("Guest token applied: %s", client.token)


def upload_files(args: argparse.Namespace, client: GofileClient) -> List[Dict[str, object]]:
    """Upload each file sequentially and return the collected results."""

    results: List[Dict[str, object]] = []
    target_folder_id = args.folder_id

    for file_path in args.files:
        if not os.path.exists(file_path):
            logger.error("File not found: %s", file_path)
            results.append({
                "file": file_path,
                "status": "error",
                "message": "File not found",
            })
            continue

        file_size = os.path.getsize(file_path)
        filename = os.path.basename(file_path)
        progress_bar = _create_progress_bar(filename, file_size, args.json)
        progress_callback = _progress_callback_factory(progress_bar)

        try:
            data = client.upload_file(
                file_path=file_path,
                folder_id=target_folder_id,
                callback=progress_callback,
            )

            if args.to_single_folder and target_folder_id is None:
                parent_folder = data.get("parentFolder")
                if parent_folder:
                    target_folder_id = str(parent_folder)
                    logger.debug("Parent folder set to: %s", target_folder_id)
                _apply_guest_token(client, data)

            results.append(_handle_upload_success(data, filename))
        except (GofileError, httpx.HTTPError, OSError) as error:
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception("Upload failed for %s", filename)
            else:
                logger.error("Upload failed for %s: %s", filename, error)
            results.append(_handle_upload_error(filename, error))
        finally:
            if progress_bar:
                progress_bar.close()

    return results


def extract_content_id(url_or_id: str) -> str:
    """Extract the content ID from a Gofile URL or return the ID as-is."""

    # Handle URLs like https://gofile.io/d/nC5ulQ or direct IDs
    if "gofile.io/d/" in url_or_id:
        return url_or_id.split("gofile.io/d/")[-1].split("?")[0].split("/")[0]
    if "gofile.io" in url_or_id:
        # Handle other URL patterns
        parts = url_or_id.rstrip("/").split("/")
        return parts[-1].split("?")[0]
    return url_or_id


def _download_single_file(
    client: GofileClient,
    file_name: str,
    download_link: str,
    output_path: str,
    file_size: int,
    *,
    quiet: bool
) -> Dict[str, object]:
    """Download a single file and return the result."""
    progress_bar = _create_progress_bar(file_name, file_size, quiet, mode="Downloading")
    progress_callback = _progress_callback_factory(progress_bar)

    try:
        client.download_file(download_link, output_path, progress_callback)
        return {
            "file": file_name,
            "status": "success",
            "path": output_path,
            "size": file_size,
        }
    except (GofileError, httpx.HTTPError, OSError) as error:
        logger.error("Download failed for %s: %s", file_name, error)
        return _handle_upload_error(file_name, error)
    finally:
        if progress_bar:
            progress_bar.close()


def _process_file_data(
    client: GofileClient,
    file_name: str,
    file_data: Dict[str, Any],
    output_dir: str,
    quiet: bool
) -> Dict[str, object]:
    """Process and download a single file from file data."""
    download_link = str(file_data.get("link", ""))

    if not download_link:
        logger.warning("No download link for %s, skipping", file_name)
        return _handle_upload_error(file_name, GofileError("No download link"))

    output_path = os.path.join(output_dir, file_name)
    file_size = int(file_data.get("size", 0))

    return _download_single_file(
        client, file_name, download_link, output_path, file_size, quiet=quiet
    )


def _download_folder_contents(
    client: GofileClient,
    children: Dict[str, Any],
    output_dir: str,
    quiet: bool
) -> List[Dict[str, object]]:
    """Download all files from a folder."""
    results: List[Dict[str, object]] = []
    logger.info("Found %s file(s) in folder", len(children))

    for child_id, child_data in children.items():
        if not isinstance(child_data, dict):
            continue

        child_type = child_data.get("type")
        if child_type != "file":
            logger.debug("Skipping non-file item: %s", child_id)
            continue

        file_name = str(child_data.get("name", f"file_{child_id}"))
        result = _process_file_data(client, file_name, child_data, output_dir, quiet)
        results.append(result)

    return results


def download_files(args: argparse.Namespace, client: GofileClient) -> List[Dict[str, object]]:
    """Download files from a Gofile URL or content ID."""
    content_id = extract_content_id(args.download)

    try:
        # Fetch content information
        logger.info("Fetching content information for: %s", content_id)
        response = client.get_contents(content_id)

        # The response is already the "data" object from get_contents
        data = response if isinstance(response, dict) else {}
        if not isinstance(data, dict):
            raise GofileError("Invalid response structure from API")

        content_type = data.get("type")

        if content_type == "file":
            # Single file download
            file_name = str(data.get("name", "downloaded_file"))
            download_link = str(data.get("link", ""))

            if not download_link:
                raise GofileError("No download link found in response")

            output_path = os.path.join(args.output, file_name)
            file_size = int(data.get("size", 0))

            result = _download_single_file(
                client, file_name, download_link, output_path, file_size, quiet=args.json
            )
            return [result]

        if content_type == "folder":
            # Multiple files in folder
            children = data.get("children", {})
            if not isinstance(children, dict):
                raise GofileError("Invalid children structure in folder response")

            return _download_folder_contents(client, children, args.output, args.json)

        raise GofileError(f"Unknown content type: {content_type}")

    except (GofileError, httpx.HTTPError) as error:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception("Failed to download from %s", content_id)
        else:
            logger.error("Failed to download from %s: %s", content_id, error)
        return [{
            "content_id": content_id,
            "status": "error",
            "message": str(error),
            "errorType": error.__class__.__name__,
        }]


def output_results(
    results: List[Dict[str, object]], json_mode: bool, is_download: bool = False
) -> None:
    """Display results in either JSON or human readable form."""

    if json_mode:
        print(json.dumps(results, indent=2))
        return

    print("\n--- Summary ---")
    for result in results:
        if result["status"] == "success":
            if is_download:
                print(f"✅ {result['file']} -> {result.get('path')}")
            else:
                print(f"✅ {result['file']} -> {result.get('downloadPage')}")
        else:
            error_name = result.get('file', result.get('content_id', 'unknown'))
            print(f"❌ {error_name} -> {result.get('message')}")
    successes = sum(1 for res in results if res["status"] == "success")
    failures = len(results) - successes
    logger.info("Summary: %s succeeded, %s failed", successes, failures)


def main() -> None:
    """Entrypoint for the CLI."""

    load_dotenv()
    args = parse_arguments()
    configure_logging(args.verbose)

    token = os.environ.get("GOFILE_TOKEN")

    # Check if we're in download mode or upload mode
    if args.download:
        _log_token_state(token, args.json)
        client = GofileClient(token=token)
        results = download_files(args, client)
        output_results(results, args.json, is_download=True)
    elif args.files:
        _log_token_state(token, args.json)
        client = GofileClient(token=token)
        results = upload_files(args, client)
        output_results(results, args.json, is_download=False)
    else:
        logger.error("No files specified for upload and no download URL provided.")
        logger.error("Use -d/--download <URL> to download or provide files to upload.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
