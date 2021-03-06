# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2019-07-20 21:45
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('zues', '0004_auto_20180701_1312'),
    ]

    operations = [
        migrations.AlterField(
            model_name='actuelepolitiekemotie',
            name='site',
            field=models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, to='sites.Site'),
        ),
        migrations.AlterField(
            model_name='amendement',
            name='site',
            field=models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, to='sites.Site'),
        ),
        migrations.AlterField(
            model_name='categorie',
            name='site',
            field=models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, to='sites.Site'),
        ),
        migrations.AlterField(
            model_name='hrwijziging',
            name='site',
            field=models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, to='sites.Site'),
        ),
        migrations.AlterField(
            model_name='login',
            name='site',
            field=models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, to='sites.Site'),
        ),
        migrations.AlterField(
            model_name='organimo',
            name='site',
            field=models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, to='sites.Site'),
        ),
        migrations.AlterField(
            model_name='politiekemotie',
            name='site',
            field=models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, to='sites.Site'),
        ),
        migrations.AlterField(
            model_name='resolutie',
            name='site',
            field=models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, to='sites.Site'),
        ),
        migrations.AlterField(
            model_name='settings',
            name='site',
            field=models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, to='sites.Site'),
        ),
    ]
