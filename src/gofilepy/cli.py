"""Command-line interface for uploading files to Gofile."""

from __future__ import annotations

import argparse
import json
import logging
import os
from typing import Callable, Dict, List, Optional

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
    parser.add_argument("files", nargs="+", help="Files to upload")
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


def _create_progress_bar(filename: str, total: int, quiet: bool) -> Optional[tqdm]:
    """Create a tqdm progress bar unless JSON mode is requested."""

    if quiet:
        return None
    return tqdm(total=total, unit="B", unit_scale=True, desc=f"Uploading {filename}")


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


def output_results(results: List[Dict[str, object]], json_mode: bool) -> None:
    """Display results in either JSON or human readable form."""

    if json_mode:
        print(json.dumps(results, indent=2))
        return

    print("\n--- Summary ---")
    for result in results:
        if result["status"] == "success":
            print(f"✅ {result['file']} -> {result['downloadPage']}")
        else:
            print(f"❌ {result['file']} -> {result.get('message')}")
    successes = sum(1 for res in results if res["status"] == "success")
    failures = len(results) - successes
    logger.info("Summary: %s succeeded, %s failed", successes, failures)


def main() -> None:
    """Entrypoint for the CLI."""

    load_dotenv()
    args = parse_arguments()
    configure_logging(args.verbose)

    token = os.environ.get("GOFILE_TOKEN")
    _log_token_state(token, args.json)

    client = GofileClient(token=token)
    results = upload_files(args, client)
    output_results(results, args.json)


if __name__ == "__main__":
    main()
