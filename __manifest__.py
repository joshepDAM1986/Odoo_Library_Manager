{
    'name': 'Library Manager',
    'version': '17.0.1.2.0',
    'category': 'Services/Library',
    'summary': 'Module for managing books, authors, and categories',
    'author': 'Jose Miguel',
    'sequence': -100,
    'depends': ['base', 'mail'],
    'data': [
        'security/library_security.xml',
        'security/ir.model.access.csv',
        'views/library_author_views.xml',
        'views/library_book_views.xml',
        'views/library_category_views.xml',
        'views/library_menus.xml',
    ],
    'demo': [
        'data/library_demo_data.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
