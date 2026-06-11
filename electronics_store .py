import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import random
import sqlite3
import os
from datetime import datetime

# ============================================================
#  DATABASE SETUP
# ============================================================
DB_FILE = "electronics_store.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT,
        price REAL,
        stock INTEGER,
        category TEXT,
        emoji TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        product_name TEXT,
        customer TEXT,
        quantity INTEGER,
        total REAL,
        status TEXT,
        timestamp TEXT
    )""")
    c.execute("SELECT COUNT(*) FROM products")
    if c.fetchone()[0] == 0:
        products = [
            (1, "iPhone 15 Pro",      4599, 10, "Phones",    "📱"),
            (2, "Samsung Galaxy S24", 3999, 8,  "Phones",    "📱"),
            (3, "MacBook Pro M3",     8999, 5,  "Laptops",   "💻"),
            (4, "Dell XPS 15",        6499, 7,  "Laptops",   "💻"),
            (5, "iPad Pro 12.9",      4299, 12, "Tablets",   "📟"),
            (6, "AirPods Pro 2",      1099, 20, "Audio",     "🎧"),
            (7, "Sony WH-1000XM5",   1299, 15, "Audio",     "🎧"),
            (8, "PS5 Console",        2499, 6,  "Gaming",    "🎮"),
            (9, "Xbox Series X",      2299, 6,  "Gaming",    "🎮"),
            (10,"Samsung 4K TV 65\"", 5999, 4,  "TVs",       "📺"),
        ]
        c.executemany("INSERT INTO products VALUES (?,?,?,?,?,?)", products)
    conn.commit()
    conn.close()

# ============================================================
#  SHARED RESOURCE  (the inventory)
# ============================================================
class Inventory:
    def __init__(self):
        self.lock = threading.Lock()
        self._load()

    def _load(self):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT id, stock FROM products")
        self.stock = {row[0]: row[1] for row in c.fetchall()}
        conn.close()

    def buy_unsafe(self, product_id, qty, customer):
        """WITHOUT synchronization — demonstrates Race Condition"""
        current = self.stock.get(product_id, 0)
        time.sleep(0.05)
        if current >= qty:
            time.sleep(0.05)
            self.stock[product_id] = current - qty
            self._save(product_id)
            return True, current - qty
        return False, current

    def buy_safe(self, product_id, qty, customer):
        """WITH Mutex Lock — thread-safe"""
        with self.lock:
            current = self.stock.get(product_id, 0)
            time.sleep(0.05)
            if current >= qty:
                time.sleep(0.05)
                self.stock[product_id] = current - qty
                self._save(product_id)
                return True, current - qty
            return False, current

    def _save(self, product_id):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE products SET stock=? WHERE id=?",
                  (self.stock[product_id], product_id))
        conn.commit()
        conn.close()

    def get_stock(self, product_id):
        return self.stock.get(product_id, 0)

    def reload(self):
        self._load()

# inventory will be initialized after init_db() in __main__
inventory = None

# ============================================================
#  COLORS & FONTS
# ============================================================
BG        = "#0D1117"
BG2       = "#161B22"
BG3       = "#21262D"
ACCENT    = "#58A6FF"
ACCENT2   = "#3FB950"
DANGER    = "#F85149"
WARNING   = "#D29922"
TEXT      = "#E6EDF3"
TEXT2     = "#8B949E"
BORDER    = "#30363D"
GOLD      = "#FFD700"

FONT_TITLE  = ("Segoe UI", 22, "bold")
FONT_HEAD   = ("Segoe UI", 13, "bold")
FONT_BODY   = ("Segoe UI", 11)
FONT_SMALL  = ("Segoe UI", 9)
FONT_CODE   = ("Consolas", 10)

# ============================================================
#  MAIN APPLICATION
# ============================================================
class ElectronicsStore(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("⚡ TechStore — نظام المتجر الإلكتروني")
        self.geometry("1280x800")
        self.minsize(1100, 700)
        self.configure(bg=BG)
        self.resizable(True, True)

        self.selected_product = None
        self.cart = {}
        self.sync_mode = tk.BooleanVar(value=True)
        self.active_threads = []
        self.order_counter = 0

        self._build_ui()
        self._load_products()
        self._start_log("🚀 النظام جاهز — TechStore مفتوح للطلبات")

    def _build_ui(self):
        topbar = tk.Frame(self, bg=BG2, height=60)
        topbar.pack(fill=tk.X)
        topbar.pack_propagate(False)

        tk.Label(topbar, text="⚡ TechStore", font=("Segoe UI", 18, "bold"),
                 bg=BG2, fg=ACCENT).pack(side=tk.LEFT, padx=20, pady=10)
        tk.Label(topbar, text="متجر الإلكترونيات المتقدم | نظام التشغيل 2",
                 font=FONT_SMALL, bg=BG2, fg=TEXT2).pack(side=tk.LEFT, padx=5, pady=10)

        sync_frame = tk.Frame(topbar, bg=BG2)
        sync_frame.pack(side=tk.RIGHT, padx=20)
        tk.Label(sync_frame, text="وضع التزامن:", font=FONT_SMALL, bg=BG2, fg=TEXT2).pack(side=tk.LEFT)
        self.sync_btn = tk.Button(sync_frame, text="🔒 مع Mutex (آمن)",
                                  font=FONT_SMALL, bg=ACCENT2, fg="white",
                                  relief=tk.FLAT, padx=10, cursor="hand2",
                                  command=self._toggle_sync)
        self.sync_btn.pack(side=tk.LEFT, padx=5)

        self.cart_lbl = tk.Label(topbar, text="🛒  السلة: 0 منتج",
                                 font=FONT_SMALL, bg=BG2, fg=GOLD, cursor="hand2")
        self.cart_lbl.pack(side=tk.RIGHT, padx=15)
        self.cart_lbl.bind("<Button-1>", lambda e: self._show_cart())

        main = tk.Frame(self, bg=BG)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        left = tk.Frame(main, bg=BG2, width=440)
        left.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 6))
        left.pack_propagate(False)
        self._build_product_panel(left)

        center = tk.Frame(main, bg=BG)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        self._build_detail_panel(center)

        right = tk.Frame(main, bg=BG2, width=370)
        right.pack(side=tk.RIGHT, fill=tk.BOTH)
        right.pack_propagate(False)
        self._build_log_panel(right)

        statusbar = tk.Frame(self, bg=BG3, height=28)
        statusbar.pack(fill=tk.X, side=tk.BOTTOM)
        statusbar.pack_propagate(False)
        self.status_var = tk.StringVar(value="جاهز")
        tk.Label(statusbar, textvariable=self.status_var,
                 font=FONT_SMALL, bg=BG3, fg=TEXT2).pack(side=tk.LEFT, padx=10)
        self.thread_lbl = tk.Label(statusbar, text="Threads: 0",
                                   font=FONT_SMALL, bg=BG3, fg=ACCENT)
        self.thread_lbl.pack(side=tk.RIGHT, padx=10)

    def _build_product_panel(self, parent):
        hdr = tk.Frame(parent, bg=BG2)
        hdr.pack(fill=tk.X, padx=10, pady=(10, 4))
        tk.Label(hdr, text="📦 المنتجات", font=FONT_HEAD, bg=BG2, fg=TEXT).pack(side=tk.LEFT)

        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *a: self._filter_products())
        sf = tk.Frame(parent, bg=BG2)
        sf.pack(fill=tk.X, padx=10, pady=(0, 6))
        tk.Label(sf, text="🔍", bg=BG2, fg=TEXT2).pack(side=tk.LEFT)
        tk.Entry(sf, textvariable=self.search_var, font=FONT_BODY,
                 bg=BG3, fg=TEXT, insertbackground=TEXT,
                 relief=tk.FLAT, bd=4).pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.cat_var = tk.StringVar(value="الكل")
        cats = ["الكل", "Phones", "Laptops", "Tablets", "Audio", "Gaming", "TVs"]
        cf = tk.Frame(parent, bg=BG2)
        cf.pack(fill=tk.X, padx=10, pady=(0, 6))
        for cat in cats:
            tk.Button(cf, text=cat, font=FONT_SMALL, bg=BG3, fg=TEXT2,
                      relief=tk.FLAT, padx=6, cursor="hand2",
                      command=lambda c=cat: self._set_category(c)).pack(side=tk.LEFT, padx=2)

        frame = tk.Frame(parent, bg=BG2)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        scrollbar = tk.Scrollbar(frame, bg=BG3)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.product_list = tk.Listbox(frame, font=FONT_BODY,
                                        bg=BG3, fg=TEXT,
                                        selectbackground=ACCENT,
                                        selectforeground="white",
                                        relief=tk.FLAT, bd=0,
                                        activestyle="none",
                                        yscrollcommand=scrollbar.set)
        self.product_list.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.product_list.yview)
        self.product_list.bind("<<ListboxSelect>>", self._on_select)

    def _build_detail_panel(self, parent):
        self.detail_frame = tk.Frame(parent, bg=BG2, relief=tk.FLAT, bd=1)
        self.detail_frame.pack(fill=tk.X, pady=(0, 6))

        self.emoji_lbl = tk.Label(self.detail_frame, text="🛍️", font=("Segoe UI", 48),
                                   bg=BG2, fg=TEXT)
        self.emoji_lbl.pack(pady=(16, 4))

        self.name_lbl = tk.Label(self.detail_frame, text="اختر منتجاً من القائمة",
                                  font=FONT_TITLE, bg=BG2, fg=TEXT, wraplength=380)
        self.name_lbl.pack()

        self.price_lbl = tk.Label(self.detail_frame, text="",
                                   font=("Segoe UI", 16, "bold"), bg=BG2, fg=GOLD)
        self.price_lbl.pack(pady=2)

        info_row = tk.Frame(self.detail_frame, bg=BG2)
        info_row.pack(pady=4)
        self.stock_lbl = tk.Label(info_row, text="", font=FONT_BODY, bg=BG2, fg=ACCENT2)
        self.stock_lbl.pack(side=tk.LEFT, padx=10)
        self.cat_lbl2 = tk.Label(info_row, text="", font=FONT_BODY, bg=BG2, fg=TEXT2)
        self.cat_lbl2.pack(side=tk.LEFT, padx=10)

        ctrl = tk.Frame(self.detail_frame, bg=BG2)
        ctrl.pack(pady=10)
        tk.Label(ctrl, text="الكمية:", font=FONT_BODY, bg=BG2, fg=TEXT2).pack(side=tk.LEFT, padx=4)
        self.qty_spin = tk.Spinbox(ctrl, from_=1, to=10, width=4,
                                    font=FONT_BODY, bg=BG3, fg=TEXT,
                                    buttonbackground=BG3, relief=tk.FLAT)
        self.qty_spin.pack(side=tk.LEFT, padx=4)
        tk.Button(ctrl, text="➕ أضف للسلة", font=FONT_BODY,
                  bg=ACCENT, fg="white", relief=tk.FLAT, padx=14, cursor="hand2",
                  command=self._add_to_cart).pack(side=tk.LEFT, padx=8)

        cart_hdr = tk.Frame(parent, bg=BG)
        cart_hdr.pack(fill=tk.X, pady=(4, 2))
        tk.Label(cart_hdr, text="🛒 سلة المشتريات", font=FONT_HEAD, bg=BG, fg=TEXT).pack(side=tk.LEFT)
        tk.Button(cart_hdr, text="مسح السلة", font=FONT_SMALL, bg=DANGER, fg="white",
                  relief=tk.FLAT, padx=8, cursor="hand2",
                  command=self._clear_cart).pack(side=tk.RIGHT)

        cart_frame = tk.Frame(parent, bg=BG2)
        cart_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        self.cart_list = tk.Listbox(cart_frame, font=FONT_BODY,
                                     bg=BG3, fg=TEXT,
                                     selectbackground=ACCENT,
                                     relief=tk.FLAT, bd=0,
                                     activestyle="none", height=5)
        self.cart_list.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        bot = tk.Frame(parent, bg=BG)
        bot.pack(fill=tk.X)
        self.total_lbl = tk.Label(bot, text="الإجمالي: 0 ل.س",
                                   font=FONT_HEAD, bg=BG, fg=GOLD)
        self.total_lbl.pack(side=tk.LEFT)

        tk.Button(bot, text="⚡ طلب واحد",
                  font=FONT_BODY, bg=ACCENT2, fg="white",
                  relief=tk.FLAT, padx=14, cursor="hand2",
                  command=self._place_order).pack(side=tk.RIGHT, padx=4)

        tk.Button(bot, text="🔥 اختبار Race Condition (5 عملاء)",
                  font=FONT_BODY, bg=WARNING, fg="white",
                  relief=tk.FLAT, padx=14, cursor="hand2",
                  command=self._race_test).pack(side=tk.RIGHT, padx=4)

    def _build_log_panel(self, parent):
        hdr = tk.Frame(parent, bg=BG2)
        hdr.pack(fill=tk.X, padx=10, pady=(10, 4))
        tk.Label(hdr, text="📋 Console Logs", font=FONT_HEAD, bg=BG2, fg=TEXT).pack(side=tk.LEFT)
        tk.Button(hdr, text="مسح", font=FONT_SMALL, bg=BG3, fg=TEXT2,
                  relief=tk.FLAT, padx=6, cursor="hand2",
                  command=self._clear_log).pack(side=tk.RIGHT)

        self.log_box = scrolledtext.ScrolledText(parent, font=FONT_CODE,
                                                  bg="#010409", fg="#39D353",
                                                  insertbackground=ACCENT,
                                                  relief=tk.FLAT, bd=0,
                                                  wrap=tk.WORD, state=tk.DISABLED)
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        self.log_box.tag_config("info",    foreground="#58A6FF")
        self.log_box.tag_config("success", foreground="#3FB950")
        self.log_box.tag_config("error",   foreground="#F85149")
        self.log_box.tag_config("warning", foreground="#D29922")
        self.log_box.tag_config("thread",  foreground="#BC8CFF")
        self.log_box.tag_config("lock",    foreground="#FFD700")

        tk.Label(parent, text="📜 سجل الطلبات", font=FONT_HEAD,
                 bg=BG2, fg=TEXT).pack(padx=10, anchor=tk.W)

        cols = ("العميل", "المنتج", "الكمية", "الحالة")
        self.orders_tree = ttk.Treeview(parent, columns=cols, show="headings", height=6)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=BG3, foreground=TEXT,
                         fieldbackground=BG3, borderwidth=0, font=FONT_SMALL)
        style.configure("Treeview.Heading", background=BG2, foreground=ACCENT,
                         font=("Segoe UI", 9, "bold"))
        for col in cols:
            self.orders_tree.heading(col, text=col)
            self.orders_tree.column(col, width=80, anchor=tk.CENTER)
        self.orders_tree.pack(fill=tk.X, padx=6, pady=(4, 10))

    def _load_products(self):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT id, name, price, stock, category, emoji FROM products")
        self.all_products = c.fetchall()
        conn.close()
        self._render_products(self.all_products)

    def _render_products(self, products):
        self.product_list.delete(0, tk.END)
        self.products_shown = products
        for p in products:
            pid, name, price, stock, cat, emoji = p
            stock_str = f"✅ {stock}" if stock > 3 else (f"⚠️ {stock}" if stock > 0 else "❌ نفد")
            self.product_list.insert(tk.END, f"  {emoji}  {name}   |  {price:,} ل.س  |  {stock_str}")
            if stock == 0:
                self.product_list.itemconfig(tk.END, fg=TEXT2)

    def _filter_products(self):
        q = self.search_var.get().lower()
        cat = self.cat_var.get()
        filtered = [p for p in self.all_products
                    if (q in p[1].lower()) and (cat == "الكل" or p[4] == cat)]
        self._render_products(filtered)

    def _set_category(self, cat):
        self.cat_var.set(cat)
        self._filter_products()

    def _on_select(self, event):
        sel = self.product_list.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(self.products_shown):
            return
        p = self.products_shown[idx]
        self.selected_product = p
        pid, name, price, stock, cat, emoji = p
        live_stock = inventory.get_stock(pid)
        self.emoji_lbl.config(text=emoji)
        self.name_lbl.config(text=name)
        self.price_lbl.config(text=f"{price:,} ل.س")
        self.stock_lbl.config(text=f"المخزون: {live_stock}",
                               fg=ACCENT2 if live_stock > 3 else (WARNING if live_stock > 0 else DANGER))
        self.cat_lbl2.config(text=f"الفئة: {cat}")

    def _add_to_cart(self):
        if not self.selected_product:
            messagebox.showwarning("تنبيه", "اختر منتجاً أولاً!")
            return
        pid, name, price, stock, cat, emoji = self.selected_product
        qty = int(self.qty_spin.get())
        if inventory.get_stock(pid) < qty:
            messagebox.showerror("خطأ", "المخزون غير كافٍ!")
            return
        self.cart[pid] = self.cart.get(pid, 0) + qty
        self._refresh_cart()
        self._start_log(f"➕ أُضيف للسلة: {emoji} {name} × {qty}", "info")

    def _refresh_cart(self):
        self.cart_list.delete(0, tk.END)
        total = 0
        count = 0
        for pid, qty in self.cart.items():
            p = next((x for x in self.all_products if x[0] == pid), None)
            if p:
                subtotal = p[2] * qty
                total += subtotal
                count += qty
                self.cart_list.insert(tk.END, f"  {p[5]} {p[1]}  × {qty}  =  {subtotal:,} ل.س")
        self.total_lbl.config(text=f"الإجمالي: {total:,} ل.س")
        self.cart_lbl.config(text=f"🛒  السلة: {count} منتج")

    def _clear_cart(self):
        self.cart.clear()
        self._refresh_cart()
        self._start_log("🗑️ تم مسح السلة", "warning")

    def _show_cart(self):
        if not self.cart:
            messagebox.showinfo("السلة", "السلة فارغة!")
            return
        lines = []
        total = 0
        for pid, qty in self.cart.items():
            p = next((x for x in self.all_products if x[0] == pid), None)
            if p:
                sub = p[2] * qty
                total += sub
                lines.append(f"{p[5]} {p[1]} × {qty} = {sub:,} ل.س")
        lines.append(f"\n💰 الإجمالي: {total:,} ل.س")
        messagebox.showinfo("محتويات السلة", "\n".join(lines))

    def _place_order(self):
        if not self.cart:
            messagebox.showwarning("تنبيه", "السلة فارغة!")
            return
        customer = f"عميل_{random.randint(100, 999)}"
        for pid, qty in list(self.cart.items()):
            t = threading.Thread(target=self._process_order,
                                  args=(pid, qty, customer), daemon=True)
            self.active_threads.append(t)
            t.start()
        self._update_thread_count()

    def _race_test(self):
        if not self.selected_product:
            messagebox.showwarning("تنبيه", "اختر منتجاً لاختبار Race Condition!")
            return
        pid = self.selected_product[0]
        name = self.selected_product[1]
        mode = "آمن 🔒" if self.sync_mode.get() else "غير آمن ⚠️"
        self._start_log(f"", "info")
        self._start_log(f"════════════════════════════════", "lock")
        self._start_log(f"🔥 اختبار Race Condition — وضع: {mode}", "lock")
        self._start_log(f"المنتج: {name} | 5 عملاء يشترون في نفس الوقت", "lock")
        self._start_log(f"════════════════════════════════", "lock")

        customers = [f"عميل_{i}" for i in range(1, 6)]
        threads = []
        for cust in customers:
            t = threading.Thread(target=self._process_order,
                                  args=(pid, 1, cust), daemon=True)
            threads.append(t)
            self.active_threads.append(t)

        for t in threads:
            t.start()
        self._update_thread_count()

        def wait_and_report():
            for t in threads:
                t.join()
            remaining = inventory.get_stock(pid)
            self.after(100, lambda: self._start_log(
                f"📊 النتيجة النهائية — المخزون المتبقي: {remaining}", "warning"))
            self.after(200, self._load_products)

        threading.Thread(target=wait_and_report, daemon=True).start()

    def _process_order(self, product_id, qty, customer):
        p = next((x for x in self.all_products if x[0] == product_id), None)
        if not p:
            return
        name, price, emoji = p[1], p[2], p[5]
        self.order_counter += 1
        order_id = self.order_counter

        self.after(0, lambda: self._start_log(
            f"🧵 Thread-{order_id} | {customer} يحاول شراء {emoji}{name} × {qty}", "thread"))

        if self.sync_mode.get():
            self.after(0, lambda: self._start_log(
                f"🔒 Thread-{order_id} | انتظار Lock...", "lock"))
            success, remaining = inventory.buy_safe(product_id, qty, customer)
        else:
            success, remaining = inventory.buy_unsafe(product_id, qty, customer)

        total = price * qty
        status = "✅ نجح" if success else "❌ فشل"

        if success:
            self.after(0, lambda: self._start_log(
                f"✅ Thread-{order_id} | {customer} اشترى {name} — المخزون: {remaining}", "success"))
            self._save_order(product_id, name, customer, qty, total, "مكتمل")
        else:
            self.after(0, lambda: self._start_log(
                f"❌ Thread-{order_id} | {customer} فشل — المخزون غير كافٍ ({remaining})", "error"))
            self._save_order(product_id, name, customer, qty, total, "فشل")

        self.after(200, lambda: self._add_order_row(customer, name, qty, status))
        self.after(300, self._load_products)

    def _save_order(self, product_id, name, customer, qty, total, status):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO orders (product_id, product_name, customer, quantity, total, status, timestamp) VALUES (?,?,?,?,?,?,?)",
                  (product_id, name, customer, qty, total, status, datetime.now().strftime("%H:%M:%S")))
        conn.commit()
        conn.close()

    def _add_order_row(self, customer, name, qty, status):
        self.orders_tree.insert("", 0, values=(customer, name[:15], qty, status))
        rows = self.orders_tree.get_children()
        if len(rows) > 20:
            self.orders_tree.delete(rows[-1])

    def _toggle_sync(self):
        current = self.sync_mode.get()
        self.sync_mode.set(not current)
        if self.sync_mode.get():
            self.sync_btn.config(text="🔒 مع Mutex (آمن)", bg=ACCENT2)
            self._start_log("🔒 تم تفعيل Mutex Lock — الوضع الآمن", "success")
        else:
            self.sync_btn.config(text="⚠️ بدون Mutex (خطر!)", bg=DANGER)
            self._start_log("⚠️ تم إيقاف Mutex — ستظهر Race Conditions!", "error")

    def _update_thread_count(self):
        alive = sum(1 for t in self.active_threads if t.is_alive())
        self.thread_lbl.config(text=f"Threads: {alive}")
        if alive > 0:
            self.after(200, self._update_thread_count)
        else:
            self.thread_lbl.config(text="Threads: 0")

    def _start_log(self, msg, tag="info"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_box.config(state=tk.NORMAL)
        self.log_box.insert(tk.END, f"[{ts}] {msg}\n", tag)
        self.log_box.see(tk.END)
        self.log_box.config(state=tk.DISABLED)

    def _clear_log(self):
        self.log_box.config(state=tk.NORMAL)
        self.log_box.delete(1.0, tk.END)
        self.log_box.config(state=tk.DISABLED)


# ============================================================
if __name__ == "__main__":
    init_db()           # 1️⃣ أنشئ قاعدة البيانات أولاً
    inventory = Inventory()  # 2️⃣ ثم أنشئ الـ Inventory
    app = ElectronicsStore()  # 3️⃣ ثم شغّل التطبيق
    app.mainloop()
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
