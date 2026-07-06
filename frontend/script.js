// Session Management
let sessionId = localStorage.getItem('crop_doctor_session_id');
if (!sessionId) {
    sessionId = 'session_' + Math.random().toString(36).substr(2, 9);
    localStorage.setItem('crop_doctor_session_id', sessionId);
}
const userId = 'user_web_client';
document.getElementById('session-display').textContent = `Session: ${sessionId}`;

// DOM Elements
const chatHistory = document.getElementById('chat-history');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const hitlContainer = document.getElementById('hitl-container');
const hitlPrompt = document.getElementById('hitl-prompt');
const hitlApproveBtn = document.getElementById('hitl-approve');
const hitlCorrectionText = document.getElementById('hitl-correction-text');
const hitlSubmitCorrectionBtn = document.getElementById('hitl-submit-correction');
const resetSessionBtn = document.getElementById('reset-session');
const mcpLog = document.getElementById('mcp-log');

// State displays
const stateDiagnosis = document.getElementById('state-diagnosis');
const stateCorrections = document.getElementById('state-corrections');
const stateTreatment = document.getElementById('state-treatment');

// Node elements
const nodes = {
    'security_checkpoint': document.getElementById('node-security'),
    'diagnose_node': document.getElementById('node-diagnose'),
    'expert_review': document.getElementById('node-hitl'),
    'treatment_node': document.getElementById('node-treatment'),
    'correction_node': document.getElementById('node-diagnose'),
    'security_error_node': document.getElementById('node-security')
};

// Reset Session
resetSessionBtn.addEventListener('click', () => {
    sessionId = 'session_' + Math.random().toString(36).substr(2, 9);
    localStorage.setItem('crop_doctor_session_id', sessionId);
    document.getElementById('session-display').textContent = `Session: ${sessionId}`;
    chatHistory.innerHTML = `
        <div class="message system">
            <div class="avatar">👨‍⚕️</div>
            <div class="bubble">
                <p>Session reset! Describe your plant symptoms to start a new diagnosis.</p>
            </div>
        </div>
    `;
    // Reset indicators and states
    clearNodeHighlights();
    stateDiagnosis.textContent = 'None';
    stateCorrections.textContent = 'None';
    stateTreatment.textContent = 'None';
    hitlContainer.classList.add('hidden');
    addMcpLog('Session reset. Stdio connection open.', 'system');
});

// Auto-grow textarea
userInput.addEventListener('input', () => {
    userInput.style.height = 'auto';
    userInput.style.height = (userInput.scrollHeight) + 'px';
});

// Send Message on Enter
userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage(userInput.value.trim());
    }
});

sendBtn.addEventListener('click', () => {
    sendMessage(userInput.value.trim());
});

// Main Send Logic
async function sendMessage(text) {
    if (!text) return;

    // Add user message to UI
    appendMessage(text, 'user', '👤');
    userInput.value = '';
    userInput.style.height = 'auto';

    // Show typing placeholder
    const typingIndicator = appendTypingIndicator();
    clearNodeHighlights();

    try {
        const response = await fetch('/run', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                newMessage: {
                    parts: [{ text: text }],
                    role: 'user'
                },
                userId: userId,
                sessionId: sessionId,
                appName: 'app'
            })
        });

        if (!response.ok) {
            throw new Error(`Server returned status: ${response.status}`);
        }

        const events = await response.json();
        typingIndicator.remove();
        processEvents(events);

    } catch (err) {
        typingIndicator.remove();
        appendMessage(`Error: ${err.message}. Make sure the backend server is running.`, 'system', '⚠️');
    }
}

// Process ADK Events
function processEvents(events) {
    if (!events || events.length === 0) return;

    events.forEach(event => {
        // 1. Highlight Active Node
        if (event.nodeInfo && event.nodeInfo.name) {
            highlightNode(event.nodeInfo.name);
        }

        // 2. Parse State updates if present in actions.stateDelta
        if (event.actions && event.actions.stateDelta) {
            updateStateDisplay(event.actions.stateDelta);
        }

        // 3. Log Tool Calls
        if (event.content && event.content.parts) {
            event.content.parts.forEach(part => {
                if (part.functionCall) {
                    addMcpLog(`Calling tool: ${part.functionCall.name}(${JSON.stringify(part.functionCall.args)})`, 'tool-call');
                }
                if (part.functionResponse) {
                    addMcpLog(`Tool returned: ${JSON.stringify(part.functionResponse.response)}`, 'tool-response');
                }
            });
        }

        // 4. Append message to chat if there is model output content
        let textOutput = extractText(event.content);
        if (textOutput && event.author !== 'security_checkpoint') {
            appendMessage(textOutput, 'model', '👨‍⚕️');
        }

        // 5. Special check for Security block message in Event.output
        if (event.nodeInfo && event.nodeInfo.name === 'security_error_node' && event.output) {
            appendMessage(event.output, 'system', '🛡️');
            if (nodes['security_error_node']) {
                nodes['security_error_node'].classList.add('flagged');
            }
        }
    });

    // 6. Check for Human-in-the-loop (HITL) Interruption
    const lastEvent = events[events.length - 1];
    if (lastEvent && lastEvent.interrupted) {
        const text = extractText(lastEvent.content) || lastEvent.output;
        showHitlPrompt(text);
        highlightNode('expert_review');
    } else {
        hitlContainer.classList.add('hidden');
    }
}

// Show HITL Card
function showHitlPrompt(promptText) {
    hitlPrompt.textContent = promptText;
    hitlContainer.classList.remove('hidden');
    
    // Clear old listeners
    const cleanApprove = hitlApproveBtn.cloneNode(true);
    hitlApproveBtn.parentNode.replaceChild(cleanApprove, hitlApproveBtn);
    
    const cleanSubmit = hitlSubmitCorrectionBtn.cloneNode(true);
    hitlSubmitCorrectionBtn.parentNode.replaceChild(cleanSubmit, hitlSubmitCorrectionBtn);

    // Rebind new listeners
    document.getElementById('hitl-approve').addEventListener('click', () => {
        hitlContainer.classList.add('hidden');
        sendMessage('yes');
    });

    document.getElementById('hitl-submit-correction').addEventListener('click', () => {
        const correction = hitlCorrectionText.value.trim();
        if (correction) {
            hitlContainer.classList.add('hidden');
            hitlCorrectionText.value = '';
            sendMessage(correction);
        }
    });
}

// Utility: Extract Text from Content
function extractText(content) {
    if (!content) return '';
    if (content.parts) {
        return content.parts
            .filter(part => part.text)
            .map(part => part.text)
            .join('');
    }
    return '';
}

// UI Helpers
function appendMessage(text, role, avatarEmoji) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;
    
    // Simple markdown highlighting for lists/bold
    let formattedText = text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');

    msgDiv.innerHTML = `
        <div class="avatar">${avatarEmoji}</div>
        <div class="bubble">
            <p>${formattedText}</p>
        </div>
    `;
    chatHistory.appendChild(msgDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function appendTypingIndicator() {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message model typing';
    msgDiv.innerHTML = `
        <div class="avatar">👨‍⚕️</div>
        <div class="bubble">
            <p>Diagnosing plant symptoms...</p>
        </div>
    `;
    chatHistory.appendChild(msgDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    return msgDiv;
}

function highlightNode(nodeName) {
    clearNodeHighlights();
    const nodeEl = nodes[nodeName];
    if (nodeEl) {
        nodeEl.classList.add('active');
        if (nodeName === 'security_error_node') {
            nodeEl.classList.add('flagged');
        }
    }
}

function clearNodeHighlights() {
    Object.values(nodes).forEach(nodeEl => {
        if (nodeEl) {
            nodeEl.classList.remove('active');
            nodeEl.classList.remove('flagged');
        }
    });
}

function updateStateDisplay(stateDelta) {
    if (stateDelta.diagnosis) stateDiagnosis.textContent = stateDelta.diagnosis;
    if (stateDelta.corrections) stateCorrections.textContent = stateDelta.corrections;
    if (stateDelta.treatment) stateTreatment.textContent = stateDelta.treatment;
}

function addMcpLog(text, className = '') {
    const entry = document.createElement('div');
    entry.className = `log-entry ${className}`;
    const now = new Date();
    const timeStr = now.toTimeString().split(' ')[0];
    entry.textContent = `[${timeStr}] ${text}`;
    mcpLog.appendChild(entry);
    mcpLog.scrollTop = mcpLog.scrollHeight;
}
