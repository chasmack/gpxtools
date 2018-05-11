import xml.etree.ElementTree as etree
import xml.dom.minidom as minidom
from datetime import datetime, timedelta
import pytz

from osgeo import ogr, osr


def gpx_write(geom, filename, srid=None):
    """ Format a list of point/linestring geometry as a GPX file.

    GPX format for waypoints and routes -

    <?xml version="1.0" encoding="utf-8" standalone="no"?>
    <gpx creator="Python pyloc" version="1.1"
        xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd
        xmlns="http://www.topografix.com/GPX/1/1"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" >
        <metadata>
            <link href="http://www.asis.com/users/chas.mack">
                <text>Charles Mack</text>
            </link>
            <time>2015-04-27T23:09:11Z</time>
        </metadata>
        <wpt lat="41.097316" lon="-123.696170">
            <ele>107.753052</ele>
            <time>2015-04-27T23:33:44Z</time>
            <name>4501</name>
            <cmt>SW212</cmt>
            <desc>SW212</desc>
            <sym>Waypoint</sym>
        </wpt>
        <rte>
            <name>ROAD-01</name>
            <rtept lat="41.097316" lon="-123.696170">
                <name>ROAD-01-001</name>
            </rtept>
            <rtept lat="41.123456" lon="-123.789012">
                <name>ROAD-01-002</name>
            </rtept>
        </rte>
    </gpx>

    """

    if srid:
        # transform geometry to EPSG:4326
        source_crs = osr.SpatialReference()
        source_crs.ImportFromEPSG(srid)
        target_crs = osr.SpatialReference()
        target_crs.ImportFromEPSG(4326)

        transform = osr.CoordinateTransformation(source_crs, target_crs)
        for rec in geom:
            rec['geom'].Transform(transform)
    else:
        source_crs = None

    ns = {
        'gpx': 'http://www.topografix.com/GPX/1/1'
    }
    etree.register_namespace('', 'http://www.topografix.com/GPX/1/1')

    gpx_attrib = {
        'creator': 'Python pyloc', 'version': '1.1',
        'xsi:schemaLocation': 'http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd',
        'xmlns': 'http://www.topografix.com/GPX/1/1',
        'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance'
    }

    # Get the ISO 8601 date-time string.
    time = datetime.now(pytz.utc)
    time -= timedelta(microseconds=time.microsecond)  # remove the microseconds
    time = time.isoformat()

    gpx = etree.Element('gpx', attrib=gpx_attrib)
    meta = etree.SubElement(gpx, 'metadata')
    link = etree.SubElement(meta, 'link', attrib={'href': 'https://cmack.org/'})
    etree.SubElement(link, 'text').text = 'Charlie'
    etree.SubElement(meta, 'time').text = time

    for rec in geom:
        g = rec['geom']
        type = g.GetGeometryName()
        if type == 'LINESTRING':
            rte = etree.SubElement(gpx, 'rte')
            if 'name' in rec:
                etree.SubElement(rte, 'name').text = rec['name']

            for i in range(g.GetPointCount()):
                p = g.GetPoint(i)
                lon = '%.8f' % p[0]
                lat = '%.8f' % p[1]
                rtept = etree.SubElement(rte, 'rtept', attrib={'lat': lat, 'lon': lon})
                if 'name' in rec:
                    etree.SubElement(rtept, 'name').text = rec['name'] + '.%03d' % (i + 1)
                etree.SubElement(rtept, 'sym').text = 'Waypoint'

        elif type == 'POINT':
            lon = '%.8f' % g.GetX()
            lat = '%.8f' % g.GetY()
            wpt = etree.SubElement(gpx, 'wpt', attrib={'lat': lat, 'lon': lon})

            if 'ele' in rec:
                ele = float(rec['ele'])
                if source_crs:
                    ele *= source_crs.GetLinearUnits()  # convert to meters
                etree.SubElement(wpt, 'ele').text = '%.4f' % ele
            if 'name' in rec:
                etree.SubElement(wpt, 'name').text = rec['name']
            if 'cmt' in rec:
                etree.SubElement(wpt, 'cmt').text = rec['cmt']
            if 'desc' in rec:
                etree.SubElement(wpt, 'desc').text = rec['desc']

            etree.SubElement(wpt, 'sym').text = 'Flag, Red'

    # Reparse the etree gpx with minidom and write pretty xml.
    dom = minidom.parseString(etree.tostring(gpx, encoding='utf-8'))
    with open(filename, 'w') as o:
        dom.writexml(o, addindent='  ', newl='\n', encoding='utf-8')


def gpx_read(filename, srid=None):
    """ Parse wpt elements from a GPX file and transform coordinates to grid.
    """

    ns = {
        'gpx': 'http://www.topografix.com/GPX/1/1',
        'gpxx': 'http://www.garmin.com/xmlschemas/GpxExtensions/v3',
        'wptx1': 'http://www.garmin.com/xmlschemas/WaypointExtension/v1',
        'ctx': 'http://www.garmin.com/xmlschemas/CreationTimeExtension/v1',
    }

    etree.register_namespace('', 'http://www.topografix.com/GPX/1/1')
    etree.register_namespace('gpxx', 'http://www.garmin.com/xmlschemas/GpxExtensions/v3')
    etree.register_namespace('wptx1', 'http://www.garmin.com/xmlschemas/WaypointExtension/v1')
    etree.register_namespace('ctx', 'http://www.garmin.com/xmlschemas/CreationTimeExtension/v1')

    geom = []
    gpx = etree.parse(filename).getroot()
    for wpt in gpx.findall('gpx:wpt', ns):
        rec = {}
        rec['geom'] = ogr.CreateGeometryFromWkt('POINT (%s %s)' % (wpt.get('lon'), wpt.get('lat')))
        tags = ['gpx:ele', 'gpx:time', 'gpx:name', 'gpx:cmt', 'gpx:desc', 'gpx:sym', 'gpx:type']
        tags += ['./gpx:extensions//wptx1:Samples']
        for t in tags:
            e = wpt.find(t, ns)
            if e is not None:
                k = t.rpartition(':')[2].lower()  # remove path and namespace
                rec[k] = e.text

        geom.append(rec)

    for trk in gpx.findall('gpx:trk', ns):

        # idle time between trkpts to start a new segment
        TRKSEG_IDLE_SECS = 600

        for trkseg in trk.findall('gpx:trkseg', ns):
            g = ogr.Geometry(ogr.wkbLineString)
            dtlast = None
            for trkpt in trkseg.findall('gpx:trkpt', ns):
                time = trkpt.find('gpx:time', ns)
                if time is not None:
                    dt = datetime.strptime(time.text, '%Y-%m-%dT%H:%M:%SZ')
                    if dtlast and (dt - dtlast).seconds > TRKSEG_IDLE_SECS:
                        # start a new segment
                        geom.append({'geom': g})
                        g = ogr.Geometry(ogr.wkbLineString)
                    dtlast = dt
                g.AddPoint_2D(float(trkpt.get('lon')), float(trkpt.get('lat')))
            geom.append({'geom': g})

    if srid:
        # transform geometry from EPSG:4326 to target crs
        source_crs = osr.SpatialReference()
        source_crs.ImportFromEPSG(4326)
        target_crs = osr.SpatialReference()
        target_crs.ImportFromEPSG(srid)

        transform = osr.CoordinateTransformation(source_crs, target_crs)
        for rec in geom:
            rec['geom'].Transform(transform)
            if 'ele' in rec:
                rec['ele'] = '%.4f' % (float(rec['ele']) / target_crs.GetLinearUnits())

    return geom


if __name__ == '__main__':

    GPX_FILE = 'data/gpsmap.gpx'

    geom = gpx_read(GPX_FILE, 2229)

    for rec in geom:
        for k in sorted(rec.keys()):
            if k == 'geom':
                print('%s: %s' % ('geom', rec['geom'].ExportToWkt()))
            else:
                print('%s: %s' % (k, rec[k]))

    print('count: %d' % len(geom))

