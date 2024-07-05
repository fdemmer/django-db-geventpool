from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.db import connection
from django.test import SimpleTestCase

from .models import TestModel

class GisTestModel(TestModel):
    pointfield = models.PointField()

class GisModelTest(SimpleTestCase):
    databases = {"default"}

    def test_gis_connection(self):
        data = {
            "charfield": "testing save",
            "jsonfield": {"test": "value"},
            "pointfield": Point(0, 0),
        }

        with connection.pool.get() as connection.connection:
            pk = GisTestModel.objects.create(**data).pk

            obj = GisTestModel.objects.get(pk=pk)
            for key in data.keys():
                self.assertEqual(data[key], getattr(obj, key))