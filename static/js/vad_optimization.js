/**
 * 🎤 VOICE ACTIVITY DETECTION OPTIMIZATION
 * Reduces API calls and improves performance by detecting speech vs silence
 */

class VADOptimization {
    constructor() {
        this.isEnabled = true;
        this.silenceThreshold = 0.002; // RMS threshold for silence - LOWERED for better sensitivity
        this.speechThreshold = 0.005;  // RMS threshold for speech - LOWERED for better sensitivity
        this.minSpeechDuration = 200; // Minimum speech duration (ms) - REDUCED for faster detection
        this.maxSilenceDuration = 2000; // Maximum silence before chunk ends (ms) - INCREASED for natural pauses
        
        this.speechStartTime = null;
        this.lastSpeechTime = null;
        this.audioBuffer = [];
        this.vadState = 'silence'; // 'silence', 'speech', 'buffering'
        
        this.statistics = {
            totalChunks: 0,
            speechChunks: 0,
            silenceChunks: 0,
            apiCallsSaved: 0
        };
        
        console.log('🎤 VAD Optimization initialized');
    }
    
    /**
     * Analyze audio chunk and determine if it contains speech
     */
    analyzeAudioChunk(audioData, timestamp = Date.now()) {
        const rms = this.calculateRMS(audioData);
        const isSpeech = rms > this.speechThreshold;
        const isSilence = rms < this.silenceThreshold;
        
        this.statistics.totalChunks++;
        
        // State machine for VAD
        switch (this.vadState) {
            case 'silence':
                if (isSpeech) {
                    this.vadState = 'speech';
                    this.speechStartTime = timestamp;
                    this.lastSpeechTime = timestamp;
                    console.log('🎤 Speech detected, starting buffering');
                }
                break;
                
            case 'speech':
                if (isSpeech) {
                    this.lastSpeechTime = timestamp;
                } else if (isSilence) {
                    const silenceDuration = timestamp - this.lastSpeechTime;
                    if (silenceDuration > this.maxSilenceDuration) {
                        this.vadState = 'silence';
                        console.log('🎤 Speech ended, returning to silence');
                        return this.processSpeechBuffer();
                    }
                }
                break;
        }
        
        // Add to buffer if in speech state
        if (this.vadState === 'speech') {
            this.audioBuffer.push({
                data: audioData,
                timestamp: timestamp,
                rms: rms
            });
        }
        
        return {
            shouldProcess: this.vadState === 'speech' && this.audioBuffer.length > 0,
            vadState: this.vadState,
            rms: rms,
            speechDuration: this.speechStartTime ? timestamp - this.speechStartTime : 0
        };
    }
    
    /**
     * Calculate RMS (Root Mean Square) for audio data
     */
    calculateRMS(audioData) {
        if (!audioData || audioData.length === 0) return 0;
        
        let sum = 0;
        for (let i = 0; i < audioData.length; i++) {
            sum += audioData[i] * audioData[i];
        }
        return Math.sqrt(sum / audioData.length);
    }
    
    /**
     * Process accumulated speech buffer
     */
    processSpeechBuffer() {
        if (this.audioBuffer.length === 0) return null;
        
        const speechDuration = this.audioBuffer[this.audioBuffer.length - 1].timestamp - this.audioBuffer[0].timestamp;
        
        // Only process if speech duration meets minimum threshold
        if (speechDuration < this.minSpeechDuration) {
            console.log(`🎤 Speech too short (${speechDuration}ms), skipping`);
            this.audioBuffer = [];
            this.statistics.apiCallsSaved++;
            return null;
        }
        
        // Combine audio buffer data
        const combinedAudio = this.combineAudioBuffers();
        const result = {
            audioData: combinedAudio,
            duration: speechDuration,
            confidence: this.calculateConfidence(),
            timestamp: this.audioBuffer[0].timestamp
        };
        
        // Clear buffer
        this.audioBuffer = [];
        this.speechStartTime = null;
        this.statistics.speechChunks++;
        
        console.log(`🎤 Speech processed: ${speechDuration}ms duration`);
        return result;
    }
    
    /**
     * Combine multiple audio buffers into one
     */
    combineAudioBuffers() {
        if (this.audioBuffer.length === 0) return new Float32Array(0);
        
        const totalLength = this.audioBuffer.reduce((sum, item) => sum + item.data.length, 0);
        const combined = new Float32Array(totalLength);
        
        let offset = 0;
        for (const item of this.audioBuffer) {
            combined.set(item.data, offset);
            offset += item.data.length;
        }
        
        return combined;
    }
    
    /**
     * Calculate confidence score based on audio quality
     */
    calculateConfidence() {
        if (this.audioBuffer.length === 0) return 0;
        
        const avgRMS = this.audioBuffer.reduce((sum, item) => sum + item.rms, 0) / this.audioBuffer.length;
        const consistency = this.calculateConsistency();
        
        // Confidence based on RMS level and consistency
        const rmsScore = Math.min(1.0, avgRMS / 0.1); // Normalize to 0-1
        const confidenceScore = (rmsScore * 0.7) + (consistency * 0.3);
        
        return Math.min(0.95, Math.max(0.1, confidenceScore));
    }
    
    /**
     * Calculate speech consistency (less variation = higher consistency)
     */
    calculateConsistency() {
        if (this.audioBuffer.length < 2) return 1.0;
        
        const rmsValues = this.audioBuffer.map(item => item.rms);
        const mean = rmsValues.reduce((sum, val) => sum + val, 0) / rmsValues.length;
        const variance = rmsValues.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / rmsValues.length;
        const standardDeviation = Math.sqrt(variance);
        
        // Lower standard deviation = higher consistency
        return Math.max(0.1, 1.0 - (standardDeviation / mean));
    }
    
    /**
     * Force process current buffer (for end of session)
     */
    forceProcessBuffer() {
        if (this.audioBuffer.length > 0) {
            console.log('🎤 Force processing remaining buffer');
            return this.processSpeechBuffer();
        }
        return null;
    }
    
    /**
     * Get VAD statistics
     */
    getStatistics() {
        const apiCallReduction = this.statistics.totalChunks > 0 
            ? (this.statistics.apiCallsSaved / this.statistics.totalChunks) * 100 
            : 0;
            
        return {
            ...this.statistics,
            apiCallReduction: Math.round(apiCallReduction),
            speechRatio: this.statistics.totalChunks > 0 
                ? (this.statistics.speechChunks / this.statistics.totalChunks) * 100 
                : 0
        };
    }
    
    /**
     * Reset VAD state
     */
    reset() {
        this.vadState = 'silence';
        this.speechStartTime = null;
        this.lastSpeechTime = null;
        this.audioBuffer = [];
        console.log('🎤 VAD state reset');
    }
    
    /**
     * Configure VAD thresholds
     */
    configure(options = {}) {
        if (options.silenceThreshold !== undefined) {
            this.silenceThreshold = options.silenceThreshold;
        }
        if (options.speechThreshold !== undefined) {
            this.speechThreshold = options.speechThreshold;
        }
        if (options.minSpeechDuration !== undefined) {
            this.minSpeechDuration = options.minSpeechDuration;
        }
        if (options.maxSilenceDuration !== undefined) {
            this.maxSilenceDuration = options.maxSilenceDuration;
        }
        
        console.log('🎤 VAD configuration updated:', options);
    }
}

// Initialize global VAD optimization
window.vadOptimization = new VADOptimization();

console.log('✅ VAD Optimization system loaded');