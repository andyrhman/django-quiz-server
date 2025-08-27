from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

class QuizInfoListPagination(PageNumberPagination):
    page_size = 10
    page_query_param = "page"

    def get_paginated_response(self, data):
        total = self.page.paginator.count
        last_pg = self.page.paginator.num_pages
        page = self.page.number if total else 1
        return Response({
            "data": data,
            "meta": {
                "total": total,
                "page": page,
                "last_page": last_pg
            }
        })
