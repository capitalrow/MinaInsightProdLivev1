/**
 * CROWN⁴.5 Delta Merger
 * 
 * Field-level conflict resolution for distributed state synchronization.
 * Server is authoritative based on (updated_at, actor_rank).
 * 
 * Key Features:
 * - Field-level granular merging
 * - Automatic conflict resolution
 * - Last-write-wins with timestamp authority
 * - Actor ranking for tie-breaking
 * - Merge metadata tracking
 */

class DeltaMerger {
    constructor() {
        this.actorRanks = {
            'server': 100,
            'ai_agent': 80,
            'user': 60,
            'batch_job': 40,
            'webhook': 20
        };
        
        this.stats = {
            merges: 0,
            conflicts: 0,
            resolutions: 0,
            fieldUpdates: 0
        };
        
        console.log('✅ DeltaMerger initialized');
    }
    
    /**
     * Merge remote changes into local state
     * @param {Object} local - Local object state
     * @param {Object} remote - Remote object state
     * @param {Object} options - Merge options {strategy, fields}
     * @returns {Object} {merged: Object, conflicts: Array, metadata: Object}
     */
    merge(local, remote, options = {}) {
        this.stats.merges++;
        
        const strategy = options.strategy || 'server_authoritative';
        const mergeableFields = options.fields || null; // null = all fields
        
        const result = {
            merged: { ...local },
            conflicts: [],
            metadata: {
                mergedAt: new Date().toISOString(),
                strategy: strategy,
                fieldsChanged: []
            }
        };
        
        // Identify all fields to merge
        const allFields = new Set([
            ...Object.keys(local || {}),
            ...Object.keys(remote || {})
        ]);
        
        for (const field of allFields) {
            // Skip if field is not in mergeable set
            if (mergeableFields && !mergeableFields.includes(field)) {
                continue;
            }
            
            // Skip system fields
            if (this.isSystemField(field)) {
                continue;
            }
            
            const localValue = local[field];
            const remoteValue = remote[field];
            
            // No conflict if values are the same
            if (this.valuesEqual(localValue, remoteValue)) {
                continue;
            }
            
            // Field only exists in one version
            if (localValue === undefined) {
                result.merged[field] = remoteValue;
                result.metadata.fieldsChanged.push({
                    field,
                    reason: 'added_remote',
                    oldValue: undefined,
                    newValue: remoteValue
                });
                this.stats.fieldUpdates++;
                continue;
            }
            
            if (remoteValue === undefined) {
                // Remote deleted field - keep or remove based on strategy
                if (strategy === 'server_authoritative') {
                    delete result.merged[field];
                    result.metadata.fieldsChanged.push({
                        field,
                        reason: 'deleted_remote',
                        oldValue: localValue,
                        newValue: undefined
                    });
                    this.stats.fieldUpdates++;
                }
                continue;
            }
            
            // Conflict detected - resolve
            const resolution = this.resolveConflict(
                field,
                localValue,
                remoteValue,
                local,
                remote,
                strategy
            );
            
            result.merged[field] = resolution.value;
            result.conflicts.push({
                field,
                localValue,
                remoteValue,
                resolution: resolution.reason,
                winner: resolution.winner
            });
            
            result.metadata.fieldsChanged.push({
                field,
                reason: resolution.reason,
                oldValue: localValue,
                newValue: resolution.value,
                conflict: true
            });
            
            this.stats.conflicts++;
            this.stats.resolutions++;
            this.stats.fieldUpdates++;
        }
        
        return result;
    }
    
    /**
     * Resolve conflict between local and remote values
     */
    resolveConflict(field, localValue, remoteValue, localObj, remoteObj, strategy) {
        // Strategy 1: Server authoritative (default)
        if (strategy === 'server_authoritative') {
            return {
                value: remoteValue,
                reason: 'server_wins',
                winner: 'remote'
            };
        }
        
        // Strategy 2: Last-write-wins using timestamps
        if (strategy === 'last_write_wins') {
            const localTime = new Date(localObj.updated_at || 0).getTime();
            const remoteTime = new Date(remoteObj.updated_at || 0).getTime();
            
            if (remoteTime > localTime) {
                return {
                    value: remoteValue,
                    reason: 'remote_newer',
                    winner: 'remote'
                };
            } else if (localTime > remoteTime) {
                return {
                    value: localValue,
                    reason: 'local_newer',
                    winner: 'local'
                };
            } else {
                // Timestamps equal - use actor rank
                return this.resolveByActorRank(localValue, remoteValue, localObj, remoteObj);
            }
        }
        
        // Strategy 3: Actor rank based
        if (strategy === 'actor_rank') {
            return this.resolveByActorRank(localValue, remoteValue, localObj, remoteObj);
        }
        
        // Strategy 4: Field-specific merge (for arrays, objects)
        if (strategy === 'field_merge' && field === 'labels') {
            // Merge arrays by combining unique values
            const merged = this.mergeArrays(localValue, remoteValue);
            return {
                value: merged,
                reason: 'array_merged',
                winner: 'both'
            };
        }
        
        // Default: Remote wins
        return {
            value: remoteValue,
            reason: 'default_remote',
            winner: 'remote'
        };
    }
    
    /**
     * Resolve using actor rank (higher rank wins)
     */
    resolveByActorRank(localValue, remoteValue, localObj, remoteObj) {
        const localActor = localObj.actor || 'user';
        const remoteActor = remoteObj.actor || 'server';
        
        const localRank = this.actorRanks[localActor] || 50;
        const remoteRank = this.actorRanks[remoteActor] || 50;
        
        if (remoteRank > localRank) {
            return {
                value: remoteValue,
                reason: `remote_actor_rank_${remoteActor}`,
                winner: 'remote'
            };
        } else {
            return {
                value: localValue,
                reason: `local_actor_rank_${localActor}`,
                winner: 'local'
            };
        }
    }
    
    /**
     * Merge two arrays by combining unique elements
     */
    mergeArrays(arr1, arr2) {
        if (!Array.isArray(arr1)) arr1 = [];
        if (!Array.isArray(arr2)) arr2 = [];
        
        // Use Set for primitives, manual dedup for objects
        if (arr1.length === 0) return [...arr2];
        if (arr2.length === 0) return [...arr1];
        
        if (typeof arr1[0] === 'object') {
            // Object array - dedupe by id
            const merged = [...arr1];
            const ids = new Set(arr1.map(item => item.id).filter(Boolean));
            
            for (const item of arr2) {
                if (!item.id || !ids.has(item.id)) {
                    merged.push(item);
                    if (item.id) ids.add(item.id);
                }
            }
            return merged;
        } else {
            // Primitive array - use Set
            return Array.from(new Set([...arr1, ...arr2]));
        }
    }
    
    /**
     * Check if field is a system field (not user-editable)
     */
    isSystemField(field) {
        const systemFields = [
            'id',
            'created_at',
            'created_by_id',
            'workspace_id',
            'meeting_id',
            'event_id',
            'sequence_num',
            'vector_clock',
            'checksum'
        ];
        return systemFields.includes(field);
    }
    
    /**
     * Deep equality check for values
     */
    valuesEqual(a, b) {
        if (a === b) return true;
        if (a == null || b == null) return a === b;
        if (typeof a !== typeof b) return false;
        
        if (Array.isArray(a) && Array.isArray(b)) {
            if (a.length !== b.length) return false;
            return a.every((val, idx) => this.valuesEqual(val, b[idx]));
        }
        
        if (typeof a === 'object' && typeof b === 'object') {
            const keysA = Object.keys(a);
            const keysB = Object.keys(b);
            if (keysA.length !== keysB.length) return false;
            return keysA.every(key => this.valuesEqual(a[key], b[key]));
        }
        
        return false;
    }
    
    /**
     * Batch merge multiple objects
     * @param {Array} localObjects - Array of local objects
     * @param {Array} remoteObjects - Array of remote objects
     * @param {Function} getKey - Function to get unique key from object (default: obj => obj.id)
     * @returns {Object} {merged: Array, stats: Object}
     */
    batchMerge(localObjects, remoteObjects, getKey = obj => obj.id) {
        const localMap = new Map(localObjects.map(obj => [getKey(obj), obj]));
        const remoteMap = new Map(remoteObjects.map(obj => [getKey(obj), obj]));
        
        const merged = [];
        const allKeys = new Set([...localMap.keys(), ...remoteMap.keys()]);
        
        let additions = 0;
        let updates = 0;
        let deletions = 0;
        const conflicts = [];
        
        for (const key of allKeys) {
            const local = localMap.get(key);
            const remote = remoteMap.get(key);
            
            if (!local && remote) {
                // New object from remote
                merged.push(remote);
                additions++;
            } else if (local && !remote) {
                // Object deleted on remote (skip it)
                deletions++;
            } else {
                // Merge existing object
                const result = this.merge(local, remote);
                merged.push(result.merged);
                if (result.conflicts.length > 0) {
                    updates++;
                    conflicts.push({ key, conflicts: result.conflicts });
                }
            }
        }
        
        return {
            merged,
            stats: {
                total: merged.length,
                additions,
                updates,
                deletions,
                conflicts: conflicts.length
            },
            conflicts
        };
    }
    
    /**
     * Get merge statistics
     */
    getStats() {
        return { ...this.stats };
    }
    
    /**
     * Reset statistics
     */
    resetStats() {
        this.stats = {
            merges: 0,
            conflicts: 0,
            resolutions: 0,
            fieldUpdates: 0
        };
    }
}

// Global instance
window.TaskDeltaMerger = new DeltaMerger();

console.log('✅ CROWN⁴.5 DeltaMerger loaded');
