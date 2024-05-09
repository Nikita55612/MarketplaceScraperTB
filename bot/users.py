import config as cfg
from pydantic import BaseModel
import time
import json
import os


def save_json(data: dict, filename: str):
    with open(filename, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


os.mkdir(cfg.USERS_DATA_DIR) if not os.path.exists(cfg.USERS_DATA_DIR) else ...
CACHE = {}


def get_users_list():
    return os.listdir(path=cfg.USERS_DATA_DIR)


class Profile(BaseModel):
    streams: dict
    registration_dt: float
    last_requested_products: dict
    sending_pictures: bool
    notifications: bool
    queue: bool
    status: str
    gpt_context: list


class User:
    def __init__(self, id: int | str) -> None:
        self.id: str = str(id)
        self.dir = f"{cfg.USERS_DATA_DIR}/{self.id}"
        self.profile_path_ = f"{self.dir}/profile.json"
        self.profile: Profile = self.__read_profile()

    def save(self) -> None:
        data = self.profile.dict()
        save_json(data, self.profile_path_)
        CACHE[self.id] = data

    def __init(self) -> dict:
        data, dt_now = cfg.DEFAULT_USER, time.time()
        data["registration_dt"] = dt_now
        return data

    def __create(self) -> dict:
        os.makedirs(f"{cfg.USERS_DATA_DIR}/{self.id}", exist_ok=True)
        data = self.__init()
        save_json(data, self.profile_path_)
        return data
        
    def __read_profile(self) -> Profile:
        if data := CACHE.get(self.id):
            return Profile(**data)
        try:
            with open(self.profile_path_, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = self.__create()
        CACHE[self.id] = data
        return Profile(**data)
    
    def upd_profile(self):
        try:
            with open(self.profile_path_, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.profile = Profile(**data)
            CACHE[self.id] = data
        except Exception as _ex:
            pass
        

def __iter_users():
    for id_ in get_users_list():
        _c = False
        try:
            with open(f"{cfg.USERS_DATA_DIR}/{id_}/profile.json", "r", encoding="utf-8") as f:
                profile: dict = json.load(f)
        except Exception as _ex:
            continue
        for i in cfg.DEFAULT_USER:
            if i not in profile:
                profile[i] = cfg.DEFAULT_USER[i]
                _c = True
        if _c:
            save_json(profile, f"{cfg.USERS_DATA_DIR}/{id_}/profile.json")
__iter_users()