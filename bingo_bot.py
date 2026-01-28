import os
import random
import telebot
from PIL import Image, ImageDraw, ImageFont

TOKEN = os.environ.get("TOKEN")
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

GRID = 5
CELL = 180
MARGIN = 60
TOP = 200

games = {}

# ================= CARD =================
def new_card():
    nums = list(range(1, 26))
    random.shuffle(nums)
    return [nums[i*5:(i+1)*5] for i in range(5)]

# ================= LINE COUNT =================
def count_lines(card, marked):
    lines = 0

    for r in range(5):
        if set(card[r]).issubset(marked):
            lines += 1

    for c in range(5):
        if {card[r][c] for r in range(5)}.issubset(marked):
            lines += 1

    if {card[i][i] for i in range(5)}.issubset(marked):
        lines += 1

    if {card[i][4-i] for i in range(5)}.issubset(marked):
        lines += 1

    return lines

def get_completed_lines(card, marked):
    done = []

    for r in range(5):
        if set(card[r]).issubset(marked):
            done.append(("row", r))

    for c in range(5):
        if {card[r][c] for r in range(5)}.issubset(marked):
            done.append(("col", c))

    if {card[i][i] for i in range(5)}.issubset(marked):
        done.append(("diag_main", None))

    if {card[i][4-i] for i in range(5)}.issubset(marked):
        done.append(("diag_anti", None))

    return done

# ================= DRAW =================
def draw_card(name, card, marked, lines):
    W = GRID*CELL + 2*MARGIN
    H = GRID*CELL + TOP + MARGIN

    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    font_big = ImageFont.truetype("DejaVuSans-Bold.ttf", 72)
    font_small = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)

    d.text((W//2, 40), f"{name} BINGO", anchor="mm", fill="black", font=font_small)

    left = MARGIN
    top = TOP

    for r in range(6):
        y = top + r*CELL
        d.line((left, y, left+GRID*CELL, y), fill="black", width=6)

    for c in range(6):
        x = left + c*CELL
        d.line((x, top, x, top+GRID*CELL), fill="black", width=6)

    for r in range(5):
        for c in range(5):
            num = card[r][c]
            x = left + c*CELL + CELL//2
            y = top + r*CELL + CELL//2
            d.text((x, y), str(num), anchor="mm", fill="black", font=font_big)

            if num in marked:
                d.line(
                    (x-60, y-60, x+60, y+60),
                    fill=(0,160,0),
                    width=12
                )
                d.line(
                    (x+60, y-60, x-60, y+60),
                    fill=(0,160,0),
                    width=12
                )

    red = (220, 0, 0)
    for t, i in get_completed_lines(card, marked):
        if t == "row":
            y = top + i*CELL + CELL//2
            d.line((left, y, left+GRID*CELL, y), fill=red, width=14)
        elif t == "col":
            x = left + i*CELL + CELL//2
            d.line((x, top, x, top+GRID*CELL), fill=red, width=14)
        elif t == "diag_main":
            d.line((left, top, left+GRID*CELL, top+GRID*CELL), fill=red, width=14)
        elif t == "diag_anti":
            d.line((left+GRID*CELL, top, left, top+GRID*CELL), fill=red, width=14)

    d.text((W//2, H-30), f"Lines {lines}/5", anchor="mm", fill="black", font=font_small)
    return img

# ================= COMMANDS =================
@bot.message_handler(commands=["startgame"])
def start_game(m):
    games[m.chat.id] = {
        "players": {},
        "marked": {},
        "lines": {},
        "called": set(),
        "locked": False
    }
    bot.send_message(m.chat.id, "🎯 Bingo started\nType <b>join</b>")

@bot.message_handler(commands=["lock"])
def lock_game(m):
    if m.chat.id in games:
        games[m.chat.id]["locked"] = True
        bot.send_message(m.chat.id, "🔒 Game locked")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "join")
def join(m):
    cid = m.chat.id
    uid = m.from_user.id
    name = m.from_user.first_name

    if cid not in games:
        return

    g = games[cid]
    if g["locked"] or uid in g["players"]:
        return

    card = new_card()
    g["players"][uid] = card
    g["marked"][uid] = set()
    g["lines"][uid] = 0

    img = draw_card(name, card, set(), 0)
    img.save("card.png")
    bot.send_photo(uid, open("card.png", "rb"))
    bot.send_message(cid, f"✅ {name} joined")

@bot.message_handler(func=lambda m: m.text and m.text.isdigit())
def call_number(m):
    cid = m.chat.id
    if cid not in games:
        return

    g = games[cid]
    num = int(m.text)

    if num in g["called"]:
        return

    g["called"].add(num)
    bot.send_message(cid, f"📣 <b>{m.from_user.first_name}</b> called <b>{num}</b>")

    for pid, card in g["players"].items():
        if num in sum(card, []):
            g["marked"][pid].add(num)

            new = count_lines(card, g["marked"][pid])
            if new > g["lines"][pid]:
                g["lines"][pid] = new
                bot.send_message(cid, f"🟢 <b>{bot.get_chat(pid).first_name}</b> {new}/5")

            img = draw_card(
                bot.get_chat(pid).first_name,
                card,
                g["marked"][pid],
                g["lines"][pid]
            )
            img.save("update.png")
            bot.send_photo(pid, open("update.png", "rb"))

            if new == 5:
                bot.send_message(cid, f"🏆 <b>{bot.get_chat(pid).first_name}</b> WINS 🎉")
                games.pop(cid)
                return

bot.infinity_polling()
