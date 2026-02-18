{
    'name': 'Purchase Shipment',
    'version': '19.0.1.0.0',
    'category': 'Supply Chain/Purchase',
    'summary': 'Track and manage inbound shipments for purchase orders',
    'description': """
Purchase Shipment Management
=============================
Introduces shipment-level management for purchase orders, allowing
organizations to track inbound logistics independently of standard
stock picking workflows.

Features:
- Create shipment records linked to one or more purchase orders
- Track shipment lifecycle: Draft > Pending > Enroute > Arrived > Cleared
- Partial shipment support with quantity validation
- ETA monitoring with automatic overdue detection
- Smart buttons for linked POs, receipts, and vendor bills
- Chatter integration for full audit trail
    """,
    'author': 'MountSol',
    'depends': ['purchase_stock'],
    'data': [
        'security/purchase_shipment_security.xml',
        'security/ir.model.access.csv',
        'data/purchase_shipment_data.xml',
        'views/purchase_shipment_views.xml',
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
