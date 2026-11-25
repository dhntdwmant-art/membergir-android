import os
import sqlite3
import time
from contextlib import closing

from kivy.app import App
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    def fa(value):
        return get_display(arabic_reshaper.reshape(str(value)))
except Exception:
    def fa(value):
        return str(value)

# -------------------- تنظیمات --------------------
APP_TITLE = "عضو بگیر"
ADMIN_PHONE = "09339934387"  # فقط برای نسخه آزمایشی؛ در نسخه آنلاین باید سمت سرور بررسی شود
DEMO_OTP = "123456"          # کد آزمایشی؛ پیامک واقعی ارسال نمی‌شود
DB_PATH = os.path.join(os.path.dirname(__file__), "members.db")

BG = get_color_from_hex("#F5FBF7")
GREEN = get_color_from_hex("#B8E6C8")
GREEN_DARK = get_color_from_hex("#24543A")
GREEN_PALE = get_color_from_hex("#E5F5EA")
WHITE = get_color_from_hex("#FFFFFF")
TEXT = get_color_from_hex("#183526")
MUTED = get_color_from_hex("#668071")
BORDER = get_color_from_hex("#D6E8DC")


def db():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with closing(db()) as conn, conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            phone TEXT PRIMARY KEY,
            coins INTEGER NOT NULL DEFAULT 50,
            is_blocked INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            channel_link TEXT NOT NULL,
            reward INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'active',
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL,
            task_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at INTEGER NOT NULL,
            UNIQUE(phone, task_id)
        );
        CREATE TABLE IF NOT EXISTS coin_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL,
            amount INTEGER NOT NULL,
            note TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );
        """)


def ensure_user(phone):
    with closing(db()) as conn, conn:
        conn.execute(
            "INSERT OR IGNORE INTO users(phone, coins, created_at) VALUES(?, 50, ?)",
            (phone, int(time.time()))
        )


def get_user(phone):
    with closing(db()) as conn:
        return conn.execute("SELECT * FROM users WHERE phone=?", (phone,)).fetchone()


def change_coins(phone, amount, note):
    with closing(db()) as conn, conn:
        row = conn.execute("SELECT coins FROM users WHERE phone=?", (phone,)).fetchone()
        if not row:
            return False, "کاربر پیدا نشد"
        new_total = row["coins"] + int(amount)
        if new_total < 0:
            return False, "موجودی کافی نیست"
        conn.execute("UPDATE users SET coins=? WHERE phone=?", (new_total, phone))
        conn.execute(
            "INSERT INTO coin_log(phone, amount, note, created_at) VALUES(?,?,?,?)",
            (phone, int(amount), note, int(time.time()))
        )
    return True, "موجودی به‌روزرسانی شد"


def add_task(title, link, reward):
    with closing(db()) as conn, conn:
        conn.execute(
            "INSERT INTO tasks(title, channel_link, reward, created_at) VALUES(?,?,?,?)",
            (title, link, int(reward), int(time.time()))
        )


def list_tasks(active_only=False):
    with closing(db()) as conn:
        sql = "SELECT * FROM tasks"
        if active_only:
            sql += " WHERE status='active'"
        sql += " ORDER BY id DESC"
        return conn.execute(sql).fetchall()


def card_label(text, size=16, color=TEXT, height=None):
    return Label(
        text=fa(text), color=color, font_size=sp(size),
        size_hint_y=None, height=dp(height or 42),
        halign="right", valign="middle"
    )


def sp(value):
    return value


def make_button(text, callback=None, primary=False, height=dp(48)):
    btn = Button(
        text=fa(text), size_hint_y=None, height=height,
        background_normal="", background_down="",
        background_color=GREEN if primary else WHITE,
        color=GREEN_DARK if primary else TEXT,
        font_size=16
    )
    if callback:
        btn.bind(on_release=callback)
    return btn


def make_input(hint, multiline=False, password=False):
    return TextInput(
        hint_text=fa(hint), multiline=multiline, password=password,
        size_hint_y=None, height=dp(48), padding=[dp(12), dp(12)],
        background_normal="", background_active="",
        background_color=WHITE, foreground_color=TEXT,
        hint_text_color=MUTED, cursor_color=GREEN_DARK,
        font_size=16
    )


class BaseScreen(Screen):
    def page(self, title):
        self.clear_widgets()
        outer = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        outer.add_widget(Label(
            text=fa(title), size_hint_y=None, height=dp(48),
            color=GREEN_DARK, font_size=22, bold=True
        ))
        self.add_widget(outer)
        self.body = outer
        return outer

    def message(self, title, message):
        Popup(
            title=fa(title),
            content=Label(text=fa(message), color=TEXT),
            size_hint=(0.85, 0.35)
        ).open()

    def add_nav(self, target="home"):
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        for label, screen in [
            ("خانه", "home"), ("سفارش‌ها", "tasks"),
            ("کیف پول", "wallet"), ("مدیریت", "admin")
        ]:
            b = make_button(label, lambda _b, s=screen: self.manager.current.__class__ if False else setattr(self.manager, "current", s))
            row.add_widget(b)
        self.body.add_widget(row)


class LoginScreen(BaseScreen):
    def on_pre_enter(self):
        box = self.page("ورود به عضو بگیر")
        box.add_widget(card_label("شماره موبایل خود را وارد کنید", 16))
        self.phone = make_input("مثلاً 09xxxxxxxxx")
        box.add_widget(self.phone)
        box.add_widget(make_button("ادامه", self.send_demo_code, True))
        box.add_widget(Label(
            text=fa("نسخه آزمایشی: پیامک واقعی ارسال نمی‌شود؛ کد ورود 123456 است."),
            color=MUTED, font_size=12, size_hint_y=None, height=dp(54)
        ))
        box.add_widget(Widget())

    def send_demo_code(self, *_):
        phone = self.phone.text.strip()
        if len(phone) != 11 or not phone.startswith("09") or not phone.isdigit():
            self.message("خطا", "شماره موبایل باید ۱۱ رقم و با 09 شروع شود")
            return
        self.manager.get_screen("otp").phone_value = phone
        self.manager.current = "otp"


class OtpScreen(BaseScreen):
    phone_value = ""

    def on_pre_enter(self):
        box = self.page("تأیید شماره")
        box.add_widget(card_label("کد آزمایشی 123456 را وارد کنید", 16))
        self.code = make_input("کد شش رقمی")
        box.add_widget(self.code)
        box.add_widget(make_button("ورود", self.verify, True))
        box.add_widget(make_button("بازگشت", lambda *_: setattr(self.manager, "current", "login")))

    def verify(self, *_):
        if self.code.text.strip() != DEMO_OTP:
            self.message("کد اشتباه", "کد آزمایشی صحیح 123456 است")
            return
        phone = self.phone_value
        ensure_user(phone)
        user = get_user(phone)
        if user and user["is_blocked"]:
            self.message("دسترسی مسدود", "این حساب توسط مدیریت مسدود شده است")
            return
        app = App.get_running_app()
        app.current_phone = phone
        app.is_admin = (phone == ADMIN_PHONE)
        self.manager.current = "home"


class HomeScreen(BaseScreen):
    def on_pre_enter(self):
        app = App.get_running_app()
        phone = app.current_phone
        user = get_user(phone) if phone else None
        coins = user["coins"] if user else 0
        box = self.page("عضو بگیر")
        box.add_widget(Label(
            text=fa("خوش آمدی 🌱"), color=GREEN_DARK,
            font_size=24, size_hint_y=None, height=dp(58), bold=True
        ))
        box.add_widget(Label(
            text=fa(f"شماره حساب: {phone or '-'}     |     موجودی: {coins} سکه"),
            color=TEXT, font_size=16, size_hint_y=None, height=dp(48)
        ))
        if app.is_admin:
            box.add_widget(make_button("ورود به پنل مدیریت", lambda *_: setattr(self.manager, "current", "admin"), True))
        box.add_widget(make_button("مشاهده سفارش‌های عضوگیری", lambda *_: setattr(self.manager, "current", "tasks")))
        box.add_widget(make_button("کیف پول و تراکنش‌ها", lambda *_: setattr(self.manager, "current", "wallet")))
        box.add_widget(make_button("دعوت دوستان", lambda *_: self.message("دعوت دوستان", "لینک دعوت در نسخه آنلاین به حساب شما متصل می‌شود")))
        box.add_widget(make_button("گردونه شانس", lambda *_: self.message("گردونه شانس", "این قابلیت در نسخه بعدی تکمیل می‌شود")))
        box.add_widget(make_button("پشتیبانی", lambda *_: self.message("پشتیبانی", "برای اتصال پشتیبانی آنلاین، سرور لازم است")))
        box.add_widget(Widget())
        box.add_widget(make_button("خروج از حساب", self.logout))
        self.add_nav()

    def logout(self, *_):
        app = App.get_running_app()
        app.current_phone = None
        app.is_admin = False
        self.manager.current = "login"


class TasksScreen(BaseScreen):
    def on_pre_enter(self):
        box = self.page("سفارش‌های عضوگیری")
        tasks = list_tasks(active_only=True)
        if not tasks:
            box.add_widget(card_label("فعلاً سفارشی ثبت نشده است", 16))
        else:
            scroll = ScrollView()
            items = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
            items.bind(minimum_height=items.setter("height"))
            for task in tasks:
                panel = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(4), size_hint_y=None, height=dp(116))
                panel.add_widget(card_label(f"{task['title']}  |  پاداش: {task['reward']} سکه", 15))
                panel.add_widget(card_label(task["channel_link"], 12, MUTED))
                panel.add_widget(make_button("ثبت انجام وظیفه", lambda _b, t=task: self.claim(t)))
                items.add_widget(panel)
            scroll.add_widget(items)
            box.add_widget(scroll)
        box.add_widget(Widget())
        self.add_nav()

    def claim(self, task):
        app = App.get_running_app()
        phone = app.current_phone
        with closing(db()) as conn, conn:
            existing = conn.execute(
                "SELECT id FROM records WHERE phone=? AND task_id=?",
                (phone, task["id"])
            ).fetchone()
            if existing:
                self.message("ثبت تکراری", "این سفارش قبلاً برای شما ثبت شده است")
                return
            conn.execute(
                "INSERT INTO records(phone, task_id, status, created_at) VALUES(?,?,?,?)",
                (phone, task["id"], "pending_manual_check", int(time.time()))
            )
        self.message("ثبت شد", "درخواست شما ثبت شد؛ بررسی عضویت واقعی در این نسخه فعال نیست.")


class WalletScreen(BaseScreen):
    def on_pre_enter(self):
        app = App.get_running_app()
        phone = app.current_phone
        user = get_user(phone)
        box = self.page("کیف پول")
        box.add_widget(Label(
            text=fa(f"موجودی شما: {user['coins'] if user else 0} سکه"),
            color=GREEN_DARK, font_size=24, size_hint_y=None, height=dp(64), bold=True
        ))
        box.add_widget(card_label("تاریخچه تراکنش‌ها", 17))
        with closing(db()) as conn:
            rows = conn.execute(
                "SELECT amount, note, created_at FROM coin_log WHERE phone=? ORDER BY id DESC LIMIT 30",
                (phone,)
            ).fetchall()
        if not rows:
            box.add_widget(card_label("هنوز تراکنشی ندارید", 14, MUTED))
        for row in rows:
            sign = "+" if row["amount"] > 0 else ""
            box.add_widget(card_label(f"{sign}{row['amount']} سکه — {row['note']}", 13))
        box.add_widget(Widget())
        self.add_nav()


class AdminScreen(BaseScreen):
    def on_pre_enter(self):
        app = App.get_running_app()
        if not app.is_admin:
            self.page("دسترسی محدود").add_widget(card_label("این بخش فقط برای مدیر اصلی فعال است", 16))
            self.add_nav()
            return

        box = self.page("پنل مدیریت")
        box.add_widget(card_label("ساخت سفارش جدید", 17))
        self.task_title = make_input("عنوان سفارش")
        self.task_link = make_input("لینک کانال روبیکا")
        self.task_reward = make_input("پاداش سکه (عدد)")
        box.add_widget(self.task_title)
        box.add_widget(self.task_link)
        box.add_widget(self.task_reward)
        box.add_widget(make_button("ثبت سفارش", self.create_task, True))
        box.add_widget(card_label("مدیریت موجودی کاربر", 17))
        self.target_phone = make_input("شماره کاربر")
        self.coin_amount = make_input("مقدار سکه؛ برای کسر عدد منفی")
        box.add_widget(self.target_phone)
        box.add_widget(self.coin_amount)
        box.add_widget(make_button("اعمال تغییر موجودی", self.adjust_coins))
        box.add_widget(make_button("نمایش کاربران", self.show_users))
        box.add_widget(make_button("نمایش سفارش‌ها", self.show_all_tasks))
        box.add_widget(Widget())
        self.add_nav()

    def create_task(self, *_):
        title = self.task_title.text.strip()
        link = self.task_link.text.strip()
        reward = self.task_reward.text.strip()
        if not title or not link or not reward.isdigit() or int(reward) <= 0:
            self.message("اطلاعات ناقص", "عنوان، لینک و پاداش مثبت را وارد کنید")
            return
        add_task(title, link, int(reward))
        self.message("موفق", "سفارش ثبت شد")
        self.on_pre_enter()

    def adjust_coins(self, *_):
        phone = self.target_phone.text.strip()
        amount = self.coin_amount.text.strip()
        if not phone or not amount:
            self.message("خطا", "شماره و مقدار سکه را وارد کنید")
            return
        try:
            amount = int(amount)
        except ValueError:
            self.message("خطا", "مقدار سکه باید عدد باشد")
            return
        result, msg = change_coins(phone, amount, "تغییر توسط مدیر")
        self.message("نتیجه", msg)

    def show_users(self, *_):
        with closing(db()) as conn:
            rows = conn.execute("SELECT phone, coins, is_blocked FROM users ORDER BY created_at DESC").fetchall()
        text = "\n".join([f"{r['phone']} | {r['coins']} سکه | مسدود: {r['is_blocked']}" for r in rows]) or "کاربری وجود ندارد"
        Popup(title=fa("کاربران"), content=Label(text=fa(text), color=TEXT), size_hint=(0.9, 0.7)).open()

    def show_all_tasks(self, *_):
        rows = list_tasks()
        text = "\n".join([f"{r['id']}. {r['title']} | {r['reward']} سکه | {r['status']}" for r in rows]) or "سفارشی وجود ندارد"
        Popup(title=fa("همه سفارش‌ها"), content=Label(text=fa(text), color=TEXT), size_hint=(0.9, 0.7)).open()


class MemberApp(App):
    current_phone = None
    is_admin = False

    def build(self):
        Window.clearcolor = BG
        init_db()
        sm = ScreenManager(transition=FadeTransition())
        for name, cls in [
            ("login", LoginScreen), ("otp", OtpScreen),
            ("home", HomeScreen), ("tasks", TasksScreen),
            ("wallet", WalletScreen), ("admin", AdminScreen)
        ]:
            sm.add_widget(cls(name=name))
        sm.current = "login"
        return sm


if __name__ == "__main__":
    MemberApp().run()