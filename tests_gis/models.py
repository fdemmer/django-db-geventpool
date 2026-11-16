from django.contrib.gis.db import models


class TestPlace(models.Model):
    point = models.PointField()

    def __str__(self):
        return str(self.pk)
