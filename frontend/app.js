const API_URL = window.location.origin;
let chartInstance = null;
let fftChartInstance = null;
let lastAnalysisData = null;
let streamInterval = null;
let currentSessionId = null;
let synthesisReady = false;
let live_sessions_markers_count = 0;

// GLOBAL ERROR CATCHER
window.onerror = function(msg, url, line) {
    showToast(`JS Error: ${msg} (Line ${line})`, '❌');
    console.error("GLOBAL ERROR:", msg, "at", url, ":", line);
    return false;
};

// Persistent Session ID (Client-side node)
const urlParams = new URLSearchParams(window.location.search);
let isRemote = urlParams.get('remote') === 'true';
let nodeId = urlParams.get('node') || localStorage.getItem('drpet_node_id');

if (!nodeId) {
    nodeId = 'node_' + Math.random().toString(36).substr(2, 9);
    localStorage.setItem('drpet_node_id', nodeId);
}

// Remote Mode Setup
if (isRemote) {
    document.addEventListener('DOMContentLoaded', () => {
        document.body.innerHTML = `
            <div style="background: black; height: 100vh; width: 100vw; display: flex; flex-direction: column; align-items: center; justify-content: center; color: white;">
                <h2 style="margin-bottom: 20px;">Remote Camera Active</h2>
                <div class="video-wrapper" style="max-width: 90vw;">
                    <video id="live-video" autoplay playsinline style="width: 100%; border-radius: 16px; border: 2px solid #10B981;"></video>
                    <canvas id="live-canvas" class="hidden"></canvas>
                </div>
                <div style="margin-top: 20px; display: flex; align-items: center; gap: 8px;">
                    <span style="display: inline-block; width: 12px; height: 12px; background: #10B981; border-radius: 50%; animation: pulse-soft 2s infinite;"></span>
                    <span>Streaming to Dr. PET...</span>
                </div>
            </div>
        `;
        startRemoteStream();
    });
}

async function startRemoteStream() {
    const video = document.getElementById('live-video');
    const canvas = document.getElementById('live-canvas');
    const ctx = canvas.getContext('2d');
    
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
        video.srcObject = stream;
        
        const wsHost = window.location.hostname;
        const wsPort = window.location.port ? `:${window.location.port}` : '';
        const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        let streamSocket = new WebSocket(`${wsProtocol}://${wsHost}${wsPort}/ws/stream?node_id=${nodeId}`);
        streamSocket.onopen = () => {
            setInterval(() => {
                if (streamSocket.readyState === WebSocket.OPEN) {
                    const scale = Math.min(640 / video.videoWidth, 1.0);
                    canvas.width = video.videoWidth * scale;
                    canvas.height = video.videoHeight * scale;
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                    canvas.toBlob((blob) => {
                        if (blob) streamSocket.send(blob);
                    }, 'image/jpeg', 0.5);
                }
            }, 400);
        };
    } catch (e) {
        alert("Camera access failed on remote device");
    }
}

// UI Elements — grabbed after DOM ready
let dropZone, fileInput, uploadProgress, analysisResults, insightIdle, apiStatusPill, apiStatusText;
let remotePollInterval = null;

document.addEventListener('DOMContentLoaded', () => {
    // Skip normal init if remote mode
    if (isRemote) return;

    dropZone       = document.getElementById('drop-zone');
    fileInput      = document.getElementById('file-input');
    uploadProgress = document.getElementById('upload-progress');
    analysisResults= document.getElementById('analysis-results');
    insightIdle    = document.getElementById('insight-idle');
    apiStatusPill  = document.getElementById('api-status-pill');
    apiStatusText  = document.getElementById('api-status-text');

    // File input change — this is THE correct trigger
    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) handleUpload(e.target.files[0]);
        });
    }

    // Drag and drop on the drop zone
    if (dropZone) {
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('drag-active');
        });
        dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-active'));
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('drag-active');
            if (e.dataTransfer.files.length > 0) handleUpload(e.dataTransfer.files[0]);
        });
    }

    checkApiHealth();
    setInterval(checkApiHealth, 60000); // every 60s is enough
    fetchDailyHighlight();
    fetchHistory();
    
    // Initialize the Wisdom Book with casual tips
    if (typeof renderPaginatedTips === "function") {
        renderPaginatedTips(CASUAL_STATIC_TIPS);
    }
});

async function checkApiHealth() {
    try {
        const res = await fetch(`/api/health`);
        const data = await res.json();
        const pill = document.getElementById('api-status-pill');
        const txt  = document.getElementById('api-status-text');
        if (pill) pill.classList.add('online');
        if (txt)  txt.innerText = 'AI Online';
    } catch (e) {
        const pill = document.getElementById('api-status-pill');
        const txt  = document.getElementById('api-status-text');
        if (pill) pill.classList.remove('online');
        if (txt)  txt.innerText = 'Offline';
    }
}

// Book Interaction Logic
window.toggleBook = function() {
    console.log("Book clicked! Toggling open state...");
    const book = document.getElementById('tips-book-wrapper');
    if (book) {
        book.classList.toggle('open');
        console.log("Book classList:", book.classList);
    } else {
        console.error("Could not find tips-book-wrapper");
    }
};

let currentTipsPage = 1;
const tipsPerPage = 2; // Show 2 tips per page

const CASUAL_STATIC_TIPS = [
    { title: "Get on a Schedule!", text: "Pets love knowing what's next. Try to feed and walk them at the same time every day—it makes them feel super safe!", img: "assets/wisdom_dog.png" },
    { title: "Making New Friends", text: "Slow and steady wins the race. Introduce new people and sounds gradually so your buddy doesn't get scared." },
    { title: "The Quiet Voice", text: "New pets are like sponges for your mood. Using a soft, calm voice helps them relax when things get hectic.", img: "assets/wisdom_cat.png" },
    { title: "Sniffing is Learning", text: "When you go for walks, let them sniff around! It's like they're reading the morning newspaper. It keeps their brain happy." },
    { title: "Safe Space", text: "Give them a cozy corner or a crate that's just theirs. When they need a 'time out' from the world, they'll know exactly where to go.", img: "assets/wisdom_rabbit.png" },
    { title: "Watch the Tail", text: "A wagging tail doesn't always mean happy! A stiff, high wag might mean they're nervous. Look for the 'helicopter' wag for pure joy!" },
    { title: "Drink Up!", text: "Fresh water is the best medicine! Make sure they always have a full bowl, especially after a big play session." },
    { title: "Toy Time!", text: "Rotate their toys every week. It makes the 'old' toys feel brand new and keeps them from getting bored.", img: "assets/wisdom_dog.png" },
    { title: "Slow Blinks", text: "If you have a cat, try blinking slowly at them. It's like giving them a tiny hug with your eyes!" },
    { title: "Brushy Brushy", text: "Brushing isn't just for hair; it's a great way to bond. Plus, it means less fur on your favorite couch!", img: "assets/wisdom_cat.png" },
    { title: "Healthy Snacks", text: "Carrots or apples (without seeds) can be a great low-calorie treat. Always check if a human food is safe first!", img: "assets/wisdom_rabbit.png" },
    { title: "Night Lights", text: "Some older pets might get confused in the dark. A tiny night light near their bed can help them feel secure." },
    { title: "The Paw Check", text: "Check their paws after walks. Mud, salt, or tiny pebbles can get stuck and hurt their toes.", img: "assets/wisdom_dog.png" },
    { title: "Hide and Seek", text: "Hide treats around the room and let them find them. It's like a treasure hunt for their nose!" },
    { title: "Talk to Them", text: "Even if they don't know the words, they love the sound of your voice. Tell them about your day!", img: "assets/wisdom_cat.png" },
    { title: "Sun Spots", text: "Every pet has a favorite sun spot. Try to keep that area clear so they can enjoy their daily vitamin D nap." },
    { title: "Gentle Paws", text: "Teach kids how to pet gently. Two fingers on the back of the head is a great way to start.", img: "assets/wisdom_rabbit.png" },
    { title: "The Lean", text: "If a dog leans against you, they're not being lazy—they're giving you a doggie hug!", img: "assets/wisdom_dog.png" },
    { title: "Purr Power", text: "A cat's purr can actually help lower your blood pressure. It's a win-win for both of you!" },
    { title: "Fresh Air", text: "Even 5 minutes of fresh air can boost a pet's mood. Open a window (safely!) if you can't go out." },
    { title: "Colorful Friends", text: "Birds love bright colors and music! Try playing some soft tunes to keep them chirpy.", img: "assets/wisdom_bird.png" }
];

window.flipPage = function(direction) {
    console.log("Flipping page:", direction);
    
    const recs = (lastAnalysisData && lastAnalysisData.recommendations && lastAnalysisData.recommendations.length > 0) 
                 ? lastAnalysisData.recommendations.map(r => ({ title: "Pet Secret", text: r }))
                 : CASUAL_STATIC_TIPS;
    
    const totalPages = Math.ceil(recs.length / tipsPerPage);
    
    currentTipsPage += direction;
    if (currentTipsPage < 1) currentTipsPage = 1;
    if (currentTipsPage > totalPages) currentTipsPage = totalPages;
    
    renderPaginatedTips(recs);
};

// --- PET JOURNAL LOGIC ---
let journalEntries = JSON.parse(localStorage.getItem('drpet_journal') || '[]');

window.switchBook = function(type) {
    const manualContainer = document.getElementById('manual-book-container');
    const journalContainer = document.getElementById('journal-book-container');
    const toggleManual = document.getElementById('toggle-manual');
    const toggleJournalBtn = document.getElementById('toggle-journal');
    
    if (type === 'manual') {
        manualContainer.classList.remove('hidden');
        journalContainer.classList.add('hidden');
        toggleManual.style.background = 'white';
        toggleManual.style.boxShadow = 'var(--shadow-sm)';
        toggleManual.style.color = 'var(--text-main)';
        toggleJournalBtn.style.background = 'none';
        toggleJournalBtn.style.boxShadow = 'none';
        toggleJournalBtn.style.color = 'var(--text-muted)';
    } else {
        manualContainer.classList.add('hidden');
        journalContainer.classList.remove('hidden');
        toggleJournalBtn.style.background = 'white';
        toggleJournalBtn.style.boxShadow = 'var(--shadow-sm)';
        toggleJournalBtn.style.color = 'var(--text-main)';
        toggleManual.style.background = 'none';
        toggleManual.style.boxShadow = 'none';
        toggleManual.style.color = 'var(--text-muted)';
        renderJournalEntries();
    }
};

window.toggleJournal = function() {
    const book = document.getElementById('journal-book-wrapper');
    if (book) book.classList.toggle('open');
};

window.openJournalEntryForm = function() {
    document.getElementById('journal-modal').classList.remove('hidden');
};

window.closeJournalModal = function() {
    document.getElementById('journal-modal').classList.add('hidden');
};

window.saveJournalEntry = async function() {
    console.log("Save Journal Entry Triggered");
    const noteEl = document.getElementById('journal-note');
    const mediaEl = document.getElementById('journal-media');
    const saveBtn = document.querySelector('.modal-content button[onclick*="saveJournalEntry"]');
    
    if (!noteEl || !mediaEl) {
        console.error("Journal elements not found!");
        return;
    }

    const note = noteEl.value;
    const mediaFile = mediaEl.files[0];
    
    if (!note && !mediaFile) return showToast('Please add a note or photo', '⚠️');
    
    if (saveBtn) {
        saveBtn.innerText = 'Saving...';
        saveBtn.disabled = true;
    }

    try {
        let mediaData = null;
        if (mediaFile) {
            console.log("Reading media file:", mediaFile.name);
            mediaData = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = (e) => {
                    console.log("File read success");
                    resolve({ name: mediaFile.name, type: mediaFile.type, data: e.target.result });
                };
                reader.onerror = (err) => {
                    console.error("File read error:", err);
                    reject('File read failed');
                };
                reader.readAsDataURL(mediaFile);
            });
        }
        
        const entry = {
            date: new Date().toLocaleDateString(),
            note: note,
            media: mediaData,
            timestamp: Date.now()
        };
        
        console.log("Saving entry to localStorage...");
        const tempEntries = [entry, ...journalEntries];
        localStorage.setItem('drpet_journal', JSON.stringify(tempEntries));
        
        journalEntries = tempEntries;
        
        noteEl.value = '';
        mediaEl.value = '';
        window.closeJournalModal();
        window.renderJournalEntries();
        showToast('Entry saved to journal!', '📓');
    } catch (err) {
        console.error("Journal save failure:", err);
        if (err.name === 'QuotaExceededError' || (err.message && err.message.includes('quota'))) {
            showToast('Media too large for browser storage!', '⚠️');
        } else {
            showToast('Save failed: ' + err.message, '❌');
        }
    } finally {
        if (saveBtn) {
            saveBtn.innerText = 'Save Entry';
            saveBtn.disabled = false;
        }
    }
};

window.renderJournalEntries = function() {
    console.log("Rendering Journal Entries...", journalEntries.length);
    const list = document.getElementById('journal-entries-list');
    if (!list) {
        console.error("Could not find journal-entries-list");
        return;
    }
    
    if (journalEntries.length === 0) {
        list.innerHTML = '<p style="text-align:center; color:#a0aec0; font-size:12px; margin-top:20px;">No entries yet. Start writing!</p>';
        return;
    }
    
    list.innerHTML = journalEntries.map((entry, index) => `
        <div onclick="event.stopPropagation(); window.viewJournalEntry(${index})" style="padding:12px; background:#fff; border-radius:12px; border:1px solid #edf2f7; cursor:pointer; transition:all 0.2s;">
            <div style="font-size:10px; color:#FF9A9E; font-weight:800; text-transform:uppercase;">${entry.date}</div>
            <div style="font-size:13px; font-weight:600; color:var(--text-main); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${entry.note || 'Untitled Moment'}</div>
        </div>
    `).join('');
};

window.viewJournalEntry = function(index) {
    console.log("Viewing Journal Entry:", index);
    const entry = journalEntries[index];
    const view = document.getElementById('journal-entry-view');
    if (!view || !entry) return;
    
    let mediaHtml = '';
    if (entry.media) {
        if (entry.media.type && entry.media.type.startsWith('video/')) {
            mediaHtml = `<video src="${entry.media.data}" controls style="width:100%; border-radius:12px; margin-bottom:16px;"></video>`;
        } else {
            mediaHtml = `<img src="${entry.media.data}" style="width:100%; border-radius:12px; margin-bottom:16px; box-shadow:var(--shadow-sm);">`;
        }
    }
    
    view.innerHTML = `
        <div style="animation: fadeIn 0.4s ease;">
            <div style="font-size:12px; font-weight:800; color:#FF9A9E; margin-bottom:4px;">${entry.date}</div>
            <h3 style="margin-bottom:16px;">Journal Moment</h3>
            ${mediaHtml}
            <p style="font-size:14px; line-height:1.6; color:var(--text-main); white-space:pre-wrap;">${entry.note}</p>
            <button onclick="window.deleteJournalEntry(${index})" style="margin-top:20px; background:none; border:none; color:#E53E3E; font-size:12px; cursor:pointer; font-weight:700;">Delete Entry</button>
        </div>
    `;
};

window.deleteJournalEntry = function(index) {
    if (confirm('Delete this journal entry?')) {
        journalEntries.splice(index, 1);
        localStorage.setItem('drpet_journal', JSON.stringify(journalEntries));
        window.renderJournalEntries();
        document.getElementById('journal-entry-view').innerHTML = '<div style="text-align:center; margin-top:80px; color:#a0aec0;"><div style="font-size:48px; margin-bottom:16px;">📸</div><p>Entry deleted</p></div>';
    }
};

window.renderPaginatedTips = function(recs) {
    const container = document.getElementById('tips-container-paginated');
    const pageNum = document.getElementById('tips-page-num');
    if (!container || !pageNum) return;
    
    const start = (currentTipsPage - 1) * tipsPerPage;
    const end = start + tipsPerPage;
    const pageRecs = recs.slice(start, end);
    
    const petName = (lastAnalysisData && lastAnalysisData.pet_name) ? lastAnalysisData.pet_name : "Your Buddy";
    let html = `<h3>${petName}'s Wisdom Page</h3>`;
    
    pageRecs.forEach((rec, idx) => {
        html += `
        <div class="tip-item">
            <h4>${rec.title || '💡 Secret'}</h4>
            ${rec.img ? `<div style="width: 100%; height: 100px; border-radius: 12px; overflow: hidden; margin-bottom: 12px; border: 1px solid #e2e8f0;"><img src="${rec.img}" style="width: 100%; height: 100%; object-fit: cover;"></div>` : ''}
            <p>${rec.text || rec}</p>
        </div>`;
    });
    
    container.innerHTML = html;
    pageNum.innerText = `PAGE ${currentTipsPage}`;
};

// Toast Utility
function showToast(msg, icon = '✅') {
    const toast = document.getElementById('toast');
    document.getElementById('toast-msg').innerText = msg;
    document.getElementById('toast-icon').innerText = icon;
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 4000);
}

// Navigation Logic
window.switchPage = function(pageId, navItem) {
    // Hide all pages
    document.querySelectorAll('.page-content').forEach(page => {
        page.classList.add('hidden');
        page.classList.remove('active');
    });
    
    // Remove active class from all nav items
    document.querySelectorAll('.bottom-nav .nav-item').forEach(item => {
        item.classList.remove('active');
    });
    
    // Show selected page
    const targetPage = document.getElementById(pageId);
    if (targetPage) {
        targetPage.classList.remove('hidden');
        targetPage.classList.add('active');
        
        // If switching to support, try to get location
        if (pageId === 'page-support') {
            window.detectLocation();
        }
    }
    
    // Set active nav item
    if (navItem) {
        navItem.classList.add('active');
    }
};

// --- SUPPORT & BOOKING LOGIC ---
window.detectLocation = function() {
    const locText = document.getElementById('support-location-text');
    if (!locText) return;

    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                locText.innerText = "Showing top veterinary professionals near Coimbatore.";
            },
            (error) => {
                locText.innerText = "Location access denied. Showing top clinics in Coimbatore.";
            }
        );
    }
};

window.openBookingModal = function(hospitalName) {
    const modal = document.getElementById('booking-modal');
    const nameEl = document.getElementById('booking-hospital-name');
    const dateEl = document.getElementById('booking-date');
    
    if (modal && nameEl) {
        nameEl.innerText = hospitalName;
        const today = new Date().toISOString().split('T')[0];
        dateEl.value = today;
        dateEl.min = today;
        modal.classList.remove('hidden');
    }
};

window.closeBookingModal = function() {
    const modal = document.getElementById('booking-modal');
    if (modal) modal.classList.add('hidden');
};

window.confirmBooking = function() {
    const hospital = document.getElementById('booking-hospital-name').innerText;
    const date = document.getElementById('booking-date').value;
    const time = document.getElementById('booking-time').value;
    
    if (!date) return showToast('Please select a date', '⚠️');
    
    showToast(`Appointment confirmed at ${hospital} for ${date} at ${time}!`, '📅');
    window.closeBookingModal();
};

// --- AI VET CHAT LOGIC ---
window.openAIChat = function() {
    const modal = document.getElementById('ai-chat-modal');
    const content = document.getElementById('draggable-chat');
    if (modal) {
        modal.classList.remove('hidden');
        if (content) {
            content.style.left = '0px';
            content.style.top = '0px';
        }
        document.getElementById('ai-chat-input').focus();
        window.makeDraggable(document.getElementById('draggable-chat'), document.getElementById('chat-header'));
    }
};

window.makeDraggable = function(el, header) {
    let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
    if (header) {
        header.onmousedown = dragMouseDown;
    } else {
        el.onmousedown = dragMouseDown;
    }

    function dragMouseDown(e) {
        e = e || window.event;
        e.preventDefault();
        pos3 = e.clientX;
        pos4 = e.clientY;
        document.onmouseup = closeDragElement;
        document.onmousemove = elementDrag;
    }

    function elementDrag(e) {
        e = e || window.event;
        e.preventDefault();
        pos1 = pos3 - e.clientX;
        pos2 = pos4 - e.clientY;
        pos3 = e.clientX;
        pos4 = e.clientY;
        el.style.top = (el.offsetTop - pos2) + "px";
        el.style.left = (el.offsetLeft - pos1) + "px";
    }

    function closeDragElement() {
        document.onmouseup = null;
        document.onmousemove = null;
    }
};

window.closeAIChat = function() {
    const modal = document.getElementById('ai-chat-modal');
    if (modal) modal.classList.add('hidden');
};

window.sendAIVetMessage = async function() {
    const input = document.getElementById('ai-chat-input');
    const container = document.getElementById('ai-chat-messages');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Add user message
    const userDiv = document.createElement('div');
    userDiv.style = "background: #6366f1; color: white; padding: 12px 16px; border-radius: 16px 16px 4px 16px; max-width: 85%; align-self: flex-end; box-shadow: 0 2px 4px rgba(0,0,0,0.1); font-size: 14px; line-height: 1.5;";
    userDiv.innerText = message;
    container.appendChild(userDiv);
    
    input.value = '';
    container.scrollTop = container.scrollHeight;
    
    // Add typing indicator
    const typingDiv = document.createElement('div');
    typingDiv.style = "background: white; padding: 12px 16px; border-radius: 16px; align-self: flex-start; font-size: 12px; color: #718096;";
    typingDiv.innerText = 'Dr. PET is thinking...';
    container.appendChild(typingDiv);
    container.scrollTop = container.scrollHeight;

    try {
        const response = await fetch('/api/ai-vet/consult', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message })
        });
        
        const data = await response.json();
        typingDiv.remove();
        
        const aiDiv = document.createElement('div');
        aiDiv.style = "background: white; padding: 12px 16px; border-radius: 16px 16px 16px 4px; max-width: 85%; align-self: flex-start; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; font-size: 14px; line-height: 1.5; animation: fadeInBubble 0.3s ease-out;";
        
        // Final safety check for the response text
        const responseText = (data && data.response) ? data.response : "I'm processing your request. Please hold on a moment or check your internet connection.";
        aiDiv.innerText = responseText;
        
        container.appendChild(aiDiv);
    } catch (err) {
        console.error("Chat error:", err);
        typingDiv.innerText = 'Unable to reach Dr. PET. Please check your connection.';
    }
    
    container.scrollTop = container.scrollHeight;
};

// Handle Enter Key for Chat
document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && document.activeElement.id === 'ai-chat-input') {
        window.sendAIVetMessage();
    }
});

// Fetch History
async function fetchHistory() {
    try {
        const token = localStorage.getItem('drpet_token');
        if (!token) return;

        const response = await fetch(`/api/history`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!response.ok) throw new Error('Failed to fetch history');

        const jsonResponse = await response.json();
        if (jsonResponse.status !== 'success') throw new Error(jsonResponse.error || 'Failed to parse history');
        const historyData = jsonResponse.data || [];
        
        // Populate Recent Activity Widget
        const recentList = document.getElementById('recent-activity-list');
        if (recentList) {
            if (historyData.length === 0) {
                recentList.innerHTML = `<div style="text-align:center; padding: 20px; color: var(--text-muted); font-size: 13px;">No recent activity</div>`;
            } else {
                let recentHtml = '';
                // Show top 3 recent activities
                historyData.slice(0, 3).forEach(item => {
                    const timeAgo = Math.round((Date.now() / 1000 - item.created_at) / 60);
                    const timeStr = timeAgo < 60 ? `${timeAgo} min ago` : `${Math.round(timeAgo/60)} hrs ago`;
                    let iconSvg = '';
                    if (item.analysis_type === 'live') {
                        iconSvg = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path></svg>`;
                    } else if (item.analysis_type === 'video') {
                        iconSvg = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>`;
                    } else {
                        iconSvg = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>`;
                    }
                    
                    recentHtml += `
                    <div class="activity-item">
                        <div class="activity-icon">${iconSvg}</div>
                        <div class="activity-info"><h5>${item.analysis_type === 'live' ? 'Live Session' : 'Video Upload'}</h5><p>${timeStr}</p></div>
                        <div class="activity-status"></div>
                    </div>`;
                });
                recentList.innerHTML = recentHtml;
            }
        }

        // Populate Behavior History Page
        const historyPageList = document.getElementById('history-list');
        if (historyPageList) {
            if (historyData.length === 0) {
                historyPageList.innerHTML = `
                <div style="text-align:center;padding:60px 20px;color:var(--text-muted);">
                    <div style="font-size:56px;margin-bottom:16px;">🔍</div>
                    <p style="font-weight:700; font-size: 18px; color: var(--text-main); margin-bottom: 8px;">No analyses yet</p>
                    <p style="font-size:14px;">Run a video or live analysis to see results here</p>
                </div>`;
            } else {
                let fullHistoryHtml = `<div style="display: flex; flex-direction: column; gap: 16px;">`;
                historyData.forEach(item => {
                    const dateObj = new Date(item.created_at * 1000);
                    const dateStr = dateObj.toLocaleDateString() + ' ' + dateObj.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                    
                    let statusColor = 'var(--success)';
                    if (item.happiness_score < 40) statusColor = 'var(--danger)';
                    else if (item.happiness_score < 70) statusColor = 'var(--warning)';

                    fullHistoryHtml += `
                    <div style="background: var(--white-solid); border-radius: var(--radius-xl); padding: 24px; border: 1px solid var(--border); box-shadow: var(--shadow-sm); display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                                <h3 style="font-size: 16px; font-weight: 800;">${item.analysis_type === 'live' ? 'Live Stream Analysis' : 'Video Analysis'}</h3>
                                <span style="background: #EBF8FF; color: var(--primary); padding: 2px 8px; border-radius: 99px; font-size: 11px; font-weight: 700;">${item.pet_name || 'Unknown Pet'}</span>
                            </div>
                            <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 4px;">${dateStr}</p>
                            <p style="font-size: 14px; color: var(--text-main); font-weight: 600;">State: ${item.emotional_state}</p>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 24px; font-weight: 800; color: ${statusColor};">${Math.round(item.happiness_score)}%</div>
                            <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 700;">Score</div>
                        </div>
                    </div>`;
                });
                fullHistoryHtml += `</div>`;
                historyPageList.innerHTML = fullHistoryHtml;
            }
        }

    } catch (e) {
        console.error("Failed to load history:", e);
    }
}

// Fetch Daily Highlight
async function fetchDailyHighlight() {
    try {
        const titleEl = document.getElementById('highlight-title');
        const moodEl = document.getElementById('highlight-mood');
        const insightEl = document.getElementById('highlight-insight');
        const suggestEl = document.getElementById('highlight-suggestion');

        if (!titleEl) return;

        const activePet = JSON.parse(localStorage.getItem('drpet_active_pet') || 'null');
        const token = localStorage.getItem('drpet_token');
        const petType = activePet ? activePet.species : 'pet';

        const response = await fetch(`/api/highlight?pet_type=${petType}`, {
            headers: token ? { 'Authorization': `Bearer ${token}` } : {}
        });
        if (!response.ok) throw new Error('Highlight API error');

        const data = await response.json();
        titleEl.innerText = data.daily_highlight || `Your pet had a good day.`;
        moodEl.innerText = data.mood_summary || 'Stable';
        insightEl.innerText = data.key_insight || 'Normal routine observed.';
        suggestEl.innerText = data.suggestion || 'Watch Summary';

    } catch (e) {
        console.error("Failed to load daily highlight:", e);
        const titleEl = document.getElementById('highlight-title');
        if (titleEl) {
            titleEl.innerText = "Run an analysis to see today's highlights ✨";
            document.getElementById('highlight-mood').innerText = "Waiting for data";
            document.getElementById('highlight-insight').innerText = "Upload a video or use live camera to start.";
            document.getElementById('highlight-suggestion').innerText = "Start Analysis";
        }
    }
}

// Main Upload Handler — uses XHR for real progress
function handleUpload(file) {
    if (!file.type.startsWith('video/')) {
        showToast('Please upload a video file', '⚠️');
        return;
    }

    uploadProgress.classList.remove('hidden');
    uploadProgress.classList.add('scanning-active');
    const iconBox = document.getElementById('upload-icon-box');
    if (iconBox) iconBox.classList.add('upload-icon-pulse');
    
    document.getElementById('progress-bar').style.width = '2%';
    document.getElementById('progress-pct').innerText = 'Starting Upload...';
    console.log("UPLOAD: Starting for file:", file.name);

    const formData = new FormData();
    formData.append('file', file);

    const activePetRaw = localStorage.getItem('drpet_active_pet');
    if (activePetRaw) {
        const pet = JSON.parse(activePetRaw);
        formData.append('pet_id', pet.id || '');
        formData.append('pet_name', pet.name || 'Unknown');
    }

    const token = localStorage.getItem('drpet_token');
    const xhr = new XMLHttpRequest();

    xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
            const pct = Math.round((e.loaded / e.total) * 60); // upload = 0–60%
            document.getElementById('progress-bar').style.width = pct + '%';
            document.getElementById('progress-pct').innerText = pct + '% uploaded';
        }
    });

    xhr.onload = () => {
        if (xhr.status === 200) {
            const res = JSON.parse(xhr.responseText);
            if (res.status === 'success' && res.data && res.data.file_id) {
                document.getElementById('progress-pct').innerText = '60% — AI analyzing...';
                document.getElementById('progress-bar').style.width = '60%';
                pollResults(res.data.file_id);
            } else {
                showToast('Upload failed: ' + (res.error || 'Unknown error'), '❌');
                uploadProgress.classList.add('hidden');
                uploadProgress.classList.remove('scanning-active');
            }
        } else {
            showToast('Upload failed: ' + xhr.status, '❌');
            uploadProgress.classList.add('hidden');
            uploadProgress.classList.remove('scanning-active');
        }
    };

    xhr.onerror = () => {
        showToast('Server connection failed', '❌');
        uploadProgress.classList.add('hidden');
    };

    xhr.open('POST', `/analyze/video`);
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    showToast('Uploading video...', '📤');
    xhr.send(formData);
}

function updateStep(stepId) {
    const steps = ['step-upload', 'step-vision', 'step-acoustic', 'step-report'];
    const currentIdx = steps.indexOf(stepId);

    steps.forEach((id, idx) => {
        const el = document.getElementById(id);
        if (idx <= currentIdx) el.classList.add('step-active');
        else el.classList.remove('step-active');
    });

    const progressPct = ((currentIdx + 1) / steps.length) * 100;
    document.getElementById('progress-bar').style.width = `${progressPct}%`;
    document.getElementById('progress-pct').innerText = `${Math.round(progressPct)}%`;
}

async function pollResults(fileId) {
    console.log("POLLING: Started for ID:", fileId);
    let phase = 0;
    let attempts = 0;
    const MAX_ATTEMPTS = 90; // 3 minutes max (90 x 2s)
    const messages = [
        'AI scanning frames...',
        'Detecting animal behavior...',
        'Analyzing body language...',
        'Cross-referencing breed data...',
        'Generating clinical report...'
    ];
    const interval = setInterval(async () => {
        attempts++;
        if (attempts > MAX_ATTEMPTS) {
            clearInterval(interval);
            showToast('Analysis timed out. Please try a shorter video.', '⏱️');
            uploadProgress.classList.add('hidden');
            uploadProgress.classList.remove('scanning-active');
            return;
        }

        try {
            const response = await fetch(`/results/${fileId}`);
            const jsonRes = await response.json();
            
            if (jsonRes.status === 'error') {
                clearInterval(interval);
                showToast(jsonRes.error || 'Analysis failed', '❌');
                uploadProgress.classList.add('hidden');
                uploadProgress.classList.remove('scanning-active');
                return;
            }

            const data = jsonRes.data || {};

            // Animate progress 60% → 98%
            phase++;
            const pct = Math.min(60 + phase * 2, 98);
            document.getElementById('progress-bar').style.width = pct + '%';
            const msg = messages[Math.min(phase - 1, messages.length - 1)];
            document.getElementById('progress-pct').innerText = msg;
            console.log("POLLING: Attempt", attempts, "Progress:", pct, "% -", msg);

            if (data.status === 'completed' || data.metrics) {
                clearInterval(interval);
                document.getElementById('progress-bar').style.width = '100%';
                document.getElementById('progress-pct').innerText = 'Complete!';
                uploadProgress.classList.remove('scanning-active');
                setTimeout(() => displayResults(data), 400);
            } else if (data.status === 'error') {
                clearInterval(interval);
                showToast(data.analysis || 'Analysis failed', '❌');
                uploadProgress.classList.add('hidden');
                uploadProgress.classList.remove('scanning-active');
            }
        } catch (error) {
            console.warn('Polling...', attempts);
        }
    }, 2000);
}

function displayResults(data) {
    lastAnalysisData = data;

    // Switch Panels
    if (insightIdle) insightIdle.classList.add('hidden');
    if (analysisResults) analysisResults.classList.remove('hidden');
    if (uploadProgress) uploadProgress.classList.add('hidden');
    
    // Switch to Analyze tab automatically
    if (window.switchPage) {
        const analyzeNav = document.querySelectorAll('.nav-menu .nav-item')[2];
        if (analyzeNav) window.switchPage('page-analyze', analyzeNav);
    }
    
    const metricsCard = document.getElementById('metrics-card');
    if (metricsCard) metricsCard.classList.add('active');

    const placeholder = document.getElementById('vision-placeholder');
    if (placeholder) placeholder.classList.add('hidden');

    // Update Banner & Ring
    const score = data.metrics ? data.metrics.happiness_score : 50;
    const sentiment = data.ai_insights ? data.ai_insights.emotional_state : (data.metrics ? data.metrics.acoustic_sentiment : 'Analyzed');

    const emotionValue = document.getElementById('emotion-value');
    if (emotionValue) emotionValue.innerText = sentiment;
    
    const ringPct = document.getElementById('ring-pct');
    if (ringPct) ringPct.innerText = `${Math.round(score)}%`;
    
    const ringFill = document.getElementById('ring-fill');
    if (ringFill) ringFill.style.strokeDasharray = `${score}, 100`;

    // Update Icons based on sentiment
    const iconMap = {
        'Happy': '😊', 'Playful': '🎾', 'Excited': '✨',
        'Anxious': '😟', 'Fearful': '🌑', 'Aggressive': '⚠️',
        'Stable': '😐', 'Balanced': '⚖️', 'Relaxed': '🍃'
    };
    const emotionIconStr = Object.entries(iconMap).find(([k]) => sentiment.includes(k))?.[1] || '🐕';
    const emotionIcon = document.getElementById('emotion-icon');
    if (emotionIcon) emotionIcon.innerText = emotionIconStr;

    // Sidebar Metrics
    const happinessEl = document.getElementById('happiness-score-text');
    if (happinessEl) {
        happinessEl.innerText = `${score.toFixed(1)}%`;
        happinessEl.style.color = score > 70 ? 'var(--success)' : (score > 40 ? 'var(--warning)' : 'var(--danger)');
    }

    const acousticSentiment = document.getElementById('acoustic-sentiment');
    if (acousticSentiment && data.metrics) acousticSentiment.innerText = data.metrics.acoustic_sentiment;

    const anomalyEl = document.getElementById('anomaly-status');
    if (anomalyEl && data.temporal_intelligence) {
        const isAnomaly = data.temporal_intelligence.is_anomaly;
        anomalyEl.innerText = isAnomaly ? "Pattern Shift Detected" : "Normal Baseline";
        anomalyEl.style.color = isAnomaly ? 'var(--danger)' : 'var(--success)';
    }

    // Summary Text
    const analysisSummary = document.getElementById('analysis-summary');
    if (analysisSummary) analysisSummary.innerText = data.analysis || "Analysis complete.";

    // New FRS Fields
    const pBadge = document.getElementById('personality-badge');
    const eBadge = document.getElementById('env-fit-badge');
    
    // Extracting from nested individual_pets or direct root if available
    const petData = (data.individual_pets && data.individual_pets[0]) ? data.individual_pets[0].pet_data : data;
    
    if (pBadge) pBadge.innerText = petData.personality_profile || "Analyzing...";
    if (eBadge) eBadge.innerText = petData.social_environmental_fit || "Optimal Setup";

    // Key Point List
    const keyPointsList = document.getElementById('keyPointsList');
    if (keyPointsList) {
        let points = [];
        if (data.ai_insights && data.ai_insights.key_points && data.ai_insights.key_points.length > 0) {
            points = data.ai_insights.key_points;
        } else if (data.ai_insights && data.ai_insights.behavioral_signals && data.ai_insights.behavioral_signals.length > 0) {
            points = data.ai_insights.behavioral_signals;
        } else {
            points = ["Visual behavior tracking active", "Acoustic signature processed"];
        }
        keyPointsList.innerHTML = `<ul style="margin:0; padding-left:16px;">${points.map(p => `<li style="margin-bottom:6px; color:#4A5568;">${p}</li>`).join('')}</ul>`;
    }

    // Breed Card Logic
    const ragBox = document.getElementById('rag-box');
    if (ragBox) {
        const card = data.breed_card;
        if (card && card.breed) {
            const traits = (card.temperament_traits || []).map(t => `<span class="breed-trait-pill">${t}</span>`).join('');
            ragBox.innerHTML = `
                <div class="breed-card">
                    <div class="breed-card-header">
                        <span class="breed-name">${card.breed}</span>
                        <span class="card-badge card-badge-green">${card.source_quality || 'AI verified'}</span>
                    </div>
                    <div class="breed-meta">
                        <span>📍 ${card.origin || 'Global'}</span>
                        <span>📏 ${card.size || 'Mixed'}</span>
                        <span>⚡ ${card.energy_level || 'Moderate'}</span>
                    </div>
                    <p class="breed-known-for">${card.known_for || 'Affectionate and intelligent companion.'}</p>
                    <div class="breed-section-label">Temperament</div>
                    <div class="breed-traits">${traits}</div>
                    <div class="breed-section-label">Expert Advice</div>
                    <p class="breed-advice">💡 ${card.owner_advice || 'Maintain consistent routine and mental stimulation.'}</p>
                </div>
            `;
        }
    }

    // Recommendations
    const recList = document.getElementById('recommendations');
    if (recList && data.recommendations && data.recommendations.length > 0) {
        recList.innerHTML = `<ul style="margin:0; padding-left:16px; color:#285E61;">${data.recommendations.map(r => `<li style="margin-bottom:6px;">${r}</li>`).join('')}</ul>`;
    } else if (recList) {
        recList.innerHTML = '<p style="color: #285E61; margin: 0; font-weight: 500;">Monitor your pet closely and ensure they have a comfortable environment.</p>';
    }

    // Behavior Management Guide (New)
    const guideBox = document.getElementById('behavior-management-guide');
    const guideTitle = document.getElementById('guide-title');
    const guideText = document.getElementById('guide-text');
    
    if (guideBox && guideTitle && guideText) {
        const isStressed = sentiment.includes('Anxious') || sentiment.includes('Fearful') || sentiment.includes('Aggressive') || sentiment.includes('Angry');
        
        if (isStressed) {
            guideBox.style.display = 'block';
            if (sentiment.includes('Aggressive') || sentiment.includes('Angry')) {
                guideTitle.innerHTML = '⚠️ Critical: Managing Aggression';
                guideText.innerHTML = 'Your pet is showing signs of high stress. **Do not approach or try to touch them.** Give them space, turn off loud noises, and let them calm down in a quiet room. If this behavior persists, consult a behaviorist.';
            } else {
                guideTitle.innerHTML = '😟 Support: Managing Anxiety';
                guideText.innerHTML = 'Your pet seems nervous. Try to speak in a soft, low voice. Avoid sudden movements and provide a "safe spot" like a crate or bed. Gentle pheromone sprays or a weighted vest can also help.';
            }
        } else {
            guideBox.style.display = 'none';
        }
    }

    // Download Button
    const downloadBtn = document.getElementById('downloadAuditBtn');
    if (downloadBtn && data.clinical_audit_url) {
        downloadBtn.onclick = () => window.open(data.clinical_audit_url, '_blank');
        downloadBtn.classList.remove('hidden');
    }

    // Populate Tips Page (3D Book UI)
    const tipsBookLeft = document.getElementById('tips-book-left');
    if (tipsBookLeft) {
        if (data && data.recommendations) {
            // Render AI results
            tipsBookLeft.innerHTML = `
                <h3>Pet Wisdom 101</h3>
                <p>Hey! Welcome to the secret manual for <strong>${data.pet_name || 'your buddy'}</strong>.</p>
                <p>Our AI spent some time watching and listening, and we've got some cool tips to make them even happier!</p>
                <div style="margin-top: 20px; padding: 15px; background: #fff5f5; border-radius: 12px; font-size: 13px; color: #e53e3e; border: 1px dashed #feb2b2;">
                    <strong>Feeling like:</strong> ${sentiment}<br>
                    <strong>Goal:</strong> Extra tail wags!
                </div>
                <div class="page-number">BY DR. PET</div>
            `;
            currentTipsPage = 1;
            renderPaginatedTips(data.recommendations.map(r => ({ title: "Pet Secret", text: r })));
        } else {
            // Render default static welcome
            currentTipsPage = 1;
            renderPaginatedTips(CASUAL_STATIC_TIPS);
        }
    }

    // Populate Shop Page
    const pageShop = document.getElementById('page-shop');
    if (pageShop) {
        let shopCategory = "General Health";
        let items = [
            { name: "Premium Joint Supplement", price: "$24.99", icon: "🦴" },
            { name: "Interactive Puzzle Toy", price: "$18.50", icon: "🧩" }
        ];
        
        if (sentiment.includes("Anxious") || sentiment.includes("Stress")) {
            shopCategory = "Calming & Stress Relief";
            items = [
                { name: "Calming Hemp Chews", price: "$29.99", icon: "🌿" },
                { name: "Anti-Anxiety Pheromone Diffuser", price: "$34.50", icon: "💨" },
                { name: "Weighted Anxiety Vest", price: "$45.00", icon: "👕" }
            ];
        } else if (sentiment.includes("Playful") || sentiment.includes("Excited")) {
            shopCategory = "Active Play & Training";
            items = [
                { name: "Durable Fetch Ball", price: "$12.99", icon: "🎾" },
                { name: "Agility Training Kit", price: "$59.99", icon: "🏃" }
            ];
        } else if (sentiment.includes("Pain")) {
             shopCategory = "Recovery & Comfort";
             items = [
                { name: "Orthopedic Memory Foam Bed", price: "$89.99", icon: "🛏️" },
                { name: "Soothing Muscle Balm", price: "$19.99", icon: "🧴" }
             ];
        }

        let shopHtml = `<div style="margin-bottom: 32px;">
            <h2 style="font-size: 24px; font-weight: 800; margin-bottom: 8px;">Pet Pharmacy & Shop</h2>
            <p style="color: var(--text-muted);">Curated for: <strong>${shopCategory}</strong></p>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px;">`;
        
        items.forEach(item => {
            shopHtml += `
            <div style="background: var(--white-solid); border-radius: var(--radius-xl); padding: 24px; text-align: center; border: 1px solid var(--border); box-shadow: var(--shadow-sm); cursor: pointer; transition: 0.2s;">
                <div style="font-size: 48px; margin-bottom: 16px;">${item.icon}</div>
                <h4 style="font-size: 14px; font-weight: 700; margin-bottom: 8px;">${item.name}</h4>
                <div style="color: var(--primary); font-weight: 800; font-size: 16px; margin-bottom: 16px;">${item.price}</div>
                <button class="btn-primary" onclick="showToast('Added to Cart! 🛒', '🛍️')" style="background: #EBF8FF; color: var(--primary); padding: 8px 16px; border: none; border-radius: 99px; font-weight: 700; width: 100%; cursor: pointer;">Add to Cart</button>
            </div>`;
        });
        shopHtml += `</div>`;
        pageShop.innerHTML = shopHtml;
    }

    // Charts
    initBehaviorChart(score);
    initFFTChart(data.metrics?.fft_peaks || []);

    showToast('Analysis complete', '✨');
}

function initBehaviorChart(score = 50) {
    const chartEl = document.getElementById('behaviorChart');
    if (!chartEl) return;
    const ctx = chartEl.getContext('2d');
    if (chartInstance) chartInstance.destroy();

    const labels = Array.from({ length: 20 }, (_, i) => `${i}s`);
    const chartData = labels.map(() => Math.sin(Date.now() / 1000) * 10 + score + Math.random() * 5);

    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                data: chartData,
                borderColor: '#6366f1',
                backgroundColor: (context) => {
                    const chart = context.chart;
                    const { ctx, chartArea } = chart;
                    if (!chartArea) return null;
                    const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
                    gradient.addColorStop(0, 'rgba(99, 102, 241, 0.2)');
                    gradient.addColorStop(1, 'rgba(99, 102, 241, 0)');
                    return gradient;
                },
                fill: true,
                tension: 0.4,
                borderWidth: 3,
                pointRadius: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { display: false },
                x: { grid: { display: false }, ticks: { display: false } }
            }
        }
    });
}

function initFFTChart(fftData) {
    const chartEl = document.getElementById('fftChart');
    if (!chartEl) return;
    const ctx = chartEl.getContext('2d');
    if (fftChartInstance) fftChartInstance.destroy();

    // Ensure we have some data to show, even if simulated
    const dataToUse = (fftData && fftData.length > 0) ? fftData : Array.from({length: 12}, () => Math.random() * 40 + 10);
    const labels = dataToUse.map((_, i) => `${i * 2}Hz`);

    fftChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                data: dataToUse,
                backgroundColor: 'rgba(99, 102, 241, 0.4)',
                hoverBackgroundColor: '#6366f1',
                borderRadius: 8,
                barThickness: 12
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 1000 },
            plugins: { 
                legend: { display: false },
                tooltip: { enabled: true }
            },
            scales: {
                y: { display: false, beginAtZero: true },
                x: { 
                    grid: { display: false },
                    ticks: { color: '#94a3b8', font: { size: 10 } }
                }
            }
        }
    });
}

// Live Stream Logic
window.startLiveStream = async function() {
    const video = document.getElementById('live-video');
    const canvas = document.getElementById('live-canvas');
    const ctx = canvas.getContext('2d');

    // Check we're on localhost/server (not file://)
    if (window.location.protocol === 'file:') {
        showToast('Please open via http://localhost:8000 — not as a file!', '⚠️');
        return;
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'environment' }
        });
        video.srcObject = stream;

        // Show inline live section
        const liveBtn = document.getElementById('live-stream-btn');
        if (liveBtn) {
            liveBtn.innerText = 'Initializing...';
            liveBtn.style.background = '#3182CE';
            liveBtn.style.color = 'white';
        }
        document.getElementById('live-feed-container').classList.remove('hidden');

        // Reset state
        live_sessions_markers_count = 0;
        synthesisReady = false;
        document.getElementById('live-observation-feed').innerHTML = '';
        document.getElementById('live-behavior-display').innerText = '';
        document.getElementById('live-animal-type').innerText = '🔍 Point your camera at your pet...';
        document.getElementById('live-confidence-bar').style.width = '0%';
        document.getElementById('live-confidence-pct').innerText = '0%';
        document.getElementById('live-obs-count').innerText = '0 observations';
        document.getElementById('synthesis-ready-banner').classList.add('hidden');

        // WebSocket connection
        let reconnectAttempts = 0;
        let wsForceClosed = false;
        
        function connectWS() {
            const wsHost = window.location.hostname;
            const wsPort = window.location.port ? `:${window.location.port}` : '';
            const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
            const wsUrl = `${wsProtocol}://${wsHost}${wsPort}/ws/stream?node_id=${nodeId}`;
            console.log('Connecting WebSocket:', wsUrl);
            streamSocket = new WebSocket(wsUrl);
            document.getElementById('api-status-text').innerText = 'Connecting...';

            streamSocket.onopen = () => {
                showToast('📡 Live Camera Active — point at your pet!', '📡');
                document.getElementById('api-status-text').innerText = 'Connected';
                const liveBtn = document.getElementById('live-stream-btn');
                if (liveBtn) {
                    liveBtn.innerText = 'ON LIVE';
                    liveBtn.style.background = '#E53E3E';
                }

                // Send frames every 500ms
                if (streamInterval) clearInterval(streamInterval);
                streamInterval = setInterval(() => {
                    if (streamSocket.readyState === WebSocket.OPEN && video.videoWidth > 0) {
                        const scale = Math.min(640 / video.videoWidth, 1.0);
                        canvas.width  = Math.round(video.videoWidth  * scale);
                        canvas.height = Math.round(video.videoHeight * scale);
                        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                        canvas.toBlob(blob => {
                            if (blob && streamSocket.readyState === WebSocket.OPEN)
                                streamSocket.send(blob);
                        }, 'image/jpeg', 0.65);
                    }
                }, 500);
            };

            streamSocket.onerror = (e) => {
                console.error('WS error', e);
                document.getElementById('api-status-text').innerText = 'Connection Error';
            };

            streamSocket.onclose = () => {
                if (streamInterval) clearInterval(streamInterval);
                document.getElementById('api-status-text').innerText = 'Disconnected';
                if (!wsForceClosed && reconnectAttempts < 5) {
                    reconnectAttempts++;
                    console.log(`WS reconnecting... Attempt ${reconnectAttempts}`);
                    setTimeout(connectWS, 2000 * reconnectAttempts);
                } else if (!wsForceClosed) {
                    showToast('Connection failed permanently', '❌');
                }
            };

            streamSocket.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    
                    if (msg.type === 'error') {
                        showToast(msg.payload.message || 'Server error', '❌');
                        return;
                    }
                    
                    if (msg.type !== 'live_update') return;
                    
                    const data = msg.payload;
                    if (data.status !== 'active') return;

                    currentSessionId = data.session_id;
                    const metrics = data.live_metrics;

                    if (metrics && metrics.pet_detected) {
                        const conf        = Math.round((metrics.confidence || 0) * 100);
                        const animalType  = (metrics.type || 'pet');
                        const animalLabel = animalType.charAt(0).toUpperCase() + animalType.slice(1);

                        document.getElementById('live-animal-type').innerHTML =
                            `🐾 <strong>${animalLabel}</strong> detected`;
                        document.getElementById('live-behavior-display').innerText =
                            metrics.behavior || 'Observing';
                        document.getElementById('live-confidence-bar').style.width = conf + '%';
                        document.getElementById('live-confidence-pct').innerText  = conf + '%';
                        document.getElementById('api-status-text').innerText =
                            `Tracking ${animalLabel} · ${conf}% conf`;

                        // Heartbeat observations
                        if (data.heartbeat && data.heartbeat.markers && data.heartbeat.markers.length > 0) {
                            const feed = document.getElementById('live-observation-feed');
                            data.heartbeat.markers.forEach(m => {
                                live_sessions_markers_count++;
                                const row = document.createElement('div');
                                row.style = 'background:rgba(255,255,255,0.07);border-radius:8px;padding:6px 10px;font-size:12px;color:#D1FAE5;animation:fadeIn 0.3s ease;';
                                row.innerHTML = `<span style="color:#10B981;margin-right:6px;">●</span>${m}`;
                                feed.insertBefore(row, feed.firstChild);
                                while (feed.children.length > 6) feed.removeChild(feed.lastChild);
                            });
                            document.getElementById('live-obs-count').innerText =
                                `${live_sessions_markers_count} observation${live_sessions_markers_count !== 1 ? 's' : ''}`;

                            if (data.heartbeat.is_ready && !synthesisReady) {
                                synthesisReady = true;
                                document.getElementById('synthesis-ready-banner').classList.remove('hidden');
                                showToast('✅ Ready! Tap "Generate Full Report"', '🧠');
                            }
                        }
                    } else {
                        document.getElementById('api-status-text').innerText = 'Scanning...';
                        document.getElementById('live-animal-type').innerText = '🔍 Point camera at your pet...';
                        document.getElementById('live-behavior-display').innerText = '';
                        document.getElementById('live-confidence-bar').style.width = '0%';
                        document.getElementById('live-confidence-pct').innerText = '0%';
                    }
                } catch (parseErr) {
                    console.warn('WS parse error:', parseErr);
                }
            };
        }
        connectWS();
        
        // Add cleanup hook onto window to cleanly close socket when switching away
        window.killLiveStream = () => {
            wsForceClosed = true;
            if (streamSocket) streamSocket.close();
            if (streamInterval) clearInterval(streamInterval);
        };

    } catch (err) {
        console.error('Camera error:', err);
        if (err.name === 'NotAllowedError') {
            showToast('Camera permission denied — allow it in your browser settings', '❌');
        } else if (err.name === 'NotFoundError') {
            showToast('No camera found on this device', '❌');
        } else {
            showToast('Camera error: ' + err.message, '❌');
        }
    }
}

// Global Synthesis Function

window.finalizeLiveSession = async () => {
    if (!currentSessionId) {
        console.warn("SYNTHESIS: No active session ID found.");
        return;
    }

    // UI Feedback: Synthesis Mode
    const banner = document.getElementById('synthesis-ready-banner');
    const summary = document.getElementById('analysis-summary');

    banner.innerHTML = `<div class="synthesis-banner-content"><span>⚙️ Processing Session Evidence...</span><div class="spinner-sm"></div></div>`;
    summary.innerHTML = `<div class="synthesis-mode"><strong>SYNTHESIS MODE:</strong> Deep AI is aggregating ${live_sessions_markers_count || 'multiple'} observations into a clinical record. Please wait...</div>`;

    console.log("SYNTHESIS: Triggering fetch for session:", currentSessionId);
    showToast("Deep Synthesis Started...", "🧠");

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);

        const token = localStorage.getItem('drpet_token');
        const activePet = JSON.parse(localStorage.getItem('drpet_active_pet') || 'null');

        const res = await fetch(`/api/live/synthesis`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { 'Authorization': `Bearer ${token}` } : {})
            },
            body: JSON.stringify({
                session_id: currentSessionId,
                pet_id: activePet?.id || null,
                pet_name: activePet?.name || null
            }),
            signal: controller.signal
        });
        clearTimeout(timeoutId);

        const report = await res.json();
        console.log("SYNTHESIS: Received result:", report);

        banner.classList.add('hidden');
        document.getElementById('marker-log').innerHTML = '';

        displayResults(report);
        currentSessionId = null;
        synthesisReady = false;
        showToast("Diagnosis Complete!", "✅");
    } catch (e) {
        console.error("SYNTHESIS FAILURE:", e);
        showToast("Synthesis timed out", "❌");
        banner.innerHTML = `<div class="synthesis-banner-content"><span>❌ Problem reaching AI brain.</span><button class="btn btn-sm" onclick="finalizeLiveSession()">Retry Synthesis</button></div>`;
    }
};

window.stopLiveStream = function() {
    if (streamInterval) clearInterval(streamInterval);
    if (streamSocket) streamSocket.close();

    const video = document.getElementById('live-video');
    const stream = video.srcObject;
    if (stream) stream.getTracks().forEach(track => track.stop());

    video.srcObject = null;
    document.getElementById('live-feed-container').classList.add('hidden');
    
    const liveBtn = document.getElementById('live-stream-btn');
    if (liveBtn) {
        liveBtn.innerText = 'Go Live';
        liveBtn.style.background = '';
        liveBtn.style.color = '';
    }

    // Hide live panel
    const livePanel = document.getElementById('live-realtime-panel');
    if (livePanel) livePanel.style.display = 'none';
    const genBtn = document.getElementById('live-gen-btn');
    if (genBtn) genBtn.remove();

    // Trigger Synthesis if we have any data
    if (currentSessionId) {
        window.finalizeLiveSession();
    }
}

// Remote Monitoring Logic
window.openRemoteModal = function() {
    const link = `${window.location.origin}/?remote=true&node=${nodeId}`;
    const display = document.getElementById('remote-link-display');
    if (display) display.innerText = link;
    const modal = document.getElementById('remote-modal');
    if (modal) modal.classList.remove('hidden');
};

window.closeRemoteModal = function() {
    const modal = document.getElementById('remote-modal');
    if (modal) modal.classList.add('hidden');
};

async function startRemoteMonitoring() {
    document.getElementById('remote-modal').classList.add('hidden');
    
    // Show live feed container in remote mode
    document.getElementById('live-stream-btn').classList.add('hidden');
    document.getElementById('stop-stream-btn').classList.remove('hidden');
    document.getElementById('live-feed-container').classList.remove('hidden');
    
    const video = document.getElementById('live-video');
    video.classList.add('hidden');
    
    // Show a placeholder for remote
    const videoWrapper = document.querySelector('.video-wrapper');
    const existingPlaceholder = document.getElementById('remote-view-placeholder');
    if (!existingPlaceholder) {
        const placeholder = document.createElement('div');
        placeholder.id = 'remote-view-placeholder';
        placeholder.style = "width: 100%; height: 240px; background: #1f2937; display: flex; flex-direction: column; align-items: center; justify-content: center; color: white; border-radius: 16px;";
        placeholder.innerHTML = `
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2" style="margin-bottom: 12px; animation: pulse-soft 2s infinite;"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"></rect><line x1="12" y1="18" x2="12.01" y2="18"></line></svg>
            <p>Receiving Feed from Remote Camera...</p>
        `;
        videoWrapper.insertBefore(placeholder, videoWrapper.firstChild);
    }
    
    document.getElementById('api-status-text').innerText = "Connecting to Remote Session...";
    
    currentSessionId = nodeId;
    live_sessions_markers_count = 0;
    
    // Poll the backend status
    remotePollInterval = setInterval(async () => {
        try {
            const res = await fetch(`/api/live/status/${nodeId}`);
            const data = await res.json();
            
            if (data.status === 'active') {
                document.getElementById('api-status-text').innerText = `Remote Tracking: ${data.primary_state}`;
                
                // Show pill if markers found
                if (data.markers_count > live_sessions_markers_count) {
                    const diff = data.markers_count - live_sessions_markers_count;
                    const log = document.getElementById('marker-log');
                    for (let i = 0; i < diff; i++) {
                        const pill = document.createElement('span');
                        pill.className = 'marker-pill';
                        pill.innerText = `📎 Remote Observation`;
                        log.prepend(pill);
                    }
                    live_sessions_markers_count = data.markers_count;
                }
                
                if (data.markers_count >= 8 && !synthesisReady) {
                    synthesisReady = true;
                    document.getElementById('synthesis-ready-banner').classList.remove('hidden');
                    showToast("Remote Observation complete.", "🧠");
                }
            } else {
                document.getElementById('api-status-text').innerText = "Waiting for remote camera...";
            }
        } catch (e) {
            console.warn("Polling remote status failed", e);
        }
    }, 2000);
    
    // Override stopLiveStream for remote
    const oldStop = window.stopLiveStream;
    window.stopLiveStream = function() {
        if (remotePollInterval) clearInterval(remotePollInterval);
        const p = document.getElementById('remote-view-placeholder');
        if (p) p.remove();
        oldStop();
        window.stopLiveStream = oldStop; // restore
    };
}

function sendFeedback(isAccurate) {
    if (!lastAnalysisData) return;
    fetch(`/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_id: lastAnalysisData.file_id, is_accurate: isAccurate })
    }).then(() => {
        showToast('Feedback recorded. Thank you!');
    });
}

function resetUI() {
    location.reload();
}
