import os, random, telebot
from PIL import Image, ImageDraw, ImageFont

TOKEN = os.environ["TOKEN"]
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ================= CONFIG =================
GRID = 5
CELL = 140
NUM_FONT = ImageFont.truetype("DejaVuSans-Bold.ttf", 64)
HEAD_FONT = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
MARGIN = 40
TOP = 120
LINE_W = 10

# ================= GAME STORE =================
games = {}
# games[chat_id] = {
#   started: bool,
#   locked: bool,
#   players: {uid: card},
#   marked: {uid: set()},
#   called: set(),
#   lines: {uid: int}
# }

# ================= HELPERS =================
def new_card():
    nums = list(range(1, 26))
    random.shuffle(nums)
    return [nums[i*5:(i+1)*5] for i in range(5)]

def count_lines(card, marked):
    lines = 0
    for i in range(5):
        if all(card[i][c] in marked for c in range(5)): lines += 1
        if all(card[r][i] in marked for r in range(5)): lines += 1
    if all(card[i][i] in marked for i in range(5)): lines += 1
    if all(card[i][4-i] in marked for i in range(5)): lines += 1
    return min(lines, 5)

def draw_card(name, card, marked, lines):
    size = GRID * CELL + MARGIN * 2
    img = Image.new("RGB", (size, size + 120), "white")
    d = ImageDraw.Draw(img)

    d.text((size//2, 30), f"{name}'s BINGO", anchor="mm", fill="black", font=HEAD_FONT)
    d.text((size//2, 80), f"Lines: {lines}/5", anchor="mm", fill="black", font=HEAD_FONT)

    for r in range(6):
        y = TOP + r * CELL
        d.line((MARGIN, y, size-MARGIN, y), fill="black", width=LINE_W)

    for c in range(6):
        x = MARGIN + c * CELL
        d.line((x, TOP, x, TOP + CELL*5), fill="black", width=LINE_W)

    for r in range(5):
        for c in range(5):
            n = card[r][c]
            x1 = MARGIN + c*CELL
            y1 = TOP + r*CELL
            x2 = x1 + CELL
            y2 = y1 + CELL

            d.text((x1+CELL//2, y1+CELL//2), str(n),
                   anchor="mm", fill="black", font=NUM_FONT)

            if n in marked:
                d.line((x1+20,y1+20,x2-20,y2-20), fill="green", width=10)
                d.line((x1+20,y2-20,x2-20,y1+20), fill="green", width=10)

    # red strike for completed rows/cols
    for i in range(5):
        if all(card[i][c] in marked for c in range(5)):
            y = TOP + i*CELL + CELL//2
            d.line((MARGIN+10,y,size-MARGIN-10,y), fill="red", width=8)
        if all(card[r][i] in marked for r in range(5)):
            x = MARGIN + i*CELL + CELL//2
            d.line((x,TOP+10,x,TOP+CELL*5-10), fill="red", width=8)

    # ================= DIAGONAL LINES =================

    # Main diagonal (top-left → bottom-right)
    if all(
        (i * GRID + i + 1) in marked
        for i in range(GRID)
    ):
        d.line(
            (
                MARGIN,
                TOP,
                MARGIN + GRID * CELL,
                TOP + GRID * CELL
            ),
            fill="red",
            width=10
        )

    # Anti-diagonal (top-right → bottom-left)
    if all(
        (i * GRID + (GRID - 1 - i) + 1) in marked
        for i in range(GRID)
    ):
        d.line(
            (
                MARGIN + GRID * CELL,
                TOP,
                MARGIN,
                TOP + GRID * CELL
            ),
            fill="red",
            width=10
        )

    return img

# ================= COMMANDS =================
@bot.message_handler(commands=["startgame"])
def start_game(m):
    games[m.chat.id] = {
        "started": True,
        "locked": False,
        "players": {},
        "marked": {},
        "called": set(),
        "lines": {}
    }
    bot.send_message(m.chat.id, "🎯 Bingo started\nUse /join to join")

@bot.message_handler(commands=["join"])
def join(m):
    g = games.get(m.chat.id)
    if not g or g["locked"]:
        bot.reply_to(m, "❌ Joining closed")
        return

    uid = m.from_user.id
    if uid in g["players"]:
        return

    card = new_card()
    g["players"][uid] = card
    g["marked"][uid] = set()
    g["lines"][uid] = 0

    img = draw_card(m.from_user.first_name, card, set(), 0)
    img.save("card.png")
    bot.send_photo(uid, open("card.png","rb"))
    bot.send_message(m.chat.id, f"✅ {m.from_user.first_name} joined")

@bot.message_handler(commands=["lock"])
def lock(m):
    g = games.get(m.chat.id)
    if not g: return
    g["locked"] = True
    bot.send_message(m.chat.id, "🔒 Game locked. Start calling numbers.")

@bot.message_handler(func=lambda m: m.text and m.text.isdigit())
def call_number(m):
    g = games.get(m.chat.id)
    if not g: return

    uid = m.from_user.id
    if uid not in g["players"]:
        bot.reply_to(m, "❌ You haven't joined")
        return

    num = int(m.text)
    if num in g["called"]:
        return

    g["called"].add(num)
    bot.send_message(m.chat.id, f"📢 <b>{m.from_user.first_name}</b> called <b>{num}</b>")

    for pid, card in g["players"].items():
        if num in sum(card, []):
            g["marked"][pid].add(num)

        new_lines = count_lines(card, g["marked"][pid])
        if new_lines > g["lines"][pid]:
            g["lines"][pid] = new_lines
            bot.send_message(
                m.chat.id,
                f"🏆 <b>{bot.get_chat(pid).first_name}</b> {new_lines}/5"
            )

# AFTER marking the number
new_lines = count_lines(card, g["marked"][pid])

if new_lines == 5:
    img = draw_card(
        bot.get_chat(pid).first_name,
        card,
        g["marked"][pid],
        new_lines
    )
    img.save("update.png")
    bot.send_photo(pid, open("update.png", "rb"))

    bot.send_message(
        m.chat.id,
        f"🏆 <b>WINNER:</b> {bot.get_chat(pid).first_name}"
    )

    games.pop(m.chat.id)
    
# ================= RUN =================
print("Bot started successfully")
bot.infinity_polling()

