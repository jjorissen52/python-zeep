import base64
import datetime
import math
import re
from decimal import Decimal as _Decimal

import isodate
import pytz
import six

from zeep.xsd.const import xsd_ns
from zeep.xsd.types.any import AnyType
from zeep.xsd.types.simple import AnySimpleType


class ParseError(ValueError):
    pass


class BuiltinType(object):
    def __init__(self, qname=None, is_global=False):
        super(BuiltinType, self).__init__(qname, is_global=True)


def check_no_collection(func):
    def _wrapper(self, value):
        if isinstance(value, (list, dict, set)):
            raise ValueError(
                "The %s type doesn't accept collections as value" % (
                    self.__class__.__name__))

        return func(self, value)
    return _wrapper


##
# Primitive types
class String(BuiltinType, AnySimpleType):
    _default_qname = xsd_ns('string')
    accepted_types = six.string_types

    @check_no_collection
    def xmlvalue(self, value):
        if isinstance(value, bytes):
            return value.decode('utf-8')
        return six.text_type(value if value is not None else '')

    def pythonvalue(self, value):
        return value


class Boolean(BuiltinType, AnySimpleType):
    _default_qname = xsd_ns('boolean')
    accepted_types = (bool,)

    @check_no_collection
    def xmlvalue(self, value):
        return 'true' if value and value not in ('false', '0') else 'false'

    def pythonvalue(self, value):
        """Return True if the 'true' or '1'. 'false' and '0' are legal false
        values, but we consider everything not true as false.

        """
        return value in ('true', '1')


class Decimal(BuiltinType, AnySimpleType):
    _default_qname = xsd_ns('decimal')
    accepted_types = (_Decimal, float) + six.string_types

    @check_no_collection
    def xmlvalue(self, value):
        return str(value)

    def pythonvalue(self, value):
        return _Decimal(value)


class Float(BuiltinType, AnySimpleType):
    _default_qname = xsd_ns('float')
    accepted_types = (float, _Decimal) + six.string_types

    def xmlvalue(self, value):
        return str(value).upper()

    def pythonvalue(self, value):
        return float(value)


class Double(BuiltinType, AnySimpleType):
    _default_qname = xsd_ns('double')
    accepted_types = (_Decimal, float) + six.string_types

    @check_no_collection
    def xmlvalue(self, value):
        return str(value)

    def pythonvalue(self, value):
        return float(value)


class Duration(BuiltinType, AnySimpleType):
    _default_qname = xsd_ns('duration')
    accepted_types = (isodate.duration.Duration,) + six.string_types

    @check_no_collection
    def xmlvalue(self, value):
        return isodate.duration_isoformat(value)

    def pythonvalue(self, value):
        if value.startswith('PT-'):
            value = value.replace('PT-', 'PT')
            result = isodate.parse_duration(value)
            return datetime.timedelta(0 - result.total_seconds())
        else:
            return isodate.parse_duration(value)


class DateTime(BuiltinType, AnySimpleType):
    _default_qname = xsd_ns('dateTime')
    accepted_types = (datetime.datetime,) + six.string_types

    @check_no_collection
    def xmlvalue(self, value):
        if type(value) == str:
            # Allow DateTime value to be pre-formatted as a string
            return value
        
        # Bit of a hack, since datetime is a subclass of date we can't just
        # test it with an isinstance(). And actually, we should not really
        # care about the type, as long as it has the required attributes
        if not all(hasattr(value, attr) for attr in ('hour', 'minute', 'second')):
            value = datetime.datetime.combine(value, datetime.time(
                getattr(value, 'hour', 0),
                getattr(value, 'minute', 0),
                getattr(value, 'second', 0)))

        if getattr(value, 'microsecond', 0):
            return isodate.isostrf.strftime(value, '%Y-%m-%dT%H:%M:%S.%f%Z')
        return isodate.isostrf.strftime(value, '%Y-%m-%dT%H:%M:%S%Z')

    def pythonvalue(self, value):
        return isodate.parse_datetime(value)


class Time(BuiltinType, AnySimpleType):
    _default_qname = xsd_ns('time')
    accepted_types = (datetime.time,) + six.string_types

    @check_no_collection
    def xmlvalue(self, value):
        if isinstance(value, six.string_types):
            return value

        if value.microsecond:
            return isodate.isostrf.strftime(value, '%H:%M:%S.%f%Z')
        return isodate.isostrf.strftime(value, '%H:%M:%S%Z')

    def pythonvalue(self, value):
        return isodate.parse_time(value)


class Date(BuiltinType, AnySimpleType):
    _default_qname = xsd_ns('date')
    accepted_types = (datetime.date,) + six.string_types

    @check_no_collection
    def xmlvalue(self, value):
        if isinstance(value, six.string_types):
            return value
        return isodate.isostrf.strftime(value, '%Y-%m-%d')

    def pythonvalue(self, value):
        return isodate.parse_date(value)


class gYearMonth(BuiltinType, AnySimpleType):
    """gYearMonth represents a specific gregorian month in a specific gregorian
    year.

    Lexical representation: CCYY-MM

    """
    accepted_types = (datetime.date,) + six.string_types
    _default_qname = xsd_ns('gYearMonth')
    _pattern = re.compile(
        r'^(?P<year>-?\d{4,})-(?P<month>\d\d)(?P<timezone>Z|[-+]\d\d:?\d\d)?$')

    @check_no_collection
    def xmlvalue(self, value):
        year, month, tzinfo = value
        return '%04d-%02d%s' % (year, month, _unparse_timezone(tzinfo))

    def pythonvalue(self, value):
        match = self._pattern.match(value)
        if not match:
            raise ParseError()
        group = match.groupdict()
        return (
            int(group['year']), int(group['month']),
            _parse_timezone(group['timezone']))


class gYear(BuiltinType, AnySimpleType):
    """gYear represents a gregorian calendar year.

    Lexical representation: CCYY

    """
    accepted_types = (datetime.date,) + six.string_types
    _default_qname = xsd_ns('gYear')
    _pattern = re.compile(r'^(?P<year>-?\d{4,})(?P<timezone>Z|[-+]\d\d:?\d\d)?$')

    @check_no_collection
    def xmlvalue(self, value):
        year, tzinfo = value
        return '%04d%s' % (year, _unparse_timezone(tzinfo))

    def pythonvalue(self, value):
        match = self._pattern.match(value)
        if not match:
            raise ParseError()
        group = match.groupdict()
        return (int(group['year']), _parse_timezone(group['timezone']))


class gMonthDay(BuiltinType, AnySimpleType):
    """gMonthDay is a gregorian date that recurs, specifically a day of the
    year such as the third of May.

    Lexical representation: --MM-DD

    """
    accepted_types = (datetime.date, ) + six.string_types
    _default_qname = xsd_ns('gMonthDay')
    _pattern = re.compile(
        r'^--(?P<month>\d\d)-(?P<day>\d\d)(?P<timezone>Z|[-+]\d\d:?\d\d)?$')

    @check_no_collection
    def xmlvalue(self, value):
        month, day, tzinfo = value
        return '--%02d-%02d%s' % (month, day, _unparse_timezone(tzinfo))

    def pythonvalue(self, value):
        match = self._pattern.match(value)
        if not match:
            raise ParseError()

        group = match.groupdict()
        return (
            int(group['month']), int(group['day']),
            _parse_timezone(group['timezone']))


class gDay(BuiltinType, AnySimpleType):
    """gDay is a gregorian day that recurs, specifically a day of the month
    such as the 5th of the month

    Lexical representation: ---DD

    """
    accepted_types = (datetime.date,) + six.string_types
    _default_qname = xsd_ns('gDay')
    _pattern = re.compile(r'^---(?P<day>\d\d)(?P<timezone>Z|[-+]\d\d:?\d\d)?$')

    @check_no_collection
    def xmlvalue(self, value):
        day, tzinfo = value
        return '---%02d%s' % (day, _unparse_timezone(tzinfo))

    def pythonvalue(self, value):
        match = self._pattern.match(value)
        if not match:
            raise ParseError()
        group = match.groupdict()
        return (int(group['day']), _parse_timezone(group['timezone']))


class gMonth(BuiltinType, AnySimpleType):
    """gMonth is a gregorian month that recurs every year.

    Lexical representation: --MM

    """
    accepted_types = (datetime.date,) + six.string_types
    _default_qname = xsd_ns('gMonth')
    _pattern = re.compile(r'^--(?P<month>\d\d)(?P<timezone>Z|[-+]\d\d:?\d\d)?$')

    @check_no_collection
    def xmlvalue(self, value):
        month, tzinfo = value
        return '--%d%s' % (month, _unparse_timezone(tzinfo))

    def pythonvalue(self, value):
        match = self._pattern.match(value)
        if not match:
            raise ParseError()
        group = match.groupdict()
        return (int(group['month']), _parse_timezone(group['timezone']))


class HexBinary(BuiltinType, AnySimpleType):
    accepted_types = six.string_types
    _default_qname = xsd_ns('hexBinary')

    @check_no_collection
    def xmlvalue(self, value):
        return value

    def pythonvalue(self, value):
        return value


class Base64Binary(BuiltinType, AnySimpleType):
    accepted_types = six.string_types
    _default_qname = xsd_ns('base64Binary')

    @check_no_collection
    def xmlvalue(self, value):
        return base64.b64encode(value)

    def pythonvalue(self, value):
        return base64.b64decode(value)


class AnyURI(BuiltinType, AnySimpleType):
    accepted_types = six.string_types
    _default_qname = xsd_ns('anyURI')

    @check_no_collection
    def xmlvalue(self, value):
        return value

    def pythonvalue(self, value):
        return value


class QName(BuiltinType, AnySimpleType):
    accepted_types = six.string_types
    _default_qname = xsd_ns('QName')

    @check_no_collection
    def xmlvalue(self, value):
        return value

    def pythonvalue(self, value):
        return value


class Notation(BuiltinType, AnySimpleType):
    accepted_types = six.string_types
    _default_qname = xsd_ns('NOTATION')


##
# Derived datatypes

class NormalizedString(String):
    _default_qname = xsd_ns('normalizedString')


class Token(NormalizedString):
    _default_qname = xsd_ns('token')


class Language(Token):
    _default_qname = xsd_ns('language')


class NmToken(Token):
    _default_qname = xsd_ns('NMTOKEN')


class NmTokens(NmToken):
    _default_qname = xsd_ns('NMTOKENS')


class Name(Token):
    _default_qname = xsd_ns('Name')


class NCName(Name):
    _default_qname = xsd_ns('NCName')


class ID(NCName):
    _default_qname = xsd_ns('ID')


class IDREF(NCName):
    _default_qname = xsd_ns('IDREF')


class IDREFS(IDREF):
    _default_qname = xsd_ns('IDREFS')


class Entity(NCName):
    _default_qname = xsd_ns('ENTITY')


class Entities(Entity):
    _default_qname = xsd_ns('ENTITIES')


class Integer(Decimal):
    _default_qname = xsd_ns('integer')
    accepted_types = (int, float) + six.string_types

    def xmlvalue(self, value):
        return str(value)

    def pythonvalue(self, value):
        return int(value)


class NonPositiveInteger(Integer):
    _default_qname = xsd_ns('nonPositiveInteger')


class NegativeInteger(Integer):
    _default_qname = xsd_ns('negativeInteger')


class Long(Integer):
    _default_qname = xsd_ns('long')

    def pythonvalue(self, value):
        return long(value) if six.PY2 else int(value)  # noqa


class Int(Long):
    _default_qname = xsd_ns('int')


class Short(Int):
    _default_qname = xsd_ns('short')


class Byte(Short):
    """A signed 8-bit integer"""
    _default_qname = xsd_ns('byte')


class NonNegativeInteger(Integer):
    _default_qname = xsd_ns('nonNegativeInteger')


class UnsignedLong(NonNegativeInteger):
    _default_qname = xsd_ns('unsignedLong')


class UnsignedInt(UnsignedLong):
    _default_qname = xsd_ns('unsignedInt')


class UnsignedShort(UnsignedInt):
    _default_qname = xsd_ns('unsignedShort')


class UnsignedByte(UnsignedShort):
    _default_qname = xsd_ns('unsignedByte')


class PositiveInteger(NonNegativeInteger):
    _default_qname = xsd_ns('positiveInteger')


##
# Other
def _parse_timezone(val):
    """Return a pytz.tzinfo object"""
    if not val:
        return

    if val == 'Z' or val == '+00:00':
        return pytz.utc

    negative = val.startswith('-')
    minutes = int(val[-2:])
    minutes += int(val[1:3]) * 60

    if negative:
        minutes = 0 - minutes
    return pytz.FixedOffset(minutes)


def _unparse_timezone(tzinfo):
    if not tzinfo:
        return ''

    if tzinfo == pytz.utc:
        return 'Z'

    hours = math.floor(tzinfo._minutes / 60)
    minutes = tzinfo._minutes % 60

    if hours > 0:
        return '+%02d:%02d' % (hours, minutes)
    return '-%02d:%02d' % (abs(hours), minutes)


_types = [
    # Primitive
    String,
    Boolean,
    Decimal,
    Float,
    Double,
    Duration,
    DateTime,
    Time,
    Date,
    gYearMonth,
    gYear,
    gMonthDay,
    gDay,
    gMonth,
    HexBinary,
    Base64Binary,
    AnyURI,
    QName,
    Notation,

    # Derived
    NormalizedString,
    Token,
    Language,
    NmToken,
    NmTokens,
    Name,
    NCName,
    ID,
    IDREF,
    IDREFS,
    Entity,
    Entities,
    Integer,
    NonPositiveInteger,  # noqa
    NegativeInteger,
    Long,
    Int,
    Short,
    Byte,
    NonNegativeInteger,  # noqa
    UnsignedByte,
    UnsignedInt,
    UnsignedLong,
    UnsignedShort,
    PositiveInteger,

    # Other
    AnyType,
    AnySimpleType,
]

default_types = {
    cls._default_qname: cls(is_global=True) for cls in _types
}
