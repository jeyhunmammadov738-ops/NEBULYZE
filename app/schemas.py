from pydantic import BaseModel, HttpUrl, validator
from typing import Optional
import re

class URLRequest(BaseModel):
    url: HttpUrl
    bitrate: str = "192k"
    fmt: str = "mp3"
    
    @validator('url')
    def validate_url(cls, v):
        # Additional URL validation
        url_str = str(v)
        # Block potentially dangerous URLs
        blocked_domains = ['localhost', '127.0.0.1', '192.168.', '10.', '172.16.']
        for domain in blocked_domains:
            if domain in url_str:
                raise ValueError('Invalid URL: potentially dangerous domain')
        return v
    
    @validator('fmt')
    def validate_format(cls, v):
        if v not in ['mp3', 'ogg']:
            raise ValueError('Format must be either mp3 or ogg')
        return v
    
    @validator('bitrate')
    def validate_bitrate(cls, v):
        # Validate bitrate format (e.g., 128k, 192k, 256k, 320k)
        valid_bitrates = ['96k', '128k', '192k', '256k', '320k']
        if v in valid_bitrates:
            return v
        # Try to parse custom bitrate
        if v.endswith('k') and v[:-1].isdigit():
            bitrate_value = int(v[:-1])
            if 96 <= bitrate_value <= 320:
                return v
        raise ValueError('Bitrate must be in format like 128k, 192k, etc.')

class TrimParams(BaseModel):
    start: int
    end: int
    
    @validator('end')
    def validate_trim_order(cls, v, values):
        if 'start' in values and v <= values['start']:
            raise ValueError('End time must be greater than start time')
        return v