/**
 * 🎵 STREAMING AUDIO CLIENT
 * Optimized client-side audio processing with PCM16 format,
 * chunking, and real-time streaming
 */

class StreamingAudioClient {
    constructor(options = {}) {
        this.options = {
            sampleRate: 16000,
            channels: 1,
            chunkDurationMs: 300,  // 300ms chunks for optimal latency
            overlapMs: 50,         // 50ms overlap for better transcription
            vadThreshold: 0.003,   // Voice Activity Detection threshold - LOWERED for better sensitivity
            maxRetries: 3,
            retryDelayMs: 1000,
            ...options
        };
        
        this.isRecording = false;
        this.mediaRecorder = null;
        this.audioContext = null;
        this.workletNode = null;
        this.sessionId = null;
        
        // Audio processing
        this.audioBuffer = [];
        this.chunkCounter = 0;
        this.lastChunkTime = 0;
        
        // Performance metrics
        this.metrics = {
            chunksProcessed: 0,
            averageLatencyMs: 0,
            totalLatencyMs: 0,
            droppedChunks: 0,
            vadSavings: 0
        };
        
        // Event callbacks
        this.onTranscription = null;
        this.onError = null;
        this.onStatusChange = null;
        
        console.log('🎵 StreamingAudioClient initialized with options:', this.options);
    }
    
    async startRecording(onTranscription, onError, onStatusChange) {
        try {
            this.onTranscription = onTranscription;
            this.onError = onError;
            this.onStatusChange = onStatusChange;
            
            if (this.isRecording) {
                console.warn('⚠️ Already recording');
                return;
            }
            
            // Request microphone access
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: this.options.sampleRate,
                    channelCount: this.options.channels,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });
            
            // Initialize audio context for PCM16 processing
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: this.options.sampleRate
            });
            
            // Start streaming session
            await this.startStreamingSession();
            
            // Set up audio worklet for real-time processing
            await this.setupAudioWorklet(stream);
            
            this.isRecording = true;
            this.onStatusChange?.('recording');
            
            console.log('✅ Recording started with session:', this.sessionId);
            
        } catch (error) {
            console.error('❌ Failed to start recording:', error);
            this.onError?.(error);
        }
    }
    
    async startStreamingSession() {
        try {
            const response = await fetch('/api/streaming/start-session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    client_id: this.generateClientId(),
                    audio_format: 'pcm16',
                    sample_rate: this.options.sampleRate,
                    client_info: {
                        userAgent: navigator.userAgent,
                        platform: navigator.platform,
                        language: navigator.language
                    }
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.sessionId = data.session_id;
                console.log('📢 Streaming session started:', this.sessionId);
            } else {
                throw new Error(data.error || 'Failed to start session');
            }
            
        } catch (error) {
            console.error('❌ Failed to start streaming session:', error);
            throw error;
        }
    }
    
    async setupAudioWorklet(stream) {
        try {
            // Create audio worklet for real-time PCM16 processing
            const source = this.audioContext.createMediaStreamSource(stream);
            
            // Use ScriptProcessorNode for broader browser compatibility
            // Note: AudioWorklet would be better but has limited support
            const bufferSize = 4096; // Balance between latency and processing efficiency
            this.workletNode = this.audioContext.createScriptProcessor(bufferSize, 1, 1);
            
            this.workletNode.onaudioprocess = (event) => {
                this.processAudioData(event.inputBuffer);
            };
            
            source.connect(this.workletNode);
            this.workletNode.connect(this.audioContext.destination);
            
            console.log('✅ Audio worklet setup complete');
            
        } catch (error) {
            console.error('❌ Audio worklet setup failed:', error);
            throw error;
        }
    }
    
    processAudioData(audioBuffer) {
        try {
            // Convert to PCM16 format
            const inputData = audioBuffer.getChannelData(0);
            const pcm16Data = this.convertToPCM16(inputData);
            
            // Add to buffer
            this.audioBuffer.push(...pcm16Data);
            
            // Check if we have enough data for a chunk
            const samplesPerChunk = (this.options.chunkDurationMs * this.options.sampleRate) / 1000;
            const bytesPerChunk = samplesPerChunk * 2; // 2 bytes per sample for 16-bit
            
            while (this.audioBuffer.length >= bytesPerChunk) {
                // Extract chunk with overlap handling
                const chunkData = this.audioBuffer.slice(0, bytesPerChunk);
                
                // Apply Voice Activity Detection
                if (this.hasVoiceActivity(chunkData)) {
                    this.sendAudioChunk(chunkData);
                } else {
                    this.metrics.vadSavings++;
                    console.debug('🔇 Skipping silent chunk');
                }
                
                // Remove processed data but keep overlap
                const overlapSamples = (this.options.overlapMs * this.options.sampleRate) / 1000;
                const overlapBytes = overlapSamples * 2;
                const advanceBytes = bytesPerChunk - overlapBytes;
                
                this.audioBuffer = this.audioBuffer.slice(advanceBytes);
                this.chunkCounter++;
            }
            
        } catch (error) {
            console.error('❌ Audio processing error:', error);
            this.onError?.(error);
        }
    }
    
    convertToPCM16(float32Array) {
        // Convert Float32 to PCM16 (16-bit signed integers)
        const pcm16 = new Int16Array(float32Array.length);
        
        for (let i = 0; i < float32Array.length; i++) {
            // Clamp and convert to 16-bit range
            const sample = Math.max(-1, Math.min(1, float32Array[i]));
            pcm16[i] = sample * 0x7FFF;
        }
        
        return new Uint8Array(pcm16.buffer);
    }
    
    hasVoiceActivity(audioData) {
        // Simple energy-based VAD
        let energy = 0;
        const int16Array = new Int16Array(audioData.buffer);
        
        for (let i = 0; i < int16Array.length; i++) {
            const sample = int16Array[i] / 32768.0; // Normalize to -1 to 1
            energy += sample * sample;
        }
        
        const rmsEnergy = Math.sqrt(energy / int16Array.length);
        return rmsEnergy > this.options.vadThreshold;
    }
    
    async sendAudioChunk(chunkData, retryCount = 0) {
        try {
            const startTime = performance.now();
            
            // Convert to base64 for transmission
            const base64Data = this.arrayBufferToBase64(chunkData);
            
            const formData = new FormData();
            formData.append('session_id', this.sessionId);
            formData.append('audio_data', base64Data);
            formData.append('chunk_id', `${this.chunkCounter}`);
            formData.append('timestamp', Date.now().toString());
            
            const response = await fetch('/api/streaming/process-chunk', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            
            if (result.success) {
                const latency = performance.now() - startTime;
                this.updateMetrics(latency);
                
                console.debug(`✅ Chunk sent: ${this.chunkCounter} (${latency.toFixed(1)}ms)`);
            } else {
                throw new Error(result.error || 'Processing failed');
            }
            
        } catch (error) {
            console.error(`❌ Failed to send chunk ${this.chunkCounter}:`, error);
            
            // Retry logic
            if (retryCount < this.options.maxRetries) {
                console.log(`🔄 Retrying chunk ${this.chunkCounter} (attempt ${retryCount + 1})`);
                
                setTimeout(() => {
                    this.sendAudioChunk(chunkData, retryCount + 1);
                }, this.options.retryDelayMs * (retryCount + 1));
                
            } else {
                this.metrics.droppedChunks++;
                this.onError?.(error);
            }
        }
    }
    
    async pollForResults() {
        if (!this.sessionId || !this.isRecording) return;
        
        try {
            const response = await fetch(`/api/streaming/get-results?session_id=${this.sessionId}&since=${this.lastResultTimestamp || 0}`);
            const data = await response.json();
            
            if (data.success && data.chunks.length > 0) {
                // Process new transcription results
                for (const chunk of data.chunks) {
                    if (chunk.transcript_text) {
                        this.onTranscription?.({
                            text: chunk.transcript_text,
                            confidence: chunk.confidence_score,
                            isInterim: chunk.is_interim,
                            isFinal: chunk.is_final,
                            chunkId: chunk.chunk_id,
                            timestamp: chunk.created_at
                        });
                    }
                }
                
                this.lastResultTimestamp = data.latest_timestamp;
            }
            
        } catch (error) {
            console.error('❌ Failed to poll for results:', error);
        }
        
        // Continue polling
        setTimeout(() => this.pollForResults(), 250); // Poll every 250ms
    }
    
    async stopRecording() {
        try {
            if (!this.isRecording) {
                console.warn('⚠️ Not currently recording');
                return;
            }
            
            this.isRecording = false;
            
            // Clean up audio resources
            if (this.workletNode) {
                this.workletNode.disconnect();
                this.workletNode = null;
            }
            
            if (this.audioContext) {
                await this.audioContext.close();
                this.audioContext = null;
            }
            
            // End streaming session
            if (this.sessionId) {
                await this.endStreamingSession();
            }
            
            this.onStatusChange?.('stopped');
            console.log('🛑 Recording stopped');
            
        } catch (error) {
            console.error('❌ Failed to stop recording:', error);
            this.onError?.(error);
        }
    }
    
    async endStreamingSession() {
        try {
            const response = await fetch('/api/streaming/end-session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: this.sessionId
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                console.log('📊 Session ended with analytics:', data.analytics);
                return data.analytics;
            } else {
                throw new Error(data.error || 'Failed to end session');
            }
            
        } catch (error) {
            console.error('❌ Failed to end streaming session:', error);
        }
    }
    
    updateMetrics(latency) {
        this.metrics.chunksProcessed++;
        this.metrics.totalLatencyMs += latency;
        this.metrics.averageLatencyMs = this.metrics.totalLatencyMs / this.metrics.chunksProcessed;
    }
    
    getMetrics() {
        return {
            ...this.metrics,
            sessionId: this.sessionId,
            isRecording: this.isRecording,
            audioBufferLength: this.audioBuffer.length,
            chunkCounter: this.chunkCounter
        };
    }
    
    generateClientId() {
        return 'client_' + Math.random().toString(36).substr(2, 9);
    }
    
    arrayBufferToBase64(buffer) {
        let binary = '';
        const bytes = new Uint8Array(buffer);
        const len = bytes.byteLength;
        
        for (let i = 0; i < len; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        
        return btoa(binary);
    }
}

// Export for use in other modules
window.StreamingAudioClient = StreamingAudioClient;