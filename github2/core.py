import sys
import time

from datetime import datetime

#: Running under Python 3
PY3K = sys.version_info[0] == 3 and True or False


GITHUB_TIMEZONE = "-0700"
GITHUB_DATE_FORMAT = "%Y/%m/%d %H:%M:%S"
#2009-03-21T18:01:48-07:00
COMMIT_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
COMMIT_TIMEZONE = "-07:00"


def strptime(string, format):
    """Parse date strings according to specified format

    We have to create our :obj:`~datetime.datetime` objects indirectly to remain
    compatible with Python 2.4, where the :class:`~datetime.datetime` class has
    no :meth:`~datetime.datetime.strptime` method.

    :param str string: String to parse
    :param str format: Datetime format
    :return datetime: Parsed datetime
    """
    return datetime(*(time.strptime(string, format)[:6]))


def ghdate_to_datetime(github_date):
    """Convert Github date string to Python datetime

    :param str github_date: date string to parse
    """
    date_without_tz = " ".join(github_date.strip().split()[:2])
    return strptime(date_without_tz, GITHUB_DATE_FORMAT)


def datetime_to_ghdate(datetime_):
    """Convert Python datetime to Github date string

    :param datetime datetime_: datetime object to convert
    """
    date_without_tz = datetime_.strftime(GITHUB_DATE_FORMAT)
    return " ".join([date_without_tz, GITHUB_TIMEZONE])


def commitdate_to_datetime(commit_date):
    """Convert commit date string to Python datetime

    :param str github_date: date string to parse
    """
    date_without_tz = commit_date[:-6]
    return strptime(date_without_tz, COMMIT_DATE_FORMAT)


def datetime_to_commitdate(datetime_):
    """Convert Python datetime to Github date string

    :param datetime datetime_: datetime object to convert
    """
    date_without_tz = datetime_.strftime(COMMIT_DATE_FORMAT)
    return "".join([date_without_tz, COMMIT_TIMEZONE])


def userdate_to_datetime(user_date):
    """Convert user date string to Python datetime

    Unfortunately this needs a special case because :meth:`~Github.users.show`
    and :meth:`~Github.users.search` return different formats for the
    ``created_at`` attributes.

    :param str user_date: date string to parse
    """
    try:
        return ghdate_to_datetime(user_date)
    except ValueError:
        return strptime(user_date, '%Y-%m-%dT%H:%M:%SZ')


def isodate_to_datetime(iso_date):
    """Convert commit date string to Python datetime

    :param str github_date: date string to parse
    """
    date_without_tz = iso_date[:-1]
    return strptime(date_without_tz, COMMIT_DATE_FORMAT)


def datetime_to_isodate(datetime_):
    """Convert Python datetime to Github date string

    :param str datetime_: datetime object to convert
    """
    return "%sZ" % datetime_.isoformat()


class AuthError(Exception):
    """Requires authentication"""


def requires_auth(f):
    """Decorate to check a function call for authentication

    Sets a ``requires_auth`` attribute on functions, for use in introspection.

    :param func f: Function to wrap
    :raises AuthError: If function called without an authenticated session
    """
    # When Python 2.4 support is dropped move straight to functools.wraps, don't
    # pass go and don't collect $200.
    def wrapper(self, *args, **kwargs):
        if not self.request.access_token and not self.request.api_token:
            raise AuthError("%r requires an authenticated session"
                            % f.__name__)
        return f(self, *args, **kwargs)
    wrapped = wrapper
    wrapped.__name__ = f.__name__
    wrapped.__doc__ = f.__doc__ + """\n.. warning:: Requires authentication"""
    wrapped.requires_auth = True
    return wrapped


def enhanced_by_auth(f):
    """Decorator to mark a function as enhanced by authentication

    Sets a ``enhanced_by_auth`` attribute on functions, for use in
    introspection.

    :param func f: Function to wrap
    """
    f.enhanced_by_auth = True
    f.__doc__ += """\n.. note:: This call is enhanced with authentication"""
    return f


class GithubCommand(object):

    def __init__(self, request):
        self.request = request

    def make_request(self, command, *args, **kwargs):
        filter = kwargs.get("filter")
        post_data = kwargs.get("post_data") or {}
        method = kwargs.get("method", "GET")
        if method.upper() in ("POST", "GET") and post_data:
            response = self.request.post(self.domain, command, *args,
                                         **post_data)
        elif method.upper() == "PUT":
            response = self.request.put(self.domain, command, *args,
                                        **post_data)
        elif method.upper() == "DELETE":
            response = self.request.delete(self.domain, command, *args,
                                           **post_data)
        else:
            response = self.request.get(self.domain, command, *args)
        if filter:
            return response[filter]
        return response

    def get_value(self, *args, **kwargs):
        datatype = kwargs.pop("datatype", None)
        value = self.make_request(*args, **kwargs)
        if datatype:
            # unicode keys are not accepted as kwargs by python, see:
            #http://mail-archives.apache.org/mod_mbox/qpid-dev/200609.mbox/%3C1159389941.4505.10.camel@localhost.localdomain%3E
            # So we make a local dict with the same keys but as strings:
            return datatype(**dict((str(k), v) for (k, v) in value.iteritems()))
        return value

    def get_values(self, *args, **kwargs):
        datatype = kwargs.pop("datatype", None)
        values = self.make_request(*args, **kwargs)
        if datatype:
            # Same as above, unicode keys will blow up in **args, so we need to
            # create a new 'values' dict with string keys
            return [datatype(**dict((str(k), v) for (k, v) in value.iteritems()))
                    for value in values]
        else:
            return values


def doc_generator(docstring, attributes):
    """Utility function to augment BaseDataType docstring

    :param str docstring: docstring to augment
    :param dict attributes: attributes to add to docstring
    """
    docstring = docstring or ""

    def bullet(title, text):
        return """.. attribute:: %s\n\n   %s\n""" % (title, text)

    b = "\n".join([bullet(attr_name, attr.help)
                   for attr_name, attr in attributes.items()])
    return "\n\n".join([docstring, b])


class Attribute(object):

    def __init__(self, help):
        self.help = help

    def to_python(self, value):
        return value

    from_python = to_python


class DateAttribute(Attribute):
    format = "github"
    converter_for_format = {
        "github": {
            "to": ghdate_to_datetime,
            "from": datetime_to_ghdate,
        },
        "commit": {
            "to": commitdate_to_datetime,
            "from": datetime_to_commitdate,
        },
        "user": {
            "to" : userdate_to_datetime,
            "from": datetime_to_ghdate,
	},
        "iso": {
            "to": isodate_to_datetime,
            "from": datetime_to_isodate,
        }
    }

    def __init__(self, *args, **kwargs):
        self.format = kwargs.pop("format", self.format)
        super(DateAttribute, self).__init__(*args, **kwargs)

    def to_python(self, value):
        if value and not isinstance(value, datetime):
            return self.converter_for_format[self.format]["to"](value)
        return value

    def from_python(self, value):
        if value and isinstance(value, datetime):
            return self.converter_for_format[self.format]["from"](value)
        return value


class BaseDataType(type):

    def __new__(cls, name, bases, attrs):
        super_new = super(BaseDataType, cls).__new__

        _meta = dict([(attr_name, attr_value)
                        for attr_name, attr_value in attrs.items()
                            if isinstance(attr_value, Attribute)])
        attrs["_meta"] = _meta
        attributes = _meta.keys()
        attrs.update(dict([(attr_name, None)
                        for attr_name in attributes]))

        def _contribute_method(name, func):
            func.func_name = name
            attrs[name] = func

        def constructor(self, **kwargs):
            for attr_name, attr_value in kwargs.items():
                attr = self._meta.get(attr_name)
                if attr:
                    setattr(self, attr_name, attr.to_python(attr_value))
                else:
                    setattr(self, attr_name, attr_value)
        _contribute_method("__init__", constructor)

        def iterate(self):
            not_empty = lambda e: e[1] is not None
            return iter(filter(not_empty, vars(self).items()))
        _contribute_method("__iter__", iterate)

        result_cls = super_new(cls, name, bases, attrs)
        result_cls.__doc__ = doc_generator(result_cls.__doc__, _meta)
        return result_cls


class BaseData(object):
    __metaclass__ = BaseDataType


def repr_string(string):
    """Shorten string for use in repr() output

    :param str string: string to operate on
    :return: string, with maximum length of 20 characters
    """
    if len(string) > 20:
        string = string[:17] + '...'
    if not PY3K:
        string.decode('utf-8')
    return string
