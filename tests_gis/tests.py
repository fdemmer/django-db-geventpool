from django.contrib.gis.geos import Point
from django.db import connections
from django.test import SimpleTestCase

from .models import TestPlace


class GeometryTest(SimpleTestCase):
    """Connections created by the pool must be able to adapt geometries."""

    databases = {"default"}
    alias = "geometry_test"

    def setUp(self):
        # A wrapper of its own gets a new pool, which creates a new connection;
        # the test database's connection was already set up by prepare_database().
        db = connections["default"].__class__(
            {**connections["default"].settings_dict}, alias=self.alias
        )
        connections[self.alias] = db
        self.addCleanup(connections.__delitem__, self.alias)
        self.addCleanup(db.closeall)
        self.addCleanup(db.close)

    def test_save_point(self):
        place = TestPlace.objects.using(self.alias).create(point=Point(16.37, 48.21))
        place.refresh_from_db(using=self.alias)
        self.assertEqual(place.point.coords, (16.37, 48.21))
        place.delete(using=self.alias)
