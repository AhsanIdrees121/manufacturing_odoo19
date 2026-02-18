from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PurchaseShipment(models.Model):
    _name = 'purchase.shipment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Purchase Shipment'
    _order = 'name desc'
    _sql_constraints = [
        ('purchase_id_unique', 'UNIQUE(purchase_id)',
         'A shipment already exists for this purchase order. You cannot create another one.'),
    ]

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default='New',
        index='trigram',
    )
    vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        required=True,
        tracking=True,
        check_company=True,
        domain="[('is_company', '=', True)]",
    )
    carrier_name = fields.Char(
        string='Carrier',
        tracking=True,
    )
    purchase_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        tracking=True,
    )
    shipment_line_ids = fields.One2many(
        'purchase.shipment.line',
        'shipment_id',
        string='Shipment Lines',
        copy=True,
    )
    dispatch_date = fields.Date(
        string='Dispatch Date',
        tracking=True,
    )
    eta = fields.Date(
        string='Expected Arrival',
        tracking=True,
    )
    arrival_date = fields.Date(
        string='Actual Arrival',
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('pending', 'Pending Dispatch'),
            ('enroute', 'Enroute'),
            ('overdue', 'Overdue'),
            ('arrived', 'Arrived'),
            ('cleared', 'Cleared'),
        ],
        string='Status',
        default='draft',
        required=True,
        copy=False,
        tracking=True,
    )
    notes = fields.Html(string='Notes')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    # Computed fields for smart buttons
    picking_ids = fields.Many2many(
        'stock.picking',
        string='Receipts',
        compute='_compute_picking_ids',
    )
    picking_count = fields.Integer(
        string='Receipt Count',
        compute='_compute_picking_ids',
    )
    invoice_ids = fields.Many2many(
        'account.move',
        string='Vendor Bills',
        compute='_compute_invoice_ids',
    )
    invoice_count = fields.Integer(
        string='Bill Count',
        compute='_compute_invoice_ids',
    )

    @api.depends('purchase_id.picking_ids')
    def _compute_picking_ids(self):
        for shipment in self:
            shipment.picking_ids = shipment.purchase_id.picking_ids
            shipment.picking_count = len(shipment.picking_ids)

    @api.depends('purchase_id.invoice_ids')
    def _compute_invoice_ids(self):
        for shipment in self:
            shipment.invoice_ids = shipment.purchase_id.invoice_ids
            shipment.invoice_count = len(shipment.invoice_ids)

    @api.onchange('purchase_id')
    def _onchange_purchase_id(self):
        """Auto-populate shipment lines from selected purchase order."""
        if not self.purchase_id:
            self.shipment_line_ids = [fields.Command.clear()]
            return
        self.vendor_id = self.purchase_id.partner_id
        existing_po_line_ids = set(self.shipment_line_ids.mapped('po_line_id').ids)
        new_lines = []
        for line in self.purchase_id.order_line:
            if line.display_type or line.id in existing_po_line_ids:
                continue
            new_lines.append(fields.Command.create({
                'purchase_order_id': self.purchase_id.id,
                'po_line_id': line.id,
                'qty_shipped': line.product_qty,
            }))
        # Remove lines that don't belong to current PO
        for line in self.shipment_line_ids:
            if line.purchase_order_id != self.purchase_id:
                new_lines.append(fields.Command.delete(line.id))
        if new_lines:
            self.update({'shipment_line_ids': new_lines})

    @api.constrains('dispatch_date', 'eta')
    def _check_dates(self):
        for shipment in self:
            if shipment.dispatch_date and shipment.eta and shipment.eta < shipment.dispatch_date:
                raise UserError(_("Expected Arrival date cannot be before Dispatch Date."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('purchase.shipment') or 'New'
        return super().create(vals_list)

    def action_confirm(self):
        for shipment in self:
            if not shipment.shipment_line_ids:
                raise UserError(_("You cannot confirm a shipment without lines."))
            if not shipment.vendor_id:
                raise UserError(_("Please set a vendor before confirming."))
        self.write({'state': 'pending'})

    def action_dispatch(self):
        for shipment in self:
            if not shipment.dispatch_date:
                shipment.dispatch_date = fields.Date.today()
        self.write({'state': 'enroute'})

    def action_arrive(self):
        for shipment in self:
            if not shipment.arrival_date:
                shipment.arrival_date = fields.Date.today()
        self.write({'state': 'arrived'})

    def action_clear(self):
        for shipment in self:
            if shipment.state != 'arrived':
                raise UserError(_("Only arrived shipments can be cleared."))
            pickings = shipment.picking_ids
            if pickings and any(p.state != 'done' for p in pickings):
                raise UserError(_(
                    "All receipts linked to this shipment must be completed "
                    "before clearing. Check the Receipts smart button for "
                    "shipment '%s'.", shipment.name
                ))
        self.write({'state': 'cleared'})

    def action_reset_draft(self):
        if not self.env.user.has_group('purchase.group_purchase_manager'):
            raise UserError(_("Only Purchase Managers can reset shipments to draft."))
        self.write({'state': 'draft', 'arrival_date': False})

    @api.model
    def _cron_check_overdue(self):
        overdue_shipments = self.search([
            ('state', '=', 'enroute'),
            ('eta', '<', fields.Date.today()),
        ])
        if overdue_shipments:
            overdue_shipments.write({'state': 'overdue'})

    def action_view_purchase_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'res_id': self.purchase_id.id,
            'views': [(self.env.ref('purchase.purchase_order_form').id, 'form')],
        }

    def action_view_pickings(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'stock.action_picking_tree_all'
        )
        if len(self.picking_ids) == 1:
            action['views'] = [(
                self.env.ref('stock.view_picking_form').id,
                'form',
            )]
            action['res_id'] = self.picking_ids.id
        else:
            action['domain'] = [('id', 'in', self.picking_ids.ids)]
        return action

    def action_view_invoices(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'account.action_move_in_invoice_type'
        )
        if len(self.invoice_ids) == 1:
            action['views'] = [(
                self.env.ref('account.view_move_form').id,
                'form',
            )]
            action['res_id'] = self.invoice_ids.id
        else:
            action['domain'] = [('id', 'in', self.invoice_ids.ids)]
        return action
