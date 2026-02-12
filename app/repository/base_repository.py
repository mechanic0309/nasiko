"""
Base Repository - Shared functionality for all repository modules
"""
import os
import base64
import cryptography.fernet
from abc import ABC


class BaseRepository(ABC):
    """Base repository class with shared functionality"""
    
    def __init__(self, db, logger):
        self.db = db
        self.logger = logger
        # Initialize encryption key for sensitive data
        self._encryption_key = self._get_or_create_encryption_key()
    
    def _get_or_create_encryption_key(self):
        """Get or create encryption key for sensitive data"""
        # Try to get key from environment first
        env_key = os.getenv("ENCRYPTION_KEY")
        if env_key:
            try:
                return base64.urlsafe_b64decode(env_key.encode())
            except Exception as e:
                self.logger.warning(f"Invalid encryption key in environment: {e}")
        
        # Try to read from file
        key_file = ".encryption_key"
        try:
            if os.path.exists(key_file):
                with open(key_file, "rb") as f:
                    return f.read()
        except Exception as e:
            self.logger.warning(f"Could not read encryption key file: {e}")
        
        # Generate new key
        key = cryptography.fernet.Fernet.generate_key()
        try:
            with open(key_file, "wb") as f:
                f.write(key)
            self.logger.info("Generated new encryption key")
        except Exception as e:
            self.logger.warning(f"Could not save encryption key: {e}")
        
        return key
    
    def _encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data"""
        if not data:
            return data
        
        try:
            fernet = cryptography.fernet.Fernet(self._encryption_key)
            encrypted_data = fernet.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted_data).decode()
        except Exception as e:
            self.logger.error(f"Encryption failed: {e}")
            raise
    
    def _decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        if not encrypted_data:
            return encrypted_data
        
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            fernet = cryptography.fernet.Fernet(self._encryption_key)
            decrypted_data = fernet.decrypt(encrypted_bytes)
            return decrypted_data.decode()
        except Exception as e:
            self.logger.error(f"Decryption failed: {e}")
            raise