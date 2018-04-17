from constance.admin import ConstanceForm
from django.core.exceptions import FieldError
from django.forms import fields
from django.test import TestCase


class TestForm(TestCase):

    def test_form_field_types(self):

        f = ConstanceForm({})

        self.assertIsInstance(f.fields['INT_VALUE'], fields.IntegerField)
        self.assertIsInstance(f.fields['LONG_VALUE'], fields.IntegerField)
        self.assertIsInstance(f.fields['BOOL_VALUE'], fields.BooleanField)
        self.assertIsInstance(f.fields['STRING_VALUE'], fields.CharField)
        self.assertIsInstance(f.fields['UNICODE_VALUE'], fields.CharField)
        self.assertIsInstance(f.fields['DECIMAL_VALUE'], fields.DecimalField)
        self.assertIsInstance(f.fields['DATETIME_VALUE'], fields.SplitDateTimeField)
        self.assertIsInstance(f.fields['TIMEDELTA_VALUE'], fields.DurationField)
        self.assertIsInstance(f.fields['FLOAT_VALUE'], fields.FloatField)
        self.assertIsInstance(f.fields['DATE_VALUE'], fields.DateField)
        self.assertIsInstance(f.fields['TIME_VALUE'], fields.TimeField)

        # from CONSTANCE_ADDITIONAL_FIELDS
        self.assertIsInstance(f.fields['CHOICE_VALUE'], fields.ChoiceField)
        self.assertIsInstance(f.fields['EMAIL_VALUE'], fields.EmailField)

    def test_form_fields_attr_str(self):
        """
        Invalid "fields" parameter (str).
        """
        try:
            class MyCustomForm(ConstanceForm):
                class Meta:
                    fields = 'abc'
            self.fail()
        except TypeError:
            pass

    def test_form_fields_attr_invalid(self):
        """
        Invalid values in "fields" parameter.
        """
        try:
            class MyCustomForm(ConstanceForm):
                class Meta:
                    fields = ('john', 'doe', 'INT_VALUE')
            self.fail()
        except FieldError:
            pass

    def test_form_fields_attr(self):
        # valid with only 3 fields
        class MyCustomForm(ConstanceForm):
            class Meta:
                fields = ('INT_VALUE', 'DATETIME_VALUE', 'EMAIL_VALUE')

        f = MyCustomForm({})

        self.assertEqual(len(f.fields), 3)

        # valid with "fields = '__all__'"
        class MyCustomForm(ConstanceForm):
            class Meta:
                fields = '__all__'

        f = MyCustomForm({})

        self.assertEqual(len(f.fields), 14)
