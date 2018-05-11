import dxfgrabber
import ezdxf
import math, re

from osgeo import ogr
from osgeo import osr

def dxf_read(dxffile):

    dxf = dxfgrabber.readfile(dxffile)

    wkt = {}
    for ent in dxf.entities:

        layer = ent.layer
        if layer.startswith('CONTOUR'):
            continue    # skip contours

        if layer not in wkt:
            wkt[layer] = []

        if ent.dxftype == 'LINE':
            wkt[layer].append('LINESTRING (%f %f, %f %f)' % (ent.start[0], ent.start[1], ent.end[0], ent.end[1]))

        elif ent.dxftype == 'ARC':

            # calc the endpoints of the arc
            c = ent.center
            r = ent.radius
            t0 = math.radians(ent.start_angle)
            t1 = math.radians(ent.end_angle)
            p0 = (c[0] + r * math.cos(t0), c[1] + r * math.sin(t0))
            p1 = (c[0] + r * math.cos(t1), c[1] + r * math.sin(t1))

            # calc the midpoint on the arc
            m = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
            t = math.atan2(m[1] - c[1], m[0] - c[0])
            pm = (c[0] + r * math.cos(t), c[1] + r * math.sin(t))

            wkt[layer].append('LINESTRING (%f %f, %f %f, %f %f)' % (p0[0], p0[1], pm[0], pm[1], p1[0], p1[1]))

        elif ent.dxftype == 'LWPOLYLINE':
            verts = []
            for i in range(len(ent.points) - 1):
                p0 = ent.points[i]
                verts.append('%f %f' % (p0[0], p0[1]))

                b = ent.bulge[i]
                if b != 0:
                    # next segment is an arc, add the midpoint
                    p1 = ent.points[i + 1]
                    d = math.sqrt((p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2) / 2  # length to midpoint of the chord
                    t = math.atan2(p1[1] - p0[1], p1[0] - p0[0]) - math.atan(b)  # direction p0 to pm
                    c = math.sqrt(1 + b**2) * d  # length p0 to pm
                    pm = (p0[0] + c * math.cos(t), p0[1] + c * math.sin(t))
                    verts.append('%f %f' % (pm[0], pm[1]))

                    # r = d / math.sin(2 * math.atan(b))  # signed radius
                    # print('p0=(%.4f,%.4f) p1=(%.4f,%.4f) b=%.8f t=%.4f c=%.4f r=%.4f' % (p0[0],p0[1], p1[0],p1[1], b, math.degrees(t), c, r))

            # add the last vertex and build the wkt
            p = ent.points[-1]
            verts.append('%f %f' % (p[0], p[1]))
            wkt[layer].append('LINESTRING (%s)' % ', '.join(verts))

        else:
            print('Skipping dxftype=%s layer=%s' % (ent.dxftype, ent.layer))
            continue

    # create geometry
    geom = []
    for layer in wkt.keys():
        for i in range(len(wkt[layer])):
            g = ogr.CreateGeometryFromWkt(wkt[layer][i])
            geom.append({'name': '%s-%03d' % (layer, i + 1), 'geom': g})

    return geom


def pnezd_read(filename):

    # read a pnezd comma delimited points file
    geom = []
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if len(line) == 0 or line[0] == '#':
                continue
            values = re.split(',', line, 4)
            if len(values) != 5:
                print('PNEZD format error: "%s"' % line)
                continue
            p, n, e, z, d = values
            if p.isdigit():
                p = '%03d' % int(p)  # zero pad
            g = ogr.CreateGeometryFromWkt('POINT (%s %s)' % (e, n))
            geom.append({'ele': z, 'name': p, 'cmt': d, 'desc': d, 'geom': g})

    return geom


def dxf_write(geom, filename):

    dwg = ezdxf.new('R2004')
    dwg.layers.new(name='GPX-TRACKS', dxfattribs={'linetype': 'CONTINUOUS', 'color': 7})
    msp = dwg.modelspace()

    for g in [g['geom'] for g in geom]:
        if g.GetGeometryName() != 'LINESTRING':
            continue
        pts = []
        for i in range(g.GetPointCount()):
            p = g.GetPoint(i)
            if p[0] < 0 or p[1] < 0:
                pts = []
                break
            pts.append((p[0], p[1]))
        if pts:
            msp.add_lwpolyline(pts, dxfattribs={'layer': 'GPX-TRACKS'})

    dwg.saveas(filename)


def pnezd_write(geom, filename):

    with open(filename, 'w') as f:
        p = 0
        for rec in geom:
            g = rec['geom']
            if g.GetGeometryName() != 'POINT':
                continue
            n = '%.4f' % g.GetY()
            e = '%.4f' % g.GetX()
            if 'name' in rec and rec['name'].isdigit():
                p = '%d' % int(rec['name'])
            else:
                p = ''
            if 'ele' in rec:
                z = '%.4f' % float(rec['ele'])
            else:
                z = '0.0000'
            if 'cmt' in rec:
                d = rec['cmt']
            elif 'desc' in rec:
                d = rec['desc']
            else:
                d = ''
            f.write(','.join([p,n,e,z,d]) + '\n')


if __name__ == '__main__':

    from gpx import gpx_write, gpx_read

    GPX_FILE =  'data/gpsmap.gpx'
    DXF_FILE = 'data/gpsmap.dxf'
    PTS_FILE = 'data/gpsmap.txt'

    geom = []
    if (GPX_FILE):
        print('Reading GPX file "%s": ' % (GPX_FILE), end='')
        geom += gpx_read(GPX_FILE, 2229)
        print('%2d objects' % (len(geom)))
        
        print('Writing DXF file "%s": ' % (DXF_FILE), end='')
        dxf_write(geom, DXF_FILE)
        print('%2d objects' % len(list(g for g in geom if g['geom'].GetGeometryName() == 'LINESTRING')))
        
        print('Writing PTS file "%s": ' % (PTS_FILE), end='')
        pnezd_write(geom, PTS_FILE)
        print('%2d objects' % len(list(g for g in geom if g['geom'].GetGeometryName() == 'POINT')))

    exit(0)

    DXF_FILE = 'data/bdy.dxf'
    PTS_FILE = 'data/points.txt'
    GPX_FILE = 'data/bdy.gpx'

    SOURCE_SRID = 2225

    geom = []
    if PTS_FILE:
        geom += pnezd_read(PTS_FILE)
    if DXF_FILE:
        geom += dxf_read(DXF_FILE)
    if geom:
        gpx_write(geom, GPX_FILE, SOURCE_SRID)

    exit(0)

