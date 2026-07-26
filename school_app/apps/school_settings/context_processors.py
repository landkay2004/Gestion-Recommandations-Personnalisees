from .models import SchoolInfo


def school_info(request):
    return {'school_info': SchoolInfo.get_info()}
