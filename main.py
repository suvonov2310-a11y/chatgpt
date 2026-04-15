import asyncio
import aiohttp
import base64
import io
import os  # Muhit o'zgaruvchilari bilan ishlash uchun shart
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart

# --- 1. XAVFSIZ SOZLAMALAR ---
# Kalitlar endi kod ichida emas, Railway Variables bo'limidan olinadi
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
RAW_KEYS = os.getenv("GEMINI_KEYS", "")
GEMINI_KEYS = [k.strip() for k in RAW_KEYS.split(",") if k.strip()]

current_key_index = 0
user_history = {}

SYSTEM_PROMPT = """Sening isming - Jorj. Seni Suvonov Sherzod telegramga olib kirdi. 
Sen Sherzodbekning sodiq do'stisan. Foydalanuvchilar bilan samimiy, yaqin do'stdek gaplash. 
Savollarga QISQA va LO'NDA javob ber. Gaplaringda 'qadrdonim', 'birodar', 'do'stim' so'zlarini ishlat."""

# --- 2. BOT VA DISPATCHER ---
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# --- 3. ASOSIY LOGIKA ---
async def get_gemini_response(user_id, text=None, photo_bytes=None):
    global current_key_index
    
    if not GEMINI_KEYS:
        return "Tizimda API kalitlar topilmadi. Iltimos, sozlamalarni tekshiring."

    if user_id not in user_history:
        user_history[user_id] = []
    
    contents = []
    for hist in user_history[user_id][-6:]:
        contents.append(hist)
    
    current_parts = [{"text": f"{SYSTEM_PROMPT}\n\nFoydalanuvchi: {text if text else 'Rasm bo`yicha savol'}"}]
    
    if photo_bytes:
        image_data = base64.b64encode(photo_bytes).decode('utf-8')
        current_parts.append({"inline_data": {"mime_type": "image/jpeg", "data": image_data}})
    
    contents.append({"role": "user", "parts": current_parts})

    for _ in range(len(GEMINI_KEYS)):
        api_key = GEMINI_KEYS[current_key_index]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={api_key}"
        
        try:
            async with aiohttp.ClientSession() as aioss:
                async with aioss.post(url, json={"contents": contents}, timeout=30) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        answer = data['candidates'][0]['content']['parts'][0]['text']
                        
                        user_history[user_id].append({"role": "user", "parts": [{"text": text if text else "Rasm yuborildi"}]})
                        user_history[user_id].append({"role": "model", "parts": [{"text": answer}]})
                        return answer
                    elif resp.status == 429:
                        current_key_index = (current_key_index + 1) % len(GEMINI_KEYS)
                        continue
        except:
            current_key_index = (current_key_index + 1) % len(GEMINI_KEYS)
            continue
            
    return "Uzr qadrdonim, Jorj hozir biroz band. Birozdan keyin gaplashamiz! 😊"

# --- 4. HANDLERLAR ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_history[message.from_user.id] = []
    await message.answer(f"Salom, {message.from_user.first_name}! Men Jorjman. Sherzodbek meni yaratgan. Qanday yordam bera olaman?")

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    await bot.send_chat_action(message.chat.id, "typing")
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    photo_buffer = io.BytesIO()
    await bot.download_file(file.file_path, destination=photo_buffer)
    res = await get_gemini_response(message.from_user.id, text=message.caption, photo_bytes=photo_buffer.getvalue())
    await message.reply(res)

@dp.message()
async def text_handler(message: types.Message):
    await bot.send_chat_action(message.chat.id, "typing")
    res = await get_gemini_response(message.from_user.id, text=message.text)
    await message.answer(res)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("🚀 Jorj Railway serverida (xavfsiz rejimda) ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())