"""
KissBot Database - Token Encryption
Chiffrement des tokens OAuth avec Fernet (AES-128-CBC + HMAC)
"""

import base64
import logging
import os
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

LOGGER = logging.getLogger(__name__)


class TokenEncryptor:
    """
    Gère le chiffrement/déchiffrement des tokens OAuth avec Fernet
    
    Fernet = AES-128-CBC + HMAC-SHA256
    - Authentification ET chiffrement
    - Protection contre tampering
    - Key rotation support
    """
    
    def __init__(self, key_file: str = ".kissbot.key"):
        """
        Initialize encryptor with encryption key
        
        Args:
            key_file: Path to the encryption key file
        """
        self.key_file = Path(key_file)
        self.key: Optional[bytes] = None
        self.fernet: Optional[Fernet] = None
        
        # Load or generate key
        self._load_or_generate_key()
    
    def _load_or_generate_key(self):
        """Load existing key or generate new one"""
        if self.key_file.exists():
            # Load existing key
            try:
                with open(self.key_file, 'rb') as f:
                    self.key = f.read()
                
                # Validate key format
                self.fernet = Fernet(self.key)
                LOGGER.info(f"🔑 Encryption key loaded from {self.key_file}")
                
            except Exception as e:
                LOGGER.error(f"❌ Failed to load encryption key: {e}")
                raise
        else:
            # Generate new key
            self.key = Fernet.generate_key()
            self.fernet = Fernet(self.key)
            
            # Save key securely (600 permissions)
            try:
                with open(self.key_file, 'wb') as f:
                    f.write(self.key)
                
                # Set secure permissions (owner only)
                os.chmod(self.key_file, 0o600)
                
                LOGGER.info(f"🔑 New encryption key generated and saved to {self.key_file}")
                LOGGER.warning(f"⚠️ BACKUP THIS KEY FILE! Without it, tokens cannot be decrypted!")
                
            except Exception as e:
                LOGGER.error(f"❌ Failed to save encryption key: {e}")
                raise
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a token string
        
        Args:
            plaintext: Token to encrypt
            
        Returns:
            Base64-encoded encrypted token
        """
        if not self.fernet:
            raise RuntimeError("Encryptor not initialized")
        
        try:
            # Encrypt (returns bytes)
            encrypted_bytes = self.fernet.encrypt(plaintext.encode('utf-8'))
            
            # Return as base64 string for SQLite storage
            return base64.b64encode(encrypted_bytes).decode('utf-8')
            
        except Exception as e:
            LOGGER.error(f"❌ Encryption failed: {e}")
            raise
    
    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt a token string
        
        Args:
            encrypted: Base64-encoded encrypted token
            
        Returns:
            Decrypted token plaintext
        """
        if not self.fernet:
            raise RuntimeError("Encryptor not initialized")
        
        try:
            # Decode from base64
            encrypted_bytes = base64.b64decode(encrypted.encode('utf-8'))
            
            # Decrypt
            plaintext_bytes = self.fernet.decrypt(encrypted_bytes)
            
            return plaintext_bytes.decode('utf-8')
            
        except InvalidToken:
            LOGGER.error("❌ Decryption failed: Invalid token or wrong key")
            raise
        except Exception as e:
            LOGGER.error(f"❌ Decryption failed: {e}")
            raise
    
    def rotate_key(self, new_key_file: str) -> 'TokenEncryptor':
        """
        Create a new encryptor with a new key for key rotation
        
        Args:
            new_key_file: Path to the new key file
            
        Returns:
            New TokenEncryptor instance with new key
        """
        new_encryptor = TokenEncryptor(key_file=new_key_file)
        LOGGER.info(f"🔄 Key rotation: new key generated in {new_key_file}")
        return new_encryptor
    
    def get_key_fingerprint(self) -> str:
        """
        Get a fingerprint of the current key (for auditing)
        
        Returns:
            SHA256 hash of the key (first 16 chars)
        """
        import hashlib
        if not self.key:
            return "NO_KEY"
        
        fingerprint = hashlib.sha256(self.key).hexdigest()
        return fingerprint[:16]


def test_encryptor():
    """Test encryption/decryption"""
    import tempfile
    import os
    
    # Use temp key file for testing (secure method)
    fd, key_file = tempfile.mkstemp(suffix='.key')
    os.close(fd)  # Close the file descriptor, we just need the path
    os.unlink(key_file)  # Remove the empty file, TokenEncryptor will create it
    
    try:
        # Create encryptor
        encryptor = TokenEncryptor(key_file=key_file)
        
        # Test data
        test_token = "abcdefghijklmnopqrstuvwxyz1234567890"
        
        # Encrypt
        encrypted = encryptor.encrypt(test_token)
        print(f"Original:  {test_token}")
        print(f"Encrypted: {encrypted}")
        print(f"Key fingerprint: {encryptor.get_key_fingerprint()}")
        
        # Decrypt
        decrypted = encryptor.decrypt(encrypted)
        print(f"Decrypted: {decrypted}")
        
        # Verify
        assert test_token == decrypted, "Decryption failed!"
        print("✅ Encryption/Decryption test PASSED")
        
    finally:
        # Cleanup
        if Path(key_file).exists():
            Path(key_file).unlink()


if __name__ == "__main__":
    # Run test
    logging.basicConfig(level=logging.INFO)
    test_encryptor()
