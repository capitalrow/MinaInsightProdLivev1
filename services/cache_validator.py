"""
CacheValidator Service - Cache integrity and drift detection

Provides SHA-256 checksums, field-level delta comparison, and automatic
cache drift detection for IndexedDB synchronization.
"""

import hashlib
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class CacheValidator:
    """Service for validating cache integrity and detecting drift"""
    
    @staticmethod
    def generate_checksum(data: Dict[str, Any], exclude_fields: Optional[List[str]] = None) -> str:
        """
        Generate SHA-256 checksum for data object.
        
        Args:
            data: Dictionary to hash
            exclude_fields: Fields to exclude from checksum (e.g., timestamps)
            
        Returns:
            SHA-256 hex digest
        """
        if exclude_fields is None:
            exclude_fields = ['checksum', 'last_validated', '_cached_at']
        
        # Create copy and remove excluded fields
        clean_data = {k: v for k, v in data.items() if k not in exclude_fields}
        
        # Serialize to JSON with sorted keys for consistent hashing
        serialized = json.dumps(clean_data, sort_keys=True, default=str)
        
        # Generate SHA-256 hash
        checksum = hashlib.sha256(serialized.encode('utf-8')).hexdigest()
        
        return checksum
    
    @staticmethod
    def validate_checksum(data: Dict[str, Any], expected_checksum: str, 
                         exclude_fields: Optional[List[str]] = None) -> bool:
        """
        Validate data against expected checksum.
        
        Args:
            data: Dictionary to validate
            expected_checksum: Expected SHA-256 checksum
            exclude_fields: Fields to exclude from validation
            
        Returns:
            True if checksums match, False otherwise
        """
        actual_checksum = CacheValidator.generate_checksum(data, exclude_fields)
        is_valid = actual_checksum == expected_checksum
        
        if not is_valid:
            logger.warning(f"Checksum mismatch: expected={expected_checksum[:8]}..., actual={actual_checksum[:8]}...")
        
        return is_valid
    
    @staticmethod
    def detect_drift(cached_data: Dict[str, Any], server_data: Dict[str, Any], 
                     critical_fields: Optional[List[str]] = None) -> Tuple[bool, List[str]]:
        """
        Detect drift between cached and server data with field-level granularity.
        
        Args:
            cached_data: Data from IndexedDB cache
            server_data: Fresh data from server
            critical_fields: Fields that require strict equality (default: all)
            
        Returns:
            Tuple of (has_drift: bool, changed_fields: List[str])
        """
        changed_fields = []
        
        # If no critical fields specified, check all fields
        if critical_fields is None:
            critical_fields = list(set(list(cached_data.keys()) + list(server_data.keys())))
        
        # Compare each critical field
        for field in critical_fields:
            cached_value = cached_data.get(field)
            server_value = server_data.get(field)
            
            # Skip timestamp fields (allowed to drift)
            if field in ['last_validated', '_cached_at', 'checksum', 'updated_at']:
                continue
            
            # Compare values
            if cached_value != server_value:
                changed_fields.append(field)
                logger.debug(f"Drift detected in field '{field}': cached={cached_value}, server={server_value}")
        
        has_drift = len(changed_fields) > 0
        
        if has_drift:
            logger.info(f"Cache drift detected: {len(changed_fields)} fields changed: {changed_fields}")
        
        return has_drift, changed_fields
    
    @staticmethod
    def compute_delta(cached_data: Dict[str, Any], server_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute field-level delta between cached and server data.
        
        Args:
            cached_data: Data from IndexedDB cache
            server_data: Fresh data from server
            
        Returns:
            Dictionary containing only changed fields with new values
        """
        delta = {}
        
        # Find all fields present in either dataset
        all_fields = set(list(cached_data.keys()) + list(server_data.keys()))
        
        for field in all_fields:
            cached_value = cached_data.get(field)
            server_value = server_data.get(field)
            
            # Skip if values are equal
            if cached_value == server_value:
                continue
            
            # Field changed or added
            if field in server_data:
                delta[field] = server_value
            # Field removed (set to None)
            else:
                delta[field] = None
        
        return delta
    
    @staticmethod
    def should_invalidate_cache(cached_data: Dict[str, Any], 
                               max_age_seconds: int = 300) -> bool:
        """
        Determine if cache should be invalidated based on age.
        
        Args:
            cached_data: Data from IndexedDB cache
            max_age_seconds: Maximum cache age in seconds (default: 5 minutes)
            
        Returns:
            True if cache should be invalidated, False otherwise
        """
        if '_cached_at' not in cached_data:
            logger.warning("Cache data missing '_cached_at' timestamp, invalidating")
            return True
        
        try:
            cached_at = datetime.fromisoformat(cached_data['_cached_at'])
            age_seconds = (datetime.utcnow() - cached_at).total_seconds()
            
            should_invalidate = age_seconds > max_age_seconds
            
            if should_invalidate:
                logger.info(f"Cache expired: age={age_seconds:.1f}s > max_age={max_age_seconds}s")
            
            return should_invalidate
            
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid '_cached_at' timestamp: {e}")
            return True
    
    @staticmethod
    def reconcile_cache(cached_data: Dict[str, Any], 
                       server_data: Dict[str, Any],
                       strategy: str = 'server_wins') -> Dict[str, Any]:
        """
        Reconcile conflicting cache and server data.
        
        Args:
            cached_data: Data from IndexedDB cache
            server_data: Fresh data from server
            strategy: Reconciliation strategy ('server_wins', 'client_wins', 'merge')
            
        Returns:
            Reconciled data dictionary
        """
        if strategy == 'server_wins':
            # Server data takes precedence
            reconciled = {**cached_data, **server_data}
            reconciled['_reconciled_at'] = datetime.utcnow().isoformat()
            reconciled['_reconciliation_strategy'] = 'server_wins'
            return reconciled
        
        elif strategy == 'client_wins':
            # Client cache takes precedence
            reconciled = {**server_data, **cached_data}
            reconciled['_reconciled_at'] = datetime.utcnow().isoformat()
            reconciled['_reconciliation_strategy'] = 'client_wins'
            return reconciled
        
        elif strategy == 'merge':
            # Intelligent merge: newer values win per-field
            reconciled = {}
            all_fields = set(list(cached_data.keys()) + list(server_data.keys()))
            
            for field in all_fields:
                # Prefer server data for most fields
                if field in server_data:
                    reconciled[field] = server_data[field]
                else:
                    reconciled[field] = cached_data.get(field)
            
            reconciled['_reconciled_at'] = datetime.utcnow().isoformat()
            reconciled['_reconciliation_strategy'] = 'merge'
            return reconciled
        
        else:
            logger.error(f"Unknown reconciliation strategy: {strategy}, defaulting to server_wins")
            return CacheValidator.reconcile_cache(cached_data, server_data, strategy='server_wins')
    
    @staticmethod
    def validate_cache_batch(cached_items: List[Dict[str, Any]], 
                            server_items: List[Dict[str, Any]],
                            id_field: str = 'id') -> Dict[str, Any]:
        """
        Validate entire batch of cached items against server data.
        
        Args:
            cached_items: List of items from IndexedDB
            server_items: List of items from server
            id_field: Field to use for matching items (default: 'id')
            
        Returns:
            Dictionary with validation results and statistics
        """
        # Create lookup maps
        cached_map = {item[id_field]: item for item in cached_items if id_field in item}
        server_map = {item[id_field]: item for item in server_items if id_field in item}
        
        results = {
            'total_cached': len(cached_items),
            'total_server': len(server_items),
            'valid_items': 0,
            'drifted_items': 0,
            'missing_from_cache': 0,
            'stale_in_cache': 0,
            'drifted_fields': [],
            'items_to_update': [],
            'items_to_add': [],
            'items_to_remove': []
        }
        
        # Check items in cache
        for item_id, cached_item in cached_map.items():
            if item_id in server_map:
                server_item = server_map[item_id]
                has_drift, changed_fields = CacheValidator.detect_drift(cached_item, server_item)
                
                if has_drift:
                    results['drifted_items'] += 1
                    results['drifted_fields'].extend(changed_fields)
                    results['items_to_update'].append(server_item)
                else:
                    results['valid_items'] += 1
            else:
                # Item in cache but not on server (removed)
                results['stale_in_cache'] += 1
                results['items_to_remove'].append(item_id)
        
        # Check for new items on server
        for item_id, server_item in server_map.items():
            if item_id not in cached_map:
                results['missing_from_cache'] += 1
                results['items_to_add'].append(server_item)
        
        # Calculate drift percentage
        if results['total_cached'] > 0:
            results['drift_percentage'] = (results['drifted_items'] / results['total_cached']) * 100
        else:
            results['drift_percentage'] = 0.0
        
        logger.info(f"Batch validation: {results['valid_items']} valid, "
                   f"{results['drifted_items']} drifted, "
                   f"{results['missing_from_cache']} missing, "
                   f"{results['stale_in_cache']} stale")
        
        return results
    
    # =========================================================================
    # CROWN⁴.5: Automatic Silent Reconciliation
    # =========================================================================
    
    @staticmethod
    def auto_reconcile_batch(
        cached_items: List[Dict[str, Any]], 
        server_items: List[Dict[str, Any]],
        id_field: str = 'id',
        strategy: str = 'server_wins'
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Automatically reconcile cache drift and return reconciled items (CROWN⁴.5).
        
        This is the silent reconciliation method called during bootstrap and idle sync.
        Guarantees cache matches server truth.
        
        Args:
            cached_items: List of items from IndexedDB
            server_items: List of items from server
            id_field: Field to use for matching items
            strategy: Reconciliation strategy (default: 'server_wins')
            
        Returns:
            Tuple of (reconciled_items, reconciliation_stats)
            - reconciled_items: List of items after reconciliation
            - reconciliation_stats: Dictionary with reconciliation metrics
        """
        # Run validation to detect drift
        validation_results = CacheValidator.validate_cache_batch(
            cached_items, server_items, id_field
        )
        
        # Build reconciled dataset
        reconciled_items = []
        
        # Start with server items (server_wins strategy ensures server truth)
        server_map = {item[id_field]: item for item in server_items if id_field in item}
        reconciled_items = list(server_map.values())
        
        # Track reconciliation actions
        stats = {
            'total_items': len(reconciled_items),
            'items_added': validation_results['missing_from_cache'],
            'items_updated': validation_results['drifted_items'],
            'items_removed': validation_results['stale_in_cache'],
            'cache_hit_rate': (validation_results['valid_items'] / max(len(cached_items), 1)) * 100,
            'drift_detected': validation_results['drifted_items'] > 0,
            'reconciliation_strategy': strategy,
            'reconciled_at': datetime.utcnow().isoformat()
        }
        
        # Log reconciliation summary
        if stats['drift_detected']:
            logger.info(
                f"🔄 Cache reconciliation completed: "
                f"+{stats['items_added']} added, "
                f"~{stats['items_updated']} updated, "
                f"-{stats['items_removed']} removed, "
                f"cache_hit_rate={stats['cache_hit_rate']:.1f}%"
            )
        else:
            logger.debug(
                f"✅ Cache validated: no drift detected, "
                f"cache_hit_rate={stats['cache_hit_rate']:.1f}%"
            )
        
        return reconciled_items, stats
    
    @staticmethod
    def compute_cache_checksum(items: List[Dict[str, Any]], id_field: str = 'id') -> str:
        """
        Compute aggregate checksum for entire cache dataset (CROWN⁴.5).
        
        Used for fast drift detection: if aggregate checksum matches,
        no individual item validation needed.
        
        Args:
            items: List of cache items
            id_field: Field to use for stable ordering
            
        Returns:
            SHA-256 checksum of entire dataset
        """
        # Sort items by ID for stable ordering
        sorted_items = sorted(items, key=lambda x: x.get(id_field, 0))
        
        # Generate checksum for each item
        item_checksums = []
        for item in sorted_items:
            checksum = CacheValidator.generate_checksum(item)
            item_checksums.append(checksum)
        
        # Compute aggregate checksum
        aggregate_data = ''.join(item_checksums)
        aggregate_checksum = hashlib.sha256(aggregate_data.encode('utf-8')).hexdigest()
        
        return aggregate_checksum
    
    @staticmethod
    def validate_aggregate_checksum(
        cached_items: List[Dict[str, Any]], 
        server_checksum: str,
        id_field: str = 'id'
    ) -> bool:
        """
        Fast drift detection using aggregate checksum (CROWN⁴.5).
        
        If checksums match, skip individual item validation.
        If mismatch, perform full batch validation.
        
        Args:
            cached_items: List of items from IndexedDB
            server_checksum: Aggregate checksum from server
            id_field: Field to use for stable ordering
            
        Returns:
            True if cache matches server (no drift), False otherwise
        """
        cached_checksum = CacheValidator.compute_cache_checksum(cached_items, id_field)
        matches = cached_checksum == server_checksum
        
        if matches:
            logger.debug("✅ Aggregate checksum matches - cache is valid")
        else:
            logger.warning(
                f"⚠️ Aggregate checksum mismatch - cache drift detected. "
                f"cached={cached_checksum[:8]}..., server={server_checksum[:8]}..."
            )
        
        return matches


# Singleton instance
cache_validator = CacheValidator()
