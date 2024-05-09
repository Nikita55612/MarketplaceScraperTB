from telebot.types import (
    InlineKeyboardMarkup as tbMarkup, 
    InlineKeyboardButton as tbButton
    )
from datetime import datetime as dt
import  multiprocessing as mp
from bot import scraper
import config as cfg
import bot as tb
import telebot
import random
import json
import time
import os


def loop():
    time.sleep(10*10)
    bot = telebot.TeleBot(cfg.TELEBOT_TOKEN, threaded=False, num_threads=0, skip_pending=True)
    while True:
        users = os.listdir(cfg.USERS_DATA_DIR)
        users.remove(".DS_Store")
        products = []
        user_profiles = {}
        for u in users:
            try:
                with open(f"{cfg.USERS_DATA_DIR}/{u}/profile.json", "r", encoding="utf-8") as f:
                    profile = json.load(f)
            except Exception as _ex:
                continue
            user_profiles[u] = profile
            streams = profile["streams"]
            for thr in streams:
                if not streams[thr]["live"]:
                    continue
                for product in streams[thr]["products"]:
                    products.append(product)
        """
        products_data = {}
        for product in list(set(products)):
            data = scraper.get_product(scraper.id_to_url(*product.split("_"))).__dict__
            if data:
                products_data[product] = data
        """
        products_data = {}
        products = list(set(products))
        random.shuffle(products)
        products_multiprocessing_data = scraper.get_products_multiprocessing(
            [scraper.id_to_url(*i.split("_")) for i in products], 3)
        for product_url in products_multiprocessing_data:
            if products_multiprocessing_data[product_url]:
                id_, mp = scraper.url_to_id(product_url)
                products_data[f"{mp}_{id_}"] = products_multiprocessing_data[product_url].__dict__
        notifications = {}
        dt_now = time.time()
        for u in users:
            profile = user_profiles[u]
            streams = profile["streams"]
            for s in streams:
                if not streams[s]["live"]:
                    continue
                profile["streams"][s]["last_update"] = dt_now
                profile["streams"][s]["total_updates"] += 1
                for p in streams[s]["products"]:
                    if p not in products_data:
                        continue
                    price = streams[s]["products"][p]["price"]
                    products_data_price = int(products_data[p]["price"])
                    profile["streams"][s]["products"][p]["name"] = products_data[p].get("name")
                    profile["streams"][s]["products"][p]["seller"] = products_data[p].get("seller")
                    profile["streams"][s]["products"][p]["popularity_index"] = scraper.try_type(products_data[p].get("popularity_index"), float)
                    if "history" not in profile["streams"][s]["products"][p]:
                        profile["streams"][s]["products"][p]["history"] = [[price, dt_now]]
                    if price != products_data_price:
                        profile["streams"][s]["products"][p]["prev_price"] = int(price) if price else products_data_price
                        profile["streams"][s]["products"][p]["price"] = products_data_price
                        profile["streams"][s]["products"][p]["history"].append([products_data_price, dt_now])
                        if profile["notifications"]:
                            if u not in notifications:
                                notifications[u] = {}
                            mp, id_ = p.split("_")
                            if s not in notifications[u]:
                                notifications[u][s] = []
                            notifications[u][s].append(
                                {"mp": mp, "id": id_, 
                                "price": profile["streams"][s]["products"][p]["price"],
                                "prev_price": profile["streams"][s]["products"][p]["prev_price"]
                                })
            try:
                with open(f"{cfg.USERS_DATA_DIR}/{u}/profile.json", "w", encoding='utf-8') as f:
                    json.dump(profile, f, indent=4, ensure_ascii=False)
            except Exception as _ex:
                pass
        for u in notifications:
            notification = "🔊 <b>Изменение цены</b>\n"
            notification_markup = tbMarkup()
            total_changes = 0
            for thr in notifications[u]:
                total_changes += len(notifications[u][thr])
                notification_markup.add(tbButton(f"⚪️ {thr}", callback_data=f"get_stream={thr}"))
                notification += f"\n<b>{thr}:</b>\n"
                if len(notifications[u][thr]) <= 12:
                    for i in notifications[u][thr]:
                        diff_price = round((i["price"] - i["prev_price"]) / i["price"] * 100, 2)
                        notification += f"{i['mp']} <code>{i['id']}</code>: {i['price']}р    {diff_price}%\n"
                else:
                    notification += f"Количесто изменений: {len(notifications[u][thr])}\n"
            notification += f"\nВсего изменений: {total_changes}\n"
            try:
                bot.send_message(u, notification, parse_mode="HTML", 
                                 reply_markup=notification_markup.add(row_width=1))
            except Exception as _ex:
                pass
            time.sleep(1)
        if dt.fromtimestamp(dt_now).hour in (23, 0, 1, 2, 3, 4, 5):
            while dt.fromtimestamp(time.time()).hour in (23, 0, 1, 2, 3, 4, 5):
                time.sleep(cfg.SCRAPER_LOOP_TIMEOUT)
        else:
            time.sleep(min([cfg.SCRAPER_LOOP_TIMEOUT + len(products), cfg.SCRAPER_LOOP_TIMEOUT * 4]))


def main():
    try:
        print("bot start polling...")
        tb.bot.infinity_polling()
    except Exception as ex:
        time.sleep(20)
        main()


if __name__ == "__main__":
    if not os.path.exists(cfg.AUTHORIZATION_KEYS_PATH):
        with open(cfg.AUTHORIZATION_KEYS_PATH, "w", encoding="utf-8") as f:
            json.dump([], f, indent=4, ensure_ascii=False)
    os.mkdir(cfg.DRIVER_DATA_DIR) if not os.path.exists(cfg.DRIVER_DATA_DIR) else ...
    p = mp.Process(target=loop)
    p.start()
    main()