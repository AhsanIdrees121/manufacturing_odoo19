from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    shipment_ids = fields.Many2many(
        'purchase.shipment',
        'purchase_shipment_purchase_order_rel',
        'purchase_order_id',
        'shipment_id',
        string='Shipments',
    )
    shipment_count = fields.Integer(
        string='Shipment Count',
        compute='_compute_shipment_count',
    )

    def _compute_shipment_count(self):
        for order in self:
            order.shipment_count = len(order.shipment_ids)

    def action_view_shipments(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'ms_purchase_shipment.action_purchase_shipment'
        )
        if len(self.shipment_ids) == 1:
            action['views'] = [(
                self.env.ref('ms_purchase_shipment.purchase_shipment_form_view').id,
                'form',
            )]
            action['res_id'] = self.shipment_ids.id
        else:
            action['domain'] = [('id', 'in', self.shipment_ids.ids)]
        return action
