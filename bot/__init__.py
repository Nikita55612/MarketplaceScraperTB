from pretty_html_table import build_table
from .users import User, get_users_list
from telebot.types import (
    InlineKeyboardMarkup as tbMarkup, 
    InlineKeyboardButton as tbButton
    )
from datetime import datetime as dt
from openai import OpenAI
from . import scraper
import config as cfg
import pandas as pd
import validators
import requests
import telebot
import uuid
import json
import time


bot = telebot.TeleBot(cfg.TELEBOT_TOKEN, num_threads=4)
#bot.set_my_commands([telebot.types.BotCommand(*i) for i in [("/client", "🗂")]])
client = OpenAI(api_key=cfg.GPT_API_KEY, base_url=cfg.GPT_BASE_URL)


def read_excel(path: str) -> dict:
    excel_data = pd.read_excel(path)
    excel_data = excel_data.fillna("")
    columns = list(map(str.lower, excel_data.columns))
    excel_data.columns = columns
    return excel_data.to_dict("records")


def pars_table(data: dict):
    for n, i in enumerate(data):
        if i.get("url") and validators.url(i.get("url")):
            id_, mp = scraper.url_to_id(i["url"])
        else:
            id_, mp = i.get("id"), i.get("mp")
            if id_ is None or mp is None:
                continue
            if mp not in ("ozon", "wb", "vi", "ym"):
                continue
        price = scraper.try_type(i["price"], int) if i.get("price") else None
        name = scraper.try_type(i["name"], str) if i.get("name") else ""
        popularity_index = scraper.try_type(i["popularity_index"], float) if i.get("popularity_index") else None
        seller = scraper.try_type(i["seller"], str) if i.get("seller") else ""
        yield n, mp, id_, price, name, popularity_index, seller


class Mark:
    close_mp = tbMarkup().add(tbButton("🚫 Закрыть", callback_data="close"))
    finish_upd_table = tbMarkup().add(tbButton("🚫 Завершить", callback_data="finish_upd_table"))


class TUser(User):
    def __init__(self, id, chat_id, name=None) -> None:
        self.chat_id = chat_id
        self.name = name
        super().__init__(id)
        if self.profile.status == "not_authorized":
            bot.send_message(self.chat_id, "⚠️ Пользователь не авторизован!\nВведите код доступа для авторизации.")

    def get_client_info(self):
        return f"🗂 <b><u><i>Личный кабинет</i></u></b>\n\n👤 " \
               f"Имя: <b>{self.name} (ID: <code>{self.id}</code>)</b>\n" \
               f"<b><u><a href='{cfg.DOC_URL}'>Документация</a></u></b>" 
    
    def get_stream_info(self, key: str):
        self.upd_profile()
        stream = self.profile.streams[key]
        products = stream["products"]
        stream_info = ("🟡 " if len(products) == 0 and stream["live"] 
                       else "⚪️ " if stream["live"] else "⚫️ ")
        stream_info += f"<b>{key}</b>\n\nТовары:\n"
        if len(products) > 0:
            for n, p in enumerate(products):
                product = products[p]
                mp, id_, deff_price = (*p.split("_"), "")
                if product["prev_price"] != product["price"] and product["price"]:
                    deff_price = round((product["price"] - product["prev_price"]) / 
                                       product["price"] * 100, 1)
                    deff_price = f"{deff_price}%"
                str_price = f"{product['price']}р" if product["price"] else "None"
                stream_info += f"{n + 1}. {mp} <code>{id_}</code>:  {str_price}    {deff_price}\n"
                if n == 19:
                    stream_info += f"+ еще {len(products) - 20}...\n"
                    break
        else:
            stream_info += "Пусто\n"
        stream_info += f"\nВсего обновлений: <b>{stream['total_updates']}</b>"
        next_update = (max([round((cfg.SCRAPER_LOOP_TIMEOUT - (time.time() - stream['last_update']))), 0]) 
                       if stream['last_update'] else '0')
        stream_info += f"\nСледующее обновление через: <b>{next_update}s</b>"
        stream_info += f"\nПоследнее обновление:\n" \
                       f"<b>{dt.fromtimestamp(stream['last_update']) if stream['last_update'] else 'None'}</b>"
        return stream_info
    
    def get_product_info(self, product: scraper.Product) -> str:
        return f"<b><a href='{product.url}'>{product.name}</a></b>\n{product.category}\n"\
               f"<a href='{product.seller_url}'>{product.seller}</a>\n\n" \
               f"Цена: <b>{product.price}</b>р\nПопулярность: <b>{product.popularity_index}</b>"\
               f"\nID ({product.mp}): <code>{product.id}</code>"
    
    def add_product_to_stream_markup(self, product: scraper.Product):
        user_streams_bt = [tbButton(f"🟡 {i}" if len(self.profile.streams[i]["products"]) == 0                                    
                                    and self.profile.streams[i]["live"] else f"⚪️ {i}" 
                                    if self.profile.streams[i]["live"] else f"⚫️ {i}", 
                                    callback_data=f"apts={i}/,{product.id}/,{product.mp}/,{product.price}") 
                                    for i in self.profile.streams]
        return tbMarkup().add(
            *user_streams_bt, row_width=2).add(
                tbButton("🚫 Закрыть", callback_data="close"), row_width=1)
    
    def add_table_to_stream_markup(self, file: str):
        user_streams_bt = [tbButton(f"🟡 {i}" if len(self.profile.streams[i]["products"]) == 0                                    
                                    and self.profile.streams[i]["live"] else f"⚪️ {i}" 
                                    if self.profile.streams[i]["live"] else f"⚫️ {i}", 
                                    callback_data=f"add_table_to_stream={i}/,{file}") 
                                    for i in self.profile.streams]
        return tbMarkup().add(
            *user_streams_bt, row_width=2).add(
                tbButton("🔂 Обновить данные таблицы", callback_data=f"update_table={file}"),
                tbButton("🚫 Закрыть", callback_data="close"), row_width=1)
    
    def get_stream_add_markup(self, key: str):
        stream = self.profile.streams[key]
        return tbMarkup().add(
            tbButton(f"{'🟡' if stream['products'] == 0 and stream['live'] else '⚪️' if stream['live'] else '⚫️'} {key}", 
                     callback_data=f"get_stream={key}"),
            tbButton("🚫 Закрыть", callback_data="close"), row_width=1)
    
    def get_stream_markup(self, key: str):
        stream = self.profile.streams[key]
        if len(self.profile.streams[key]["products"]) > 0:
            download_stream_data_bt = tbButton("⬇️ Загрузить", callback_data=f"download_stream_data={key}") 
            download_stream_history_bt = tbButton("⬇️ История цен", callback_data=f"download_stream_history={key}") 
        else:
            download_stream_data_bt = tbButton("🔒 Загрузить", callback_data="None")
            download_stream_history_bt = tbButton("🔒 История цен", callback_data="None")
        return tbMarkup().add(
            tbButton("⏸ Остановить" if stream["live"] else "▶️ Проболжить", callback_data=f"switch_stream_state={key}"),
            tbButton("🗑 Удалить поток", callback_data=f"del_stream={key}"), 
            download_stream_history_bt, tbButton("➖ Удалить товар", callback_data=f"del_stream_item={key}"), 
            download_stream_data_bt, row_width=2).add(
                tbButton("⬅️ Назад", callback_data="client"), row_width=1)
    
    def get_product_by_id_markup(self, id: str | int):
        return tbMarkup().add(
            tbButton("🛠 VseInstrumenti", callback_data=f"product_by_id=vi_{id}"),
            tbButton("〽️ YandexMarket", callback_data=f"product_by_id=ym_{id}"), 
            tbButton("🍇 Wildberries", callback_data=f"product_by_id=wb_{id}"), 
            tbButton("🌀 Ozon", callback_data=f"product_by_id=ozon_{id}"), row_width=1)

    def get_client_markup(self):
        user_streams_bt = [tbButton(f"🟡 {i}" if len(self.profile.streams[i]["products"]) == 0 
                                    and self.profile.streams[i]["live"] else f"⚪️ {i}" 
                                    if self.profile.streams[i]["live"] else f"⚫️ {i}", 
                                    callback_data=f"get_stream={i}") for i in self.profile.streams]
        add_stream = "Thread"
        for t in range(1, cfg.MAX_USER_STREAMS + 1):
            if f"Thread{t}" not in self.profile.streams:
                add_stream += f"{t}"
                break
        return tbMarkup().add(
            tbButton("⚙️ Настройки", callback_data="settings"), row_width=1).add(
            *user_streams_bt, row_width=2).add(
                tbButton("🆕 Создать поток", callback_data=f"add_stream={add_stream}"), 
                row_width=1)
    
    def get_settings_markup(self):
        return tbMarkup().add(
            tbButton("✏️ Переименовать поток", callback_data=f"rename_stream"), 
            tbButton(f"{'✅    ' if self.profile.sending_pictures else '🚫    '}🖼 Отправка картинок", 
                     callback_data=f"sending_pictures"), 
            tbButton(f"{'🔊  ' if self.profile.notifications else '🔇  '}Уведомления", 
                     callback_data=f"notifications"), 
            tbButton("⬅️ Назад", callback_data="client"), row_width=1)
    
    def get_rename_stream_markup(self):
        user_streams_bt = [tbButton(f"🟡 {i}" if len(self.profile.streams[i]["products"]) == 0 
                                    and self.profile.streams[i]["live"] else f"⚪️ {i}" 
                                    if self.profile.streams[i]["live"] else f"⚫️ {i}", 
                                    callback_data=f"rename_stream={i}") for i in self.profile.streams]
        return tbMarkup().add(*user_streams_bt, tbButton("⬅️ Назад", callback_data="settings"), row_width=1)
    
    def try_request_again_markup(self, mp: str, id: str | int):
        return tbMarkup().add(
            tbButton(f"🔄 Повторить", callback_data=f"request_again={mp}_{id}"),
            tbButton("🚫 Закрыть", callback_data="close"), row_width=1)
    
    def turn_off_streams(self, save: bool = False):
        turn_off_streams = []
        for stream in self.profile.streams:
            if self.profile.streams[stream]["live"]:
                self.profile.streams[stream]["live"] = False
                turn_off_streams.append(stream)
        if save:
            self.save()
        return turn_off_streams
    
    def product_request(self, url: str, last_requested_products: bool = True):
        info_message_id = bot.send_message(self.chat_id, "⏳ Обработка запроса...").message_id
        product = scraper.get_product(url)
        if not product:
            bot.edit_message_text("⚠️  Что то пошло не так! Повторите попытку позже.", 
                                  self.chat_id, info_message_id, 
                                  reply_markup=self.try_request_again_markup(*scraper.url_to_id(url)))
            return

        product_info = f"{self.get_product_info(product)}\n\nДобавить в:"
        reply_markup = self.add_product_to_stream_markup(product)
        img_resource = None
        if self.profile.sending_pictures and product.img:
            try:
                img_resource = requests.get(product.img)
            except Exception as _ex:
                pass
        if img_resource and img_resource.status_code == 200:
            with open(f"{self.dir}/send_product_img.jpg", "wb") as f_:
                f_.write(img_resource.content)
            bot.delete_message(self.chat_id, info_message_id)
            with open(f"{self.dir}/send_product_img.jpg", 'rb') as f_:
                bot.send_photo(self.chat_id, f_, caption=product_info, 
                               reply_markup=reply_markup, 
                               parse_mode="HTML")
        else:
            bot.edit_message_text(product_info, self.chat_id, info_message_id, 
                                  reply_markup=reply_markup,
                                  parse_mode="HTML")
        if last_requested_products:
            if len(self.profile.last_requested_products) > 4:
                del self.profile.last_requested_products[list(self.profile.last_requested_products.keys())[0]]
            self.profile.last_requested_products[f"{product.mp}_{product.id}"] = product.__dict__
            self.save()
        return product
    
    def send_table(self, data, file_name: str, caption: str = ""):
        df = pd.DataFrame(data)
        html_table = build_table(df, "grey_dark")
        with open(f"{self.dir}/{file_name}.html", "w", encoding="utf-8") as f:
            f.write(html_table)
        df.to_excel(f"{self.dir}/{file_name}.xlsx", index=False)
        with open(f"{self.dir}/{file_name}.html", "rb") as f1, open(f"{self.dir}/{file_name}.xlsx", "rb") as f2:
            bot.send_media_group(self.chat_id, [
                telebot.types.InputMediaDocument(f1), 
                telebot.types.InputMediaDocument(f2, caption=f"{caption}shape: {df.shape}", parse_mode="HTML")])
            
    def gpt_request(self, prompt: str):
        info_message_id = bot.send_message(self.chat_id, "⏳ Обработка запроса...").message_id
        try:
            response = client.chat.completions.create(
                model=cfg.GPT_MODEL,
                messages=[{"role": "system", "content": "You are a very useful assistant in Russian"}] + \
                    self.profile.gpt_context + [{"role": "user", "content": prompt}]
            )
            content = response.choices[0].message.content
            self.profile.gpt_context.append({"role": "user", "content": prompt})
            self.profile.gpt_context.append({"role": "assistant", "content": content})
            self.profile.gpt_context = self.profile.gpt_context[-2:]
            self.save()
        except Exception as ex_:
            content = "⚠️  Что то пошло не так! Повторите попытку позже."
        bot.edit_message_text(content, self.chat_id, info_message_id)


        
@bot.message_handler(commands=["start", "client", "a"])
def commands_processing(m):
    u = TUser(m.from_user.id, m.chat.id, m.from_user.username)
    if u.profile.status == "not_authorized":
        return

    if m.text in ("/client", "/start"):
        bot.send_message(u.chat_id, u.get_client_info(), 
                         reply_markup=u.get_client_markup(), 
                         parse_mode="HTML")
    elif m.text == "/a":
        if u.profile.status == "admin":
            bot.send_message(u.chat_id, "-", reply_markup=tbMarkup().add(
                tbButton(f"🔑 Выпустить ключ авторизации", callback_data="add_authorization_key"),
                tbButton("🚫 Закрыть", callback_data="close"), row_width=1))
            

def register_next_step_handler(m, data):
    u = TUser(m.from_user.id, m.chat.id)

    if data.startswith("rename_stream="):
        stream = data.replace("rename_stream=", "")
        if any([s in m.text.lower() for s in "йцукенгшщзхфывапролджячсмитьбюэ"]):
            bot.send_message(u.chat_id, f"⚠️  Название потока должно быть на английском!", 
                reply_markup=Mark.close_mp)
            return
        if len(m.text) <= 12:
            u.profile.streams[m.text] = u.profile.streams.pop(stream)
            bot.send_message(u.chat_id, f"✅  Поток {stream} переименован на {m.text}!", 
                            reply_markup=Mark.close_mp)
            u.save()
        else:
            bot.send_message(u.chat_id, f"⚠️  Название потока должно быть короче!", 
                            reply_markup=Mark.close_mp)
    elif data.startswith("del_stream_item="):
        stream = data.replace("del_stream_item=", "")
        for id_ in m.text.split(","):
            id_ = id_.strip()
            id_mp = {i.split("_")[1]: i.split("_")[0] for i in u.profile.streams[stream]["products"]}
            if id_ in id_mp:
                del u.profile.streams[stream]["products"][f'{id_mp[id_]}_{id_}']
                bot.send_message(u.chat_id, f"✅  Товар {f'{id_mp[id_]} {id_}'} успешно удален из потока {stream}!", 
                                reply_markup=Mark.close_mp)
                u.save()
            else:
                bot.send_message(u.chat_id, f"⚠️  В потоке {stream} нет товара с таким id!", 
                                reply_markup=Mark.close_mp)

        
@bot.callback_query_handler(func=lambda call: True)
def callback(c):
    u = TUser(c.from_user.id, c.message.chat.id, c.from_user.username)
    if u.profile.status == "not_authorized":
        return

    if c.data == "client":
        bot.edit_message_text(u.get_client_info(), u.chat_id, c.message.message_id,
                              reply_markup=u.get_client_markup(), 
                              parse_mode="HTML")
    elif c.data == "settings":
        bot.edit_message_text(u.get_client_info(), u.chat_id, c.message.message_id,
                              reply_markup=u.get_settings_markup(), 
                              parse_mode="HTML")
    elif c.data == "close":
        bot.delete_message(u.chat_id, c.message.message_id)
    elif c.data.startswith("get_stream="):
        stream = c.data.replace("get_stream=", "")
        try:
            bot.edit_message_text(u.get_stream_info(stream), u.chat_id, c.message.message_id,
                                reply_markup=u.get_stream_markup(stream), 
                                parse_mode="HTML")
        except telebot.apihelper.ApiTelegramException:
            pass
    elif c.data == "add_authorization_key":
        with open(cfg.AUTHORIZATION_KEYS_PATH, "r", encoding="utf-8") as f_:
            authorization_keys: list = json.load(f_)
        authorization_key = str(uuid.uuid4())
        authorization_keys.append(authorization_key)
        with open(cfg.AUTHORIZATION_KEYS_PATH, "w", encoding='utf-8') as f:
            json.dump(authorization_keys, f, indent=4, ensure_ascii=False)
        bot.send_message(u.chat_id, f"<code>{authorization_key}</code>", parse_mode="HTML")
    elif c.data == "rename_stream":
        bot.edit_message_text("Переименовать поток:", u.chat_id, c.message.message_id,
                              reply_markup=u.get_rename_stream_markup(), 
                              parse_mode="HTML")
    elif c.data == "sending_pictures":
        u.profile.sending_pictures = not u.profile.sending_pictures
        bot.edit_message_text(u.get_client_info(), u.chat_id, c.message.message_id,
                              reply_markup=u.get_settings_markup(), 
                              parse_mode="HTML")
        u.save()
    elif c.data == "notifications":
        u.profile.notifications = not u.profile.notifications
        bot.edit_message_text(u.get_client_info(), u.chat_id, c.message.message_id,
                              reply_markup=u.get_settings_markup(), 
                              parse_mode="HTML")
        u.save()
    elif c.data == "finish_upd_table":
        u.profile.queue = False
        bot.send_message(u.chat_id, "✅  Процесс обновления таблицы скоро завершится!",
                         reply_markup=Mark.close_mp)
        u.save()
    elif c.data.startswith("del_stream="):
        stream = c.data.replace("del_stream=", "")
        del u.profile.streams[stream]
        u.save()
        bot.edit_message_text(u.get_client_info(), u.chat_id, c.message.message_id,
                              reply_markup=u.get_client_markup(), 
                              parse_mode="HTML")
    elif c.data.startswith("del_stream_item="):
        stream = c.data.replace("del_stream_item=", "")
        message = bot.send_message(u.chat_id, f"Введите id товара который хотите удалить из потока <b>{stream}</b>:", 
                                   parse_mode="HTML")
        bot.register_next_step_handler(message, register_next_step_handler, c.data)
    elif c.data.startswith("rename_stream="):
        stream = c.data.replace("rename_stream=", "")
        message = bot.send_message(u.chat_id, f"Введите имя для потока <b>{stream}</b>:", parse_mode="HTML")
        bot.register_next_step_handler(message, register_next_step_handler, c.data)
    elif c.data.startswith("switch_stream_state="):
        stream = c.data.replace("switch_stream_state=", "")
        u.profile.streams[stream]["live"] = not u.profile.streams[stream]["live"]
        u.save()
        bot.edit_message_text(u.get_stream_info(stream), u.chat_id, c.message.message_id,
                              reply_markup=u.get_stream_markup(stream), 
                              parse_mode="HTML")
    elif c.data.startswith("download_stream_data="):
        stream = c.data.replace("download_stream_data=", "")
        data = []
        history = {}
        for p in u.profile.streams[stream]["products"]:
            product = u.profile.streams[stream]["products"][p]
            mp, id_ = p.split("_")
            deff_price = (round((product["price"] - product["prev_price"]) / product["price"] * 100, 1) 
                          if product["price"] else None)
            data.append({"mp": mp, "name": product.get("name"), 
                         "id": id_, "price": product["price"],
                         "prev %": deff_price,
                         "popularity_index": product.get("popularity_index"),
                         "seller": product.get("seller"), 
                         "url": scraper.id_to_url(mp, id_)})
        u.send_table(data, f"{stream}_data")
    elif c.data.startswith("download_stream_history="):
        stream = c.data.replace("download_stream_history=", "")
        history = {}
        for p in u.profile.streams[stream]["products"]:
            product = u.profile.streams[stream]["products"][p]
            mp, id_ = p.split("_")
            if product.get("history"):
                history[f"{mp} {id_} price"] = []
                history[f"{mp} {id_} dt"] = []
                for price, dt_ in product["history"]:
                    history[f"{mp} {id_} price"].append(price)
                    history[f"{mp} {id_} dt"].append(dt.fromtimestamp(dt_))
        if len(history) > 0:
            max_length = max(tuple(map(len, history.values())))
            for i in history.copy():
                length = len(history[i])
                if length < max_length:
                    history[i] += [""] * (max_length - length)
            u.send_table(history, f"{stream}_history")
        else:
            bot.send_message(u.chat_id, f"Нет истории для загрузки!", reply_markup=Mark.close_mp)
    elif c.data.startswith("add_stream="):
        stream = c.data.replace("add_stream=", "")
        if len(u.profile.streams) >= cfg.MAX_USER_STREAMS:
            bot.send_message(u.chat_id, f"⚠️ Максимальное количество потоков {cfg.MAX_USER_STREAMS}!", 
                             reply_markup=Mark.close_mp)
            return
        u.profile.streams[stream] = cfg.DEFAULT_USER_STREAM
        u.save()
        bot.edit_message_text(u.get_client_info(), u.chat_id, c.message.message_id,
                              reply_markup=u.get_client_markup(), 
                              parse_mode="HTML")
    elif c.data.startswith("product_by_id="):
        mp, id_ = c.data.replace("product_by_id=", "").split("_")
        url = scraper.id_to_url(mp, id_)
        bot.delete_message(u.chat_id, c.message.message_id)
        u.product_request(url)
    elif c.data.startswith("request_again="):
        mp, id_ = c.data.replace("request_again=", "").split("_")
        url = scraper.id_to_url(mp, id_)
        bot.delete_message(u.chat_id, c.message.message_id)
        u.product_request(url)
    elif c.data.startswith("update_table="):
        file = c.data.replace("update_table=", "")
        if u.profile.queue:
            bot.send_message(u.chat_id, f"⚠️ Очередь обработчика занята!", 
                             reply_markup=Mark.close_mp)
            return
        data = read_excel(f"{u.dir}/{file}")
        if len(data) > cfg.MAX_TABLE_REQ:
            bot.send_message(u.chat_id, f"⚠️ Таблица для запроса слишком большая! >{cfg.MAX_TABLE_REQ}", 
                             reply_markup=Mark.close_mp)
            return 
        u.profile.queue = True
        turn_off_streams = u.turn_off_streams()
        u.save()
        try:
            info_message_id = bot.send_message(
                u.chat_id, "⏳ Обработка запроса...\nПрогресс: 1%").message_id
            products = {}
            urls = []
            for _n, mp, id_, price, name, popularity_index, seller in pars_table(data):
                products[f"{mp}_{id_}"] = {
                    "mp": mp, "id": id_, "name": name,
                    "price": price, "prev %": "", 
                    "popularity_index": popularity_index, "seller": seller}
                urls.append(scraper.id_to_url(mp, id_))
            number_processes = min([3, len(urls)])
            for n, return_ in enumerate(
                scraper.yield_get_products_multiprocessing(urls, number_processes)):
                _url, product = return_
                if product:
                    deff_price = 0.0
                    prev_price = products[f"{product.mp}_{product.id}"].get("price")
                    if prev_price:
                        deff_price = round((product.price - prev_price) / product.price * 100, 1)
                    products[f"{product.mp}_{product.id}"] = {
                        "mp": product.mp, "id": product.id, "name": product.name,
                        "price": product.price, "prev %": deff_price, 
                        "popularity_index": product.popularity_index, "seller": product.seller}
                if (n + 1) % number_processes == 0:
                    info_message_id = bot.edit_message_text(
                        f"⏳ Обработка запроса...\nПрогресс: {round((n + 1) / max([len(data), 1]) * 100)}%", 
                        u.chat_id, info_message_id, reply_markup=Mark.finish_upd_table).message_id
                    u = TUser(c.from_user.id, c.message.chat.id, c.from_user.username)
                if not u.profile.queue:
                    break
            data = [i for i in products.values()]
            u.send_table(data, "new_table")
            bot.delete_message(u.chat_id, info_message_id)
        except Exception as _ex:
            bot.edit_message_text(f"⚠️  Что то пошло не так! Повторите попытку позже.",  
                                  u.chat_id, info_message_id, 
                                  reply_markup=Mark.close_mp)
        finally:
            if u.profile.queue:
                u.profile.queue = False
            for stream in turn_off_streams:
                u.profile.streams[stream]["live"] = True
            u.save()
    elif c.data.startswith("add_table_to_stream="):
        stream, file = c.data.replace("add_table_to_stream=", "").split("/,")
        data = read_excel(f"{u.dir}/{file}")
        if len(data) + len(u.profile.streams[stream]["products"]) > cfg.MAX_STREAM_PRODUCTS:
            bot.send_message(u.chat_id, f"⚠️ Количество товаров в потоке не может быть больше {cfg.MAX_STREAM_PRODUCTS}!", 
                             reply_markup=Mark.close_mp)
            return
        save = False
        missed_items_n = 0
        add_items_n = 0
        for _n, mp, id_, price, name, popularity_index, seller in pars_table(data):
            if f"{mp}_{id_}" not in u.profile.streams[stream]["products"]:
                u.profile.streams[stream]["products"][f"{mp}_{id_}"] = {
                    "price": price, "prev_price": price, "name": name,
                    "popularity_index": popularity_index, "seller": seller}
                save = True
                add_items_n += 1
            else:
                missed_items_n += 1
        if save:
            u.save()
            bot.send_message(u.chat_id, 
                             f"<b>{stream}</b>\n\nДобавлено: {add_items_n}\nПропущено: {missed_items_n}", 
                             reply_markup=u.get_stream_add_markup(stream), 
                             parse_mode="HTML")
        else:
            bot.send_message(u.chat_id, f"⚠️ Таблица уже добавлена в поток {stream}!", 
                             reply_markup=Mark.close_mp)
    elif c.data.startswith("apts="):
        stream, id_, mp, price = c.data.replace("apts=", "").split("/,")
        if len(u.profile.streams[stream]["products"]) > cfg.MAX_STREAM_PRODUCTS:
            bot.send_message(u.chat_id, f"⚠️ Достигнуто максимально число товаров в потоке!", 
                             reply_markup=Mark.close_mp)
            return
        product = None
        if u.profile.last_requested_products.get(f"{mp}_{id_}"):
            product = scraper.Product(u.profile.last_requested_products[f"{mp}_{id_}"])
        if f"{mp}_{id_}" not in u.profile.streams[stream]["products"]:
            u.profile.streams[stream]["products"][f"{mp}_{id_}"] = {
                "price": int(price), "prev_price": int(price)} if not product else {
                    "price": product.price, "prev_price": product.price, "name": product.name, 
                    "popularity_index": product.popularity_index, "seller": product.seller, }
            u.save()
            bot.send_message(u.chat_id, f"✅ {mp} <code>{id_}</code> добавлен в поток {stream}!", 
                             reply_markup=u.get_stream_add_markup(stream),
                             parse_mode="HTML")
        else:
            bot.send_message(u.chat_id, f"⚠️ {mp} <code>{id_}</code> уже добавлен в поток {stream}!", 
                             reply_markup=Mark.close_mp,
                             parse_mode="HTML")


@bot.message_handler(content_types=["text"])
def text_processing(m):
    u = TUser(m.from_user.id, m.chat.id)
    if u.profile.status == "not_authorized":
        with open(cfg.AUTHORIZATION_KEYS_PATH, "r", encoding="utf-8") as f_:
            authorization_keys: list = json.load(f_)
        if m.text in authorization_keys:
            u.profile.status = "authorized"
            u.save()
            authorization_keys.remove(m.text)
            with open(cfg.AUTHORIZATION_KEYS_PATH, "w", encoding='utf-8') as f:
                json.dump(authorization_keys, f, indent=4, ensure_ascii=False)
            bot.send_message(u.chat_id, "✅ Пользователь успешно авторизован!")
        else:
            bot.send_message(u.chat_id, "⚠️ Неверный ключ авторизации!")
        return
    
    for req in m.text.split(","):
        req = req.strip()
        try:
            int("".join(req.split("-")))
            bot.send_message(u.chat_id, f"<code>{req}</code>:", 
                             reply_markup=u.get_product_by_id_markup(req), 
                             parse_mode="HTML")
            continue
        except ValueError:
            pass
        if validators.url(req):
            u.product_request(req)
        else:
            u.gpt_request(m.text)
            break
        
    
        
@bot.message_handler(content_types=["document"])
def document_processing(m):
    u = TUser(m.from_user.id, m.chat.id)
    if u.profile.status == "not_authorized":
        return

    file_name = m.document.file_name
    file_type = file_name.split(".")[-1]
    if file_type == "xlsx":
        with open(f"{u.dir}/document.xlsx", "wb") as f_:
            f_.write(bot.download_file(bot.get_file(m.document.file_id).file_path))
        data = read_excel(f"{u.dir}//document.xlsx")
        keys = list(data[0].keys())
        if not all(["id" in keys, "mp" in keys]) and "url" not in keys:
            bot.send_message(u.chat_id, f"⚠️ В таблице отсутствуют необходимые колонки\n"
                                        f"'mp', 'id' or 'url' not in {keys}")
            return
        send_message = f"<b>{file_name}\n\nТовары:\n</b>"
        for n, mp, id_, price, *_any in pars_table(data):
            send_message += f"{n + 1}. {mp} <code>{id_}</code>:  " + \
                (f"{price}р\n" if price else  "None\n")
            if n == 19:
                send_message += f"+ еще {len(data) - 20}...\n"
                break
        shape = (len(data), len(keys))
        send_message += f"\ncolumns: {keys}\nshape: {shape}\nДобавить в:"
        bot.send_message(u.chat_id, send_message, 
                            reply_markup=u.add_table_to_stream_markup("document.xlsx"), 
                            parse_mode="HTML")
        

