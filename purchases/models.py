from django.db import models
from suppliers.models import Supplier
from inventory.models import Inventory
import uuid

class Purchase(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Partially Delivered', 'Partially Delivered'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
    ]

    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='purchases')
    date = models.DateTimeField(auto_now_add=True)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    purchase_code = models.CharField(max_length=20, unique=True, editable=False, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')

    def __str__(self):
        return f"Purchase {self.purchase_code} from {self.supplier.name} on {self.date}"

    def save(self, *args, **kwargs):
        if not self.purchase_code:  # Generate code only if it doesn't exist
            self.purchase_code = f"PUR-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='items')
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name='purchase_items')
    quantity = models.PositiveIntegerField(default=0)
    delivered_quantity = models.PositiveIntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    def __str__(self):
        return f"{self.inventory.product.product_name} ({self.quantity})"

    def save(self, *args, **kwargs):
        if not self.price:
            self.price = self.inventory.product.purchase_price
        super().save(*args, **kwargs)