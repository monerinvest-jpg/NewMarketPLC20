"""
Shared rate limiter instance, kept in its own module so both main.py and the
auth endpoints can import it without a circular dependency.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=[])
