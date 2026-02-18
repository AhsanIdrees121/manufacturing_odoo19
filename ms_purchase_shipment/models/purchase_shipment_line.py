from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PurchaseShipmentLine(models.Model):
    _name = 'purchase.shipment.line'
    _description = 'Purchase Shipment Line'

    shipment_id = fields.Many2one(
        'purchase.shipment',
        string='Shipment',
        required=True,
        ondelete='cascade',
        index=True,
    )
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        required=True,
    )
    po_line_id = fields.Many2one(
        'purchase.order.line',
        string='PO Line',
        required=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        related='po_line_id.product_id',
        store=True,
        readonly=True,
    )
    qty_ordered = fields.Float(
        string='Qty Ordered',
        related='po_line_id.product_qty',
        readonly=True,
    )
    qty_shipped = fields.Float(
        string='Qty Shipped',
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='UoM',
        related='po_line_id.product_uom_id',
        store=True,
        readonly=True,
    )
    price_unit = fields.Float(
        string='Unit Price',
        related='po_line_id.price_unit',
        readonly=True,
    )

    @api.constrains('qty_shipped')
    def _check_qty_shipped(self):
        for line in self:
            if line.qty_shipped < 0:
                raise ValidationError(_(
                    "Shipped quantity cannot be negative for product '%s'.",
                    line.product_id.display_name,
                ))
            if line.qty_ordered and line.qty_shipped > line.qty_ordered:
                raise ValidationError(_(
                    "Shipped quantity (%(shipped)s) cannot exceed ordered quantity "
                    "(%(ordered)s) for product '%(product)s'.",
                    shipped=line.qty_shipped,
                    ordered=line.qty_ordered,
                    product=line.product_id.display_name,
                ))

    @api.onchange('purchase_order_id')
    def _onchange_purchase_order_id(self):
        self.po_line_id = False
