// ================= CONFIG ==================
let CURRENT_TOPIC = "food";
let IS_LOGGED_IN = document.body.dataset.user !== "";

document.addEventListener("DOMContentLoaded", () => {
    const msgBox = document.getElementById("communityMessages");
    const input = document.getElementById("communityInput");
    const sendBtn = document.getElementById("sendBtn");
    const imgBtn = document.getElementById("imgBtn");
    const imgInput = document.getElementById("imgInput");
    const emojiPicker = document.getElementById("emojiPicker");
    const emojiBtn = document.getElementById("emojiBtn");

    const EMOJIS = [
        "😀","😁","😂","🤣","😊","😍","😘","😎","🤩","😮",
        "😢","😭","😡","🙏","💪","👏","👍","👎","🔥","✨",
        "❤️","💔","💯","🎉","🎈","🍔","🍕","🍟","🍣","🍜",
        "🍰","🍩","☕","🍺","🥂","🌮","🌶️","🐶","🐱","🐼"
    ];

    // ================ ENTER TO SEND ================
    sendBtn.addEventListener("click", (e) => {
        e.preventDefault();
        sendMsg();
    });

    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            if (e.shiftKey) return; 
            e.preventDefault();
            sendMsg();
        }
    });

    input.addEventListener("input", () => {
        input.style.height = "auto";
        input.style.height = (input.scrollHeight) + "px";
    });

    // ================ LIMIT 500 CHARS =================
    const MAX_LEN = 500;

    input.addEventListener("input", () => {
        if (input.value.length > MAX_LEN) {
            input.value = input.value.substring(0, MAX_LEN);
        }

        let counter = document.getElementById("charCounterCommunity");
        if (!counter) {
            counter = document.createElement("div");
            counter.id = "charCounterCommunity";
            counter.style.cssText = `
                text-align:right;
                font-size:12px;
                color:#777;
                margin-top:3px;
                margin-right:10px;
            `;
            input.parentElement.appendChild(counter);
        }

        counter.textContent = `${input.value.length}/500`;
        counter.style.color = input.value.length >= 450 ? "#d22620ff" : "#777";
    });

    // ================ EMOJI PICKER =================
    EMOJIS.forEach(e => {
        const span = document.createElement("span");
        span.textContent = e;
        span.onclick = () => {
            input.value += e;
            emojiPicker.style.display = "none";
        };
        emojiPicker.appendChild(span);
    });

    emojiBtn.onclick = () => {
        emojiPicker.style.display =
            emojiPicker.style.display === "block" ? "none" : "block";
    };

    // ================ AUTH =================
    function checkAuth() {
        if (!IS_LOGGED_IN) {
            document.querySelector('.chat-input-footer').style.display = 'none';
            return false;
        }
        return true;
    }

    // ================ REACTIONS =================
    function addReactionListeners() {
        document.addEventListener('click', (e) => {
            const msgRow = e.target.closest('.msg-row');
            if (msgRow && !e.target.closest('.reactions-container')) {
                const messageId = msgRow.dataset.messageId;
                if (messageId) {
                    showReactionPopup(messageId, e.clientX, e.clientY);
                }
            }
        });
    }

    function showReactionPopup(messageId, x, y) {
        const oldPopup = document.getElementById('reaction-popup');
        if (oldPopup) oldPopup.remove();
        
        const reactions = ["👍", "😂", "❤️", "😮", "😢", "😡"];
        
        const popup = document.createElement('div');
        popup.id = 'reaction-popup';
        popup.style.cssText = `
            position: fixed;
            left: ${x}px;
            top: ${y - 50}px;
            background: white;
            border-radius: 25px;
            padding: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            display: flex;
            gap: 5px;
            z-index: 10000;
            border: 1px solid #e0e0e0;
        `;
        
        reactions.forEach(reaction => {
            const btn = document.createElement('button');
            btn.textContent = reaction;
            btn.style.cssText = `
                font-size: 20px;
                border: none;
                background: none;
                cursor: pointer;
                padding: 5px;
                border-radius: 50%;
                transition: transform 0.2s;
            `;
            btn.onmouseover = () => btn.style.transform = 'scale(1.3)';
            btn.onmouseout = () => btn.style.transform = 'scale(1)';
            btn.onclick = () => {
                addReaction(messageId, reaction);
                popup.remove();
            };
            popup.appendChild(btn);
        });
        
        document.body.appendChild(popup);
        setTimeout(() => popup.remove(), 3000);
    }

    async function addReaction(messageId, reaction) {
        if (!IS_LOGGED_IN) {
            alert("Vui lòng đăng nhập để thả reaction");
            return;
        }
        
        try {
            const response = await fetch("/community/react", {
                method: "POST",
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ message_id: messageId, reaction: reaction })
            });
            
            if (response.ok) loadReactions(messageId);
        } catch (error) {
            console.error("Reaction error:", error);
        }
    }

    async function loadReactions(messageId) {
        try {
            const response = await fetch(`/community/reactions/${messageId}`);
            const reactions = await response.json();
            renderReactions(messageId, reactions);
        } catch (error) {
            console.error("Load reactions error:", error);
        }
    }

    function renderReactions(messageId, reactions) {
        const msgRow = document.querySelector(`[data-message-id="${messageId}"]`);
        if (!msgRow) return;
        
        let container = msgRow.querySelector('.reactions-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'reactions-container';
            msgRow.querySelector('.msg-body').appendChild(container);
        }
        
        if (reactions.length === 0) {
            container.innerHTML = '';
            return;
        }
        
        container.innerHTML = reactions
            .map(r => `<span class="reaction-item">${r[0]}${r[1]}</span>`)
            .join('');
    }

    // ================ SEND MESSAGE =================
    async function sendMsg() {
        if (!checkAuth()) return;

        const text = input.value.trim();
        if (!text) return;

        try {
            const response = await fetch("/community/add", {
                method: "POST",
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: `topic=${CURRENT_TOPIC}&message=${encodeURIComponent(text)}`
            });

            if (response.ok) {
                input.value = "";
                loadMessages(CURRENT_TOPIC);
            } else {
                const result = await response.json();
                alert(result.error || "Lỗi gửi tin nhắn!");
            }
        } catch (error) {
            alert("Lỗi kết nối!");
        }
    }

    // ================ SEND IMAGE =================
    imgBtn.onclick = () => imgInput.click();
    
    imgInput.onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        
        if (file.size > 5 * 1024 * 1024) {
            alert("Ảnh tối đa 5MB");
            return;
        }

        if (!checkAuth()) return;

        try {
            const formData = new FormData();
            formData.append("topic", CURRENT_TOPIC);
            formData.append("image", file);

            const response = await fetch("/community/add", {
                method: "POST",
                body: formData
            });

            if (response.ok) {
                imgInput.value = "";
                loadMessages(CURRENT_TOPIC);
            } else {
                alert("Lỗi gửi ảnh!");
            }
        } catch (error) {
            alert("Lỗi kết nối!");
        }
    };

    // ================ LOAD MESSAGES =================
    async function loadMessages(topic = "food") {
        try {
            const response = await fetch(`/community/get?topic=${topic}`);
            const messages = await response.json();

            msgBox.innerHTML = '';
            
            if (messages.length === 0) {
                msgBox.innerHTML =
                    `<div style="text-align:center;padding:20px;color:#666;">Chưa có tin nhắn nào</div>`;
            } else {
                messages.reverse().forEach(msg => renderMessage(msg));
            }
            
            msgBox.scrollTop = msgBox.scrollHeight;
        } catch (error) {
            msgBox.innerHTML =
                `<div style="color:red;text-align:center;padding:20px;">Lỗi tải tin nhắn</div>`;
        }
    }

    // ================ RENDER MESSAGE =================
    function renderMessage(msg) {
        const avatarUrl = `/static/uploads/${msg.avatar || 'default-avatar.png'}`;
        let text = msg.message ? msg.message.replace(/\n/g, "<br>") : "";

        let messageContent = msg.image
            ? `<div class="msg-bubble msg-image"><img src="data:image/jpeg;base64,${msg.image}"></div>`
            : `<div class="msg-bubble">${text}</div>`;

        const html = `
        <div class="msg-row" data-message-id="${msg.id}">
            <img class="msg-avatar" src="${avatarUrl}">
            <div class="msg-body">
                <div class="msg-header">
                    <span class="msg-name">${msg.username}</span>
                    <span class="msg-time">${formatTime(msg.created_at)}</span>
                </div>
                ${messageContent}
                <div class="reactions-container"></div>
            </div>
        </div>
        `;

        msgBox.insertAdjacentHTML("beforeend", html);
        loadReactions(msg.id);
    }

    // ================ SWITCH TOPIC =================
    document.querySelectorAll(".cat-item").forEach(tab => {
        tab.onclick = () => {
            document.querySelectorAll(".cat-item")
                .forEach(t => t.classList.remove("active"));

            tab.classList.add("active");

            CURRENT_TOPIC = tab.dataset.topic;
            loadMessages(CURRENT_TOPIC);
        };
    });

    // INIT
    loadMessages(CURRENT_TOPIC);
    checkAuth();
    addReactionListeners();
});


// ================= UTILS ==================
function formatTime(isoTime) {
    const date = new Date(isoTime);

    const day = date.getDate().toString().padStart(2, "0");
    const month = (date.getMonth() + 1).toString().padStart(2, "0");
    const year = date.getFullYear();

    const hours = date.getHours().toString().padStart(2, "0");
    const minutes = date.getMinutes().toString().padStart(2, "0");

    return `${day}/${month}/${year} - ${hours}:${minutes}`;
}










// =================== CHATBOT STORAGE MANAGER ===================
window.ChatStorage = {
  STORAGE_KEY: 'foodie_chat_history',
  
  saveMessage(role, content) {
    const history = this.getHistory();
    history.push({
      role: role,
      content: content,
      timestamp: new Date().toISOString()
    });
    
    if (history.length > 50) {
      history.splice(0, history.length - 50);
    }
    
    sessionStorage.setItem(this.STORAGE_KEY, JSON.stringify(history));
    console.log(`💾 Saved ${role} message (${history.length} total)`);
  },
  
  getHistory() {
    const stored = sessionStorage.getItem(this.STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  },
  
  clearHistory() {
    sessionStorage.removeItem(this.STORAGE_KEY);
    console.log('🗑️ Chat history cleared');
  }
};

// =================== DOM ELEMENTS ===================
let chatbotIcon, chatbox, closeChat, sendChat, chatInput, chatBody;
let uploadBtn, imageInput, langToggle, langVi, langEn;
let targetLanguage = 'vi';
let responseLanguage = 'vi'; // Ngôn ngữ chatbot trả lời
let initialized = false;

// =================== INIT FUNCTION ===================
function initChatbot() {
  if (initialized) {
    console.warn('⚠️ Chatbot already initialized');
    return;
  }
  
  // Get elements
  chatbotIcon = document.getElementById("chatbotIcon");
  chatbox = document.getElementById("chatbox");
  closeChat = document.getElementById("closeChat");
  sendChat = document.getElementById("sendChat");
  chatInput = document.getElementById("chatInput");
  chatBody = document.getElementById("chatBody");
  uploadBtn = document.getElementById("uploadBtn");
  imageInput = document.getElementById("imageInput");
  langToggle = document.getElementById("langToggle");
  langVi = document.getElementById("langVi");
  langEn = document.getElementById("langEn");
  
  // Check critical elements
  if (!chatBody) {
    console.warn('⚠️ chatBody not found, chatbot disabled');
    return;
  }
  
  console.log('✅ Chatbot elements found:', {
    icon: !!chatbotIcon,
    box: !!chatbox,
    body: !!chatBody,
    input: !!chatInput,
    upload: !!uploadBtn
  });

  if (langToggle) {
    langToggle.style.display = 'flex';
  }

  // Load history
  loadChatHistory();
  
  // Setup event listeners
  setupEventListeners();
  
  initialized = true;
  console.log(`✅ Chatbot initialized with ${window.ChatStorage.getHistory().length} messages`);
}

// =================== LOAD HISTORY ===================
function loadChatHistory() {
  const history = window.ChatStorage.getHistory();
  
  if (history.length === 0) {
    console.log('📭 No chat history');
    return;
  }
  
  console.log(`📚 Loading ${history.length} messages...`);
  chatBody.innerHTML = '';
  
  history.forEach((msg, index) => {
    try {
      if (msg.role === 'user') {
        addUserMessage(msg.content, false);
      } else if (msg.role === 'bot') {
        addBotMessage(msg.content, false);
      } else if (msg.role === 'image') {
        const imageDiv = document.createElement('div');
        imageDiv.className = 'image-message user';
        imageDiv.innerHTML = `<img src="${msg.content}" alt="Uploaded menu" style="max-width: 100%; border-radius: 8px;">`;
        chatBody.appendChild(imageDiv);
      }
    } catch (err) {
      console.error(`❌ Error loading message ${index}:`, err);
    }
  });
  
  chatBody.scrollTop = chatBody.scrollHeight;
}

// =================== EVENT LISTENERS ===================
function setupEventListeners() {
  // Chatbot toggle
  if (chatbotIcon && chatbox) {
    chatbotIcon.addEventListener("click", () => {
      chatbox.classList.add("open");
      if (chatBody) chatBody.scrollTop = chatBody.scrollHeight;
    });
  }
  
  // Close button
  if (closeChat && chatbox) {
    closeChat.addEventListener("click", () => {
      chatbox.classList.remove("open");
    });
  }
  
  // Send button
  if (sendChat) {
    sendChat.addEventListener("click", sendMessage);
  }
  
  // Enter key
  if (chatInput) {
    chatInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  }
  
  // Xử lý chuyển đổi ngôn ngữ trả lời
  if (langVi && langEn) {
    langVi.addEventListener('click', () => {
      // EN→VI: OCR tiếng Anh, dịch ra tiếng Việt, chatbot trả lời tiếng Anh
      targetLanguage = 'vi';
      responseLanguage = 'vi'; // Chatbot trả lời bằng tiếng Anh
      langVi.classList.add('active');
      langEn.classList.remove('active');
      console.log('🌍 Mode: VI (Chatbot responds in Vietnamese)');
    });

    langEn.addEventListener('click', () => {
      // VI→EN: OCR tiếng Việt, dịch ra tiếng Anh, chatbot trả lời tiếng Việt
      targetLanguage = 'en';
      responseLanguage = 'en'; // Chatbot trả lời bằng tiếng Việt
      langEn.classList.add('active');
      langVi.classList.remove('active');
      console.log('🌍 Mode: EN (Chatbot responds in English)');
    });
  }
  
  if (uploadBtn && imageInput) {
    uploadBtn.addEventListener('click', () => {
      imageInput.click();
    });
    
    imageInput.addEventListener('change', handleImageUpload);
  }
}

// =================== TEXT MESSAGE ===================
async function sendMessage() {
  if (!chatInput || !chatBody) return;
  
  const msg = chatInput.value.trim();
  if (!msg) return;

  // Hide language toggle
  if (langToggle) langToggle.style.display = 'flex';

  addUserMessage(msg);
  chatInput.value = "";

  showTypingIndicator();

  try {
    const res = await fetch("http://127.0.0.1:5000/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        question: msg,
        response_language: responseLanguage // Gửi ngôn ngữ trả lời
      })
    });

    const data = await res.json();
    removeTypingIndicator();

    if (data.answer) {
      addBotMessage(data.answer);
    } else {
      const errorMsg = responseLanguage === 'en' 
        ? '❌ Sorry, I could not understand your question.'
        : '❌ Xin lỗi, mình không hiểu câu hỏi của bạn.';
      addBotMessage(errorMsg);
    }
  } catch (err) {
    removeTypingIndicator();
    const errorMsg = responseLanguage === 'en'
      ? '❌ Connection error. Please try again.'
      : '❌ Lỗi kết nối. Vui lòng thử lại.';
    addBotMessage(errorMsg);
    console.error('Error:', err);
  }
}

// =================== IMAGE UPLOAD ===================
async function handleImageUpload(e) {
  const file = e.target.files[0];
  if (!file) return;

  // Show language toggle
  if (langToggle) langToggle.style.display = 'flex';

  // Show preview
  const reader = new FileReader();
  reader.onload = (event) => {
    const base64Image = event.target.result;
    
    const imageDiv = document.createElement('div');
    imageDiv.className = 'image-message user';
    imageDiv.innerHTML = `<img src="${base64Image}" alt="Uploaded menu" style="max-width: 100%; border-radius: 8px;">`;
    chatBody.appendChild(imageDiv);
    chatBody.scrollTop = chatBody.scrollHeight;

    window.ChatStorage.saveMessage('image', base64Image);
  };
  reader.readAsDataURL(file);

  showTypingIndicator();

  const formData = new FormData();
  formData.append('image', file);
  formData.append('targetLanguage', targetLanguage);

  try {
    const response = await fetch('http://127.0.0.1:5000/translate-menu', {
      method: 'POST',
      body: formData
    });

    const data = await response.json();
    removeTypingIndicator();

    if (data.success) {
      addBotMessage(data.answer);
    } else {
      addBotMessage(data.answer || '❌ Sorry, I could not process the image.');
    }
  } catch (error) {
    removeTypingIndicator();
    addBotMessage('❌ Connection error. Please try again.');
    console.error('Error:', error);
  }

  imageInput.value = '';
}

// =================== UI HELPERS ===================
function addUserMessage(text, saveToStorage = true) {
  if (!chatBody) return;
  
  const messageDiv = document.createElement('div');
  messageDiv.className = 'message user';
  messageDiv.innerHTML = `<p class="user-message">${text}</p>`;
  chatBody.appendChild(messageDiv);
  chatBody.scrollTop = chatBody.scrollHeight;
  
  if (saveToStorage) {
    window.ChatStorage.saveMessage('user', text);
  }
}

function addBotMessage(text, saveToStorage = true) {
  if (!chatBody) return;
  
  const messageDiv = document.createElement('div');
  messageDiv.className = 'message';
  messageDiv.innerHTML = `<p class="bot-message">${text.replace(/\n/g, '<br>')}</p>`;
  chatBody.appendChild(messageDiv);
  chatBody.scrollTop = chatBody.scrollHeight;
  
  if (saveToStorage) {
    window.ChatStorage.saveMessage('bot', text);
  }
}

function showTypingIndicator() {
  if (!chatBody) return;
  
  const indicator = document.createElement('div');
  indicator.className = 'message typing';
  indicator.id = 'typingIndicator';
  indicator.innerHTML = `
    <div class="typing-indicator">
      <span></span>
      <span></span>
      <span></span>
    </div>
  `;
  chatBody.appendChild(indicator);
  chatBody.scrollTop = chatBody.scrollHeight;
}

function removeTypingIndicator() {
  const indicator = document.getElementById('typingIndicator');
  if (indicator) {
    indicator.remove();
  }
}

// =================== AUTO INIT ===================
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initChatbot);
} else {
  initChatbot();
}

// =================== EXPOSE API ===================
window.FoodieChatbot = {
  init: initChatbot,
  clearHistory: () => window.ChatStorage.clearHistory(),
  getHistory: () => window.ChatStorage.getHistory()
};

console.log('✅ Chatbot Module Loaded');
// })();