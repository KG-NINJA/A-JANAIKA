document.addEventListener('DOMContentLoaded', () => {
    const recordButton = document.getElementById('recordButton');
    const stopButton = document.getElementById('stopButton');
    const composeButton = document.getElementById('composeButton');
    const downloadLink = document.getElementById('downloadLink');
    const statusDisplay = document.getElementById('status');

    let mediaRecorder;
    let audioChunks = [];
    // audioContext, analyser, etc. were planned for pitch detection, not used yet.

    async function getMicrophoneAccess() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            statusDisplay.textContent = 'Error: Your browser does not support microphone access (getUserMedia).';
            statusDisplay.className = 'status-error';
            return null;
        }
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            statusDisplay.textContent = 'Microphone access granted. Ready to record.';
            statusDisplay.className = 'status-success';
            return stream;
        } catch (err) {
            statusDisplay.textContent = `Error accessing microphone: ${err.name} - ${err.message}. Please ensure permission is granted.`;
            statusDisplay.className = 'status-error';
            console.error('Error accessing microphone:', err);
            return null;
        }
    }

    if (recordButton) {
        recordButton.addEventListener('click', async () => {
            const stream = await getMicrophoneAccess();
            if (!stream) return;

            audioChunks = [];
            mediaRecorder = new MediaRecorder(stream);

            mediaRecorder.ondataavailable = event => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstart = () => {
                recordButton.disabled = true;
                stopButton.disabled = false;
                composeButton.disabled = true;
                downloadLink.style.display = 'none';
                statusDisplay.textContent = 'Recording...';
                statusDisplay.className = 'status-info';
                console.log('Recording started');
            };

            mediaRecorder.onstop = async () => {
                recordButton.disabled = false;
                stopButton.disabled = true;
                // Enable compose only if there's some audio
                composeButton.disabled = audioChunks.length === 0;
                statusDisplay.textContent = 'Recording stopped. Ready to compose or re-record.';
                statusDisplay.className = 'status-info';
                console.log('Recording stopped');
                if (audioChunks.length === 0) {
                    statusDisplay.textContent = 'No audio recorded. Please try recording again.';
                    statusDisplay.className = 'status-warning';
                }
            };

            // Handle errors during recording itself if any are emitted by MediaRecorder
            mediaRecorder.onerror = (event) => {
                console.error('MediaRecorder error:', event.error);
                statusDisplay.textContent = `Recording error: ${event.error.name} - ${event.error.message}`;
                statusDisplay.className = 'status-error';
                recordButton.disabled = false;
                stopButton.disabled = true;
                composeButton.disabled = true;
            };

            mediaRecorder.start();
        });
    }

    if (stopButton) {
        stopButton.addEventListener('click', () => {
            if (mediaRecorder && mediaRecorder.state === 'recording') {
                mediaRecorder.stop();
                if (mediaRecorder.stream) {
                    mediaRecorder.stream.getTracks().forEach(track => track.stop());
                }
            }
        });
    }

    if (composeButton) {
        composeButton.addEventListener('click', async () => {
            if (audioChunks.length === 0) {
                statusDisplay.textContent = 'Please record a melody first.';
                statusDisplay.className = 'status-warning';
                return;
            }
            statusDisplay.textContent = 'Processing audio and preparing for composition...';
            statusDisplay.className = 'status-info';

            const placeholderMelodyData = { // Still using placeholder
                notes: [
                    { pitch: 60, startTime: 0.0, endTime: 0.5 },
                    { pitch: 62, startTime: 0.5, endTime: 1.0 },
                    { pitch: 64, startTime: 1.0, endTime: 1.5 }
                ],
                tempo: 120
            };
            console.log('Sending placeholder melody data to backend:', placeholderMelodyData);

            try {
                composeButton.disabled = true; // Disable while processing
                const response = await fetch('/compose', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ melody: placeholderMelodyData }),
                });

                if (response.ok) {
                    const result = await response.json();
                    statusDisplay.textContent = `${result.message || 'Composition complete!'}`;
                    statusDisplay.className = 'status-success';
                    if (result.midi_file_url) {
                        downloadLink.href = result.midi_file_url;
                        downloadLink.style.display = 'block';
                        downloadLink.textContent = 'Download Composed MIDI';
                    } else {
                        downloadLink.style.display = 'none';
                        statusDisplay.textContent = 'Composition succeeded but no MIDI URL provided.';
                        statusDisplay.className = 'status-warning';
                    }
                } else {
                    const errorData = await response.json().catch(() => ({ error: "Unknown server error. Response was not valid JSON." }));
                    statusDisplay.textContent = `Error from server: ${errorData.error || response.statusText || 'Unknown error'}`;
                    statusDisplay.className = 'status-error';
                    console.error('Error from backend:', errorData, response.status);
                    downloadLink.style.display = 'none';
                }
            } catch (error) {
                statusDisplay.textContent = `Network or client-side error: ${error.message}. Check console for details.`;
                statusDisplay.className = 'status-error';
                console.error('Error sending melody data:', error);
                downloadLink.style.display = 'none';
            } finally {
                // Re-enable compose button only if there was an error and user might want to retry
                // If successful, it should remain disabled until a new recording.
                // For now, let's re-enable it if audioChunks exist, to allow retries on failure.
                 if (audioChunks.length > 0) {
                    composeButton.disabled = false;
                 }
            }
        });
    }
});
