
def patch_postgis_bad_geomery_escape():
    """
    When using django 1.3.X with PostgreSQL 9.1 some geometry can be badly
    escaped. Monkey patch PostGISAdapter to fix this issue.
    see https://code.djangoproject.com/ticket/16778
    """
    # TODO: Remove when support for django 1.3 is dropped
    import django
    if django.VERSION < (1, 4):
        from django.db import connections
        postgis_engine = 'django.contrib.gis.db.backends.postgis'
        if any(connection.settings_dict['ENGINE'] == postgis_engine
               for connection in connections.all()):
            from psycopg2 import Binary
            from django.contrib.gis.db.backends.postgis.adapter import PostGISAdapter
            
            PostGISAdapter__init__ = PostGISAdapter.__init__
            def _PostGISAdapter__init__(self, *args, **kwargs):
                PostGISAdapter__init__(self, *args, **kwargs)
                self._adapter = Binary(self.ewkb)
            PostGISAdapter.__init__ = _PostGISAdapter__init__
            
            def _PostGISAdapter_prepare(self, conn):
                self._adapter.prepare(conn)
            PostGISAdapter.prepare = _PostGISAdapter_prepare
            
            def _PostGISAdapter_getquoted(self):
                return 'ST_GeomFromEWKB(%s)' % self._adapter.getquoted()
            PostGISAdapter.getquoted = _PostGISAdapter_getquoted

def patch_db_field_compare():
    """
    Field instances cannot be compared to other objects because of attribute
    presence assumptions in it's __cmp__ method. To allow full_clean we must
    override the item_field __cmp__ method to return NotImplemented if the
    object it's compared to isn't a Field instance. Let's monkey patch it!
    see https://code.djangoproject.com/ticket/17851
    """
    # TODO: Remove when support for django 1.4 is dropped
    from django.db.models.fields import Field
    try:
        assert Field() != None
    except AttributeError:
        del Field.__cmp__
        def _Field__lt__(self, other):
            if isinstance(other, Field):
                return self.creation_counter < other.creation_counter
            return NotImplemented
        Field.__lt__ = _Field__lt__
        assert Field() != None

def patch_model_option_verbose_name_raw():
    """
    Until #17763 and all the permission name length issues are fixed we patch
    the `verbose_name_raw` method to return a truncated string in order to
    avoid DatabaseError.
    """
    from django.db.models.options import Options
    verbose_name_raw = Options.verbose_name_raw.fget
    if hasattr(verbose_name_raw, '_patched'):
        return
    def _get_verbose_name_raw(self):
        name = verbose_name_raw(self)
        if len(name) >= 40:
            name = "%s..." % name[0:36]
        return name
    _get_verbose_name_raw.patched = True
    Options.verbose_name_raw = property(_get_verbose_name_raw)

def get_concrete_model(model):
    """
    Prior to django r17573 (django 1.4), `proxy_for_model` returned the
    actual concrete model of a proxy and there was no `concrete_model`
    property so we try to fetch the `concrete_model` from the opts
    and fallback to `proxy_for_model` if it's not defined.
    """
    # TODO: Remove when support for django 1.4 is dropped
    return getattr(model._meta, 'concrete_model', model._meta.proxy_for_model)

def get_real_content_type(model, db=None):
    """
    Prior to #18399 being fixed there was no way to retrieve `ContentType`
    of proxy models. This is a shim that tries to use the newly introduced
    flag and fallback to another method.
    """
    # TODO: Remove when support for django 1.4 is dropped
    from django.contrib.contenttypes.models import ContentType
    from django.utils.encoding import smart_unicode
    cts = ContentType.objects
    if db:
        cts = cts.db_manager(db)
    opts = model._meta
    if opts.proxy:
        try:
            # Attempt to use the `for_concrete_model` kwarg available in
            # django >= 1.5
            return cts.get_for_model(model, for_concrete_model=False)
        except TypeError:
            if model._deferred:
                opts = opts.proxy_for_model._meta
            try:
                ct = cts._get_from_cache(opts)
            except KeyError:
                ct, _created = cts.get_or_create(
                    app_label = opts.app_label,
                    model = opts.object_name.lower(),
                    defaults = {'name': smart_unicode(opts.verbose_name_raw)},
                )
                cts._add_to_cache(cts.db, ct)
                return ct
    else:
        return cts.get_for_model(model)
 