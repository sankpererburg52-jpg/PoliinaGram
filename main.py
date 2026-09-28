# PolinaGram — мобильный клиент (Kivy)
# Перед сборкой APK укажите адрес вашего сервера:
SERVER = "http://10.0.2.2:8000"   # 10.0.2.2 = localhost ПК из Android-эмулятора
                                   # для реального телефона — IP ПК в Wi-Fi или https://ваш-домен
WS_BASE = SERVER.replace("http", "ws", 1)

import json
import threading

import requests
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.textinput import TextInput


def api(method, path, token=None, **kwargs):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = requests.request(method, SERVER + path, headers=headers, timeout=10, **kwargs)
    r.raise_for_status()
    return r.json() if r.content else {}


class LoginScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        box = BoxLayout(orientation="vertical", padding=40, spacing=12)
        box.add_widget(Label(text="PolinaGram", font_size=32))
        self.phone = TextInput(hint_text="Телефон (+79991234567)", multiline=False)
        self.code = TextInput(hint_text="Код из SMS", multiline=False, password=True)
        self.name = TextInput(hint_text="Ваше имя", multiline=False)
        self.info = Label(text="", color=(0.6, 0.6, 0.6, 1), size_hint_y=None, height=30)
        btn = Button(text="Получить код", size_hint_y=None, height=48)
        btn.bind(on_release=self.step)
        box.add_widget(self.phone)
        box.add_widget(self.code)
        box.add_widget(self.name)
        box.add_widget(self.info)
        box.add_widget(btn)
        self.add_widget(box)
        self._stage = 0

    def step(self, _):
        try:
            if self._stage == 0:
                res = api("POST", "/auth/request-code", json={"phone": self.phone.text})
                self._stage = 1
                self.info.text = f"Код отправлен (dev: {res.get('dev_code') or 'см. SMS'})"
            else:
                res = api("POST", "/auth/verify", json={
                    "phone": self.phone.text, "code": self.code.text,
                    "name": self.name.text or None})
                self.app.login(res["token"], res["name"])
        except Exception as e:
            self.info.text = f"Ошибка: {e}"


class ChatsScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        box = BoxLayout(orientation="vertical")
        top = BoxLayout(size_hint_y=None, height=50, padding=8, spacing=8)
        top.add_widget(Label(text="PolinaGram", bold=True))
        search = TextInput(hint_text="Найти пользователя", multiline=False,
                           size_hint_x=None, width=220)
        search.bind(on_text_validate=self.do_search)
        top.add_widget(search)
        self.results = BoxLayout(orientation="vertical", size_hint_y=None, height=0)
        self.list = BoxLayout(orientation="vertical", spacing=4, size_hint_y=None)
        self.list.bind(minimum_height=self.list.setter("height"))
        sv = ScrollView()
        sv.add_widget(self.list)
        box.add_widget(top)
        box.add_widget(self.results)
        box.add_widget(sv)
        self.add_widget(box)

    def on_pre_enter(self, _):
        self.load()

    def do_search(self, inp):
        try:
            users = api("GET", f"/users?q={inp.text}", token=self.app.token)
        except Exception:
            return
        self.results.clear_widgets()
        self.results.height = 0
        for u in users[:5]:
            b = Button(text=f"Написать: {u['name']}", size_hint_y=None, height=44)
            b.bind(on_release=lambda _b, uid=u["id"]: self.open_with(uid))
            self.results.add_widget(b)
            self.results.height += 44

    def open_with(self, peer_id):
        chat = api("POST", f"/chats?peer_id={peer_id}", token=self.app.token)
        self.app.show_chat(chat["id"], chat["title"])

    def load(self):
        self.list.clear_widgets()
        try:
            chats = api("GET", "/chats", token=self.app.token)
        except Exception as e:
            self.list.add_widget(Label(text=f"Нет связи с сервером: {e}"))
            return
        for c in chats:
            unread = f"  •{c['unread']} новых" if c["unread"] else ""
            b = Button(text=f"{c['title']}{unread}\n{c['last_message'] or ''}",
                       size_hint_y=None, height=64, halign="left")
            b.bind(on_release=lambda _b, cid=c["id"], t=c["title"]:
                   self.app.show_chat(cid, t))
            self.list.add_widget(b)


class ChatScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.chat_id = None
        self._stop = threading.Event()
        box = BoxLayout(orientation="vertical")
        self.title = Label(text="", size_hint_y=None, height=40, bold=True)
        self.msgs = BoxLayout(orientation="vertical", spacing=4, size_hint_y=None)
        self.msgs.bind(minimum_height=self.msgs.setter("height"))
        sv = ScrollView()
        sv.add_widget(self.msgs)
        bottom = BoxLayout(size_hint_y=None, height=52, padding=6, spacing=6)
        self.inp = TextInput(hint_text="Сообщение…", multiline=False)
        self.inp.bind(on_text_validate=self.send)
        send = Button(text="➤", size_hint_x=None, width=56)
        send.bind(on_release=self.send)
        back = Button(text="‹", size_hint_x=None, width=48)
        back.bind(on_release=lambda _b: setattr(self.app.sm, "current", "chats"))
        bottom.add_widget(back)
        bottom.add_widget(self.inp)
        bottom.add_widget(send)
        box.add_widget(self.title)
        box.add_widget(sv)
        box.add_widget(bottom)
        self.add_widget(box)

    def open(self, chat_id, title):
        self.chat_id = chat_id
        self.title.text = title
        self._stop.clear()
        self.load_history()
        threading.Thread(target=self.ws_loop, daemon=True).start()

    def load_history(self):
        self.msgs.clear_widgets()
        try:
            msgs = api("GET", f"/chats/{self.chat_id}/messages", token=self.app.token)
        except Exception:
            return
        for m in msgs:
            self.add_bubble(m)
        if msgs:
            try:
                api("POST", f"/chats/{self.chat_id}/read?up_to={msgs[-1]['id']}",
                    token=self.app.token)
            except Exception:
                pass

    def add_bubble(self, m):
        mine = m["user_id"] == self.app.user_id
        text = f"{m['author']}: {m['text']}" if not mine else m["text"]
        lb = Label(text=text, size_hint_y=None, halign="right" if mine else "left")
        lb.bind(texture_size=lambda w, ts: setattr(w, "height", ts[1] + 12))
        self.msgs.add_widget(lb)

    def send(self, _):
        text = self.inp.text.strip()
        if not text or self.chat_id is None:
            return
        self.inp.text = ""
        threading.Thread(
            target=lambda: api("POST", f"/chats/{self.chat_id}/messages",
                               token=self.app.token, json={"text": text}),
            daemon=True).start()

    def ws_loop(self):
        # синхронный клиент websockets (>=12) в отдельном потоке
        from websockets.sync.client import connect
        url = f"{WS_BASE}/ws/{self.chat_id}?token={self.app.token}"
        try:
            with connect(url) as ws:
                for raw in ws:
                    if self._stop.is_set():
                        break
                    event = json.loads(raw)
                    if event.get("type") == "message":
                        Clock.schedule_once(lambda _dt: self.add_bubble(event))
        except Exception:
            pass  # реконнект при следующем входе в чат

    def on_leave(self):
        self._stop.set()


class PolinaGramApp(App):
    title = "PolinaGram"

    def build(self):
        self.token = None
        self.user_id = None
        self.sm = ScreenManager()
        self.sm.add_widget(LoginScreen(self, name="login"))
        self.sm.add_widget(ChatsScreen(self, name="chats"))
        self.sm.add_widget(ChatScreen(self, name="chat"))
        return self.sm

    def login(self, token, _name):
        self.token = token
        self.user_id = int(__import__("jwt").decode(
            token, options={"verify_signature": False})["sub"])
        self.sm.current = "chats"

    def show_chat(self, chat_id, title):
        chat = self.sm.get_screen("chat")
        chat.open(chat_id, title)
        self.sm.current = "chat"


if __name__ == "__main__":
    PolinaGramApp().run()
