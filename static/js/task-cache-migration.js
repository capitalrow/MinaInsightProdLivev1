/**
 * CROWN⁴.5 Cache Migration System
 * Handles backward compatibility and cleans corrupted cache data on first load.
 * Ensures smooth upgrades for existing users.
 */

class CacheMigrationManager {
    constructor() {
        this.currentSchemaVersion = 3;  // CROWN⁴.5 schema version
        this.versionKey = 'mina_cache_schema_version';
        this.migrationKey = 'mina_last_migration';
        this.migrations = this._defineMigrations();
        
        console.log('✅ Cache Migration Manager initialized');
    }
    
    /**
     * Define all migrations
     * @returns {Array} Migration definitions
     */
    _defineMigrations() {
        return [
            {
                version: 1,
                name: 'initial_schema',
                description: 'Create initial IndexedDB schema',
                migrate: async (db) => {
                    console.log('🔄 Migration 1: Initial schema - already handled by IndexedDB upgrade');
                    return true;
                }
            },
            {
                version: 2,
                name: 'add_vector_clocks',
                description: 'Add vector clock support to events and tasks',
                migrate: async (db) => {
                    console.log('🔄 Migration 2: Adding vector clock support');
                    
                    // Clean tasks with invalid vector clocks
                    const tasks = await this._getAllFromStore(db, 'tasks');
                    let cleaned = 0;
                    
                    for (const task of tasks) {
                        if (task.vector_clock && !Array.isArray(task.vector_clock)) {
                            // Invalid vector clock - remove it
                            delete task.vector_clock;
                            cleaned++;
                        }
                    }
                    
                    console.log(`✅ Migration 2 complete: cleaned ${cleaned} invalid vector clocks`);
                    return true;
                }
            },
            {
                version: 3,
                name: 'crown45_reconciliation',
                description: 'Add CROWN⁴.5 reconciliation fields and clean orphaned temp IDs',
                migrate: async (db) => {
                    console.log('🔄 Migration 3: CROWN⁴.5 reconciliation cleanup');
                    
                    const tasks = await this._getAllFromStore(db, 'tasks');
                    const now = Date.now();
                    const orphanThreshold = 24 * 60 * 60 * 1000;  // 24 hours
                    
                    let orphanedTempIds = 0;
                    let corruptedTasks = 0;
                    let fixedTasks = 0;
                    
                    const tx = db.transaction(['tasks'], 'readwrite');
                    const store = tx.objectStore('tasks');
                    
                    for (const task of tasks) {
                        let shouldDelete = false;
                        let shouldUpdate = false;
                        
                        // 1. Clean orphaned temp IDs (older than 24h)
                        if (task.id && typeof task.id === 'string' && task.id.startsWith('temp_')) {
                            const createdAt = new Date(task.created_at || 0).getTime();
                            const age = now - createdAt;
                            
                            if (age > orphanThreshold) {
                                shouldDelete = true;
                                orphanedTempIds++;
                            }
                        }
                        
                        // 2. Clean tasks with missing required fields
                        if (!task.id || !task.created_at) {
                            shouldDelete = true;
                            corruptedTasks++;
                        }
                        
                        // 3. Fix tasks with invalid status
                        if (task.status && !['todo', 'in_progress', 'completed', 'archived'].includes(task.status)) {
                            task.status = 'todo';
                            shouldUpdate = true;
                            fixedTasks++;
                        }
                        
                        // 4. Remove internal cache fields that shouldn't be persisted
                        const internalFields = ['_checksum', '_cached_at', '_reconciliation_strategy'];
                        let hadInternalFields = false;
                        for (const field of internalFields) {
                            if (task[field]) {
                                delete task[field];
                                hadInternalFields = true;
                            }
                        }
                        if (hadInternalFields) {
                            shouldUpdate = true;
                        }
                        
                        // Apply changes
                        if (shouldDelete) {
                            store.delete(task.id);
                        } else if (shouldUpdate) {
                            store.put(task);
                        }
                    }
                    
                    await new Promise((resolve, reject) => {
                        tx.oncomplete = () => resolve();
                        tx.onerror = () => reject(tx.error);
                    });
                    
                    console.log(`✅ Migration 3 complete:`);
                    console.log(`   - Removed ${orphanedTempIds} orphaned temp IDs`);
                    console.log(`   - Removed ${corruptedTasks} corrupted tasks`);
                    console.log(`   - Fixed ${fixedTasks} tasks with invalid data`);
                    
                    return true;
                }
            }
        ];
    }
    
    /**
     * Check if migration is needed and run it
     * @param {IDBDatabase} db - IndexedDB instance
     * @returns {Promise<Object>} Migration result
     */
    async runMigrations(db) {
        const startTime = performance.now();
        
        try {
            // Get current schema version from localStorage
            const storedVersion = parseInt(localStorage.getItem(this.versionKey) || '0');
            const lastMigration = localStorage.getItem(this.migrationKey);
            
            console.log(`📊 Current schema version: ${storedVersion}, target: ${this.currentSchemaVersion}`);
            
            if (storedVersion >= this.currentSchemaVersion) {
                console.log('✅ Schema is up to date, no migration needed');
                return {
                    migrated: false,
                    reason: 'up_to_date',
                    current_version: this.currentSchemaVersion
                };
            }
            
            // Run migrations in sequence
            const results = [];
            for (const migration of this.migrations) {
                if (migration.version > storedVersion) {
                    console.log(`🔄 Running migration ${migration.version}: ${migration.name}`);
                    console.log(`   ${migration.description}`);
                    
                    try {
                        const success = await migration.migrate(db);
                        results.push({
                            version: migration.version,
                            name: migration.name,
                            success
                        });
                    } catch (error) {
                        console.error(`❌ Migration ${migration.version} failed:`, error);
                        results.push({
                            version: migration.version,
                            name: migration.name,
                            success: false,
                            error: error.message
                        });
                        
                        // Stop on first failure
                        break;
                    }
                }
            }
            
            // Update schema version
            localStorage.setItem(this.versionKey, this.currentSchemaVersion.toString());
            localStorage.setItem(this.migrationKey, new Date().toISOString());
            
            const migrationTime = Math.round(performance.now() - startTime);
            console.log(`✅ All migrations complete in ${migrationTime}ms`);
            
            return {
                migrated: true,
                from_version: storedVersion,
                to_version: this.currentSchemaVersion,
                migrations: results,
                migration_time_ms: migrationTime
            };
            
        } catch (error) {
            console.error('❌ Migration failed:', error);
            return {
                migrated: false,
                error: error.message
            };
        }
    }
    
    /**
     * Clean all corrupted data (emergency reset)
     * @param {IDBDatabase} db - IndexedDB instance
     * @returns {Promise<Object>} Cleanup result
     */
    async emergencyCleanup(db) {
        console.warn('⚠️ Running emergency cleanup - this will remove all corrupted data');
        
        const startTime = performance.now();
        const stats = {
            tasks_removed: 0,
            events_removed: 0,
            queue_removed: 0
        };
        
        try {
            // Clean tasks
            const tasks = await this._getAllFromStore(db, 'tasks');
            const tx1 = db.transaction(['tasks'], 'readwrite');
            const taskStore = tx1.objectStore('tasks');
            
            for (const task of tasks) {
                const isCorrupted = !task.id || !task.created_at || 
                                   (typeof task.id === 'string' && task.id.startsWith('temp_'));
                
                if (isCorrupted) {
                    taskStore.delete(task.id);
                    stats.tasks_removed++;
                }
            }
            
            await new Promise((resolve, reject) => {
                tx1.oncomplete = () => resolve();
                tx1.onerror = () => reject(tx1.error);
            });
            
            // Clean events
            const events = await this._getAllFromStore(db, 'events');
            const tx2 = db.transaction(['events'], 'readwrite');
            const eventStore = tx2.objectStore('events');
            
            for (const event of events) {
                const age = Date.now() - event.timestamp;
                if (age > 7 * 24 * 60 * 60 * 1000) {  // Older than 7 days
                    eventStore.delete(event.id);
                    stats.events_removed++;
                }
            }
            
            await new Promise((resolve, reject) => {
                tx2.oncomplete = () => resolve();
                tx2.onerror = () => reject(tx2.error);
            });
            
            const cleanupTime = Math.round(performance.now() - startTime);
            console.log(`✅ Emergency cleanup complete in ${cleanupTime}ms:`, stats);
            
            return {
                success: true,
                stats,
                cleanup_time_ms: cleanupTime
            };
            
        } catch (error) {
            console.error('❌ Emergency cleanup failed:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }
    
    /**
     * Get all records from a store
     * @private
     */
    async _getAllFromStore(db, storeName) {
        return new Promise((resolve, reject) => {
            const tx = db.transaction([storeName], 'readonly');
            const store = tx.objectStore(storeName);
            const request = store.getAll();
            
            request.onsuccess = () => resolve(request.result || []);
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * Reset schema version (for testing)
     */
    resetSchemaVersion() {
        localStorage.removeItem(this.versionKey);
        localStorage.removeItem(this.migrationKey);
        console.log('🔄 Schema version reset');
    }
    
    /**
     * Get migration status
     * @returns {Object} Status
     */
    getStatus() {
        return {
            current_version: parseInt(localStorage.getItem(this.versionKey) || '0'),
            target_version: this.currentSchemaVersion,
            last_migration: localStorage.getItem(this.migrationKey),
            needs_migration: parseInt(localStorage.getItem(this.versionKey) || '0') < this.currentSchemaVersion
        };
    }
}

// Export singleton
window.cacheMigration = new CacheMigrationManager();

console.log('🔄 CROWN⁴.5 Cache Migration System loaded');
