import re
import math


class DmsFormatError(Exception):
    pass


def meters_per_user_unit(units):

    if   units == 'meters': return 1.0
    elif units == 'sft':    return 12.0 / 39.37
    elif units == 'int_ft': return 0.0254 * 12.0
    elif units == 'chains': return 66.0 * 12.0 / 39.37
    else:
        raise ValueError('Bad units: \'{0}\''.format(units))


def user_units_per_meter(units):
    return 1.0 / meters_per_user_unit(units)


def dms_radians(dms):
    """ Convert degrees-minutes and degrees-minutes-seconds string to radians.
    """

    dms = dms.strip()
    if len(dms) == 0:
        raise DmsFormatError('Empty dms string.')

    if dms[0] == '-':
        sign = -1.0
        v = dms[1:].split('-')
    else:
        sign = 1.0
        v = dms.split('-')

    if len(v) > 3:
        raise DmsFormatError('s=%s' % dms)

    if v[0].isdigit():
        degrees = float(v[0])
    else:
        raise DmsFormatError('s=%s' % dms)

    minutes = 0.0
    if len(v) > 1:
        if re.match('^\d{1,2}$', v[1]):
            minutes = float(v[1])
        else:
            raise DmsFormatError('s=%s' % dms)

    seconds = 0.0
    if len(v) > 2:
        if re.match('^\d{1,2}(\.\d+)?$', v[2]):
            seconds = float(v[2])
        else:
            raise DmsFormatError('s=%s' % dms)

    if not (minutes < 60.0 and seconds < 60.0):
        raise DmsFormatError('s=%s' % dms)

    return math.radians(sign * (degrees + minutes/60.0 + seconds/3600.0))


if __name__ == "__main__":

    pass