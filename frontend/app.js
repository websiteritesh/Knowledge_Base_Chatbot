  // Relative address: works whether this runs on localhost, Codespaces, or a real deployed URL —
    // it always means "the same server this page was loaded from."
    const API = "";

    function getToken() { return localStorage.getItem("token"); }
    function showApp() { document.getElementById("loginOverlay").style.display = "none"; }
    function showLogin() { document.getElementById("loginOverlay").style.display = "flex"; }

    async function doLogin() {
        const username = document.getElementById("loginUsername").value;
        const password = document.getElementById("loginPassword").value;
        const errorEl = document.getElementById("loginError");
        const btn = document.getElementById("loginBtn");
        errorEl.style.display = "none";
        btn.disabled = true;
        btn.textContent = "Signing in…";

        const body = new URLSearchParams();
        body.append("username", username);
        body.append("password", password);

        try {
            const res = await fetch(`${API}/login`, {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: body
            });
            if (!res.ok) {
                errorEl.textContent = "Incorrect username or password.";
                errorEl.style.display = "block";
            } else {
                const data = await res.json();
                localStorage.setItem("token", data.access_token);
                showApp();
                checkStatus();
            }
        } catch {
            errorEl.textContent = "Can't reach the server. Make sure uvicorn is running.";
            errorEl.style.display = "block";
        }
        btn.disabled = false;
        btn.textContent = "Sign in";
    }

    function doLogout() {
        localStorage.removeItem("token");
        showLogin();
    }

    async function checkStatus() {
        const bar = document.getElementById("statusBar");
        try {
            const res = await fetch(`${API}/status`);
            const data = await res.json();
            if (data.knowledge_base_ready) {
                bar.innerHTML = `<span class="dot ready"></span>Ready — ${data.pdf_count} document${data.pdf_count === 1 ? '' : 's'} in the archive`;
            } else {
                bar.innerHTML = `<span class="dot"></span>No documents yet — upload one to get started`;
            }
        } catch {
            bar.innerHTML = `<span class="dot error"></span>Can't reach the server`;
        }
    }

    async function uploadPDF() {
        const fileInput = document.getElementById("pdfFile");
        const msg = document.getElementById("uploadMsg");
        const btn = document.getElementById("uploadBtn");

        if (!fileInput.files[0]) {
            msg.className = "upload-msg error";
            msg.textContent = "Choose a PDF first.";
            return;
        }

        btn.disabled = true;
        btn.textContent = "Uploading…";
        msg.className = "upload-msg";
        msg.textContent = "";

        const formData = new FormData();
        formData.append("file", fileInput.files[0]);

        try {
            const res = await fetch(`${API}/upload`, { method: "POST", body: formData });
            const data = await res.json();
            if (data.error) {
                msg.className = "upload-msg error";
                msg.textContent = data.error;
            } else {
                msg.className = "upload-msg success";
                msg.textContent = data.message;
                checkStatus();
            }
        } catch {
            msg.className = "upload-msg error";
            msg.textContent = "Upload failed. Make sure the backend is running.";
        }
        btn.disabled = false;
        btn.textContent = "Upload";
    }

    async function askQuestion() {
        const input = document.getElementById("questionInput");
        const chatBox = document.getElementById("chatBox");
        const btn = document.getElementById("askBtn");
        const question = input.value.trim();
        if (!question) return;

        chatBox.innerHTML += `
            <div class="entry user">
                <div class="who">You</div>
                <p>${question}</p>
            </div>`;
        input.value = "";
        btn.disabled = true;
        btn.textContent = "Thinking…";

        const loadingId = "loading-" + Date.now();
        chatBox.innerHTML += `
            <div class="entry ai" id="${loadingId}">
                <div class="who">Assistant</div>
                <p class="thinking">Searching your documents…</p>
            </div>`;
        chatBox.scrollTop = chatBox.scrollHeight;

        try {
            const res = await fetch(`${API}/ask`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + getToken()
                },
                body: JSON.stringify({ question })
            });

            if (res.status === 401) {
                document.getElementById(loadingId).innerHTML =
                    `<div class="who">Assistant</div><p>Your session expired — please sign in again.</p>`;
                doLogout();
                btn.disabled = false;
                btn.textContent = "Ask";
                return;
            }

            const data = await res.json();
            const el = document.getElementById(loadingId);
            if (data.error) {
                el.innerHTML = `<div class="who">Assistant</div><p>${data.error}</p>`;
            } else {
                const sourceLabel = data.source === "general_knowledge"
                    ? "Answered from general AI knowledge (not found in your documents)"
                    : `${data.sources_found} source section${data.sources_found === 1 ? '' : 's'} referenced from your documents`;
                el.innerHTML = `
                    <div class="who">Assistant</div>
                    <p>${data.answer}</p>
                    <div class="sources">${sourceLabel}</div>`;
            }
        } catch {
            document.getElementById(loadingId).innerHTML =
                `<div class="who">Assistant</div><p>Couldn't reach the server. Make sure uvicorn is running.</p>`;
        }
        btn.disabled = false;
        btn.textContent = "Ask";
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    if (getToken()) { showApp(); } else { showLogin(); }
    checkStatus();
    setInterval(checkStatus, 10000);