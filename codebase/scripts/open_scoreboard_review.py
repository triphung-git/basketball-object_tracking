#!/usr/bin/env python3
"""Open the local review in installed Chrome/Edge instead of an IDE preview."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess


def find_browser():
    """Never use a shell or change the user's default browser."""
    candidates = [
        Path(os.environ.get('PROGRAMFILES', 'C:/Program Files')) / 'Google/Chrome/Application/chrome.exe',
        Path(os.environ.get('LOCALAPPDATA', 'C:/Users/Admin/AppData/Local')) / 'Google/Chrome/Application/chrome.exe',
        Path(os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)')) / 'Microsoft/Edge/Application/msedge.exe',
        Path(os.environ.get('PROGRAMFILES', 'C:/Program Files')) / 'Microsoft/Edge/Application/msedge.exe',
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    for name in ('google-chrome', 'microsoft-edge', 'chromium'):
        found = shutil.which(name)
        if found:
            return Path(found).resolve()
    raise FileNotFoundError('No installed Chrome/Edge found; open review.html manually in a browser')


def prepare(packet_dir):
    packet = Path(packet_dir).resolve()
    page = packet / 'review.html'
    manifest = packet / 'review-manifest.json'
    if not page.is_file() or not manifest.is_file():
        raise FileNotFoundError('Keep the launcher beside review.html and review-manifest.json')
    data = json.loads(manifest.read_text(encoding='utf-8'))
    for entry in data['entries']:
        video = (packet / entry['video']).resolve()
        if not video.is_relative_to(packet) or not video.is_file():
            raise FileNotFoundError('A clip is missing or outside the review folder')
    return find_browser(), page.as_uri()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet-dir', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    browser, url = prepare(args.packet_dir)
    if not args.check_only:
        subprocess.Popen([str(browser), '--new-window', url],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         close_fds=True)
    print(json.dumps(dict(status='checked' if args.check_only else 'opened',
                          browser=str(browser), url=url), ensure_ascii=True))


if __name__ == '__main__':
    main()
