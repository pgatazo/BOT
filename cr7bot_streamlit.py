import streamlit as st
import hashlib
import json
import os
import pandas as pd
from io import BytesIO
from datetime import datetime

# ======== FICHEIROS ========
USERS_FILE = "users.json"
CUSTOM_FILE = "ligas_e_equipas_custom.json"
PESOS_FILE = "pesos_personalizados.json"
CHAT_FILE = "chat.json"
ONLINE_FILE = "online_users.json"

# ======== LOGIN =========
def hash_pwd(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def load_users():
    if not os.path.exists(USERS_FILE):
        base_users = {
            "paulo": hash_pwd("damas2024"),
            "admin": hash_pwd("admin123")
        }
        with open(USERS_FILE, "w") as f:
            json.dump(base_users, f)
    with open(USERS_FILE, "r") as f:
        return json.load(f)
USERS = load_users()

# Função para gerir presença online dos utilizadores
def set_online(username, online=True):
    data = {}
    if os.path.exists(ONLINE_FILE):
        with open(ONLINE_FILE, "r") as f:
            data = json.load(f)
    data[username] = {"online": online, "dt": datetime.now().strftime('%H:%M')}
    with open(ONLINE_FILE, "w") as f:
        json.dump(data, f)

def get_all_online():
    if os.path.exists(ONLINE_FILE):
        with open(ONLINE_FILE, "r") as f:
            return json.load(f)
    return {}

def login_screen():
    st.title("🔒 Login - PauloDamas-GPT")
    username = st.text_input("Utilizador")
    password = st.text_input("Password", type="password")
    login_btn = st.button("Entrar")
    if login_btn:
        if username in USERS and hash_pwd(password) == USERS[username]:
            st.success(f"Bem-vindo, {username}!")
            st.session_state.login_success = True
            st.session_state.logged_user = username
            set_online(username, True)
        else:
            st.error("Credenciais inválidas ou não autorizado!")
    return st.session_state.get("login_success", False)

if "login_success" not in st.session_state or not st.session_state["login_success"]:
    if not login_screen():
        st.stop()
else:
    set_online(st.session_state['logged_user'], True)

st.set_page_config(page_title="PauloDamas-GPT", layout="wide")
st.markdown("""
    <style>
    .mainblock {max-width: 980px; margin-left: auto; margin-right: auto;}
    .fixed-chat {position:fixed; top:0; right:0; width:340px; height:100vh; background:#f7f7fb; border-left:1.5px solid #ddd; z-index:9999; padding:12px 18px 85px 12px; overflow-y:auto;}
    .fixed-chat .chat-title {font-weight:bold; font-size:21px; margin-bottom:8px;}
    .fixed-chat .chat-box {height:52vh;overflow-y:auto; background:#fff; border-radius:9px; box-shadow:0 0 6px #eee; padding:10px; margin-bottom:8px;}
    .fixed-chat .chat-input-row {display:flex; gap:5px;}
    .fixed-chat .chat-input {flex:1;}
    .fixed-chat .chat-emoji {font-size:20px; cursor:pointer;}
    .online-users {margin-bottom:10px; padding:10px; background:#fff; border-radius:8px; box-shadow:0 1px 2px #eee;}
    .online-dot {height:10px;width:10px;border-radius:50%;display:inline-block;margin-right:6px;}
    .dot-online {background:#18cc0e;}
    .dot-offline {background:#bbb;}
    section[data-testid="stSidebar"] {min-width:340px; width:340px;}
    .block-container {padding-right:360px !important;}
    </style>
""", unsafe_allow_html=True)

st.title("⚽️ PauloDamas-GPT — Análise Pré-Jogo + Live + IA + Chat")

# ... (restante código da aplicação, igual ao anterior) ...

# ====================== PAINEL FIXO DE CHAT E UTILIZADORES À DIREITA ======================
def emoji_bar():
    emojis = ["😀","👍","⚽","🔥","🤔","😭","🙌","💰","😎","🤡","🤩","🤬","😂","🥳","👏","🟢","🔴","🔵","🟠","🟣","⚠️","❤️"]
    bar = ''.join([f'<span class="chat-emoji" onclick="addEmoji(\'{e}\')">{e}</span>' for e in emojis])
    st.markdown(f"""
    <div style='margin-bottom:5px;'>{bar}</div>
    <script>
    function addEmoji(e) {{
        var chat_input = window.parent.document.querySelector('textarea[aria-label="Message to PauloDamas-GPT"]');
        if (chat_input) {{
            chat_input.value += e;
            chat_input.focus();
        }}
    }}
    </script>
    """, unsafe_allow_html=True)

with st.container():
    st.markdown('<div class="fixed-chat">', unsafe_allow_html=True)
    # UTILIZADORES ONLINE
    st.markdown('<div class="chat-title">👤 Utilizadores Online</div>', unsafe_allow_html=True)
    users_data = load_users()
    all_online = get_all_online()
    for u in users_data.keys():
        online = all_online.get(u, {}).get("online", False)
        dt = all_online.get(u, {}).get("dt", "")
        dot = "dot-online" if online else "dot-offline"
        st.markdown(f"<div class='online-users'><span class='online-dot {dot}'></span> <b>{u}</b> <span style='font-size:13px;color:#bbb'>{'(online)' if online else f'(offline {dt})'}</span></div>", unsafe_allow_html=True)
    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown('<div class="chat-title">💬 Chat Global</div>', unsafe_allow_html=True)
    chat_msgs = load_chat()[-120:]
    st.markdown('<div class="chat-box">', unsafe_allow_html=True)
    for m in chat_msgs:
        u, msg, dt = m['user'], m['msg'], m['dt']
        userstyle = "font-weight:700;color:#3131b0" if u==st.session_state['logged_user'] else "font-weight:500"
        st.markdown(f"<div style='{userstyle}'>{u} <span style='font-size:13px;color:#bbb'>{dt}</span>:</div><div style='margin-left:9px;margin-bottom:5px;font-size:16px'>{msg}</div>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    emoji_bar()
    with st.form(key="chat_form", clear_on_submit=True):
        msg = st.text_input("Message to PauloDamas-GPT", key="chatinput")
        enviar = st.form_submit_button("Enviar")
        if enviar and msg.strip():
            save_message(st.session_state["logged_user"], msg.strip())
            st.experimental_rerun()
    st.markdown('</div>', unsafe_allow_html=True)
