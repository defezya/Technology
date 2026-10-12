from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from .forms import RegisterForm, CheckoutForm
from .models import Category, Product, Order, OrderItem

def about(request):
    featured = Product.objects.filter(active=True, stock__gt=0)[:4]
    return render(request, "store/about.html", {"featured": featured})

def catalog(request):
    products = Product.objects.filter(active=True)
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    sort = request.GET.get("sort", "new")
    if query:
        products = products.filter(Q(name__icontains=query) | Q(manufacturer__icontains=query) | Q(model_name__icontains=query))
    if category.isdigit():
        products = products.filter(category_id=int(category))
    if sort == "price_asc":
        products = products.order_by("price")
    elif sort == "price_desc":
        products = products.order_by("-price")
    elif sort == "name":
        products = products.order_by("name")
    else:
        products = products.order_by("-created_at")
    return render(request, "store/catalog.html", {
        "products": products, "categories": Category.objects.all(),
        "query": query, "selected_category": category, "sort": sort,
    })

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk, active=True)
    return render(request, "store/product_detail.html", {"product": product})

def register(request):
    if request.user.is_authenticated:
        return redirect("catalog")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Регистрация прошла успешно.")
        return redirect("catalog")
    return render(request, "store/register.html", {"form": form})

def logout_view(request):
    logout(request)
    messages.info(request, "Вы вышли из аккаунта.")
    return redirect("about")

def _cart_items(request):
    cart_data = request.session.get("cart", {})
    items, total = [], Decimal("0.00")
    for product_id, quantity in cart_data.items():
        try:
            product = Product.objects.get(pk=int(product_id), active=True)
            quantity = min(max(int(quantity), 1), product.stock)
            if quantity:
                subtotal = product.price * quantity
                items.append({"product": product, "quantity": quantity, "subtotal": subtotal})
                total += subtotal
        except (Product.DoesNotExist, ValueError, TypeError):
            continue
    return items, total

def cart(request):
    items, total = _cart_items(request)
    return render(request, "store/cart.html", {"items": items, "total": total})

def cart_add(request, pk):
    if request.method != "POST":
        return redirect("catalog")
    product = get_object_or_404(Product, pk=pk, active=True)
    if not request.user.is_authenticated:
        messages.info(request, "Войдите в аккаунт, чтобы добавлять товары в корзину.")
        return redirect("login")
    cart_data = request.session.get("cart", {})
    current = int(cart_data.get(str(pk), 0))
    if product.stock <= current:
        messages.error(request, "Нельзя добавить больше товаров, чем есть в наличии.")
    else:
        cart_data[str(pk)] = current + 1
        request.session["cart"] = cart_data
        messages.success(request, "Товар добавлен в корзину.")
    return redirect(request.META.get("HTTP_REFERER", "catalog"))

@login_required
def cart_update(request, pk):
    if request.method == "POST":
        product = get_object_or_404(Product, pk=pk, active=True)
        try:
            quantity = int(request.POST.get("quantity", "1"))
        except ValueError:
            quantity = 1
        cart_data = request.session.get("cart", {})
        if quantity <= 0:
            cart_data.pop(str(pk), None)
        elif quantity <= product.stock:
            cart_data[str(pk)] = quantity
        else:
            messages.error(request, f"Доступно только {product.stock} шт.")
        request.session["cart"] = cart_data
    return redirect("cart")

@login_required
def cart_remove(request, pk):
    if request.method == "POST":
        cart_data = request.session.get("cart", {})
        cart_data.pop(str(pk), None)
        request.session["cart"] = cart_data
    return redirect("cart")

@login_required
def checkout(request):
    items, total = _cart_items(request)
    if not items:
        messages.info(request, "Корзина пуста.")
        return redirect("catalog")
    form = CheckoutForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not authenticate(request, username=request.user.username, password=form.cleaned_data["password"]):
            form.add_error("password", "Неверный пароль.")
        else:
            with transaction.atomic():
                # Recheck stock at order creation to avoid overselling.
                locked_products = {p.pk: Product.objects.select_for_update().get(pk=p.pk) for p in [i["product"] for i in items]}
                for item in items:
                    if locked_products[item["product"].pk].stock < item["quantity"]:
                        form.add_error(None, f"Недостаточно товара «{item['product'].name}» на складе.")
                        return render(request, "store/checkout.html", {"form": form, "items": items, "total": total})
                order = Order.objects.create(user=request.user, total=total)
                for item in items:
                    product = locked_products[item["product"].pk]
                    OrderItem.objects.create(order=order, product=product, quantity=item["quantity"], price=product.price)
                    product.stock -= item["quantity"]
                    product.save(update_fields=["stock"])
                request.session["cart"] = {}
            messages.success(request, f"Заказ №{order.pk} оформлен.")
            return redirect("orders")
    return render(request, "store/checkout.html", {"form": form, "items": items, "total": total})

@login_required
def orders(request):
    user_orders = Order.objects.filter(user=request.user).prefetch_related("items__product")
    return render(request, "store/orders.html", {"orders": user_orders})

@login_required
def order_delete(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    if request.method == "POST" and order.status == "new":
        with transaction.atomic():
            for item in order.items.select_related("product"):
                product = item.product
                product.stock += item.quantity
                product.save(update_fields=["stock"])
            order.delete()
        messages.success(request, "Новый заказ удалён, товары возвращены на склад.")
    return redirect("orders")

def contacts(request):
    return render(request, "store/contacts.html")
