from django.apps import AppConfig
import os

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # சர்வர் ஸ்டார்ட் ஆகும்போது இதை ரன் பண்ணும்
        from django.contrib.auth.models import User
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@grandmart.com', 'admin123')
            print("Superuser 'admin' created automatically!")
