import logging
import traceback
from functools import wraps

from django.contrib import messages
from django.db import connection
from django.db.utils import DatabaseError
from django.shortcuts import redirect

logger = logging.getLogger('db_errors')


class StoredProcedureError(Exception):
    """Ошибка хранимой логики с сообщением, понятным пользователю."""


# Понятные сообщения для типовых ошибок MySQL (коды errno).
ERROR_HINTS = {
    1045: 'Нет доступа к базе данных: проверьте логин и пароль в .env',
    1049: 'База данных не найдена',
    1062: 'Такая запись уже существует (нарушен UNIQUE-ограничение)',
    1064: 'Ошибка SQL-синтаксиса в хранимом объекте',
    1146: 'Таблица не найдена: выполните sql/schema.sql',
    1305: 'Хранимая {kind} не найдена: проверьте sql/{script}.sql',
    1317: 'Вызов прерван пользователем',
    1318: 'Неверное число OUT-параметров у процедуры',
    1414: 'Некорректный вызов: OUT-параметры должны передаваться переменными',
    1451: 'Нельзя удалить запись, на неё ссылаются другие таблицы (FK)',
    1452: 'Нарушение внешнего ключа: проверьте, что категория/клиент/товар существует',
    1582: 'Хранимая функция не найдена: проверьте sql/functions.sql',
    1584: 'Объект с таким именем уже существует',
}

# MySQL отдаёт 1305 и для отсутствующей функции, поэтому уточняем вид объекта.
KIND_BY_CALL = {'CALL': ('процедура', 'procedures'), 'SELECT': ('функция', 'functions')}


def _explain(prefix, exc, sql_verb):
    code = exc.args[0] if exc.args and isinstance(exc.args[0], int) else None
    kind, script = KIND_BY_CALL.get(sql_verb, ('объект', ''))
    hint = ERROR_HINTS.get(code)
    if hint and '{kind}' in hint:
        hint = hint.format(kind=kind, script=script)
    base = hint or (exc.args[1] if len(exc.args) > 1 else str(exc))
    return f'{prefix}: {base}'


def _rollback():
    """Сбросить возможно незакрытую транзакцию после сбоя."""
    try:
        with connection.cursor() as cur:
            cur.execute('ROLLBACK')
    except DatabaseError:
        pass


def call_procedure(name, params=(), out_count=0, fetch=True):
    """
    Универсальный вызов хранимой процедуры.

    :param name:       имя процедуры
    :param params:     значения IN-параметров
    :param out_count:  сколько OUT-параметров нужно забрать
    :param fetch:      возвращать ли строки результата
    :return:           (rows, out_values)

    MySQL не принимает литералы и плейсхолдеры ? на месте OUT-параметров
    (ошибка 1414), поэтому для них заводятся сессионные переменные @_out_N,
    значение которых читается отдельным SELECT сразу после вызова.
    """
    params = list(params)
    out_vars = [f'@_out_{i}' for i in range(out_count)]
    placeholders = ','.join(['%s'] * len(params) + out_vars)
    sql = f'CALL {name}({placeholders})'

    try:
        with connection.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall() if fetch else None

            while cur.nextset():
                pass

            out_values = []
            if out_count:
                cur.execute('SELECT ' + ','.join(out_vars))
                row = cur.fetchone()
                out_values = list(row) if row else []
        return rows, out_values
    except DatabaseError as exc:
        _rollback()
        logger.error('DB error in CALL %s: %s\n%s', name, exc, traceback.format_exc())
        raise StoredProcedureError(
            _explain(f'Не удалось выполнить {name}', exc, 'CALL')) from exc


def call_function(name, params=()):
    """Вызов хранимой функции, возвращающей скаляр."""
    placeholders = ','.join(['%s'] * len(params))
    sql = f'SELECT {name}({placeholders})'
    try:
        with connection.cursor() as cur:
            cur.execute(sql, list(params))
            return cur.fetchone()[0]
    except DatabaseError as exc:
        _rollback()
        logger.error('DB error in SELECT %s: %s\n%s', name, exc, traceback.format_exc())
        raise StoredProcedureError(
            _explain(f'Не удалось вычислить {name}', exc, 'SELECT')) from exc


def handle_db_errors(fallback='products_list'):
    """Декоратор: превращает ошибку БД в сообщение пользователю."""
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            try:
                return view(request, *args, **kwargs)
            except StoredProcedureError as exc:
                messages.error(request, str(exc))
            except (KeyError, ValueError, TypeError):
                logger.error('Bad input in %s\n%s', view.__name__, traceback.format_exc())
                messages.error(request, 'Проверьте правильность заполнения полей формы')
            return redirect(fallback)
        return wrapper
    return decorator