from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from seleniumbase import Driver
from bs4 import BeautifulSoup
import  multiprocessing as mp
import config as cfg
import validators
import requests
import json
import time
import os


def try_type(obj, type):
    try:
        return type(obj)
    except Exception as _ex:
        return
    

class Product:
    def __init__(self, data: dict) -> None:
        self.mp: str = data.get("mp", "None")
        self.id: str | int = data.get("id", "None")
        self.url: str = data.get("url", "None")
        self.img: str = data.get("img", "https://png.pngtree.com/png-vector/20190820/ourlarge"
                                 "/pngtree-no-image-vector-illustration-isolated-png-image_1694547.jpg")
        self.name: str = data.get("name", "None")
        self.price: int = data.get("price", "None")
        self.seller: str = data.get("seller", "None")
        self.seller_url: str = data.get("seller_url", "None")
        self.reviews: str | int = data.get("reviews", "None")
        self.rating: str | float = data.get("rating", "None")
        self.popularity_index: float = data.get("popularity_index", "None")
        self.category: str = data.get("category", "None")


def url_to_id(url: str) -> tuple[str]:
    if "market.yandex.ru" in url:
        p_id, sku_id = url.split("/product")[-1].split("/")[-1].split("?sku=")
        sku_id = sku_id.split("&")[0]
        return f"{p_id}-{sku_id}", "ym"
    url = url.split("?")[0]
    if "www.wildberries.ru" in url:
        return int(url.split("/catalog/")[-1].split("/")[0].replace("/", "")), "wb"
    elif "www.ozon.ru" in url:
        return int(url.split("/product/")[-1].split("-")[-1].replace("/", "")), "ozon"
    elif "www.vseinstrumenti.ru" in url:
        return "-".join(url.split("/product/")[-1].split("-")[-2:]).replace("/", ""), "vi"



def get_product(url: str) -> Product | None:
    print(f"{url} processing...")
    if not validators.url(url):
        return
    try:
        id_, mp = url_to_id(url)
        if mp == "ozon":
            return get_ozon_product(id_)
        elif mp == "wb":
            return get_wb_product(id_)
        elif mp == "vi":
            return get_vi_product(id_)
        elif mp == "ym":
            return get_ym_product(id_)
        return
    except Exception as ex:
        return
    

def chunks(lst: list, chunk_size: int):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]


def __get_product_processing(url: str, container: dict) -> Product | None:
    container[url] = get_product(url)


def get_products_multiprocessing(urls: list[str], number_processes: int) -> list:
    pool = []
    with mp.Manager() as manager:
        container = manager.dict()
        for n in range(len(urls)):
            p = mp.Process(target=__get_product_processing, args=(urls[n], container))
            pool.append(p)
            p.start()
            if len(pool) == number_processes:
                for p_ in pool:
                    p_.join()
                pool.clear()
            time.sleep(1.5)
        for p_ in pool:
            p_.join()
        container = container.copy()
    return container


def yield_get_products_multiprocessing(urls: list[str], number_processes: int):
    for chunk in chunks(urls, number_processes):
        number_processes = len(chunk) if number_processes > len(chunk) else number_processes
        container = get_products_multiprocessing(chunk, number_processes)
        for p in container:
            yield p, container[p]


def id_to_url(mp: str, id: str | int) -> str:
    if mp == "ozon":
        return f"https://www.ozon.ru/product/{id}/"
    elif mp == "wb":
        return f"https://www.wildberries.ru/catalog/{id}/detail.aspx"
    elif mp == "vi":
        return f"https://www.vseinstrumenti.ru/product/{id}/"
    elif mp == "ym":
        p_id, sku_id = str(id).split("-")
        return f"https://market.yandex.ru/product/{p_id}?sku={sku_id}"
    return f"https://www.ozon.ru/product/{id}/"


def driver_get_soup(url: str, wait_xpath: str, captcha_path: str = None, user_data_dir=None) -> BeautifulSoup:
    driver = Driver(uc=True, headless=True, user_data_dir=user_data_dir)
    driver.maximize_window()
    try:
        driver.get(url)
        if driver.current_url == "chrome://new-tab-page/":
            driver.quit()
            return driver_get_soup(url, wait_xpath)
        if captcha_path:
            try:
                captcha = WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located(captcha_path)).click()
                ActionChains(driver).click(captcha).perform() if captcha else ...
            except Exception as _ex:
                pass
        WebDriverWait(driver, 16).until(
            EC.presence_of_element_located((By.XPATH, wait_xpath)))
        soup = BeautifulSoup(driver.page_source, "lxml")
    except Exception as _ex:
        soup = None
    finally:
        driver.quit()
    return soup


def get_ym_product(id: str | int) -> Product | None:
    if "-" not in id:
        return None
    p_id, sku_id = str(id).split("-")
    url = f"https://market.yandex.ru/product/{p_id}?sku={sku_id}"
    soup = driver_get_soup(url, '//*[@id="cardContent"]/div[1]/div/div[1]/div[3]/div[2]/div/div[3]/div',
                           (By.CLASS_NAME, "CheckboxCaptcha-Checkbox"), cfg.DRIVER_DATA_DIR)
    product = {"mp": "ym", "id": id, "url": url}
    if not soup:
        return
    price_div = soup.find("div", {"data-zone-name": "price"})
    img_div = soup.find("div", {"data-auto": "image-gallery-nav-item"})
    name_div = soup.find("h1", {"data-auto": "productCardTitle"})
    category_items = soup.find_all("span", {"itemprop": "name"})
    rating_div = soup.find("div", {"data-zone-name": "ProductReviewsBadge"})
    seller_div = soup.find("div", {"data-zone-name": "shop-name"})
    if price_div:
        snippet_price_old = price_div.find("span", {"data-auto": "snippet-price-old"})
        if snippet_price_old:
            price = price_div.text.split("Вместо:")[-1].replace("\u2009", "").split("₽")[0].strip()
        else:
            price_value = price_div.find("span", {"data-auto": "price-value"})
            price = price_value.text.replace("\u2009", "").split("₽")[0].strip()
        product["price"] = try_type(price, int)
    if name_div:
        product["name"] = name_div.text.strip()
    if img_div:
        img = img_div.find("img")
        if img:
            product["img"] = img.get("src")
    if category_items:
        pass
    if rating_div:
        rating = rating_div.find("span").text
        reviews = rating_div.find_all("span")[-1].text
        product["rating"] = try_type(rating, float)
        product["reviews"] = try_type(reviews.replace("(", "").replace(")", "").replace("K", "111"), int)
    if all([product.get("rating"), product.get("reviews")]):
        product["popularity_index"] = round(product["rating"] * product["reviews"] / 100, 2)
    if category_items:
        product["category"] = "/".join([c.text for c in category_items])
    if seller_div:
        product["seller"] = seller_div.text.strip()
        seller_href = seller_div.find("a")
        product["seller_url"] = "https://market.yandex.ru" + (seller_href.get("href") if seller_href else "")
    return Product(product) if product.get("price") is not None else None

    
def get_ozon_product(id: str | int) -> Product | None:
    url = f"https://www.ozon.ru/api/entrypoint-api.bx/page/json/v2?url=/product/{id}/"
    soup = driver_get_soup(url, "/html/body/pre")
    if not soup:
        return
    data = json.loads(soup.text)
    product = {"mp": "ozon", "id": int(id), "url": id_to_url("ozon", id)}
    ws = data.get("widgetStates")
    if not ws:
        return
    for key in ws:
        if key.startswith("webPrice-"):
            web_price = json.loads(ws[key])
            if web_price.get("price"):
                product["price"] = try_type(web_price["price"].replace("\u2009", "")[:-1], int)
        elif key.startswith("webStickyProducts-"):
            sticky_products = json.loads(ws[key])
            product["name"] = sticky_products.get("name")
            seller = sticky_products.get("seller")
            if seller:
                product["seller"] = seller.get("name")
                product["seller_url"] = "https://www.ozon.ru" + seller.get("link")
        elif key.startswith("webGallery-"):
            product["img"] = json.loads(ws[key]).get("coverImage")
        elif key.startswith("webReviewProductScore"):
            product_score = json.loads(ws[key])
            product["reviews"] = try_type(product_score.get("reviewsCount"), int)
            product["rating"] = try_type(product_score.get("totalScore"), float)
            if all([product["rating"], product["reviews"]]):
                product["popularity_index"] = round(product["rating"] * product["reviews"] / 100, 2)
        elif "breadCrumbs-" in key:
            breadcrumbs = json.loads(ws[key]).get("breadcrumbs")
            if breadcrumbs:
                product["category"] = "/".join([c.get("text") for c in breadcrumbs])
    return Product(product) if product.get("price") is not None else None


def get_wb_product(id: str | int) -> Product | None:
    url = f"https://www.wildberries.ru/catalog/{id}/detail.aspx"
    soup = driver_get_soup(url, "/html/body/div[1]/main/div[2]/div/div[3]/div/div[3]/div[11]")
    product = {"mp": "wb", "id": int(id), "url": url}
    if soup:
        price_div = soup.find("ins", {"class": "price-block__final-price wallet"})
        img_div = soup.find("div", {"class": "zoom-image-container"})
        name_div = soup.find("h1", {"class": "product-page__title"})
        category_items = soup.find_all("li", {"class": "breadcrumbs__item"})
        rating_reviews_div = soup.find("div", {"class": "product-page__common-info"})
        seller_div = soup.find("span", {"class": "seller-info__name"})

        if price_div:
            price = price_div.text.replace("\xa0", "").replace("₽", "")
            product["price"] = try_type(price, int)
        if img_div:
            img = img_div.find("img")
            if img:
                product["img"] = img.get("src")
        if name_div:
            product["name"] = name_div.text.strip()
        if category_items:
            try:
                product["category"] = "/".join(
                    [i.find("span").text for i in category_items])
            except Exception as _ex:
                pass
        if rating_reviews_div:
            rating_div = rating_reviews_div.find("span")
            reviews_div = rating_reviews_div.find(
                "span", {"data-wba-location": "reviews"})
            if rating_div:
                product["rating"] = try_type(rating_div.text, float)
            if reviews_div:
                reviews = reviews_div.text.replace(" ", "").replace("оценок", "")
                product["reviews"] = try_type(reviews, int)
        if all([product.get("rating"), product.get("reviews")]):
            product["popularity_index"] = round(product["rating"] * product["reviews"] / 100, 2)
        if seller_div:
            product["seller"] = seller_div.text.strip()
            product["seller_url"] = f"https://www.wildberries.ru{seller_div.get('href')}"
    try:
        response = requests.get(f"https://card.wb.ru/cards/detail?nm={id}", timeout=7, 
                        headers={'Accept': "*/*", 'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        if response.status_code == 200:
            data = response.json().get("data")
            data = data.get("products") if data else None
            data = data[0] if data else None
    except Exception as _ex:
        data = None
    if data:
        if data.get("salePriceU") and not product.get("price"):
            product["price"] = try_type(data.get("salePriceU") / 100, int)
        product["name"] = data.get("name") if "name" not in product else product.get("name")
        product["reviews"] = data.get("feedbacks")
        product["rating"] = data.get("reviewRating")
        if all([product["rating"], product["reviews"]]):
            product["popularity_index"] = round(product["rating"] * product["reviews"] / 100, 2)
        product["seller"] = data.get("supplier")
        product["seller_url"] = f"https://www.wildberries.ru/seller/{data.get('supplierId')}"
    return Product(product) if product.get("price") is not None else None


def get_vi_product(id: str | int) -> Product | None:
    url = f"https://www.vseinstrumenti.ru/product/{id}/"
    soup = driver_get_soup(url, "/html/body/div[1]/div/div/div[2]/div/div[1]/section[2]/div[1]/div/div[2]/div/div[2]")
    product = {"mp": "vi", "id": id, "url": url}
    if not soup:
        return None
    price_div = soup.find("p", {"data-behavior": "price-now"})
    img_div = soup.find("div", {"data-qa": "open-product-image"})
    name_div = soup.find("h1", {"data-qa": "get-product-title"})
    category_items = soup.find_all("div", {"itemprop": "itemListElement"})
    rating_div = soup.find("input", {"name": "rating"}).get("value")
    reviews_div = soup.find("a", {"data-qa": "responses"})

    if price_div:
        product["price"] = try_type(price_div.text.strip().replace("\xa0", "")[:-2], int)
    if name_div:
        product["name"] = name_div.text.strip()
    if img_div:
        img = img_div.find("img")
        if img:
            product["img"] = img.get("src")
    if category_items:
        product["category"] = "/".join([i.find_next("span").text for i in category_items])
    if rating_div:
        product["rating"] = try_type(rating_div.strip(), float)
    if reviews_div:
        reviews_div = reviews_div.find_next("span")
        if reviews_div:
            reviews = reviews_div.text.strip().split(" ")[0]
            product["reviews"] = try_type(reviews, int)
    if all([product.get("rating"), product.get("reviews")]):
        product["popularity_index"] = round(product["rating"] * product["reviews"] / 100, 2)
    if category_items:
        seller_item = category_items[-1]
        seller_a = seller_item.find("a", {"itemprop": "item"})
        if seller_a:
            product["seller"] = seller_a.find("span").text
            product["seller_url"] = f"https://www.vseinstrumenti.ru{seller_a.get('href')}"
    return Product(product) if product.get("price") is not None else None
