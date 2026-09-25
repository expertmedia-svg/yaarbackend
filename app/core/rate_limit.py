from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared instance so public discovery can be limited without requiring accounts.
limiter = Limiter(key_func=get_remote_address)
