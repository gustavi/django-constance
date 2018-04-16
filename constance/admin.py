from collections import OrderedDict
from datetime import datetime, date
from operator import itemgetter

from django import forms, VERSION
from django.apps import apps
from django.conf.urls import url
from django.contrib import admin, messages
from django.contrib.admin.options import csrf_protect_m
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.utils.formats import localize
from django.utils.translation import ugettext_lazy as _

from constance.forms import ConstanceForm
from . import LazyConfig, settings


config = LazyConfig()


def get_values():
    """
    Get dictionary of values from the backend
    :return:
    """

    # First load a mapping between config name and default value
    default_initial = ((name, options[0])
                       for name, options in settings.CONFIG.items())
    # Then update the mapping with actually values from the backend
    initial = dict(default_initial, **dict(config._backend.mget(settings.CONFIG)))

    return initial


class ConstanceAdmin(admin.ModelAdmin):
    change_list_template = 'admin/constance/change_list.html'
    change_list_form = ConstanceForm

    def get_urls(self):
        info = self.model._meta.app_label, self.model._meta.module_name
        return [
            url(r'^$',
                self.admin_site.admin_view(self.changelist_view),
                name='%s_%s_changelist' % info),
            url(r'^$',
                self.admin_site.admin_view(self.changelist_view),
                name='%s_%s_add' % info),
        ]

    def get_config_value(self, name, options, form, initial):
        default, help_text = options[0], options[1]
        # First try to load the value from the actual backend
        value = initial.get(name)
        # Then if the returned value is None, get the default
        if value is None:
            value = getattr(config, name)
        config_value = {
            'name': name,
            'default': localize(default),
            'raw_default': default,
            'help_text': _(help_text),
            'value': localize(value),
            'modified': localize(value) != localize(default),
            'form_field': form[name],
            'is_date': isinstance(default, date),
            'is_datetime': isinstance(default, datetime),
            'is_checkbox': isinstance(form[name].field.widget, forms.CheckboxInput),
            'is_file': isinstance(form[name].field.widget, forms.FileInput),
        }

        return config_value

    def get_changelist_form(self, request):
        """
        Returns a Form class for use in the changelist_view.
        """
        # Defaults to self.change_list_form in order to preserve backward
        # compatibility
        return self.change_list_form

    @csrf_protect_m
    def changelist_view(self, request, extra_context=None):
        if not self.has_change_permission(request, None):
            raise PermissionDenied
        initial = get_values()
        form_cls = self.get_changelist_form(request)
        form = form_cls(initial=initial)
        if request.method == 'POST':
            form = form_cls(
                data=request.POST, files=request.FILES, initial=initial
            )
            if form.is_valid():
                form.save()
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    _('Live settings updated successfully.'),
                )
                return HttpResponseRedirect('.')
        context = dict(
            self.admin_site.each_context(request),
            config_values=[],
            title=self.model._meta.app_config.verbose_name,
            app_label='constance',
            opts=self.model._meta,
            form=form,
            media=self.media + form.media,
            icon_type='gif' if VERSION < (1, 9) else 'svg',
        )
        for name, options in settings.CONFIG.items():
            context['config_values'].append(
                self.get_config_value(name, options, form, initial)
            )

        if settings.CONFIG_FIELDSETS:
            context['fieldsets'] = []
            for fieldset_title, fields_list in settings.CONFIG_FIELDSETS.items():
                fields_exist = all(field in settings.CONFIG for field in fields_list)
                assert fields_exist, "CONSTANCE_CONFIG_FIELDSETS contains field(s) that does not exist"
                config_values = []

                for name in fields_list:
                    options = settings.CONFIG.get(name)
                    if options:
                        config_values.append(
                            self.get_config_value(name, options, form, initial)
                        )

                context['fieldsets'].append({
                    'title': fieldset_title,
                    'config_values': config_values
                })
            if not isinstance(settings.CONFIG_FIELDSETS, OrderedDict):
                context['fieldsets'].sort(key=itemgetter('title'))

        if not isinstance(settings.CONFIG, OrderedDict):
            context['config_values'].sort(key=itemgetter('name'))
        request.current_app = self.admin_site.name
        return TemplateResponse(request, self.change_list_template, context)

    def has_add_permission(self, *args, **kwargs):
        return False

    def has_delete_permission(self, *args, **kwargs):
        return False

    def has_change_permission(self, request, obj=None):
        if settings.SUPERUSER_ONLY:
            return request.user.is_superuser
        return super(ConstanceAdmin, self).has_change_permission(request, obj)


class Config(object):
    class Meta(object):
        app_label = 'constance'
        object_name = 'Config'
        model_name = module_name = 'config'
        verbose_name_plural = _('config')
        abstract = False
        swapped = False

        def get_ordered_objects(self):
            return False

        def get_change_permission(self):
            return 'change_%s' % self.model_name

        @property
        def app_config(self):
            return apps.get_app_config(self.app_label)

        @property
        def label(self):
            return '%s.%s' % (self.app_label, self.object_name)

        @property
        def label_lower(self):
            return '%s.%s' % (self.app_label, self.model_name)

    _meta = Meta()


admin.site.register([Config], ConstanceAdmin)
