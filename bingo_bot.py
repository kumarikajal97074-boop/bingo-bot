import os
import random
import telebot
from PIL import Image, ImageDraw, ImageFont

# ---------- BOT ----------
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise RuntimeError("TOKEN not set")

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

games = {}

# ---------- CARD CONFIG ----------
GRID = 5
CELL = 140
FONT_SIZE = 60
MARGIN = 30
TOP = 100
IMG_W = GRID * CELL + MARGIN * 2

FONT = ImageFont.truetype("DejaVuSans-Bold.ttf", FONT_SIZE)
TITLE_FONT = ImageFont.truetype("DejaVuSans-Bold.ttf", 32)

# ---------- CARD LOGIC ----------
def new_card():
    nums = list(range(1, 26))
    random.shuffle(nums)
    return [nums[i*5:(i+1)*5] for i in range(5)]

def draw_card(name, card):
    img = Image.new("RGB", (IMG_W, IMG_W + 80), "white")
    d = ImageDraw.Draw(img)

    d.text((IMG_W//2, 20), f"{name}'s BINGO",
           fill="black", anchor="mm", font=TITLE_FONT)

    for r in range(5):
        for c in range(5):
            x1 = MARGIN + c * CELL
            y1 = TOP + r * CELL
            x2 = x1 + CELL
            y2 = y1 + CELL

            d.rectangle([x1, y1, x2, y2], outline="black", width=4)
            num = str(card[r][c])
            w, h = d.textbbox((0,0), num, font=FONT)[2:]
            d.text((x1 + CELL//2, y1 + CELL//2),
                   num, fill="black", anchor="mm", font=FONT)

    return img

# ---------- COMMANDS ----------
@bot.message_handler(commands=["startgame"])
def start_game(m):
    games[m.chat.id] = {
        "players": {},   # uid -> card
        "marked": {},    # uid -> set(numbers)
        "called": set()  # ← REQUIRED
    }

    bot.send_message(
        m.chat.id,
        "🎯 Bingo started\nUse /join to join",
        parse_mode="HTML"
    )


@bot.message_handler(commands=["join"])
def join(m):
    cid = m.chat.id
    uid = m.from_user.id
    name = m.from_user.first_name

    if cid not in games:
        bot.reply_to(m, "❌ No active game. Use /startgame")
        return

    if uid in games[cid]:
        bot.reply_to(m, "⚠️ You already joined")
        return

    card = new_card()
    games[cid][uid] = card

    img = draw_card(name, card)
    img.save("card.png")

    try:
        bot.send_photo(uid, open("card.png", "rb"))
        bot.send_message(cid, f"✅ {name} joined")
    except:
        bot.reply_to(
            m,
            "❌ Please open bot DM once and press Start"
        )
# ================= NUMBER CALL + MARK X =================
@bot.message_handler(func=lambda m: m.text and m.text.isdigit())
def call_number(m):
    chat_id = m.chat.id
    uid = m.from_user.id
    number = int(m.text)

    # game must exist
    if chat_id not in games:
        return

    g = games[chat_id]

    # only joined players can call numbers
    if uid not in g["players"]:
        bot.reply_to(m, "❌ You have not joined the game")
        return

    # block duplicate numbers
    if number in g["called"]:
        bot.reply_to(m, "⚠️ Number already called")
        return

    # save number
    g["called"].add(number)

    # announce in group
    bot.send_message(
        chat_id,
        f"📢 <b>{m.from_user.first_name}</b> called <b>{number}</b>",
        parse_mode="HTML"
    )

    # update all joined players
    for pid, card in g["players"].items():
        if number in card:
            g["marked"][pid].add(number)

        lines = count_lines(card, g["marked"][pid])

        img = draw_card(
            bot.get_chat(pid).first_name,
            card,
            g["marked"][pid],
            lines
        )

        img.save("update.png")
        bot.send_photo(pid, open("update.png", "rb"))


# ---------- RUN ----------
bot.infinity_polling(skip_pending=True)
