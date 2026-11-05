"""Durable immutable artifacts and fail-closed project locking.

S3 needs conditional PutObject support. Locks deliberately have no automatic
expiry: an operator must verify a crashed job stopped before removing its lock.
"""

from contextlib import contextmanager
from hashlib import sha256
import json
import os
import re
from pathlib import Path, PurePosixPath
import secrets

from .errors import WorkerError


def safe_key(key):
    if not isinstance(key, str) or not key or len(key) > 512:
        raise WorkerError("invalid_key", "Storage key must be a nonempty relative key.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", key) or any(p in ("", ".", "..") for p in key.split("/")):
        raise WorkerError("invalid_key", "Storage keys cannot contain paths, URLs, or traversal.")
    return str(PurePosixPath(key))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return sha256(canonical(value)).hexdigest()


class Store:
    def read_json(self, key):
        try:
            return json.loads(self.read(key))
        except (ValueError, UnicodeError) as exc:
            raise WorkerError("corrupt_artifact", "Stored JSON artifact is corrupt.") from exc

    def write_json(self, key, value):
        self.write(key, canonical(value))

    @contextmanager
    def lock(self, project):
        key = f"projects/{project}/execution.lock"
        token = secrets.token_hex(16)
        if not self.create(key, canonical({"token": token})):
            raise WorkerError("project_busy", "Project is locked; retry later. After a crash, operator verification is required before removing the lock.")
        try:
            yield
        finally:
            self.delete(key)


class LocalStore(Store):
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key):
        path = (self.root / safe_key(key)).resolve()
        if not path.is_relative_to(self.root):
            raise WorkerError("invalid_key", "Storage key escapes the storage root.")
        return path

    def read(self, key):
        try:
            path = self.path(key)
            if path.stat().st_size > 100 * 1024 * 1024:
                raise WorkerError("asset_too_large", "Artifact exceeds 100 MiB.")
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise WorkerError("not_found", f"Missing artifact: {key}") from exc

    def write(self, key, data):
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + "." + secrets.token_hex(8) + ".tmp")
        try:
            tmp.write_bytes(data)
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)

    def create(self, key, data):
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as handle:
                handle.write(data)
            return True
        except FileExistsError:
            return False

    def delete(self, key):
        self.path(key).unlink(missing_ok=True)

    def location(self, key):
        return {"key": safe_key(key), "local_path": str(self.path(key))}


class S3Store(Store):
    def __init__(self, bucket, prefix="openmontage", endpoint=None, client=None):
        if not bucket:
            raise WorkerError("configuration", "S3_BUCKET must be set for S3 storage.")
        self.bucket = bucket
        self.prefix = safe_key(prefix).rstrip("/")
        if client is None:
            import boto3
            client = boto3.client("s3", endpoint_url=endpoint)
        self.client = client

    def key(self, key):
        return self.prefix + "/" + safe_key(key)

    def read(self, key):
        from botocore.exceptions import ClientError
        try:
            result = self.client.get_object(Bucket=self.bucket, Key=self.key(key))
            body = result["Body"]
            try:
                if result.get("ContentLength", 0) > 100 * 1024 * 1024:
                    raise WorkerError("asset_too_large", "Artifact exceeds 100 MiB.")
                data = body.read(100 * 1024 * 1024 + 1)
                if len(data) > 100 * 1024 * 1024:
                    raise WorkerError("asset_too_large", "Artifact exceeds 100 MiB.")
                return data
            finally:
                body.close()
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
                raise WorkerError("not_found", f"Missing artifact: {key}") from exc
            raise

    def write(self, key, data):
        self.client.put_object(Bucket=self.bucket, Key=self.key(key), Body=data)

    def create(self, key, data):
        from botocore.exceptions import ClientError
        try:
            self.client.put_object(Bucket=self.bucket, Key=self.key(key), Body=data, IfNoneMatch="*")
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("PreconditionFailed", "ConditionalRequestConflict", "412", "409"):
                return False
            raise

    def delete(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=self.key(key))

    def location(self, key):
        return {"key": safe_key(key), "uri": f"s3://{self.bucket}/{self.key(key)}",
                "download_url": self.client.generate_presigned_url("get_object", Params={"Bucket": self.bucket, "Key": self.key(key)}, ExpiresIn=3600)}


def configured_store():
    backend = os.getenv("STORAGE_BACKEND", "local")
    if backend == "local":
        return LocalStore(os.getenv("LOCAL_STORAGE_ROOT", ".local-storage"))
    if backend == "s3":
        return S3Store(os.getenv("S3_BUCKET"), os.getenv("S3_PREFIX", "openmontage"), os.getenv("S3_ENDPOINT_URL"))
    raise WorkerError("configuration", "STORAGE_BACKEND must be local or s3.")
