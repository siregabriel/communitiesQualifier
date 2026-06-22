#!/usr/bin/env python3
"""
One-time migration: copy existing inspection photos from the local
static/uploads/ folder into the S3 bucket, preserving their relative paths
(object key = "uploads/<community>/<filename>").

Stored photo_path values in inspections.json stay valid because the app maps
"<community>/<filename>" -> "uploads/<community>/<filename>" when signing URLs.

Usage (on the server, with the same env the app uses):
    S3_BUCKET=your-bucket AWS_REGION=us-east-1 \
    python3 scripts/migrate_uploads_to_s3.py

Safe to re-run: existing objects are simply overwritten.
"""

import os
import sys

import boto3

_CONTENT_TYPES = {
    'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
    'gif': 'image/gif', 'webp': 'image/webp',
}

PREFIX = 'uploads'


def main():
    bucket = os.environ.get('S3_BUCKET', '').strip()
    region = os.environ.get('AWS_REGION', 'us-east-1')
    if not bucket:
        print('ERROR: set S3_BUCKET (and AWS creds) in the environment first.')
        sys.exit(1)

    # static/uploads relative to this script (../static/uploads)
    here = os.path.dirname(os.path.abspath(__file__))
    upload_folder = os.path.normpath(os.path.join(here, '..', 'static', 'uploads'))
    if not os.path.isdir(upload_folder):
        print(f'Nothing to migrate: {upload_folder} does not exist.')
        return

    s3 = boto3.client('s3', region_name=region)

    uploaded, skipped = 0, 0
    for root, _dirs, files in os.walk(upload_folder):
        for name in files:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, upload_folder).replace(os.sep, '/')
            ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
            if ext not in _CONTENT_TYPES:
                skipped += 1
                continue
            key = f'{PREFIX}/{rel}'
            try:
                with open(full, 'rb') as fh:
                    s3.upload_fileobj(
                        fh, bucket, key,
                        ExtraArgs={'ContentType': _CONTENT_TYPES[ext]},
                    )
                uploaded += 1
                print(f'  uploaded  {key}')
            except Exception as e:
                print(f'  FAILED    {key}: {e}')

    print(f'\nDone. Uploaded {uploaded} file(s), skipped {skipped} non-image file(s).')
    print(f'Bucket: {bucket} ({region})')


if __name__ == '__main__':
    main()
