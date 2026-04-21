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
# Kalitlarni tozalash va ro'yxatga olish
GEMINI_KEYS = [k.strip().replace('"', '').replace("'", "") for k in RAW_KEYS.split(",") if k.strip()]

current_key_index = 0
user_history = {}

# Jorjning "odamshavanda" xarakteri
SYSTEM_PROMPT = """Sening isming - Jorj. Seni Suvonov Sherzod yaratgan. 
Sen foydalanuvchining samimiy do'stisan. 
QOIDALARING:
1. 'Qadrdonim', 'birodar', 'do'stim' kabi so'zlarini ishlatib gaplash.
2. Savollarga qisqa, lo'nda va tushunarli javob ber.
3. Rasm yuborilsa, uni diqqat bilan tahlil qilib, nima ekanligini ayt."""

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# --- 2. ASOSIY LOGIKA: KEYLARNI AYLANISH ---
async def get_gemini_response(user_id, text=None, photo_bytes=None):
    global current_key_index
    
    if not GEMINI_KEYS:
        return "Xato: Railway Variables'da kalitlar topilmadi, qadrdonim!"

    if user_id not in user_history:
        user_history[user_id] = []
    
    # Tarixni (kontekstni) tayyorlash
    contents = []
    for hist in user_history[user_id][-6:]:
        contents.append(hist)
    
    # Yangi so'rovni shakllantirish
    prompt_text = f"{SYSTEM_PROMPT}\n\nFoydalanuvchi: {text if text else 'Mana bu rasmda nima bor?'}"
    current_parts = [{"text": prompt_text}]
    
    if photo_bytes:
        image_data = base64.b64encode(photo_bytes).decode('utf-8')
        current_parts.append({"inline_data": {"mime_type": "image/jpeg", "data": image_data}})
    
    contents.append({"role": "user", "parts": current_parts})

    # 7 TA KALITNI KETMA-KET TEKSHIRISH
    for attempt in range(len(GEMINI_KEYS)):
        api_key = GEMINI_KEYS[current_key_index]
        # Gemini 3 modelining maxsus manzili
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={api_key}"
        
        try:
            async with aiohttp.ClientSession() as aioss:
                async with aioss.post(url, json={"contents": contents}, timeout=30) as resp:
                    status = resp.status
                    data = await resp.json()
                    
                    if status == 200:
                        if 'candidates' in data and data['candidates']:
                            answer = data['candidates'][0]['content']['parts'][0]['text']
                            
                            # Tarixni yangilash
                            user_history[user_id].append({"role": "user", "parts": [{"text": text if text else "Rasm yubordi"}]})
                            user_history[user_id].append({"role": "model", "parts": [{"text": answer}]})
                            return answer
                    
                    # Agar limit (429) yoki boshqa xato bo'lsa, keyingi kalitga o'tish
                    print(f"DEBUG: Key-{current_key_index} ishlamadi ({status}). Keyingisiga o'taman...")
                    current_key_index = (current_key_index + 1) % len(GEMINI_KEYS)
                    
        except Exception as e:
            print(f"DEBUG: Xatolik yuz berdi: {e}")
            current_key_index = (current_key_index + 1) % len(GEMINI_KEYS)
            continue
            
    return "Uzr do'stim,tizimda muammo bor chiqdi. Birozdan keyin urinib ko'ramiz! 😊"

# --- 3. HANDLERLAR ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_history[message.from_user.id] = []
    await message.answer(f"Assalomu alaykum, qadrdonim! Men Jorjman.Nima deysiz?")

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

# --- 4. ISHGA TUSHIRISH ---
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print(f"🚀 Jorj Gemini 3 bilan yondi! Jami kalitlar: {len(GEMINI_KEYS)}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())