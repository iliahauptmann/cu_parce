import telebot
import requests
import re
import io
import PyPDF2
from telebot import types
import json
import os
from datetime import datetime
import asyncio
import aiofiles
from requests.exceptions import ReadTimeout

bot = telebot.TeleBot('TOKEN') # Инициализация бота с токеном

# Глобальные переменные для хранения данных
cached_data = {}            # Кэширование данных о количестве абитуриентов
last_update_time = None     # Время последних обновлений данных
all_snils = set()           # Множество всех номеров СНИЛС

def download_pdf(url):
    response = requests.get(url)
    return io.BytesIO(response.content)

def extract_text_from_pdf(pdf_file): # Функция извлекает текст из PDF-файла, возвращает извлеченный текст
    reader = PyPDF2.PdfReader(pdf_file) # Создаем объект PdfReader
    return "\n".join([page.extract_text() for page in reader.pages]) # Извлекаем текст из каждой страницы и объединяем

async def save_cache(): # Асинхронно сохраняет кэшированные данные в JSON-файл.
    async with aiofiles.open('cache.json', mode='w') as f:
        await f.write(json.dumps({
            'data': cached_data,
            'last_update': last_update_time.isoformat() if last_update_time else None
        }))

async def load_cache(): # Асинхронно загружает кэшированные данные из JSON-файла.
    global cached_data, last_update_time
    try:
        async with aiofiles.open('cache.json', mode='r') as f:
            content = await f.read()
            cache = json.loads(content)
            cached_data = cache['data']
            last_update_time = datetime.fromisoformat(cache['last_update']) if cache['last_update'] else None
    except FileNotFoundError:
        print("Cache file not found. Starting with empty cache.")
    except json.JSONDecodeError:
        print("Error decoding cache file. Starting with empty cache.")

def check_snils(message):  # Проверяет, есть ли введенный СНИЛС в списке абитуриентов
    snils = message.text.strip()
    if re.match(r'^\d{11}$', snils):
        if snils in all_snils:
            bot.send_message(message.chat.id, "Поздравляем! Ваш СНИЛС найден в списке абитуриентов.")
        else:
            bot.send_message(message.chat.id, "К сожалению, ваш СНИЛС не найден в списке абитуриентов.")
    else:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректный номер СНИЛС (11 цифр без пробелов и тире).")

async def update_data(): # Асинхронно обновляет данные о количестве абитуриентов.
    global cached_data, last_update_time, all_snils
    url = "https://static.centraluniversity.ru/documents/legal/apply/%D0%A1%D0%BF%D0%B8%D1%81%D0%BE%D0%BA%20%D0%BB%D0%B8%D1%86%20%D0%BF%D0%BE%D0%B4%D0%B0%D0%B2%D1%88%D0%B8%D1%85%20%D0%B4%D0%BE%D0%BA%D1%83%D0%BC%D0%B5%D0%BD%D1%82%D1%8B.pdf"

    competition_groups = [
        "02.03.01 Математика и компьютерные науки, Очная, Полное возмещение затрат",
        "02.03.01 Математика и компьютерные науки, Очная, Общие бюджетные места",
        "02.03.01 Математика и компьютерные науки, Очная, Места целевой квоты",
        "02.03.01 Математика и компьютерные науки, Очная, Места особой квоты",
        "38.03.05 Бизнес-информатика, Очная, Полное возмещение затрат"
    ]

    pdf_file = download_pdf(url) # Загружаем PDF-файл
    text_content = extract_text_from_pdf(pdf_file) # Извлекаем текст из PDF
    results = {group: [] for group in competition_groups} # Инициализируем словарь результатов

    sections = re.split(r'(?=' + '|'.join(re.escape(group) for group in competition_groups) + ')', text_content)  # Разделяем текст на секции по группам

    all_snils.clear() # Очищаем множество перед обновлением

    for section in sections:
        for group in competition_groups:
            if section.startswith(group):
                numbers = re.findall(r'\b\d{11}\b', section) # Ищем все 11-значные числа (СНИЛС)
                results[group].extend(numbers) # Добавляем найденные СНИЛС в соответствующую группу
                all_snils.update(numbers) # Добавляем все СНИЛС в общее множество
                break

    all_numbers = set() # Считает количество всех абитуриентов, подавших документы
    for group in competition_groups:
        for number in results[group]:
            all_numbers.add(number)

    cached_data = { # Обновляем кэшированные данные
        "mkn_platka": len(results["02.03.01 Математика и компьютерные науки, Очная, Полное возмещение затрат"]),
        "bi_platka": len(results["38.03.05 Бизнес-информатика, Очная, Полное возмещение затрат"]),
        "mkn_budget": len(results["02.03.01 Математика и компьютерные науки, Очная, Общие бюджетные места"]),
        "mkn_celevoe": len(results["02.03.01 Математика и компьютерные науки, Очная, Места целевой квоты"]),
        "mkn_osobaya": len(results["02.03.01 Математика и компьютерные науки, Очная, Места особой квоты"]),
        "vsego": len(all_numbers)
    }

    last_update_time = datetime.now() # Обновляем время последнего обновления

    print(f"Data updated at {last_update_time}")

    await save_cache() # Сохраняем кэш

@bot.message_handler(commands=['start'])
def welcome(message): # Обработчик команды /start. Отправляет приветственное сообщение и показывает клавиатуру.
    sticker = open('hi.webm', 'rb')
    bot.send_sticker(message.chat.id, sticker)

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    contacts = types.KeyboardButton('Контакты создателя')
    info = types.KeyboardButton('Вся информация по спискам')
    stata = types.KeyboardButton('Статистика')
    find_sebya = types.KeyboardButton('Найти себя')
    markup.add(info, contacts, stata, find_sebya)

    bot.send_message(message.chat.id, 'Привет, {0.first_name}!\nВыбери информацию, которую хочешь узнать)\n'.format(message.from_user, bot.get_me()), parse_mode='html', reply_markup=markup)

@bot.message_handler(content_types=['text'])
def lalala(message): # Обработчик текстовых сообщений. Отвечает на запросы пользователя.
    if message.chat.type == 'private':
        if message.text == 'Контакты создателя':
            bot.send_message(message.chat.id, 'tg создателя: @ilija07\ngithub проекта: https://vk.cc/cy5I30')
        elif message.text == 'Вся информация по спискам':
            if not cached_data:
                bot.send_message(message.chat.id, "Данные еще не загружены. Пожалуйста, попробуйте позже.")
            else:
                response = f'''02.03.01 Математика и компьютерные науки, Очная, Полное возмещение затрат
Количество абитуриентов в группе: <b>{cached_data['mkn_platka']}</b>

02.03.01 Математика и компьютерные науки, Очная, Общие бюджетные места
Количество абитуриентов в группе: <b>{cached_data['mkn_budget']}</b>

02.03.01 Математика и компьютерные науки, Очная, Места целевой квоты
Количество абитуриентов в группе: <b>{cached_data['mkn_celevoe']}</b>

02.03.01 Математика и компьютерные науки, Очная, Места особой квоты
Количество абитуриентов в группе: <b>{cached_data['mkn_osobaya']}</b>

38.03.05 Бизнес-информатика, Очная, Полное возмещение затрат
Количество абитуриентов в группе: <b>{cached_data['bi_platka']}</b>

Общее количество абитурентов, подавших документы: <b>{cached_data['vsego']}</b>

Последнее обновление данных: {last_update_time}'''
                bot.send_message(message.chat.id, response, parse_mode='html')
        elif message.text == 'Статистика':
            bot.send_message(message.chat.id, "<b>Статистика количества абитуриентов, подавших документы\n</b> \n 29.06.2024 - 116 человек\n 01.07.2024 - 158 человек",  parse_mode='html') # Обновляется вручную
        elif message.text == 'Найти себя':
            bot.send_message(message.chat.id, "Пожалуйста, введите ваш номер СНИЛС (11 цифр без пробелов и тире):")
            bot.register_next_step_handler(message, check_snils)
        else:
            bot.send_message(message.chat.id, "Извините, я не понимаю эту команду.")


def run_bot(): #Запускает бота в режиме polling
    try:
        bot.polling(none_stop=True, timeout=120)
    except ReadTimeout:
        print("ReadTimeout error occurred. Restarting polling...")
        run_bot()

async def run_scheduler(): # Асинхронно запускает планировщик для периодического обновления данных.
    while True:
        await update_data()
        await asyncio.sleep(1800)  # Ждем 30 минут перед следующим обновлением

async def main():   # Основная асинхронная функция, которая запускает бота и планировщик.
    await load_cache() # Загружаем кэш
    if not cached_data: # Если кэш пуст, обновляем данные
        await update_data()

    bot_thread = asyncio.to_thread(run_bot) # Запускаем бота в отдельном потоке
    scheduler_task = asyncio.create_task(run_scheduler()) # Создаем задачу для планировщика

    await asyncio.gather(bot_thread, scheduler_task) # Ожидаем завершения обоих задач

if __name__ == '__main__':
    asyncio.run(main()) # Запускаем основную асинхронную функцию
