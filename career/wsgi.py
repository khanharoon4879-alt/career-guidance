"""
WSGI config for career project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'career.settings')

application = get_wsgi_application()
app = application

# Auto-apply database migrations on startup so auth_user and other tables are always created
try:
    from django.core.management import call_command
    call_command('migrate', interactive=False)
    print("Database migrations applied successfully on startup.")
except Exception as e:
    print(f"Startup migration notice: {e}")
