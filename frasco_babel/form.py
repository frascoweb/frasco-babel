from frasco import current_context, current_app
from wtforms import SelectField


class LocaleField(SelectField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('choices', current_app.features.babel.available_locales())
        kwargs.setdefault("default", current_context['current_locale'])
        super(LocaleField, self).__init__(*args, **kwargs)


class CurrencyField(SelectField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('choices', [(c[0], c[1]) for c in current_app.features.babel.available_currencies()])
        kwargs.setdefault("default", current_context['current_currency'])
        super(CurrencyField, self).__init__(*args, **kwargs)
