# ShopAPI

Веб-приложение на Django 5, работающее с MySQL 8 **через хранимые процедуры и
функции**. ORM Django для бизнес-операций не используется: все запросы к данным
идут через `CALL`/`SELECT` по хранимым объектам MySQL.

Подробный разбор решения — в [REPORT.md](REPORT.md).

---

## Требования

| Компонент | Версия |
|-----------|--------|
| Python    | 3.11+ (проверено на 3.12) |
| Django    | 5.x |
| MySQL     | 8.x |
| Драйвер   | mysqlclient |
| Фронтенд  | Django Templates + Bootstrap 5 (CDN) |

---

## Структура проекта

```
shopapi/
├── manage.py
├── .env                        # параметры подключения к БД
├── requirements.txt
├── shopapi/                    # настройки Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── store/
│   ├── db.py                   # обёртки над процедурами и функциями
│   ├── views.py                # контроллеры
│   ├── urls.py                 # маршруты
│   └── templates/store/        # шаблоны (найдены через APP_DIRS)
├── sql/
│   ├── schema.sql              # база и таблицы
│   ├── functions.sql           # 3 хранимые функции
│   ├── procedures.sql          # 7 основных + 6 вспомогательных процедур
│   └── seed.sql                # тестовые данные
├── static/
└── logs/
    └── db_errors.log           # лог ошибок БД
```

---

## 1. Установка зависимостей

```bash
cd shopapi
pip install -r requirements.txt
```

> `mysqlclient` на Windows ставится через бинарные wheels, дополнительных
> инструментов (vcbuild) для Python 3.12 не требуется.

---

## 2. Развёртывание базы данных

Скрипты выполняются **строго по порядку** — `procedures.sql` вызывает
`fn_customer_avg_check` из `functions.sql`, а `seed.sql` зависит от таблиц.

```bash
mysql -u root -p --default-character-set=utf8mb4 -e "source sql/schema.sql"
mysql -u root -p --default-character-set=utf8mb4 -e "source sql/functions.sql"
mysql -u root -p --default-character-set=utf8mb4 -e "source sql/procedures.sql"
mysql -u root -p --default-character-set=utf8mb4 -e "source sql/seed.sql"
```

**Важно:** `sql/schema.sql` начинается с `DROP DATABASE IF EXISTS shop_django` —
скрипт полностью пересоздаёт базу.

> **Windows:** если путь к проекту содержит кириллицу (например
> `C:\Users\Студент\...`), клиент `mysql` не может открыть файл через
> `source`. Скопируйте скрипты в путь только с латиницей и запустите оттуда:
> ```powershell
> Copy-Item sql\*.sql C:\sql\ -Force
> mysql -u root -p --default-character-set=utf8mb4 -e "source C:/sql/schema.sql"
> ```

---

## 3. Настройка подключения

Файл `.env` в корне проекта:

```
DB_NAME=shop_django
DB_USER=root
DB_PASSWORD=your_password
DB_HOST=127.0.0.1
DB_PORT=3306
```

Значения читаются через `python-dotenv`. В коде обязательно вызывается
`load_dotenv(BASE_DIR / '.env')` — иначе все `os.getenv('DB_*')` вернут `None`,
и MySQL попытается подключиться под именем текущего пользователя ОС.

---

## 4. Миграции Django

```bash
python manage.py makemigrations
python manage.py migrate
```

ORM-модели в приложении `store` не используются, поэтому `makemigrations`
сообщает `No changes detected` — это ожидаемо. `migrate` создаёт служебные
таблицы Django (`auth_user`, `django_session` и т. д.), которые нужны для
админки, сессий и flash-сообщений.

> `sql/schema.sql` удаляет базу целиком, после чего `migrate` нужно выполнить
> заново — таблица `django_migrations` исчезает вместе с базой.

---

## 5. Запуск

```bash
python manage.py runserver 127.0.0.1:8000
```

Приложение: <http://127.0.0.1:8000/>

---

## Страницы

| URL | Задание | Хранимый объект |
|-----|---------|-----------------|
| `/` , `/products/` | 1. Список товаров | `sp_products_list` |
| `/products/add/` | 2. Добавление товара | `sp_categories_list`, `sp_product_add` (OUT) |
| `/products/<id>/price/` | 3. Изменение цены | `sp_product_update_price` |
| `/orders/create/` | 4. Создание заказа | `sp_customers_list`, `sp_order_create` (OUT) |
| `/orders/<id>/add-item/` | 4. Позиция заказа | `sp_products_list`, `sp_order_add_item` (OUT, OUT) |
| `/orders/<id>/` | 4. Детали заказа | `sp_order_items` |
| `/customers/<id>/orders/` | 5. Заказы клиента | `sp_customer_orders` → `fn_customer_avg_check` |
| `/stats/categories/` | 6. Статистика | `sp_category_stats` |
| `/discount/` | 7. Расчёт скидки | `fn_customer_discount` |

---

## Проверка вызовов из консоли

```bash
python manage.py shell
```

```python
>>> from store.db import call_procedure, call_function
>>> rows, out = call_procedure('sp_products_list')
>>> rows
((1, 'Смартфон', 'Электроника', Decimal('29990.00'), 15), ...)

>>> _, out = call_procedure('sp_product_add', ['Планшет', 1, 19990, 10], out_count=1, fetch=False)
>>> out
[5]

>>> call_function('fn_customer_discount', [2, 20000])
Decimal('10.00')
```

---

## Ошибки

Все вызовы проходят через обёртку `store/db.py`, которая:

* перехватывает `django.db.utils.DatabaseError`;
* пишет полный traceback в `logs/db_errors.log`;
* превращает код ошибки MySQL в понятное сообщение и показывает его
  пользователю через `django.contrib.messages` (декоратор `@handle_db_errors`);
* откатывает незакрытую транзакцию перед повторным использованием соединения.

Пример:

```
Не удалось выполнить sp_product_add: Нарушение внешнего ключа:
проверьте, что категория/клиент/товар существует
```