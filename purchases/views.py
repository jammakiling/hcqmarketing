from django.contrib import messages
from django.db import transaction, IntegrityError
from django.db.models import Count
from django.shortcuts import render, redirect, get_object_or_404
from datetime import datetime
from .models import Purchase, PurchaseItem
from .forms import PurchaseForm, PurchaseItemFormSet
from suppliers.models import Supplier
from inventory.models import Inventory


def update_inventory_for_item(item, added_quantity, reverse=False):
    """Adjust the inventory stock based on the delivered quantity.
       If reverse=True, we subtract the delivered quantity, otherwise add it."""
    inventory = item.inventory
    if reverse:
        # Reverse the delivery by subtracting the delivered quantity from the stock
        inventory.inventory_stock -= item.delivered_quantity
    else:
        # Add the added quantity to inventory
        inventory.inventory_stock += added_quantity
    inventory.save()


def add_purchase(request):
    if request.method == "POST":
        purchase_form = PurchaseForm(request.POST)
        formset = PurchaseItemFormSet(request.POST, queryset=PurchaseItem.objects.none())

        if purchase_form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    purchase = purchase_form.save(commit=False)
                    today = datetime.now().strftime("%Y%m%d")
                    latest_purchase = Purchase.objects.filter(purchase_code__startswith=f"PUR-{today}").order_by("id").last()
                    next_number = 1 if not latest_purchase else int(latest_purchase.purchase_code.split('-')[-1]) + 1
                    purchase.purchase_code = f"PUR-{today}-{next_number:03d}"
                    purchase.save()

                    total_cost = 0
                    purchase_items = []
                    for form in formset:
                        purchase_item = form.save(commit=False)
                        purchase_item.purchase = purchase
                        if not purchase_item.price:
                            purchase_item.price = purchase_item.inventory.product.purchase_price
                        purchase_item.save()
                        purchase_items.append(purchase_item)
                        total_cost += purchase_item.quantity * purchase_item.price

                    purchase.total_cost = total_cost
                    purchase.save()

                    if purchase.status == 'Delivered':
                        for item in purchase_items:
                            update_inventory_for_item(item, item.quantity)

                return redirect('purchases:purchase_index')

            except IntegrityError as e:
                messages.error(request, f"Error saving purchase: {e}")
        else:
            messages.error(request, "There was an error with the form submission.")

    else:
        purchase_form = PurchaseForm()
        formset = PurchaseItemFormSet(queryset=PurchaseItem.objects.none())

    suppliers = Supplier.objects.all()
    inventories = Inventory.objects.all()

    return render(request, 'purchases/add_purchase.html', {
        'purchase_form': purchase_form,
        'formset': formset,
        'suppliers': suppliers,
        'inventories': inventories,
    })


def change_purchase_status(request, id):
    if request.method == 'POST':
        purchase = get_object_or_404(Purchase, id=id)
        new_status = request.POST.get('status')

        try:
            with transaction.atomic():
                if new_status == 'Pending':
                    # Reset delivered quantities and subtract from inventory
                    for item in purchase.items.all():
                        if item.delivered_quantity > 0:
                            update_inventory_for_item(item, -item.delivered_quantity, reverse=True)
                            item.delivered_quantity = 0
                            item.save()
                    purchase.status = 'Pending'

                elif new_status == 'Partially Delivered':
                    for item in purchase.items.all():
                        delivered_key = f"delivered_quantity_{item.id}"
                        try:
                            newly_delivered_quantity = int(request.POST.get(delivered_key, 0))
                        except ValueError:
                            messages.error(request, f"Invalid input for {item.inventory.product.product_name}.")
                            continue

                        remaining_quantity = item.quantity - item.delivered_quantity

                        if newly_delivered_quantity > remaining_quantity:
                            messages.error(
                                request,
                                f"Cannot deliver more than the remaining quantity for {item.inventory.product.product_name}. "
                                f"Ordered: {item.quantity}, Already Delivered: {item.delivered_quantity}, Remaining: {remaining_quantity}."
                            )
                            continue
                        elif newly_delivered_quantity < 0:
                            messages.error(
                                request,
                                f"Invalid delivery quantity for {item.inventory.product.product_name}. Must be 0 or greater."
                            )
                            continue
                        else:
                            # Increment delivered quantity
                            update_inventory_for_item(item, newly_delivered_quantity)
                            item.delivered_quantity += newly_delivered_quantity
                            item.save()

                    purchase.status = 'Partially Delivered'

                elif new_status == 'Delivered':
                    # Fully deliver all items
                    for item in purchase.items.all():
                        if item.delivered_quantity < item.quantity:
                            remaining_quantity = item.quantity - item.delivered_quantity
                            update_inventory_for_item(item, remaining_quantity)
                            item.delivered_quantity = item.quantity
                            item.save()
                    purchase.status = 'Delivered'

                purchase.save()
                messages.success(request, f"Purchase {purchase.purchase_code} status updated to {new_status}.")

        except Exception as e:
            messages.error(request, f"Error updating status: {e}")

    return redirect('purchases:purchase_index')


def purchase_index(request):
    purchases = Purchase.objects.annotate(product_count=Count('items'))
    for purchase in purchases:
        for item in purchase.items.all():
            item.remaining_quantity = item.quantity - item.delivered_quantity
    return render(request, 'purchases/index.html', {'purchases': purchases})


def purchase_detail(request, id):
    purchase = get_object_or_404(Purchase, id=id)
    return render(request, 'purchases/purchase_detail.html', {'purchase': purchase})
