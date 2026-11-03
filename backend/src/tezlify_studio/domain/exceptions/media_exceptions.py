class DomainException(Exception):
    """Base domain exception"""
    pass

class EntityNotFoundException(DomainException):
    """Entity not found in repository"""
    def __init__(self, entity_name: str, entity_id: str):
        super().__init__(f"{entity_name} with id '{entity_id}' was not found.")
        self.entity_name = entity_name
        self.entity_id = entity_id

class DuplicateMediaException(DomainException):
    """Media with identical content hash already exists"""
    def __init__(self, sha256_hash: str, existing_id: str):
        super().__init__(f"Media file with identical content hash already exists (ID: {existing_id}).")
        self.sha256_hash = sha256_hash
        self.existing_id = existing_id

class InvalidMediaFileException(DomainException):
    """Uploaded file violates media format or security requirements"""
    def __init__(self, reason: str):
        super().__init__(f"Invalid media file: {reason}")
        self.reason = reason

class MediaStorageException(DomainException):
    """Error reading or writing media on the storage layer"""
    def __init__(self, message: str):
        super().__init__(f"Storage error: {message}")

