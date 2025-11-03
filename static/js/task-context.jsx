/**
 * CROWN⁴.5 Task Context
 * React context for task state management with IndexedDB mirroring
 * 
 * Features:
 * - Cache-first <200ms bootstrap
 * - Optimistic UI updates
 * - Real-time WebSocket sync
 * - IndexedDB persistence
 * - Reactive state updates
 */

import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';

const TaskContext = createContext(null);

export function TaskProvider({ children, workspaceId, userId }) {
    // State
    const [tasks, setTasks] = useState([]);
    const [isBootstrapping, setIsBootstrapping] = useState(true);
    const [isConnected, setIsConnected] = useState(false);
    const [lastEventId, setLastEventId] = useState(null);
    const [error, setError] = useState(null);
    
    // Stats
    const [stats, setStats] = useState({
        total: 0,
        pending: 0,
        completed: 0,
        optimistic: 0
    });
    
    // Refs
    const taskStoreRef = useRef(null);
    const temporalEngineRef = useRef(null);
    const socketRef = useRef(null);
    const unsubscribeRef = useRef(null);
    
    /**
     * Initialize task store and bootstrap from cache
     */
    const bootstrap = useCallback(async () => {
        console.log('🚀 Bootstrapping task store...');
        const startTime = performance.now();
        
        try {
            // Wait for global services to be ready
            await waitForServices();
            
            // Initialize task store
            taskStoreRef.current = window.taskStore;
            temporalEngineRef.current = window.temporalRecoveryEngine;
            
            await taskStoreRef.current.init(userId);
            
            // Bootstrap from IndexedDB
            const result = await taskStoreRef.current.bootstrap();
            
            if (result.success) {
                const cachedTasks = taskStoreRef.current.getAllTasks();
                setTasks(cachedTasks);
                setLastEventId(result.last_event_id);
                updateStats(cachedTasks);
                
                const bootstrapTime = performance.now() - startTime;
                console.log(`✅ Bootstrap complete in ${Math.round(bootstrapTime)}ms`);
                console.log(`   Loaded ${result.count} tasks from cache`);
                
                // Report performance
                if (bootstrapTime > 200) {
                    console.warn(`⚠️ Bootstrap exceeded target: ${Math.round(bootstrapTime)}ms > 200ms`);
                }
            } else {
                throw new Error(result.error || 'Bootstrap failed');
            }
            
            // Subscribe to task store changes
            unsubscribeRef.current = taskStoreRef.current.subscribe(handleTaskStoreChange);
            
            // Initialize temporal recovery engine
            if (temporalEngineRef.current) {
                await temporalEngineRef.current.init(workspaceId, result.last_event_id);
            }
            
            setIsBootstrapping(false);
            
        } catch (err) {
            console.error('❌ Bootstrap failed:', err);
            setError(err.message);
            setIsBootstrapping(false);
        }
    }, [userId, workspaceId]);
    
    /**
     * Connect to WebSocket for real-time updates
     */
    const connectWebSocket = useCallback(() => {
        if (!workspaceId) return;
        
        console.log(`🔌 Connecting to WebSocket for workspace ${workspaceId}`);
        
        const socket = io({
            query: {
                workspace_id: workspaceId,
                last_event_id: lastEventId
            }
        });
        
        socket.on('connect', () => {
            console.log('✅ WebSocket connected');
            setIsConnected(true);
            
            // Subscribe to task events
            socket.emit('subscribe_tasks', { workspace_id: workspaceId });
        });
        
        socket.on('disconnect', () => {
            console.log('❌ WebSocket disconnected');
            setIsConnected(false);
        });
        
        // Task event handlers
        socket.on('task_create', handleTaskCreate);
        socket.on('task_update', handleTaskUpdate);
        socket.on('task_delete', handleTaskDelete);
        socket.on('tasks_sync', handleTasksSync);
        
        socketRef.current = socket;
        
        return () => {
            if (socketRef.current) {
                socketRef.current.disconnect();
                socketRef.current = null;
            }
        };
    }, [workspaceId, lastEventId]);
    
    /**
     * Handle task store changes
     */
    const handleTaskStoreChange = useCallback((event) => {
        console.log(`📣 Task store event: ${event.type}`);
        
        const currentTasks = taskStoreRef.current.getAllTasks();
        setTasks(currentTasks);
        updateStats(currentTasks);
        
        // Update last event ID if provided
        if (event.last_event_id) {
            setLastEventId(event.last_event_id);
        }
    }, []);
    
    /**
     * Handle incoming task create event
     */
    const handleTaskCreate = useCallback(async (data) => {
        console.log('📝 Received task_create event:', data.event_id);
        
        if (temporalEngineRef.current) {
            await temporalEngineRef.current.processEvent({
                event_id: data.event_id,
                workspace_sequence_num: data.workspace_sequence_num,
                vector_clock: data.vector_clock,
                event_type: 'task_create',
                data: data.task
            });
        }
    }, []);
    
    /**
     * Handle incoming task update event
     */
    const handleTaskUpdate = useCallback(async (data) => {
        console.log('✏️  Received task_update event:', data.event_id);
        
        if (temporalEngineRef.current) {
            await temporalEngineRef.current.processEvent({
                event_id: data.event_id,
                workspace_sequence_num: data.workspace_sequence_num,
                vector_clock: data.vector_clock,
                event_type: 'task_update',
                data: data.task
            });
        }
    }, []);
    
    /**
     * Handle incoming task delete event
     */
    const handleTaskDelete = useCallback(async (data) => {
        console.log('🗑️  Received task_delete event:', data.event_id);
        
        if (temporalEngineRef.current) {
            await temporalEngineRef.current.processEvent({
                event_id: data.event_id,
                workspace_sequence_num: data.workspace_sequence_num,
                vector_clock: data.vector_clock,
                event_type: 'task_delete',
                data: { id: data.task_id, deleted_at: data.deleted_at }
            });
        }
    }, []);
    
    /**
     * Handle full tasks sync event
     */
    const handleTasksSync = useCallback(async (data) => {
        console.log('🔄 Received tasks_sync event');
        
        if (taskStoreRef.current) {
            await taskStoreRef.current.syncWithServer(
                data.tasks,
                data.checksum,
                data.last_event_id
            );
        }
    }, []);
    
    /**
     * Update task statistics
     */
    const updateStats = useCallback((taskList) => {
        const pending = taskList.filter(t => t.status === 'pending' && !t.deleted_at).length;
        const completed = taskList.filter(t => t.status === 'completed' && !t.deleted_at).length;
        const optimistic = taskList.filter(t => t._optimistic_update).length;
        
        setStats({
            total: taskList.filter(t => !t.deleted_at).length,
            pending,
            completed,
            optimistic
        });
    }, []);
    
    /**
     * Create task optimistically
     */
    const createTask = useCallback(async (taskData) => {
        if (!taskStoreRef.current) return null;
        
        let provisionalTask = null;
        
        try {
            // Create optimistic task
            provisionalTask = await taskStoreRef.current.createTaskOptimistic({
                ...taskData,
                status: taskData.status || 'pending',
                created_at: new Date().toISOString()
            });
            
            // Send to server
            const response = await fetch('/api/tasks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ...taskData,
                    workspace_id: workspaceId,
                    provisional_id: provisionalTask.id
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to create task');
            }
            
            const { task: confirmedTask } = await response.json();
            
            // Confirm with server response
            await taskStoreRef.current.confirmTask(provisionalTask.id, confirmedTask);
            
            return confirmedTask;
            
        } catch (error) {
            console.error('Failed to create task:', error);
            
            // Rollback optimistic update if provisional task was created
            if (provisionalTask && taskStoreRef.current) {
                try {
                    await taskStoreRef.current.rollbackTask(provisionalTask.id, null);
                    console.log(`↩️  Rolled back provisional task ${provisionalTask.id}`);
                } catch (rollbackError) {
                    console.error('Failed to rollback provisional task:', rollbackError);
                    // Force remove from in-memory store
                    if (taskStoreRef.current.tasks.has(provisionalTask.id)) {
                        taskStoreRef.current.tasks.delete(provisionalTask.id);
                        // Trigger re-render
                        const currentTasks = taskStoreRef.current.getAllTasks();
                        setTasks(currentTasks);
                        updateStats(currentTasks);
                    }
                }
            }
            
            throw error;
        }
    }, [workspaceId, updateStats]);
    
    /**
     * Update task optimistically
     */
    const updateTask = useCallback(async (taskId, updates) => {
        if (!taskStoreRef.current) return null;
        
        const originalTask = taskStoreRef.current.getTask(taskId);
        if (!originalTask) {
            throw new Error(`Task ${taskId} not found`);
        }
        
        try {
            // Apply optimistic update
            const updated = await taskStoreRef.current.updateTaskOptimistic(taskId, updates);
            
            // Send to server
            const response = await fetch(`/api/tasks/${taskId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updates)
            });
            
            if (!response.ok) {
                throw new Error('Failed to update task');
            }
            
            const { task: confirmedTask } = await response.json();
            
            // Server will broadcast update via WebSocket
            return confirmedTask;
            
        } catch (error) {
            console.error('Failed to update task:', error);
            // Rollback optimistic update
            await taskStoreRef.current.rollbackTask(taskId, originalTask);
            throw error;
        }
    }, []);
    
    /**
     * Delete task (soft delete)
     */
    const deleteTask = useCallback(async (taskId) => {
        return updateTask(taskId, { deleted_at: new Date().toISOString() });
    }, [updateTask]);
    
    /**
     * Get filtered tasks
     */
    const getFilteredTasks = useCallback((filter = {}) => {
        if (!taskStoreRef.current) return [];
        return taskStoreRef.current.getFilteredTasks(filter);
    }, []);
    
    // Bootstrap on mount
    useEffect(() => {
        bootstrap();
        
        return () => {
            if (unsubscribeRef.current) {
                unsubscribeRef.current();
            }
        };
    }, [bootstrap]);
    
    // Connect WebSocket after bootstrap
    useEffect(() => {
        if (!isBootstrapping && workspaceId) {
            const cleanup = connectWebSocket();
            return cleanup;
        }
    }, [isBootstrapping, workspaceId, connectWebSocket]);
    
    const value = {
        tasks,
        stats,
        isBootstrapping,
        isConnected,
        error,
        lastEventId,
        createTask,
        updateTask,
        deleteTask,
        getFilteredTasks
    };
    
    return (
        <TaskContext.Provider value={value}>
            {children}
        </TaskContext.Provider>
    );
}

/**
 * Hook to use task context
 */
export function useTasks() {
    const context = useContext(TaskContext);
    if (!context) {
        throw new Error('useTasks must be used within TaskProvider');
    }
    return context;
}

/**
 * Wait for global services to be ready
 */
async function waitForServices() {
    const maxWait = 5000; // 5 seconds
    const start = Date.now();
    
    while (!window.taskStore || !window.cacheManager || !window.cacheValidator) {
        if (Date.now() - start > maxWait) {
            throw new Error('Timeout waiting for services');
        }
        await new Promise(resolve => setTimeout(resolve, 100));
    }
}
