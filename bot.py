import os
import re
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8876399952:AAENDO__fBmozBLMxZGNlNwm_HefiQ2K3vE")
TARGET_CHANNEL = int(os.environ.get("TARGET_CHANNEL", "-1003546186616"))
DATABASE_URL = os.environ.get("DATABASE_URL")
MAX_GAME_NUM = 1440
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
STAT_CERBER = "https://t.me/s/Stat_cerber"

SUIT_TABLE = {
    ('♠️', '♠️'): '♥️', ('♠️', '♥️'): '♦️', ('♠️', '♦️'): '♥️', ('♠️', '♣️'): '♦️',
    ('♣️', '♠️'): '♣️', ('♣️', '♥️'): '♠️', ('♣️', '♦️'): '♣️', ('♣️', '♣️'): '♥️',
    ('♥️', '♠️'): '♠️', ('♥️', '♥️'): '♣️', ('♥️', '♦️'): '♦️', ('♥️', '♣️'): '♦️',
    ('♦️', '♠️'): '♥️', ('♦️', '♥️'): '♠️', ('♦️', '♦️'): '♦️', ('♦️', '♣️'): '♦️',
}

RANKS = {'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'10':10,'J':11,'Q':12,'K':13,'A':1}

def get_conn():
    if DATABASE_URL:
        import psycopg
        return psycopg.connect(DATABASE_URL)
    else:
        import sqlite3
        return sqlite3.connect("bot4.db")

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    try:
        if DATABASE_URL:
            cur.execute("CREATE TABLE IF NOT EXISTS state4 (id INT PRIMARY KEY, last_processed INT DEFAULT 0)")
            cur.execute("INSERT INTO state4 (id, last_processed) VALUES (1, 0) ON CONFLICT (id) DO NOTHING")
            cur.execute("CREATE TABLE IF NOT EXISTS preds4 (id SERIAL PRIMARY KEY, target_game INT NOT NULL, suit TEXT NOT NULL, msg_id BIGINT NOT NULL, status TEXT DEFAULT 'pending', check_games TEXT, check_idx INT DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        else:
            cur.execute("CREATE TABLE IF NOT EXISTS state4 (id INTEGER PRIMARY KEY, last_processed INTEGER DEFAULT 0)")
            cur.execute("INSERT OR IGNORE INTO state4 (id, last_processed) VALUES (1, 0)")
            cur.execute("CREATE TABLE IF NOT EXISTS preds4 (id INTEGER PRIMARY KEY AUTOINCREMENT, target_game INT NOT NULL, suit TEXT NOT NULL, msg_id BIGINT NOT NULL, status TEXT DEFAULT 'pending', check_games TEXT, check_idx INT DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        conn.commit()
    except Exception as e:
        print("DB init:", e)
    finally:
        cur.close()
        conn.close()

def load_lp():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT last_processed FROM state4 WHERE id = 1")
        row = cur.fetchone()
        return int(row[0]) if row else 0
    except:
        return 0
    finally:
        cur.close()
        conn.close()

def save_lp(lp):
    conn = get_conn()
    cur = conn.cursor()
    try:
        if DATABASE_URL:
            cur.execute("UPDATE state4 SET last_processed = %s WHERE id = 1", (lp,))
        else:
            cur.execute("UPDATE state4 SET last_processed = ? WHERE id = 1", (lp,))
        conn.commit()
    except Exception as e:
        print("Save lp:", e)
    finally:
        cur.close()
        conn.close()

def add_pred(tg, suit, mid):
    conn = get_conn()
    cur = conn.cursor()
    cgs = [str((tg + i - 1) % MAX_GAME_NUM + 1) for i in range(4)]
    try:
        if DATABASE_URL:
            cur.execute("INSERT INTO preds4 (target_game, suit, msg_id, check_games) VALUES (%s, %s, %s, %s)", (tg, suit, mid, ",".join(cgs)))
        else:
            cur.execute("INSERT INTO preds4 (target_game, suit, msg_id, check_games) VALUES (?, ?, ?, ?)", (tg, suit, mid, ",".join(cgs)))
        conn.commit()
    except Exception as e:
        print("Add pred:", e)
    finally:
        cur.close()
        conn.close()

def get_pending():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, target_game, suit, msg_id, check_games, check_idx FROM preds4 WHERE status = 'pending'")
        rows = []
        for r in cur.fetchall():
            rows.append({'id': r[0], 'target_game': r[1], 'suit': r[2], 'msg_id': r[3], 'check_games': r[4].split(','), 'check_idx': r[5]})
        return rows
    except Exception as e:
        print("Get pending:", e)
        return []
    finally:
        cur.close()
        conn.close()

def update_pred(pid, status):
    conn = get_conn()
    cur = conn.cursor()
    try:
        if DATABASE_URL:
            cur.execute("UPDATE preds4 SET status = %s WHERE id = %s", (status, pid))
        else:
            cur.execute("UPDATE preds4 SET status = ? WHERE id = ?", (status, pid))
        conn.commit()
    finally:
        cur.close()
        conn.close()

def update_idx(pid, idx):
    conn = get_conn()
    cur = conn.cursor()
    try:
        if DATABASE_URL:
            cur.execute("UPDATE preds4 SET check_idx = %s WHERE id = %s", (idx, pid))
        else:
            cur.execute("UPDATE preds4 SET check_idx = ? WHERE id = ?", (idx, pid))
        conn.commit()
    finally:
        cur.close()
        conn.close()

init_db()

def tg_send(cid, text):
    try:
        r = requests.post(f"{API_URL}/sendMessage", json={"chat_id": cid, "text": text}, timeout=10)
        d = r.json()
        return d["result"]["message_id"] if d.get("ok") else None
    except Exception as e:
        print("tg_send:", e)
        return None

def tg_edit(cid, mid, text):
    try:
        r = requests.post(f"{API_URL}/editMessageText", json={"chat_id": cid, "message_id": mid, "text": text}, timeout=10)
        return r.json().get("ok", False)
    except Exception as e:
        print("tg_edit:", e)
        return False

def parse_cerber():
    try:
        h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        r = requests.get(STAT_CERBER, headers=h, timeout=15)
        if r.status_code != 200:
            return {}
        games = {}
        parts = re.split(r'(?=#n\d+)', r.text)
        for p in parts:
            m = re.search(r'#n?(\d+)', p)
            if m:
                num = int(m.group(1))
                clean = re.sub(r'<[^>]+>', ' ', p)
                clean = re.sub(r'\s+', ' ', clean).strip()
                games[num] = clean
        return games
    except Exception as e:
        print("Parse:", e)
        return {}

def is_game_completed(text):
    return '✅' in text or '🔰' in text

def parse_cards(txt):
    cards = re.findall(r'([AKQJ\d10]+)([♠♥♣♦♠️♥️♣️♦️])', txt)
    return [(r, s.replace('\ufe0f','')+'\ufe0f') for r, s in cards]

def get_high_card(cards):
    best = None
    bv = -1
    for r, s in cards:
        v = RANKS.get(r, 0)
        if v > bv:
            bv = v
            best = (r, s)
    return best

def get_suits(text):
    b = re.findall(r'\(([^)]+)\)', text)
    if len(b) < 2:
        return None, None
    c1 = parse_cards(b[0])
    c2 = parse_cards(b[1])
    if not c1 or not c2:
        return None, None
    return get_high_card(c1)[1], get_high_card(c2)[1]

def check_first_hand(text, suit):
    m = re.search(r'\(([^)]+)\)', text)
    if not m:
        return False
    hand = m.group(1)
    t = suit.replace('\ufe0f', '')
    return any(s.replace('\ufe0f','') == t for s in re.findall(r'[♠♥♣♦♠️♥️♣️♦️]', hand))

def process_preds():
    preds = get_pending()
    if not preds:
        return
    games = parse_cerber()
    if not games:
        return
    emojis = ['0️⃣','1️⃣','2️⃣','3️⃣']
    for p in preds:
        pid, tg, suit, mid = p['id'], p['target_game'], p['suit'], p['msg_id']
        cgs, idx = p['check_games'], p['check_idx']
        if idx >= len(cgs):
            continue
        cgn = int(cgs[idx])
        if cgn not in games:
            continue
        gt = games[cgn]
        if not is_game_completed(gt):
            print(f"Game #{cgn} not completed, waiting...")
            continue
        print(f"Check pred {tg} suit {suit} vs game {cgn}")
        if check_first_hand(gt, suit):
            txt = f"{tg} — игрок {suit} | ✅{emojis[idx]}"
            if tg_edit(TARGET_CHANNEL, mid, txt):
                update_pred(pid, 'won')
        else:
            nidx = idx + 1
            if nidx >= len(cgs):
                txt = f"{tg} — игрок {suit} | ❌"
                if tg_edit(TARGET_CHANNEL, mid, txt):
                    update_pred(pid, 'lost')
            else:
                update_idx(pid, nidx)

def create_predictions():
    last_processed = load_lp()
    games = parse_cerber()
    if not games:
        return "no games"
    updated = False
    for gn in sorted(games.keys()):
        if gn <= last_processed:
            continue
        gt = games[gn]
        if not is_game_completed(gt):
            continue
        s1, s2 = get_suits(gt)
        if not s1 or not s2:
            last_processed = gn
            updated = True
            continue
        ps = SUIT_TABLE.get((s1, s2))
        if not ps:
            last_processed = gn
            updated = True
            continue
        tg = gn + 3
        if tg > MAX_GAME_NUM:
            tg -= MAX_GAME_NUM
        txt = f"{tg} — игрок {ps} | Догон 1-2 игры (RX+1)"
        mid = tg_send(TARGET_CHANNEL, txt)
        if mid:
            add_pred(tg, ps, mid)
            print(f"Pred {tg} {ps} from game {gn}")
        last_processed = gn
        updated = True
    if updated:
        save_lp(last_processed)
    return f"processed #{last_processed}"

@app.route("/")
def home():
    return "Bot 4 is alive"

@app.route("/tick", methods=["GET","POST"])
def tick():
    res = create_predictions()
    process_preds()
    return {"result": res}, 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}
    msg = data.get("message", {})
    if not msg:
        return "ok", 200
    cid = msg["chat"]["id"]
    text = msg.get("text", "")

    if text.startswith("/start"):
        parts = text.split()
        if len(parts) > 1:
            try:
                n = int(parts[1])
                if 1 <= n <= MAX_GAME_NUM:
                    save_lp(n)
                    tg_send(cid, f"✅ ЗАПУЩЕН! Старт с игры: #{n}")
                else:
                    tg_send(cid, f"❌ От 1 до {MAX_GAME_NUM}")
            except ValueError:
                tg_send(cid, "❌ Пример: /start 860")
        else:
            tg_send(cid, "🎴 /start <номер>\n/stop\n/status")

    elif text == "/stop":
        tg_send(cid, "🛑 ОСТАНОВЛЕН! (cron остановится)")

    elif text == "/status":
        lp = load_lp()
        preds = get_pending()
        tg_send(cid, f"🟢 РАБОТАЕТ\nОбработана: #{lp}\nПрогнозов: {len(preds)}")

    return "ok", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
