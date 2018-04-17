from datetime import datetime, date, time, timedelta
from decimal import Decimal
import hashlib
import os

from django import forms
from django.conf import settings as django_settings
from django.contrib.admin import widgets
from django.core.exceptions import FieldError, ImproperlyConfigured
from django.forms import ALL_FIELDS, fields
from django.forms.forms import DeclarativeFieldsMetaclass
from django.utils import six
from django.utils.encoding import smart_bytes
from django.utils.module_loading import import_string
from django.utils.translation import ugettext_lazy as _

from . import LazyConfig, settings


config = LazyConfig()


NUMERIC_WIDGET = forms.TextInput(attrs={'size': 10})

INTEGER_LIKE = (fields.IntegerField, {'widget': NUMERIC_WIDGET})
STRING_LIKE = (fields.CharField, {
    'widget': forms.Textarea(attrs={'rows': 3}),
    'required': False,
})

FIELDS = {
    bool: (fields.BooleanField, {'required': False}),
    int: INTEGER_LIKE,
    Decimal: (fields.DecimalField, {'widget': NUMERIC_WIDGET}),
    str: STRING_LIKE,
    datetime: (
        fields.SplitDateTimeField, {'widget': widgets.AdminSplitDateTime}
    ),
    timedelta: (
        fields.DurationField, {'widget': widgets.AdminTextInputWidget}
    ),
    date: (fields.DateField, {'widget': widgets.AdminDateWidget}),
    time: (fields.TimeField, {'widget': widgets.AdminTimeWidget}),
    float: (fields.FloatField, {'widget': NUMERIC_WIDGET}),
}


def parse_additional_fields(fields):
    for key in fields:
        field = list(fields[key])

        if len(field) == 1:
            field.append({})

        field[0] = import_string(field[0])

        if 'widget' in field[1]:
            klass = import_string(field[1]['widget'])
            field[1]['widget'] = klass(
                **(field[1].get('widget_kwargs', {}) or {})
            )

            if 'widget_kwargs' in field[1]:
                del field[1]['widget_kwargs']

        fields[key] = field

    return fields


FIELDS.update(parse_additional_fields(settings.ADDITIONAL_FIELDS))

if not six.PY3:
    FIELDS.update({
        long: INTEGER_LIKE,
        unicode: STRING_LIKE,
    })


class ConstanceOptions(object):
    def __init__(self, options=None):
        self.fields = getattr(options, 'fields', None)
        self.exclude = getattr(options, 'exclude', None)


class ConstanceMetaclass(DeclarativeFieldsMetaclass):
    def __new__(mcs, name, bases, attrs):
        new_class = super(ConstanceMetaclass, mcs).__new__(mcs, name, bases, attrs)

        opts = new_class._meta = ConstanceOptions(getattr(new_class, 'Meta', None))
        # We check if a string was passed to `fields` or `exclude`,
        # which is likely to be a mistake where the user typed ('foo') instead
        # of ('foo',)
        for opt in ['fields', 'exclude']:
            value = getattr(opts, opt)
            if isinstance(value, six.string_types) and value != ALL_FIELDS:
                msg = ("%(model)s.Meta.%(opt)s cannot be a string. "
                       "Did you mean to type: ('%(value)s',)?" % {
                           'model': new_class.__name__,
                           'opt': opt,
                           'value': value,
                       })

                raise TypeError(msg)

        base_fields = dict()

        if opts.fields is not None and opts.fields != ALL_FIELDS:
            for field in opts.fields:
                if field in settings.CONFIG.keys():
                    base_fields[field] = None
                else:
                    message = "Unknown field '%s' specified for %s"
                    message = message % (field, new_class.__name__)
                    raise FieldError(message)

        else:
            base_fields = settings.CONFIG

        new_class.base_fields = base_fields

        return new_class


class BaseConstanceForm(forms.Form):
    version = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, initial, *args, **kwargs):
        super(BaseConstanceForm, self).__init__(*args, initial=initial, **kwargs)
        version_hash = hashlib.md5()

        for name, options in settings.CONFIG.items():
            if name not in self.base_fields:
                continue

            default = options[0]
            if len(options) == 3:
                config_type = options[2]
                if config_type not in settings.ADDITIONAL_FIELDS and not isinstance(default, config_type):
                    raise ImproperlyConfigured(_("Default value type must be "
                                                 "equal to declared config "
                                                 "parameter type. Please fix "
                                                 "the default value of "
                                                 "'%(name)s'.")
                                               % {'name': name})
            else:
                config_type = type(default)

            if config_type not in FIELDS:
                raise ImproperlyConfigured(_("Constance doesn't support "
                                             "config values of the type "
                                             "%(config_type)s. Please fix "
                                             "the value of '%(name)s'.")
                                           % {'config_type': config_type,
                                              'name': name})
            field_class, kwargs = FIELDS[config_type]
            self.fields[name] = field_class(label=name, **kwargs)

            version_hash.update(smart_bytes(initial.get(name, '')))
        self.initial['version'] = version_hash.hexdigest()

    def save(self):
        for file_field in self.files:
            file = self.cleaned_data[file_field]
            file_path = os.path.join(django_settings.MEDIA_ROOT, file.name)
            with open(file_path, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
                self.cleaned_data[file_field] = file.name

        for name in settings.CONFIG:
            if getattr(config, name) != self.cleaned_data[name]:
                setattr(config, name, self.cleaned_data[name])

    def clean_version(self):
        value = self.cleaned_data['version']

        if settings.IGNORE_ADMIN_VERSION_CHECK:
            return value

        if value != self.initial['version']:
            raise forms.ValidationError(_('The settings have been modified '
                                          'by someone else. Please reload the '
                                          'form and resubmit your changes.'))
        return value

    def clean(self):
        cleaned_data = super(BaseConstanceForm, self).clean()

        if not settings.CONFIG_FIELDSETS:
            return cleaned_data

        field_name_list = []
        for fieldset_title, fields_list in settings.CONFIG_FIELDSETS.items():
            for field_name in fields_list:
                field_name_list.append(field_name)
        if field_name_list and set(set(settings.CONFIG.keys()) - set(field_name_list)):
            raise forms.ValidationError(_('CONSTANCE_CONFIG_FIELDSETS is missing '
                                          'field(s) that exists in CONSTANCE_CONFIG.'))

        return cleaned_data


class ConstanceForm(six.with_metaclass(ConstanceMetaclass, BaseConstanceForm)):
    pass
