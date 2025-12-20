// chat.js (updated) - drop in place of old file
class ChatManager {
    constructor() {
        // Use sessionStorage for tab-scoped stable session
        this.sessionId = sessionStorage.getItem('sessionId') || null;
        this.isRecording = false;
        this.recognition = null;
        this.init();
    }

    async init() {
        await this.ensureSession();
        this.setupEventListeners();
        this.initVoiceRecognition();
    }

    async ensureSession() {
        // Prefer existing sessionId in sessionStorage (tab-level)
        const stored = sessionStorage.getItem('sessionId');
        if (stored) {
            this.sessionId = stored;
            window.sessionId = stored;
            const el = document.getElementById('sessionId');
            if (el) el.textContent = `Session: ${this.sessionId.substring(0,8)}...`;
            return;
        }

        // Try to create a server session (server will set cookie + return session_id)
        try {
            const resp = await fetch(API_ENDPOINTS.sessionCreate, {
                method: 'POST',
                headers: {
                    "Content-Type": "application/json",
                    ...getAuthHeaders()
                },
                credentials: "include"
            });
            if (resp.ok) {
                const data = await resp.json();
                if (data && data.session_id) {
                    this.sessionId = data.session_id;
                    sessionStorage.setItem('sessionId', this.sessionId);
                    window.sessionId = this.sessionId;
                    const el = document.getElementById('sessionId');
                    if (el) el.textContent = `Session: ${this.sessionId.substring(0,8)}...`;
                    console.debug("[CHAT] created new server session:", this.sessionId);
                    return;
                }
            }
            // fallback: create temporary tab-local session id (will be replaced once server responds)
            this.sessionId = 'temp-' + Date.now();
            sessionStorage.setItem('sessionId', this.sessionId);
            window.sessionId = this.sessionId;
            const el = document.getElementById('sessionId');
            if (el) el.textContent = `Session: ${this.sessionId.substring(0,8)}...`;
            console.warn("[CHAT] using temporary session id (server unreachable):", this.sessionId);
        } catch (err) {
            console.error("ensureSession error:", err);
            this.sessionId = 'temp-' + Date.now();
            sessionStorage.setItem('sessionId', this.sessionId);
            window.sessionId = this.sessionId;
        }
    }

    setupEventListeners() {
        const chatTrigger = document.getElementById('chatBotTrigger');
        const chatPanel = document.getElementById('chatPanel');
        const chatClose = document.getElementById('chatClose');
        const chatInput = document.getElementById('chatInput');
        const sendButton = document.getElementById('sendButton');
        const voiceButton = document.getElementById('voiceButton');
        const langButton = document.getElementById('langButton');
        const preferenceButton = document.getElementById('preferenceButton');

        chatTrigger && chatTrigger.addEventListener('click', () => {
            chatPanel && chatPanel.classList.add('active');
            chatInput && chatInput.focus();
        });
        chatClose && chatClose.addEventListener('click', () => chatPanel && chatPanel.classList.remove('active'));
        sendButton && sendButton.addEventListener('click', () => this.sendMessage());
        chatInput && chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        voiceButton && voiceButton.addEventListener('click', () => this.toggleVoiceRecording());
        langButton && langButton.addEventListener('click', () => document.getElementById('langModal') && document.getElementById('langModal').classList.add('active'));
        preferenceButton && preferenceButton.addEventListener('click', () => document.getElementById('preferenceModal') && document.getElementById('preferenceModal').classList.add('active'));

        const langModalClose = document.getElementById('langModalClose');
        langModalClose && langModalClose.addEventListener('click', () => document.getElementById('langModal') && document.getElementById('langModal').classList.remove('active'));
        const prefModalClose = document.getElementById('preferenceModalClose');
        prefModalClose && prefModalClose.addEventListener('click', () => document.getElementById('preferenceModal') && document.getElementById('preferenceModal').classList.remove('active'));

        document.querySelectorAll('.lang-option').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const lang = e.target.dataset.lang;
                updateLanguage(lang);
                document.getElementById('langModal') && document.getElementById('langModal').classList.remove('active');
            });
        });

        document.getElementById('langModal') && document.getElementById('langModal').addEventListener('click', (e) => {
            if (e.target.id === 'langModal') e.target.classList.remove('active');
        });
        document.getElementById('preferenceModal') && document.getElementById('preferenceModal').addEventListener('click', (e) => {
            if (e.target.id === 'preferenceModal') e.target.classList.remove('active');
        });
    }

    async sendMessage() {
        const chatInput = document.getElementById('chatInput');
        const message = chatInput ? chatInput.value.trim() : '';
        if (!message) return;

        // show user message immediately
        this.addMessage(message, 'user');
        if (chatInput) chatInput.value = '';

        this.showTypingIndicator();

        try {
            // Ensure we have the latest sessionId from sessionStorage (tab-scoped)
            this.sessionId = sessionStorage.getItem('sessionId') || this.sessionId || null;

            // If sessionId is missing, we let the backend create a session. If present, always include it.
            const payload = {
                message: message,
                session_id: this.sessionId || null,
                customer_id: customerId ? parseInt(customerId) : null,
                lang: currentLanguage
            };

            const headers = {
                "Content-Type": "application/json",
                ...getAuthHeaders()
            };

            if (this.sessionId) {
                headers["X-Session-Id"] = this.sessionId;
            }

            const response = await fetch(API_ENDPOINTS.chat, {
                method: 'POST',
                headers,
                credentials: "include", // crucial so cookies are accepted and sent
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const text = await response.text().catch(()=>'');
                console.error("Chat API error:", response.status, text);
                this.hideTypingIndicator();
                this.addMessage('Sorry, the server returned an error. Try again.', 'bot');
                return;
            }

            const data = await response.json();
            this.hideTypingIndicator();

            // Persist authoritative server session_id if provided
            if (data && data.session_id) {
                if (!this.sessionId || this.sessionId !== data.session_id) {
                    this.sessionId = data.session_id;
                    sessionStorage.setItem('sessionId', this.sessionId);
                    window.sessionId = this.sessionId;
                    const el = document.getElementById('sessionId');
                    if (el) el.textContent = `Session: ${this.sessionId.substring(0,8)}...`;
                    console.debug("[CHAT] session persisted from server:", this.sessionId);
                }
            }

            // Show bot response
            this.addMessage(data.bot_response || "I couldn't process that right now.", 'bot');

            if (data && data.lang && data.lang !== currentLanguage) updateLanguage(data.lang);
        } catch (err) {
            console.error("sendMessage error:", err);
            this.hideTypingIndicator();
            this.addMessage('Sorry, I encountered an error. Please try again.', 'bot');
        }
    }

    addMessage(text, sender) {
        const chatMessages = document.getElementById('chatMessages');
        if (!chatMessages) return;

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = sender === 'user' ? '👤' : '🤖';

        const content = document.createElement('div');
        content.className = 'message-content';
        const p = document.createElement('p');
        p.innerHTML = this.formatMessage(text);
        content.appendChild(p);

        if (sender === 'bot') {
            const speakerBtn = document.createElement('button');
            speakerBtn.className = 'speaker-btn';
            speakerBtn.innerHTML = '🔊';
            speakerBtn.title = 'Listen to response';
            speakerBtn.onclick = () => this.speakText(text);
            content.appendChild(speakerBtn);
        }

        messageDiv.appendChild(avatar);
        messageDiv.appendChild(content);
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    speakText(text) {
        const cleanText = (text || '').replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').trim();
        if (!cleanText) return;
        if ('speechSynthesis' in window) {
            const utterance = new SpeechSynthesisUtterance(cleanText);
            utterance.lang = currentLanguage === 'bn' ? 'bn-BD' : currentLanguage === 'hi' ? 'hi-IN' : 'en-US';
            utterance.rate = 1.0;
            utterance.pitch = 1.0;
            utterance.volume = 1.0;
            speechSynthesis.speak(utterance);
        } else {
            alert('Text-to-speech is not supported in your browser.');
        }
    }

    formatMessage(text) {
        text = (text || '').replace(/\n/g, '<br>');
        return text.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
    }

    showTypingIndicator() {
        const chatMessages = document.getElementById('chatMessages');
        if (!chatMessages) return;
        this.hideTypingIndicator();
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message bot-message typing-indicator';
        typingDiv.id = 'typingIndicator';
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = '🤖';
        const content = document.createElement('div');
        content.className = 'message-content';
        content.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';
        typingDiv.appendChild(avatar);
        typingDiv.appendChild(content);
        chatMessages.appendChild(typingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    hideTypingIndicator() {
        const t = document.getElementById('typingIndicator');
        if (t) t.remove();
    }

    initVoiceRecognition() {
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            this.recognition = new SpeechRecognition();
            this.recognition.continuous = false;
            this.recognition.interimResults = false;
            this.recognition.lang = currentLanguage === 'en' ? 'en-US' : currentLanguage === 'bn' ? 'bn-BD' : 'hi-IN';

            this.recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                const input = document.getElementById('chatInput');
                if (input) input.value = transcript;
                this.sendMessage();
            };

            this.recognition.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
                this.isRecording = false;
                this.updateVoiceButton();
            };

            this.recognition.onend = () => {
                this.isRecording = false;
                this.updateVoiceButton();
            };
        }
    }

    toggleVoiceRecording() {
        if (!this.recognition) {
            alert('Voice recognition is not supported in your browser.');
            return;
        }
        if (this.isRecording) {
            this.recognition.stop();
            this.isRecording = false;
        } else {
            this.recognition.start();
            this.isRecording = true;
        }
        this.updateVoiceButton();
    }

    updateVoiceButton() {
        const vb = document.getElementById('voiceButton');
        if (!vb) return;
        if (this.isRecording) {
            vb.style.background = '#ef4444'; vb.textContent = '⏹';
        } else {
            vb.style.background = ''; vb.textContent = '🎤';
        }
    }
}

// initialize on DOM ready
let chatManager;
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => { chatManager = new ChatManager(); });
} else {
    chatManager = new ChatManager();
}
