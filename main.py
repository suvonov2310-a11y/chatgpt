import asyncio
import aiohttp
import base64
import io
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart

# --- 1. SOZLAMALAR ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
RAW_KEYS = os.getenv("GEMINI_KEYS", "")
# Kalitlarni tozalab ro'yxatga olamiz
GEMINI_KEYS = [k.strip() for k in RAW_KEYS.split(",") if k.strip()]

current_key_index = 0
user_history = {}

# Jorjning xarakteristikasi: Qisqa, lo'nda va samimiy
SYSTEM_PROMPT = """Sening isming - Jorj. Seni Suvonov Sherzod yaratgan. 
Sen foydalanuvchining yaqin do'stisan. 
QOIDALARING:
1. Har doim samimiy, 'odamdek' gaplash (robotdek emas).
2. Javoblaring juda QISQA va LO'NDA bo'lsin.
3. 'Qadrdonim', 'birodar', 'do'stim' kabi so'zlarini ishlat.
4. Savolga javob berishda ortiqcha lof urma, faqat mag'zini ayt.
5. Rasm yuborilsa, uni o'tkir ko'zlar bilan ko'rib, qisqa xulosa ber."""

# --- 2. BOT VA DISPATCHER ---
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# --- 3. KEYLAR ORASIDA AYLANISH VA JAVOB OLISH ---
async def get_gemini_response(user_id, text=None, photo_bytes=None):
    global current_key_index
    
    if not GEMINI_KEYS:
        return "Xatolik: API kalitlar topilmadi!"

    if user_id not in user_history:
        user_history[user_id] = []
    
    # Kontekst tayyorlash (Oxirgi 6 ta xabar)
    contents = []
    for hist in user_history[user_id][-6:]:
        contents.append(hist)
    
    # Hozirgi xabar
    prompt_text = f"{SYSTEM_PROMPT}\n\nFoydalanuvchi: {text if text else 'Rasm bo`yicha savol'}"
    current_parts = [{"text": prompt_text}]
    
    if photo_bytes:
        image_data = base64.b64encode(photo_bytes).decode('utf-8')
        current_parts.append({"inline_data": {"mime_type": "image/jpeg", "data": image_data}})
    
    contents.append({"role": "user", "parts": current_parts})

    # 7 TA KALITNI KETMA-KET TEKSHIRISH (LOOP)
    for _ in range(len(GEMINI_KEYS)):
        api_key = GEMINI_KEYS[current_key_index]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        
        try:
            async with aiohttp.ClientSession() as aioss:
                async with aioss.post(url, json={"contents": contents}, timeout=20) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        answer = data['candidates'][0]['content']['parts'][0]['text']
                        
                        # Tarixni yangilash
                        user_history[user_id].append({"role": "user", "parts": [{"text": text if text else "Rasm"}]})
                        user_history[user_id].append({"role": "model", "parts": [{"text": answer}]})
                        return answer
                    
                    # Agar limit tugasa (429) yoki xato bo'lsa, keyingisiga o'tish
                    else:
                        print(f"Kalit {current_key_index} ishlamadi ({resp.status}). Keyingisiga o'tildi.")
                        current_key_index = (current_key_index + 1) % len(GEMINI_KEYS)
                        continue
        except Exception as e:
            print(f"Ulanishda xato: {e}. Keyingi kalitga o'tilmoqda...")
            current_key_index = (current_key_index + 1) % len(GEMINI_KEYS)
            continue
            
    return "Uzr qadrdonim, hozir hamma kalitlarda limit tugabdi. Biroz dam olib, keyin yozvor! 😊"

# --- 4. HANDLERLAR ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_history[message.from_user.id] = []
    await message.answer(f"Assalomu alaykum! Men Jorjman. Sherzodbekning xizmatidaman. Qanday yordam kerak, do'stim?")

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    await bot.send_chat_action(message.chat.id, "typing")
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    photo_buffer = io.BytesIO()
    await bot.download_file(file.file_path, destination=photo_buffer)
    
    res = await get_gemini_response(
        message.from_user.id, 
        text=message.caption, 
        photo_bytes=photo_buffer.getvalue()
    )
    await message.reply(res)

@dp.message()
async def text_handler(message: types.Message):
    await bot.send_chat_action(message.chat.id, "typing")
    res = await get_gemini_response(message.from_user.id, text=message.text)
    await message.answer(res)

# --- 5. RUN ---
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("🚀 Jorj (7-Key System) Railway'da yondi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())