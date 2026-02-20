from collections import OrderedDict

from odoo import http, _
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.portal.controllers import portal
from odoo.addons.portal.controllers.portal import pager as portal_pager


# Allowed one-step transitions for portal users
_PORTAL_NEXT_STATE = {
    'draft': 'pending',
    'pending': 'enroute',
    'enroute': 'arrived',
    'overdue': 'arrived',
    'arrived': 'cleared',
}
_PORTAL_PREV_STATE = {
    'pending': 'draft',
    'enroute': 'pending',
    'overdue': 'enroute',
    'arrived': 'enroute',
    'cleared': 'arrived',
}


class CustomerPortal(portal.CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'shipment_count' in counters:
            Shipment = request.env['purchase.shipment']
            values['shipment_count'] = (
                Shipment.search_count([])
                if Shipment.has_access('read') else 0
            )
        return values

    def _get_shipment_searchbar_sortings(self):
        return {
            'date': {'label': _('Newest'), 'order': 'create_date desc, id desc'},
            'name': {'label': _('Reference'), 'order': 'name asc, id asc'},
            'eta': {'label': _('ETA'), 'order': 'eta asc, id asc'},
            'state': {'label': _('Status'), 'order': 'state asc, id asc'},
        }

    def _get_shipment_searchbar_filters(self):
        return {
            'all': {'label': _('All'), 'domain': []},
            'draft': {'label': _('Draft'), 'domain': [('state', '=', 'draft')]},
            'pending': {'label': _('Pending Dispatch'), 'domain': [('state', '=', 'pending')]},
            'enroute': {'label': _('Enroute'), 'domain': [('state', '=', 'enroute')]},
            'overdue': {'label': _('Overdue'), 'domain': [('state', '=', 'overdue')]},
            'arrived': {'label': _('Arrived'), 'domain': [('state', '=', 'arrived')]},
            'cleared': {'label': _('Cleared'), 'domain': [('state', '=', 'cleared')]},
        }

    @http.route(
        ['/my/shipments', '/my/shipments/page/<int:page>'],
        type='http', auth='user', website=True,
    )
    def portal_my_shipments(self, page=1, sortby=None, filterby=None, **kw):
        Shipment = request.env['purchase.shipment']
        values = self._prepare_portal_layout_values()
        domain = []

        searchbar_sortings = self._get_shipment_searchbar_sortings()
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        searchbar_filters = self._get_shipment_searchbar_filters()
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']

        count = Shipment.search_count(domain)
        pager = portal_pager(
            url='/my/shipments',
            url_args={'sortby': sortby, 'filterby': filterby},
            total=count,
            page=page,
            step=self._items_per_page,
        )
        shipments = Shipment.search(
            domain,
            order=order,
            limit=self._items_per_page,
            offset=pager['offset'],
        )
        request.session['my_shipments_history'] = shipments.ids[:100]

        values.update({
            'shipments': shipments.sudo(),
            'page_name': 'shipments',
            'pager': pager,
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'searchbar_filters': OrderedDict(sorted(searchbar_filters.items())),
            'filterby': filterby,
            'default_url': '/my/shipments',
        })
        return request.render('ms_purchase_shipment.portal_my_shipments', values)

    @http.route(
        ['/my/shipments/<int:shipment_id>'],
        type='http', auth='user', website=True,
    )
    def portal_my_shipment_detail(self, shipment_id, **kw):
        try:
            shipment_sudo = self._document_check_access(
                'purchase.shipment', shipment_id,
            )
        except (AccessError, MissingError):
            return request.redirect('/my')

        state_labels = dict(shipment_sudo._fields['state'].selection)
        current = shipment_sudo.state
        next_state = _PORTAL_NEXT_STATE.get(current)
        prev_state = _PORTAL_PREV_STATE.get(current)

        values = {
            'shipment': shipment_sudo,
            'page_name': 'shipment',
            'next_state': next_state,
            'next_state_label': state_labels.get(next_state, ''),
            'prev_state': prev_state,
            'prev_state_label': state_labels.get(prev_state, ''),
        }
        values.update(self._get_page_view_values(
            shipment_sudo, False, values, 'my_shipments_history', False,
        ))
        return request.render('ms_purchase_shipment.portal_my_shipment_detail', values)

    @http.route(
        ['/my/shipments/<int:shipment_id>/update_state'],
        type='http', auth='user', website=True, methods=['POST'],
    )
    def portal_shipment_update_state(self, shipment_id, new_state, **kw):
        try:
            shipment_sudo = self._document_check_access(
                'purchase.shipment', shipment_id,
            )
        except (AccessError, MissingError):
            return request.redirect('/my')

        current = shipment_sudo.state
        allowed_next = _PORTAL_NEXT_STATE.get(current)
        allowed_prev = _PORTAL_PREV_STATE.get(current)
        if new_state in (allowed_next, allowed_prev):
            shipment_sudo.sudo().write({'state': new_state})

        return request.redirect('/my/shipments/%s' % shipment_id)
