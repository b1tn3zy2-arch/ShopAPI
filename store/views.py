from django.contrib import messages
from django.shortcuts import redirect, render

from .db import call_function, call_procedure, handle_db_errors


@handle_db_errors()
def products_list(request):
    rows, _ = call_procedure('sp_products_list')
    products = [
        {'id': r[0], 'name': r[1], 'category': r[2], 'price': r[3], 'stock': r[4]}
        for r in rows
    ]
    return render(request, 'store/products_list.html', {'products': products})


@handle_db_errors()
def product_add(request):
    if request.method == 'POST':
        name = request.POST['name']
        category_id = int(request.POST['category_id'])
        price = float(request.POST['price'])
        stock = int(request.POST['stock'])
        _, out = call_procedure(
            'sp_product_add', [name, category_id, price, stock],
            out_count=1, fetch=False,
        )
        messages.success(request, f'Товар #{out[0]} добавлен')
        return redirect('products_list')
    cats, _ = call_procedure('sp_categories_list')
    return render(request, 'store/product_add.html',
                  {'categories': [{'id': c[0], 'name': c[1]} for c in cats]})


@handle_db_errors()
def product_price(request, pk):
    if request.method == 'POST':
        new_price = float(request.POST['price'])
        call_procedure('sp_product_update_price', [pk, new_price], fetch=False)
        messages.success(request, f'Цена товара #{pk} обновлена')
        return redirect('products_list')
    return render(request, 'store/product_price.html', {'product_id': pk})


@handle_db_errors()
def order_create(request):
    if request.method == 'POST':
        customer_id = int(request.POST['customer_id'])
        _, out = call_procedure('sp_order_create', [customer_id],
                                out_count=1, fetch=False)
        messages.success(request, f'Заказ #{out[0]} создан')
        return redirect('order_detail', order_id=out[0])
    cust, _ = call_procedure('sp_customers_list')
    return render(request, 'store/order_create.html',
                  {'customers': [{'id': c[0], 'fio': f'{c[1]} {c[2]}'}
                                 for c in cust]})


@handle_db_errors()
def order_add_item(request, order_id):
    products, _ = call_procedure('sp_products_list')
    products = [{'id': r[0], 'name': r[1], 'price': r[3], 'stock': r[4]}
                for r in products]
    if request.method == 'POST':
        product_id = int(request.POST['product_id'])
        qty = int(request.POST['quantity'])
        _, out = call_procedure(
            'sp_order_add_item', [order_id, product_id, qty],
            out_count=2, fetch=False,
        )
        success, msg = out[0], out[1]
        if success:
            messages.success(request, 'Позиция добавлена')
            return redirect('order_detail', order_id=order_id)
        messages.error(request, msg)
    return render(request, 'store/order_create.html',
                  {'products': products, 'order_id': order_id, 'step': 'item'})


@handle_db_errors()
def order_detail(request, order_id):
    rows, _ = call_procedure('sp_order_items', [order_id])
    items = [{'product_id': r[0], 'product': r[1],
              'quantity': r[2], 'price': r[3], 'subtotal': r[4]} for r in rows]
    total = sum(i['subtotal'] for i in items)
    return render(request, 'store/order_detail.html',
                  {'items': items, 'order_id': order_id, 'total': total})


@handle_db_errors()
def customer_orders(request, pk):
    rows, _ = call_procedure('sp_customer_orders', [pk])
    orders = [{'order_id': r[0], 'created_at': r[1],
               'total': r[2], 'avg_check': r[3]} for r in rows]
    return render(request, 'store/customer_orders.html',
                  {'orders': orders, 'customer_id': pk})


@handle_db_errors()
def category_stats(request):
    rows, _ = call_procedure('sp_category_stats')
    stats = [{'category': r[0], 'products_count': r[1],
              'sold_units': r[2], 'revenue': r[3]} for r in rows]
    top_revenue = max((s['revenue'] for s in stats), default=0)
    return render(request, 'store/category_stats.html',
                  {'stats': stats, 'top_revenue': top_revenue})


@handle_db_errors()
def discount_view(request):
    result = None
    if request.method == 'POST':
        customer_id = int(request.POST['customer_id'])
        amount = float(request.POST['amount'])
        percent = call_function('fn_customer_discount', [customer_id, amount])
        total = amount * (1 - float(percent) / 100)
        result = {'customer_id': customer_id, 'amount': amount,
                  'percent': percent, 'total': round(total, 2)}
    return render(request, 'store/discount.html', {'result': result})