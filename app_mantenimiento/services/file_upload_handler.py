"""
File Upload Handler Service
Handles file validation, secure filename generation, and file storage
"""

import os
import logging
from datetime import datetime
from werkzeug.utils import secure_filename
from typing import Tuple

logger = logging.getLogger(__name__)

# MIME type per extension (for correct in-browser rendering from S3)
_CONTENT_TYPES = {
    'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
    'gif': 'image/gif', 'webp': 'image/webp',
}


class FileUploadHandler:
    """
    Handles file upload operations including validation, secure filename generation,
    and community-based folder organization.

    Storage backend is selected at construction:
      - If an S3 bucket is provided, files are uploaded to S3 (private) and served
        via short-lived presigned URLs.
      - Otherwise files are saved to the local upload folder and served from /static.
    Stored path format is identical in both modes ("<community>/<filename>"), so the
    rest of the app doesn't care which backend is active. For S3 the object key is
    that path prefixed with "uploads/".
    """

    # Allowed file extensions for uploads
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}

    # Maximum file size in bytes (16MB)
    MAX_FILE_SIZE = 16 * 1024 * 1024

    # Prefix used for all object keys in the bucket
    S3_PREFIX = 'uploads'

    def __init__(self, upload_folder: str, s3_bucket: str = None,
                 region: str = None, url_expiry: int = 3600):
        """
        Initialize the FileUploadHandler.

        Args:
            upload_folder: Base path for local file uploads (fallback / dev)
            s3_bucket: If set, uploads go to this S3 bucket (private)
            region: AWS region for the bucket
            url_expiry: Lifetime (seconds) of generated presigned URLs
        """
        self.upload_folder = upload_folder
        self.s3_bucket = s3_bucket or None
        self.region = region
        self.url_expiry = url_expiry
        self.use_s3 = bool(self.s3_bucket)
        self._s3 = None  # lazy boto3 client

    @property
    def s3(self):
        if self._s3 is None:
            import boto3
            from botocore.config import Config
            # Use the REGIONAL endpoint + SigV4 + virtual-host addressing so the
            # host in the presigned URL matches what was signed. Without the
            # regional endpoint, boto3 signs for the region but builds a
            # region-less host -> SignatureDoesNotMatch in regions like us-east-2.
            kwargs = dict(
                region_name=self.region,
                config=Config(
                    signature_version='s3v4',
                    s3={'addressing_style': 'virtual'},
                ),
            )
            if self.region:
                kwargs['endpoint_url'] = f'https://s3.{self.region}.amazonaws.com'
            self._s3 = boto3.client('s3', **kwargs)
        return self._s3

    def _s3_key(self, relative_path: str) -> str:
        """Map a stored relative path to its full S3 object key."""
        rel = (relative_path or '').lstrip('/')
        if rel.startswith(self.S3_PREFIX + '/'):
            return rel
        return f"{self.S3_PREFIX}/{rel}"

    def generate_presigned_url(self, relative_path: str, download_name: str = None):
        """Return a short-lived signed GET URL for a stored object, or None.
        If download_name is given, the object downloads as that filename."""
        if not self.use_s3 or not relative_path:
            return None
        try:
            params = {'Bucket': self.s3_bucket, 'Key': self._s3_key(relative_path)}
            if download_name:
                params['ResponseContentDisposition'] = f'attachment; filename="{download_name}"'
            return self.s3.generate_presigned_url(
                'get_object', Params=params, ExpiresIn=self.url_expiry)
        except Exception as e:
            logger.error(f'Could not presign {relative_path}: {e}')
            return None

    def save_resource(self, file) -> tuple:
        """
        Save an admin resource file (any allowed doc/image type) under the
        'resources/' prefix. Returns (relative_path, stored_filename).
        """
        ts = int(datetime.now().timestamp())
        original = secure_filename(file.filename) or 'file'
        stored = f"{ts}_{original}"
        relative_path = f"resources/{stored}"
        if self.use_s3:
            file.seek(0)
            self.s3.upload_fileobj(file, self.s3_bucket, self._s3_key(relative_path))
            return relative_path, stored
        directory = os.path.join(self.upload_folder, 'resources')
        os.makedirs(directory, exist_ok=True)
        file.save(os.path.join(directory, stored))
        return relative_path, stored

    def save_cover(self, file, slug: str) -> tuple:
        """
        Save a community cover image under 'community_covers/<slug>.<ext>'.
        Re-uploading replaces the previous object. Returns (relative_path,
        stored_filename).
        """
        original = secure_filename(file.filename) or 'cover.jpg'
        ext = original.rsplit('.', 1)[1].lower() if '.' in original else 'jpg'
        relative_path = f"community_covers/{slug}.{ext}"
        if self.use_s3:
            content_type = _CONTENT_TYPES.get(ext, 'application/octet-stream')
            file.seek(0)
            self.s3.upload_fileobj(
                file, self.s3_bucket, self._s3_key(relative_path),
                ExtraArgs={'ContentType': content_type},
            )
            return relative_path, original
        directory = os.path.join(self.upload_folder, 'community_covers')
        os.makedirs(directory, exist_ok=True)
        file.seek(0)
        file.save(os.path.join(directory, f"{slug}.{ext}"))
        return relative_path, original

    def delete_file(self, relative_path: str) -> None:
        """Best-effort removal of a stored file (S3 object or local file)."""
        if not relative_path:
            return
        try:
            if self.use_s3:
                self.s3.delete_object(Bucket=self.s3_bucket, Key=self._s3_key(relative_path))
            else:
                p = os.path.join(self.upload_folder, relative_path)
                if os.path.exists(p):
                    os.remove(p)
        except Exception as e:
            logger.error(f'Could not delete {relative_path}: {e}')

    def validate_file(self, file) -> Tuple[bool, str]:
        """
        Validate file type and size.
        
        Args:
            file: FileStorage object from Flask request
            
        Returns:
            Tuple of (valid: bool, error_message: str)
            If valid is True, error_message will be empty string
            If valid is False, error_message contains the validation error
        """
        # Check if file exists
        if not file or file.filename == '':
            return (False, "No file provided")
        
        # Check file extension
        if not self._allowed_file(file.filename):
            allowed_exts = ', '.join(self.ALLOWED_EXTENSIONS)
            return (False, f"Invalid file type. Allowed types: {allowed_exts}")
        
        # Check file size
        # Seek to end to get file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if file_size > self.MAX_FILE_SIZE:
            max_size_mb = self.MAX_FILE_SIZE / (1024 * 1024)
            return (False, f"File size exceeds maximum allowed size of {max_size_mb}MB")
        
        return (True, "")
    
    def save_file(self, file, username: str, community: str) -> str:
        """
        Save file with secure filename generation and return relative path.
        
        Args:
            file: FileStorage object from Flask request
            username: Username of the person uploading the file
            community: Community name for folder organization
            
        Returns:
            Relative path to the saved file (e.g., "uploads/Community_A/john_Community_A_1705317600.jpg")
            
        Raises:
            IOError: If file cannot be saved to disk
        """
        # Generate a clean, URL-safe filename (no spaces/commas)
        timestamp = int(datetime.now().timestamp())
        file_ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
        safe_community = secure_filename(community)
        filename = f"{secure_filename(username)}_{timestamp}.{file_ext}"
        relative_path = f"{safe_community}/{filename}"

        if self.use_s3:
            try:
                content_type = _CONTENT_TYPES.get(file_ext, 'application/octet-stream')
                file.seek(0)
                self.s3.upload_fileobj(
                    file,
                    self.s3_bucket,
                    self._s3_key(relative_path),
                    ExtraArgs={'ContentType': content_type},
                )
                return relative_path
            except Exception as e:
                raise IOError(f"Failed to upload file to S3: {str(e)}")

        try:
            community_folder_path = self.ensure_community_folder(community)
            full_path = os.path.join(community_folder_path, filename)
            file.save(full_path)
            return relative_path
        except (OSError, IOError) as e:
            raise IOError(f"Failed to save file: {str(e)}")
    
    def ensure_community_folder(self, community: str) -> str:
        """
        Create community folder if it doesn't exist.
        
        Args:
            community: Community name
            
        Returns:
            Full path to the community folder
            
        Raises:
            IOError: If folder cannot be created
        """
        try:
            # Sanitize community name for filesystem
            safe_community_name = secure_filename(community)
            community_folder_path = os.path.join(self.upload_folder, safe_community_name)
            
            # Create folder if it doesn't exist
            os.makedirs(community_folder_path, exist_ok=True)
            
            return community_folder_path
        except (OSError, IOError) as e:
            raise IOError(f"Failed to create community folder: {str(e)}")
    
    def _allowed_file(self, filename: str) -> bool:
        """
        Check if file extension is allowed.
        
        Args:
            filename: Name of the file
            
        Returns:
            True if file extension is allowed, False otherwise
        """
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.ALLOWED_EXTENSIONS
