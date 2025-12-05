/**
 * ADVANCED ERROR RECOVERY SYSTEM
 * Comprehensive error handling and automatic recovery mechanisms
 */

class AdvancedErrorRecovery {
    static _instance = null;
    static _initialized = false;
    
    constructor() {
        if (AdvancedErrorRecovery._instance) {
            return AdvancedErrorRecovery._instance;
        }
        
        this.isActive = false;
        this.errorHistory = [];
        this.recoveryStrategies = new Map();
        this.autoRecoveryEnabled = true;
        this.maxRetryAttempts = 3;
        this.backoffMultiplier = 1.5;
        this.healthMonitorInterval = null;
        this.performanceMonitorInterval = null;
        
        this.systemState = {
            audioSystem: 'unknown',
            transcriptionSystem: 'unknown',
            networkConnection: 'unknown',
            enhancementSystems: 'unknown'
        };
        
        this.setupRecoveryStrategies();
        this.setupErrorPatterns();
        
        AdvancedErrorRecovery._instance = this;
    }
    
    initialize() {
        if (AdvancedErrorRecovery._initialized) {
            console.log('🛡️ Advanced Error Recovery System already initialized');
            return true;
        }
        
        console.log('🛡️ Initializing Advanced Error Recovery System');
        
        this.setupGlobalErrorHandlers();
        this.startHealthMonitoring();
        this.isActive = true;
        AdvancedErrorRecovery._initialized = true;
        
        console.log('✅ Error recovery system active');
        return true;
    }
    
    setupRecoveryStrategies() {
        // Audio system recovery strategies
        this.recoveryStrategies.set('microphone_access_denied', {
            priority: 'high',
            autoRecover: true,
            strategy: this.recoverMicrophoneAccess.bind(this),
            userMessage: 'Microphone access needed. Please allow microphone permissions.',
            timeout: 5000
        });
        
        this.recoveryStrategies.set('audio_context_suspended', {
            priority: 'high',
            autoRecover: true,
            strategy: this.recoverAudioContext.bind(this),
            userMessage: 'Audio system suspended. Attempting to resume...',
            timeout: 3000
        });
        
        this.recoveryStrategies.set('media_recorder_error', {
            priority: 'high',
            autoRecover: true,
            strategy: this.recoverMediaRecorder.bind(this),
            userMessage: 'Recording error detected. Restarting audio system...',
            timeout: 5000
        });
        
        // Network recovery strategies
        this.recoveryStrategies.set('network_disconnected', {
            priority: 'critical',
            autoRecover: true,
            strategy: this.recoverNetworkConnection.bind(this),
            userMessage: 'Connection lost. Attempting to reconnect...',
            timeout: 10000
        });
        
        this.recoveryStrategies.set('api_timeout', {
            priority: 'medium',
            autoRecover: true,
            strategy: this.recoverApiTimeout.bind(this),
            userMessage: 'API response timeout. Retrying with optimized settings...',
            timeout: 8000
        });
        
        // Transcription system recovery
        this.recoveryStrategies.set('transcription_service_error', {
            priority: 'high',
            autoRecover: true,
            strategy: this.recoverTranscriptionService.bind(this),
            userMessage: 'Transcription service error. Switching to backup system...',
            timeout: 7000
        });
        
        this.recoveryStrategies.set('low_confidence_streak', {
            priority: 'medium',
            autoRecover: true,
            strategy: this.recoverLowConfidence.bind(this),
            userMessage: 'Audio quality issues detected. Optimizing settings...',
            timeout: 3000
        });
        
        // System resource recovery
        this.recoveryStrategies.set('memory_pressure', {
            priority: 'medium',
            autoRecover: true,
            strategy: this.recoverMemoryPressure.bind(this),
            userMessage: 'Optimizing memory usage...',
            timeout: 5000
        });
        
        this.recoveryStrategies.set('performance_degradation', {
            priority: 'low',
            autoRecover: true,
            strategy: this.recoverPerformance.bind(this),
            userMessage: 'Performance optimization in progress...',
            timeout: 4000
        });
    }
    
    setupErrorPatterns() {
        this.errorPatterns = [
            {
                pattern: /microphone|permission|notallowed/i,
                errorType: 'microphone_access_denied'
            },
            {
                pattern: /suspended|audio.*context/i,
                errorType: 'audio_context_suspended'
            },
            {
                pattern: /mediarecorder|recording.*error/i,
                errorType: 'media_recorder_error'
            },
            {
                pattern: /network|connection|disconnect/i,
                errorType: 'network_disconnected'
            },
            {
                pattern: /timeout|timed.*out/i,
                errorType: 'api_timeout'
            },
            {
                pattern: /transcription.*error|whisper.*error/i,
                errorType: 'transcription_service_error'
            },
            {
                pattern: /memory|heap|out.*of.*memory/i,
                errorType: 'memory_pressure'
            }
        ];
    }
    
    setupGlobalErrorHandlers() {
        // Capture JavaScript errors
        window.addEventListener('error', (event) => {
            this.handleError({
                type: 'javascript_error',
                message: event.message,
                filename: event.filename,
                lineno: event.lineno,
                error: event.error
            });
        });
        
        // Capture unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            this.handleError({
                type: 'promise_rejection',
                message: event.reason?.message || 'Unhandled promise rejection',
                error: event.reason
            });
        });
        
        // Capture MediaRecorder errors
        if (window.minaTranscriptionFix && window.minaTranscriptionFix.mediaRecorder) {
            const originalOnError = window.minaTranscriptionFix.mediaRecorder.onerror;
            window.minaTranscriptionFix.mediaRecorder.onerror = (event) => {
                this.handleError({
                    type: 'media_recorder_error',
                    message: 'MediaRecorder error occurred',
                    error: event.error
                });
                if (originalOnError) originalOnError.call(this, event);
            };
        }
    }
    
    startHealthMonitoring() {
        // Clear any existing intervals to prevent duplicates
        if (this.healthMonitorInterval) {
            clearInterval(this.healthMonitorInterval);
            this.healthMonitorInterval = null;
        }
        if (this.performanceMonitorInterval) {
            clearInterval(this.performanceMonitorInterval);
            this.performanceMonitorInterval = null;
        }
        
        // 🔥 OPTIMIZED: Reduced monitoring frequency to prevent spam
        // Monitor system health every 10 seconds (was 2 seconds)
        this.healthMonitorInterval = setInterval(() => {
            this.checkSystemHealth();
        }, 10000);
        
        // Monitor performance metrics every 30 seconds (was 5 seconds)
        // Prevents constant memory pressure alerts
        this.performanceMonitorInterval = setInterval(() => {
            this.checkPerformanceHealth();
        }, 30000);
    }
    
    handleError(errorInfo) {
        if (!this.isActive) return;
        
        console.log('🚨 Error detected:', errorInfo);
        
        // Add to error history
        const errorRecord = {
            timestamp: Date.now(),
            ...errorInfo,
            id: this.generateErrorId()
        };
        
        this.errorHistory.push(errorRecord);
        
        // Keep history bounded
        if (this.errorHistory.length > 50) {
            this.errorHistory.shift();
        }
        
        // Classify error type
        const errorType = this.classifyError(errorInfo);
        
        // Attempt recovery if enabled
        if (this.autoRecoveryEnabled && errorType) {
            this.attemptRecovery(errorType, errorRecord);
        }
        
        // Update system state
        this.updateSystemState(errorType, 'error');
        
        // Broadcast error event
        this.broadcastErrorEvent(errorRecord, errorType);
    }
    
    classifyError(errorInfo) {
        const errorMessage = (errorInfo.message || '').toLowerCase();
        
        for (const pattern of this.errorPatterns) {
            if (pattern.pattern.test(errorMessage)) {
                return pattern.errorType;
            }
        }
        
        // Default classification based on type
        if (errorInfo.type === 'media_recorder_error') return 'media_recorder_error';
        if (errorInfo.type === 'network_error') return 'network_disconnected';
        
        return 'unknown_error';
    }
    
    async attemptRecovery(errorType, errorRecord) {
        const strategy = this.recoveryStrategies.get(errorType);
        
        if (!strategy) {
            console.warn(`⚠️ No recovery strategy for error type: ${errorType}`);
            return false;
        }
        
        console.log(`🔧 Attempting recovery for: ${errorType}`);
        
        // Show user message if available
        if (strategy.userMessage) {
            this.showRecoveryMessage(strategy.userMessage);
        }
        
        try {
            // Set timeout for recovery attempt
            const recoveryPromise = strategy.strategy(errorRecord);
            const timeoutPromise = new Promise((_, reject) => 
                setTimeout(() => reject(new Error('Recovery timeout')), strategy.timeout)
            );
            
            const success = await Promise.race([recoveryPromise, timeoutPromise]);
            
            if (success) {
                console.log(`✅ Recovery successful for: ${errorType}`);
                this.logRecoverySuccess(errorType, errorRecord);
                this.updateSystemState(errorType, 'recovered');
                return true;
            } else {
                console.error(`❌ Recovery failed for: ${errorType}`);
                this.logRecoveryFailure(errorType, errorRecord);
                return false;
            }
            
        } catch (error) {
            console.error(`❌ Recovery error for ${errorType}:`, error);
            this.logRecoveryFailure(errorType, errorRecord, error);
            return false;
        }
    }
    
    // Recovery strategy implementations
    async recoverMicrophoneAccess(errorRecord) {
        try {
            // Request microphone permission again
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            
            // If successful, reinitialize audio system
            if (window.minaTranscriptionFix) {
                await window.minaTranscriptionFix.setupAudioRecording();
            }
            
            // Close the test stream
            stream.getTracks().forEach(track => track.stop());
            
            return true;
        } catch (error) {
            return false;
        }
    }
    
    async recoverAudioContext(errorRecord) {
        try {
            // Resume suspended audio context
            if (window.enhancedSystemIntegration?.audioOptimizer?.audioContext) {
                await window.enhancedSystemIntegration.audioOptimizer.audioContext.resume();
                return true;
            }
            
            // Try to create new audio context
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            if (audioContext.state === 'running' || audioContext.state === 'suspended') {
                if (audioContext.state === 'suspended') {
                    await audioContext.resume();
                }
                return true;
            }
            
            return false;
        } catch (error) {
            return false;
        }
    }
    
    async recoverMediaRecorder(errorRecord) {
        try {
            // Stop current recorder if it exists
            if (window.minaTranscriptionFix?.mediaRecorder) {
                try {
                    window.minaTranscriptionFix.mediaRecorder.stop();
                } catch (e) {
                    // Ignore stop errors
                }
            }
            
            // Wait a moment before restarting
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            // Reinitialize audio recording
            if (window.minaTranscriptionFix) {
                return await window.minaTranscriptionFix.setupAudioRecording();
            }
            
            return false;
        } catch (error) {
            return false;
        }
    }
    
    async recoverNetworkConnection(errorRecord) {
        try {
            // Test network connectivity
            const response = await fetch('/api/ping', { 
                method: 'GET',
                timeout: 5000 
            });
            
            if (response.ok) {
                // Network is back, reinitialize connections
                if (window.socket && !window.socket.connected) {
                    window.socket.connect();
                }
                
                return true;
            }
            
            return false;
        } catch (error) {
            return false;
        }
    }
    
    async recoverApiTimeout(errorRecord) {
        try {
            // Reduce chunk size for faster processing
            if (window.performanceOptimizer) {
                window.performanceOptimizer.optimizations.chunkSize = Math.max(
                    window.performanceOptimizer.optimizations.chunkSize * 0.7,
                    1000
                );
            }
            
            // Reduce concurrent processing
            if (window.performanceOptimizer) {
                window.performanceOptimizer.optimizations.maxConcurrent = Math.max(
                    window.performanceOptimizer.optimizations.maxConcurrent - 1,
                    1
                );
            }
            
            return true;
        } catch (error) {
            return false;
        }
    }
    
    async recoverTranscriptionService(errorRecord) {
        try {
            // Switch to HTTP fallback if using WebSocket
            if (window.httpTranscriptionFallback) {
                window.httpTranscriptionFallback.forceHttpMode = true;
                return true;
            }
            
            return false;
        } catch (error) {
            return false;
        }
    }
    
    async recoverLowConfidence(errorRecord) {
        try {
            // Increase audio quality filtering
            if (window.enhancedSystemIntegration?.audioOptimizer) {
                const optimizer = window.enhancedSystemIntegration.audioOptimizer;
                
                // Tighten noise gate
                if (optimizer.filters?.noiseGate) {
                    optimizer.filters.noiseGate.gain.setValueAtTime(0.8, optimizer.audioContext.currentTime);
                }
                
                // Increase compression
                if (optimizer.filters?.compressor) {
                    optimizer.filters.compressor.ratio.setValueAtTime(4, optimizer.audioContext.currentTime);
                }
            }
            
            return true;
        } catch (error) {
            return false;
        }
    }
    
    async recoverMemoryPressure(errorRecord) {
        try {
            // Reduce buffer sizes
            if (window.performanceOptimizer) {
                window.performanceOptimizer.optimizations.bufferSize = Math.max(
                    window.performanceOptimizer.optimizations.bufferSize - 1,
                    1
                );
            }
            
            // Clear old history
            if (window.transcriptDisplayFix) {
                // Keep only recent segments
                const container = document.getElementById('transcriptContainer');
                if (container && container.children.length > 10) {
                    Array.from(container.children).slice(0, -5).forEach(child => child.remove());
                }
            }
            
            // Garbage collection hint
            if (window.gc) {
                window.gc();
            }
            
            return true;
        } catch (error) {
            return false;
        }
    }
    
    async recoverPerformance(errorRecord) {
        try {
            // Optimize processing parameters
            if (window.performanceOptimizer) {
                const optimizer = window.performanceOptimizer;
                
                // Reduce chunk size for lower latency
                optimizer.optimizations.chunkSize = Math.max(
                    optimizer.optimizations.chunkSize * 0.9,
                    1000
                );
                
                // Reduce concurrent processing if overloaded
                if (optimizer.currentLoad > 0.8) {
                    optimizer.optimizations.maxConcurrent = Math.max(
                        optimizer.optimizations.maxConcurrent - 1,
                        1
                    );
                }
            }
            
            return true;
        } catch (error) {
            return false;
        }
    }
    
    checkSystemHealth() {
        // Check audio system health
        this.checkAudioSystemHealth();
        
        // Check network health
        this.checkNetworkHealth();
        
        // Check transcription system health
        this.checkTranscriptionHealth();
    }
    
    checkAudioSystemHealth() {
        try {
            // Check if MediaRecorder is working
            if (window.minaTranscriptionFix?.mediaRecorder) {
                const recorder = window.minaTranscriptionFix.mediaRecorder;
                if (recorder.state === 'inactive' && window.minaTranscriptionFix.isRecording) {
                    this.handleError({
                        type: 'media_recorder_error',
                        message: 'MediaRecorder unexpectedly inactive'
                    });
                }
            }
            
            // Check audio context
            if (window.enhancedSystemIntegration?.audioOptimizer?.audioContext) {
                const context = window.enhancedSystemIntegration.audioOptimizer.audioContext;
                if (context.state === 'suspended') {
                    this.handleError({
                        type: 'audio_context_suspended',
                        message: 'Audio context suspended'
                    });
                }
            }
            
            this.systemState.audioSystem = 'healthy';
        } catch (error) {
            this.systemState.audioSystem = 'error';
        }
    }
    
    checkNetworkHealth() {
        // This would be implemented with periodic ping checks
        // For now, assume healthy unless we detect issues
        this.systemState.networkConnection = 'healthy';
    }
    
    checkTranscriptionHealth() {
        // Check for repeated low confidence scores
        const recentHistory = this.errorHistory.slice(-5);
        const lowConfidenceCount = recentHistory.filter(error => 
            error.type === 'low_confidence' || error.message?.includes('confidence')
        ).length;
        
        if (lowConfidenceCount >= 3) {
            this.handleError({
                type: 'low_confidence_streak',
                message: 'Repeated low confidence transcriptions detected'
            });
        }
        
        this.systemState.transcriptionSystem = 'healthy';
    }
    
    checkPerformanceHealth() {
        // 🔥 OPTIMIZED: Memory usage monitoring with realistic thresholds
        if (performance.memory) {
            const memoryUsage = performance.memory.usedJSHeapSize / performance.memory.totalJSHeapSize;
            
            // 🔥 CRITICAL FIX: Increased threshold to prevent false alarms
            // Only trigger at truly critical memory levels (95%+)
            if (memoryUsage > 0.95) {  // Changed from 0.85 to 0.95
                this.handleError({
                    type: 'memory_pressure',
                    message: `Critical memory usage: ${Math.round(memoryUsage * 100)}%`
                });
            }
        }
    }
    
    showRecoveryMessage(message) {
        // Show user-friendly recovery message
        if (window.showNotification) {
            window.showNotification(message, 'info', 3000);
        } else {
            console.log(`🔧 ${message}`);
        }
    }
    
    logRecoverySuccess(errorType, errorRecord) {
        console.log(`✅ Recovery successful: ${errorType}`);
        
        // Update error record
        errorRecord.recoveryAttempted = true;
        errorRecord.recoverySuccessful = true;
        errorRecord.recoveryTime = Date.now();
    }
    
    logRecoveryFailure(errorType, errorRecord, error = null) {
        console.error(`❌ Recovery failed: ${errorType}`, error);
        
        // Update error record
        errorRecord.recoveryAttempted = true;
        errorRecord.recoverySuccessful = false;
        errorRecord.recoveryTime = Date.now();
        errorRecord.recoveryError = error?.message;
    }
    
    updateSystemState(errorType, status) {
        // Map error types to system components
        const componentMap = {
            'microphone_access_denied': 'audioSystem',
            'audio_context_suspended': 'audioSystem',
            'media_recorder_error': 'audioSystem',
            'network_disconnected': 'networkConnection',
            'api_timeout': 'networkConnection',
            'transcription_service_error': 'transcriptionSystem',
            'low_confidence_streak': 'transcriptionSystem'
        };
        
        const component = componentMap[errorType];
        if (component) {
            this.systemState[component] = status;
        }
    }
    
    broadcastErrorEvent(errorRecord, errorType) {
        const event = new CustomEvent('systemError', {
            detail: {
                error: errorRecord,
                errorType: errorType,
                systemState: this.systemState
            }
        });
        
        window.dispatchEvent(event);
    }
    
    generateErrorId() {
        return `err_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`;
    }
    
    getErrorReport() {
        const recentErrors = this.errorHistory.slice(-10);
        const errorTypes = {};
        
        // Count error types
        recentErrors.forEach(error => {
            const type = this.classifyError(error);
            errorTypes[type] = (errorTypes[type] || 0) + 1;
        });
        
        return {
            totalErrors: this.errorHistory.length,
            recentErrors: recentErrors.length,
            errorTypes: errorTypes,
            systemState: this.systemState,
            recoveryRate: this.calculateRecoveryRate()
        };
    }
    
    calculateRecoveryRate() {
        const recoveryAttempts = this.errorHistory.filter(error => error.recoveryAttempted);
        if (recoveryAttempts.length === 0) return 0;
        
        const successful = recoveryAttempts.filter(error => error.recoverySuccessful);
        return (successful.length / recoveryAttempts.length) * 100;
    }
    
    stop() {
        this.isActive = false;
        
        if (this.healthMonitorInterval) {
            clearInterval(this.healthMonitorInterval);
        }
        
        if (this.performanceMonitorInterval) {
            clearInterval(this.performanceMonitorInterval);
        }
        
        console.log('🛑 Advanced error recovery system stopped');
    }
}

// Initialize global error recovery system
window.advancedErrorRecovery = new AdvancedErrorRecovery();

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    window.advancedErrorRecovery.initialize();
    console.log('🛡️ Advanced Error Recovery System initialized');
});