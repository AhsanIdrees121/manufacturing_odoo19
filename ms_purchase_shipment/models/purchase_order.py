from odoo import api, fields, models, _
from odoo.exceptions import UserError

SHIPMENT_STATE_SELECTION = [
    ('draft', 'Draft'),
    ('pending', 'Pending Dispatch'),
    ('enroute', 'Enroute'),
    ('overdue', 'Overdue'),
    ('arrived', 'Arrived'),
    ('cleared', 'Cleared'),
]


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    shipment_ids = fields.One2many(
        'purchase.shipment',
        'purchase_id',
        string='Shipments',
    )
    shipment_count = fields.Integer(
        string='Shipment Count',
        compute='_compute_shipment_count',
    )
    shipment_status = fields.Selection(
        selection=SHIPMENT_STATE_SELECTION,
        string='Shipment Status',
        compute='_compute_shipment_status',
        store=True,
    )

    def _compute_shipment_count(self):
        for order in self:
            order.shipment_count = len(order.shipment_ids)

    @api.depends('shipment_ids.state')
    def _compute_shipment_status(self):
        for order in self:
            shipments = order.shipment_ids
            if not shipments:
                order.shipment_status = False
            elif len(shipments) == 1:
                order.shipment_status = shipments.state
            else:
                # Show the most "active" state among multiple shipments
                priority = ['draft', 'pending', 'enroute', 'overdue', 'arrived', 'cleared']
                order.shipment_status = min(
                    shipments.mapped('state'),
                    key=lambda s: priority.index(s),
                )

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

    def action_create_shipment(self):
        self.ensure_one()
        if self.shipment_ids:
            raise UserError(_(
                "A shipment already exists for this purchase order (%s). "
                "You cannot create another one.",
                self.shipment_ids[0].name,
            ))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.shipment',
            'view_mode': 'form',
            'views': [(
                self.env.ref('ms_purchase_shipment.purchase_shipment_form_view').id,
                'form',
            )],
            'context': {
                'default_vendor_id': self.partner_id.id,
                'default_purchase_id': self.id,
            },
            'target': 'current',
        }
