from frasco import (Feature, action, hook, set_translation_callbacks, copy_extra_feature_options,\
                    session, request, signal, current_app, command, shell_exec, current_context, json)
from flask_babel import (Babel, gettext, ngettext, lazy_gettext, format_datetime, format_date,\
                             format_time, format_currency as babel_format_currency, get_locale,\
                             get_timezone, refresh as refresh_babel)
from babel import Locale
from flask import _request_ctx_stack
import os
import tempfile
import contextlib
import re


_DEFAULT_CURRENCY = "USD"


def get_currency():
    """Returns the timezone that should be used for this request as
    `pytz.timezone` object.  This returns `None` if used outside of
    a request. If flask-babel was not attached to application, will
    return UTC timezone object.
    """
    ctx = _request_ctx_stack.top
    currency = getattr(ctx, 'babel_currency', None)

    if currency is None:
        babel = ctx.app.extensions.get('babel')

        if babel is None:
            currency = _DEFAULT_CURRENCY
        else:
            if getattr(babel, "currency_selector_func") is None:
                currency = babel.default_currency
            else:
                currency = babel.currency_selector_func()
                if currency is None:
                    currency = babel.default_currency

        ctx.babel_currency = currency

    return currency


def format_currency(number, format=None):
    return babel_format_currency(number, get_currency(), format)


class BabelFeature(Feature):
    name = "babel"
    defaults = {"locales": ["en"],
                "currencies": ["USD"],
                "default_currency": "USD",
                "currency_name_format": u"{name} ({symbol})",
                "store_locale_in_session": True,
                "store_locale_in_user": False,
                "user_locale_column": "locale",
                "user_timezone_column": "timezone",
                "user_currency_column": "currency",
                "extract_locale_from_request": False,
                "always_add_locale_to_urls": True,
                "store_request_locale_in_session": False,
                "request_arg": "locale",
                "extractors": [],
                "extract_jinja_dirs": ["views", "templates", "emails", "features"],
                "extract_with_jinja_exts": ["jinja2.ext.autoescape", "jinja2.ext.with_",
                    "jinja2.ext.do", "frasco.templating.RemoveYamlFrontMatterExtension",
                    "jinja_layout.LayoutExtension", "jinja_macro_tags.LoadMacroExtension",
                    "jinja_macro_tags.CallMacroTagExtension", "jinja_macro_tags.JinjaMacroTagsExtension",
                    "jinja_macro_tags.HtmlMacroTagsExtension", "frasco.templating.FlashMessagesExtension"],
                "request_locale_arg_ignore_endpoints": ["static", "static_upload"],
                "compile_to_json": False,
                "compile_to_js": False,
                "js_catalog_varname": "LOCALE_%s_CATALOG"}

    translation_extracted_signal = signal("translation_extracted")
    translation_updated_signal = signal("translation_updated")
    translation_compiled_signal = signal("translation_compiled")

    def init_app(self, app):
        copy_extra_feature_options(self, app.config, "BABEL_")
        self.extract_dirs = []
        self.app = app

        self.babel = Babel(app)
        self.babel.default_currency = self.options["default_currency"]
        self.babel.localeselector(self.detect_locale)
        self.babel.timezoneselector(self.detect_timezone)
        self.babel.currency_selector_func = self.detect_currency

        set_translation_callbacks(translate=gettext,
                                  ntranslate=ngettext,
                                  lazy_translate=lazy_gettext,
                                  format_datetime=format_datetime,
                                  format_date=format_date,
                                  format_time=format_time)

        app.jinja_env.filters["currencyformat"] = format_currency

        if self.options["store_locale_in_user"]:
            signal('users_init').connect(self.init_user_model)

    def init_user_model(self, sender):
        signal("user_signup").connect(lambda _, user: self.update_user(user), weak=False)
        sender.features.models.ensure_model(sender.features.users.model, **dict([
            (self.options['user_locale_column'], str),
            (self.options['user_timezone_column'], str),
            (self.options['user_currency_column'], str)]))

    def add_extract_dir(self, path, jinja_dirs=None, jinja_exts=None, extractors=None):
        jinja_exts = jinja_exts or []
        jinja_exts.extend(self.options["extract_with_jinja_exts"])
        self.extract_dirs.append((path, jinja_dirs, jinja_exts, extractors))

    def detect_locale(self):
        if self.options["extract_locale_from_request"]:
            if self.options["request_arg"] in request.args:
                locale = request.args[self.options["request_arg"]]
                if self.options["store_request_locale_in_session"]:
                    session["locale"] = locale
                return locale
        if self.options["store_locale_in_user"] and self.app.features.exists("users"):
            if self.app.features.users.logged_in():
                locale = getattr(self.app.features.users.current, self.options["user_locale_column"], None)
                if locale:
                    return locale
        if self.options["store_locale_in_session"] and "locale" in session:
            return session["locale"]
        return request.accept_languages.best_match(self.options["locales"])

    def detect_timezone(self):
        if self.options["store_locale_in_user"] and self.app.features.exists("users"):
            if self.app.features.users.logged_in():
                tz = getattr(self.app.features.users.current, self.options["user_timezone_column"], None)
                if tz:
                    return tz
        if self.options["store_locale_in_session"] and "timezone" in session:
            return session["timezone"]
        return None

    def detect_currency(self):
        if self.options["store_locale_in_user"] and self.app.features.exists("users"):
            if self.app.features.users.logged_in():
                currency = getattr(self.app.features.users.current, self.options["user_currency_column"], None)
                if currency:
                    return currency
        if self.options["store_locale_in_session"] and "currency" in session:
            return session["currency"]
        return None
        
    @hook('url_value_preprocessor')
    def extract_locale_from_values(self, endpoint, values):
        if self.options["extract_locale_from_request"] and values:
            values.pop(self.options["request_arg"], None)
     
    @hook('url_defaults')
    def add_locale_to_url_params(self, endpoint, values):
        if endpoint not in self.options["request_locale_arg_ignore_endpoints"] and \
          self.options["extract_locale_from_request"] and self.options['always_add_locale_to_urls'] and \
          self.options["request_arg"] not in values:
            values[self.options["request_arg"]] = get_locale().language

    @action(default_option="locale")
    def set_locale(self, locale, refresh=False):
        if self.options["store_locale_in_user"] and app.features.exists("users"):
            if app.features.users.logged_in():
                self.update_user(current_app.features.users.current, locale=locale)
                return
        if self.options["store_locale_in_session"]:
            session["locale"] = locale
        if refresh:
            refresh_babel()

    @action(default_option="tz")
    def set_timezone(self, tz):
        if self.options["store_locale_in_user"] and app.features.exists("users"):
            if app.features.users.logged_in():
                self.update_user(current_app.features.users.current, timezone=tz)
                return
        if self.options["store_locale_in_session"]:
            session["timezone"] = tz

    @action(default_option="currency")
    def set_currency(self, currency):
        if self.options["store_locale_in_user"] and app.features.exists("users"):
            if app.features.users.logged_in():
                self.update_user(current_app.features.users.current, currency=currency)
                return
        if self.options["store_locale_in_session"]:
            session["currency"] = currency

    def update_user(self, user, locale=None, timezone=None, currency=None):
        with current_app.features.models.transaction() as tx:
            setattr(user, self.options["user_locale_column"], locale or get_locale().language)
            setattr(user, self.options["user_timezone_column"], timezone or get_timezone().zone)
            setattr(user, self.options["user_currency_column"], currency or get_currency())
            tx.add(user)

    @action('refresh_locale')
    def refresh(self):
        refresh_babel()

    @hook()
    def before_request(self):
        locale = get_locale()
        currency = get_currency()
        current_context["current_locale"] = locale.language
        current_context["current_timezone"] = get_timezone().zone
        current_context["current_currency"] = currency

        current_context["current_language"] = locale.display_name
        current_context["current_currency_name"] = self.options["currency_name_format"].format(
            code=currency,
            name=locale.currencies[currency],
            symbol=locale.currency_symbols[currency])

        if current_app.features.exists('assets'):
            current_app.config['EXPORTED_JS_VARS']['CURRENT_LOCALE'] = {
                "locale": current_context['current_locale'],
                "lang": current_context['current_language'],
                "timezone": current_context['current_timezone'],
                "currency": current_context['current_currency'],
                "currency_name": current_context['current_currency_name']}

            if self.options['compile_to_js']:
                current_app.config['EXPORTED_JS_VARS']['CURRENT_LOCALE']['catalog_var'] = self.options['js_catalog_varname'] % current_context['current_locale'].upper()

    @hook('template_global', _force_call=True)
    def available_locales(self, english_name=False):
        locales = []
        for language in self.options["locales"]:
            locale = Locale(language)
            name = locale.english_name if english_name else locale.display_name
            locales.append((language, name))
        return locales

    @hook('template_global', _force_call=True)
    def available_currencies(self):
        currencies = []
        locale = get_locale()
        for currency in self.options["currencies"]:
            currencies.append((currency, locale.currencies[currency], locale.currency_symbols[currency]))
        return currencies

    @command(pass_script_info=True)
    def extract(self, info, bin="pybabel", keywords=None):
        path = os.path.join(info.app_import_path, "translations")
        if not os.path.exists(path):
            os.mkdir(path)
        potfile = os.path.join(path, "messages.pot")

        mapping = create_babel_mapping(self.options["extract_jinja_dirs"],
            self.options["extract_with_jinja_exts"], self.options["extractors"])
        self._extract(info.app_import_path, potfile, mapping, bin, keywords)

        # we need to extract message from other paths independently then
        # merge the catalogs because babel's mapping configuration does
        # not support absolute paths
        for path, jinja_dirs, jinja_exts, extractors in self.extract_dirs:
            mapping = create_babel_mapping(jinja_dirs, jinja_exts, extractors)
            path_potfile = tempfile.NamedTemporaryFile()
            self._extract(path, path_potfile.name, mapping, bin)
            with self.edit_pofile(path_potfile.name) as path_catalog:
                with self.edit_pofile(potfile) as catalog:
                    for msg in path_catalog:
                        if msg.id not in catalog:
                            catalog[msg.id] = msg
            path_potfile.close()

        self.translation_extracted_signal.send(self)

    def _extract(self, path, potfile, mapping=None, bin="pybabel", keywords=None):
        if mapping:
            mapping_file = tempfile.NamedTemporaryFile()
            mapping_file.write(mapping)
            mapping_file.flush()

        if isinstance(keywords, (str, unicode)):
            keywords = map(str.strip, str(keywords).split(";"))
        elif not keywords:
            keywords = []
        keywords.extend(["_n:1,2", "translatable", "translate", "ntranslate",
                         "lazy_translate", "lazy_gettext"])

        cmdline = [bin, "extract", "-o", potfile]
        if mapping:
            cmdline.extend(["-F", mapping_file.name])
        for k in keywords:
            cmdline.append("-k")
            cmdline.append(k)
        cmdline.append(path)

        command.echo("Extracting translatable strings from %s in %s" % (path, potfile))
        shell_exec(cmdline)
        if mapping:
            mapping_file.close()

    @command("init", pass_script_info=True)
    def init_translation(self, info, locale, bin="pybabel", gotrans=False):
        path = os.path.join(info.app_import_path, "translations")
        potfile = os.path.join(path, "messages.pot")
        if not os.path.exists(potfile):
            self.extract(info, bin)
        command.echo("Initializing new translation '%s' in %s" % (locale, os.path.join(path, locale)))
        shell_exec([bin, "init", "-i", potfile, "-d", path, "-l", locale])
        self.translation_updated_signal.send(self, locale=locale)
        if gotrans:
            self.translate_with_google(info, locale)

    @command("compile", pass_script_info=True)
    def compile_translations(self, info, bin="pybabel"):
        command.echo("Compiling all translations")
        path = os.path.join(info.app_import_path, "translations")
        shell_exec([bin, "compile", "-d", path])
        if self.options['compile_to_json']:
            output = os.path.join(current_app.static_folder, self.options['compile_to_json'])
            for f in os.listdir(path):
                if os.path.isdir(os.path.join(path, f)):
                    self.po2json(info, f, output % f)
        if self.options['compile_to_js']:
            output = os.path.join(current_app.static_folder, self.options['compile_to_js'])
            for f in os.listdir(path):
                if os.path.isdir(os.path.join(path, f)):
                    self.po2js(info, f, output % f)

        self.translation_compiled_signal.send(self)

    @command("update", pass_script_info=True)
    def update_translations(self, info, bin="pybabel", extract=True, gotrans=False):
        path = os.path.join(info.app_import_path, "translations")
        potfile = os.path.join(path, "messages.pot")
        if not os.path.exists(potfile) or extract:
            self.extract(info, bin)
        command.echo("Updating all translations")
        shell_exec([bin, "update", "-i", potfile, "-d", path])
        for f in os.listdir(path):
            if os.path.isdir(os.path.join(path, f)):
                self.translation_updated_signal.send(self, locale=f)
                if gotrans:
                    self.translate_with_google(info, f)

    @command("gotrans", pass_script_info=True)
    def translate_with_google(self, info, locale):
        import goslate
        command.echo("Google translating '%s'" % locale)
        command.echo("WARNING: you must go through the translation after the process as placeholders may have been modified", fg="red")
        filename = os.path.join(info.app_import_path, "translations", locale, "LC_MESSAGES", "messages.po")
        
        def translate(id):
            # google translate messes with the format placeholders thus
            # we replace them with something which is easily recoverable
            string, placeholders = safe_placeholders(id)
            string = gs.translate(string, locale)
            return unsafe_placeholders(string, placeholders, "## %s ##")

        with self.edit_pofile(filename) as catalog:
            gs = goslate.Goslate()
            for message in catalog:
                if not message.id:
                    continue
                if message.pluralizable:
                    string = list(message.string)
                    if not string[0]:
                        string[0] = translate(message.id[0])
                    if not string[1]:
                        string[1] = translate(message.id[1])
                    message.string = tuple(string)
                elif not message.string:
                    message.string = translate(message.id)

    def _po2json(self, info, locale):
        filename = os.path.join(info.app_import_path, "translations", locale, "LC_MESSAGES", "messages.po")
        json_dct = {}
        with self.edit_pofile(filename) as catalog:
            for message in catalog:
                if not message.id:
                    continue
                if message.pluralizable:
                    json_dct[message.id[0]] = [message.id[1]] + list(message.string)
                else:
                    json_dct[message.id] = [None, message.string]
        return json.dumps(json_dct)

    @command(pass_script_info=True)
    def po2json(self, info, locale, output=None):
        dump = self._po2json(info, locale)
        if output:
            with open(output, 'w') as f:
                f.write(dump)
        else:
            command.echo(dump)

    @command(pass_script_info=True)
    def po2js(self, info, locale, output=None):
        dump = "var %s = %s;" % (self.options['js_catalog_varname'] % locale.upper(), self._po2json(info, locale))
        if output:
            with open(output, 'w') as f:
                f.write(dump)
        else:
            command.echo(dump)

    @contextlib.contextmanager
    def edit_pofile(self, filename, save=True):
        from babel.messages import pofile
        with open(filename, "r") as f:
            catalog = pofile.read_po(f)
        yield catalog
        if save:
            with open(filename, "w") as f:
                pofile.write_po(f, catalog)


def create_babel_mapping(jinja_dirs=None, jinja_exts=None, extractors=None):
    exts = ",".join(jinja_exts or [])
    conf = "[python:**.py]\n"
    if jinja_dirs:
        for jinja_dir in jinja_dirs:
            if jinja_dir == '.':
                jinja_dir = ''
            conf += "[jinja2:%s]\n" % os.path.join(jinja_dir, "**.html")
            if exts:
                conf += "extensions=%s\n" % exts
    if extractors:
        for extractor, settings in extractors:
            conf += "[%s]\n" % extractor
            for k, v in settings.iteritems():
                conf += "%s = %s\n" % (k, v)
    return conf


def safe_placeholders(string, repl="##%s##"):
    placeholders = []
    def replace_placeholder(m):
        placeholders.append(m.group(1))
        return repl % (len(placeholders) - 1)
    string = re.sub(r"%\(([a-zA-Z_]+)\)s", replace_placeholder, string)
    return string, placeholders


def unsafe_placeholders(string, placeholders, repl="##%s##"):
    for i, placeholder in enumerate(placeholders):
        string = string.replace(repl % i, "%%(%s)s" % placeholder)
    return string


try:
    import frasco_forms.form
    import form
    frasco_forms.form.field_type_map.update({
        "locale": form.LocaleField,
        "currency": form.CurrencyField})
except ImportError:
    pass