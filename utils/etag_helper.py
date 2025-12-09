"""
ETag Helper - CROWN ¹⁰ Law #5: ETag Reconciliation Every 30s

Provides utilities for generating ETags (checksums) for API responses
and handling conditional requests with If-None-Match headers.
"""

import hashlib
import json
from flask import request, Response, make_response
from functools import wraps
from typing import Any, Callable, Optional


def generate_etag(data: Any) -> str:
    """
    Generate ETag (checksum) from data.
    
    Args:
        data: Any JSON-serializable data
        
    Returns:
        str: MD5 hash as ETag
    """
    # Convert data to stable JSON string (sorted keys)
    json_str = json.dumps(data, sort_keys=True, default=str)
    
    # Generate MD5 hash
    md5_hash = hashlib.md5(json_str.encode('utf-8')).hexdigest()
    
    return f'"{md5_hash}"'


def with_etag(f: Callable) -> Callable:
    """
    Decorator to add ETag support to Flask routes.
    
    Automatically:
    1. Generates ETag from response data
    2. Adds ETag header to response (ALWAYS, including HEAD requests)
    3. Returns 304 Not Modified if If-None-Match matches
    
    Usage:
        @app.route('/api/data')
        @with_etag
        def get_data():
            return jsonify({'data': ...})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check If-None-Match header
        if_none_match = request.headers.get('If-None-Match')
        is_head_request = request.method == 'HEAD'
        
        # Call original function
        response = f(*args, **kwargs)
        
        # Handle different response types
        if isinstance(response, tuple):
            data, status_code = response if len(response) == 2 else (response[0], 200)
        elif isinstance(response, Response):
            # Already a Flask Response object - ALWAYS try to add ETag
            try:
                if response.is_json:
                    data = response.get_json()
                    etag = generate_etag(data)
                    
                    # Check if client's ETag matches (304 Not Modified)
                    if if_none_match and if_none_match == etag:
                        not_modified = make_response('', 304)
                        not_modified.headers['ETag'] = etag
                        not_modified.headers['Cache-Control'] = 'no-cache'
                        return not_modified
                    
                    # ALWAYS add ETag header (fixes HEAD request issue)
                    response.headers['ETag'] = etag
                    response.headers['Cache-Control'] = 'no-cache'
            except Exception:
                pass
            
            return response
        else:
            data = response
            status_code = 200
        
        # Generate ETag from response data
        if hasattr(data, 'get_json'):
            # Flask Response object
            response_data = data.get_json()
        elif isinstance(data, dict):
            response_data = data
        else:
            # Can't generate ETag for non-JSON response
            return response
        
        etag = generate_etag(response_data)
        
        # Check if client's ETag matches
        if if_none_match and if_none_match == etag:
            # Return 304 Not Modified
            not_modified = make_response('', 304)
            not_modified.headers['ETag'] = etag
            not_modified.headers['Cache-Control'] = 'no-cache'
            return not_modified
        
        # Add ETag to response
        if isinstance(data, Response):
            data.headers['ETag'] = etag
            data.headers['Cache-Control'] = 'no-cache'
            return data
        else:
            # Create new response with ETag
            from flask import jsonify
            resp = make_response(jsonify(response_data) if isinstance(response_data, dict) else data, status_code)
            resp.headers['ETag'] = etag
            resp.headers['Cache-Control'] = 'no-cache'
            return resp
    
    return decorated_function


def compute_collection_etag(items: list, extra_data: Optional[dict] = None) -> str:
    """
    Compute ETag for a collection of items with optional metadata.
    
    Args:
        items: List of items (typically dicts from to_dict())
        extra_data: Optional extra data to include in ETag calculation
        
    Returns:
        str: ETag string
    """
    etag_data = {
        'items': items,
        'count': len(items)
    }
    
    if extra_data:
        etag_data.update(extra_data)
    
    return generate_etag(etag_data)
