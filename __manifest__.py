{
    'name': 'Library Manager',
    'version': '17.0.1.0.0',
    'category': 'Services',
    'summary': 'Module for managing books, authors, and loans',
    'author': 'Jose Miguel',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/library_views.xml',
    ],
    'installable': True,
    'application': True,
}