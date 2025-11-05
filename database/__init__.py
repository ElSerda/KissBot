"""
KissBot Database Module
SQLite database with encrypted OAuth tokens
"""

from .crypto import TokenEncryptor

__all__ = ['TokenEncryptor']
