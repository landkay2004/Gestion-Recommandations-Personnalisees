import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from tenants.models import Ecole, AdminEcole
print('ecoles:', list(Ecole.objects.values('id','schema_name','nom','onboarding_complete')[:20]))
print('admin_ecole:', list(AdminEcole.objects.values('id','email','ecole_id','onboarding_step','is_active')[:20]))
