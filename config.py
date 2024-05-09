import os

#test 5784668759:AAEebBmBdCUXUX_MyjU5mMpsJp8LQx7tchQ
#test2 6734347719:AAEEP-kUqd_r_JlNoy0nyz0bPaTvKtoBDPg
#main 6827193677:AAFQ1I8MYPET9hkfvPCxP--Ww3aGLJ1mgzQ

#----------------------------------------------------------------
TELEBOT_TOKEN = "6734347719:AAEEP-kUqd_r_JlNoy0nyz0bPaTvKtoBDPg"
#----------------------------------------------------------------

DIR = os.path.dirname(os.path.abspath(__file__))
DRIVER_DATA_DIR = f"{DIR}/driver_data"
USERS_DATA_DIR = "users_data"
DEFAULT_USER_STREAM = {
    "live": True,
    "products": {}, 
    "last_update": None,
    "total_updates": 0
}
DEFAULT_USER = {
    "streams": {"Thread1": DEFAULT_USER_STREAM},
    "last_requested_products": {},
    "sending_pictures": True,
    "notifications": True,
    "queue": False,
    "status": "authorized",
    "gpt_context": []
}
MAX_USER_STREAMS = 32
SCRAPER_LOOP_TIMEOUT = 3500
MAX_TABLE_REQ = 300
MAX_STREAM_PRODUCTS = 10000
AUTHORIZATION_KEYS_PATH = "bot/authorization_keys.json"
GPT_API_KEY = "sk-ece8f0db3ddd472ab05e045fdc3c92f2"
GPT_BASE_URL = "https://api.deepseek.com/v1"
GPT_MODEL = "deepseek-chat"
DOC_URL = r"https://sites.google.com/view/marketplacelivescraper/documentation"