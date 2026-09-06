"""
Minimal, allofuggosegmentes TNEF (winmail.dat) body-kinyero.
Csak azt csinalja amire szuksegunk van: a HTML / RTF(compressed) / plain body
kinyereset a TNEF attributum-streambol, a MAPI Properties (0x9003) blokkon
keresztul. Attachment-eket, recipient-tablat, dátumokat stb. NEM dolgoz fel.

Alapja (reverse-engineered a forrasbol, nem szo szerinti masolat):
  https://github.com/koodaamo/tnefparse  (LGPL-3.0)
A MAPI property-tipusok mérete/elrendezese szükséges ahhoz, hogy a nem
érdekes property-ken is helyesen at tudjunk lepni (a stream szekvencialis).

Hasznalat:
    body = parse_tnef_body(data)   # data: a winmail.dat / attMAPI_ATTACH_DATA_OBJ nyers bajtjai
    body['htmlbody']            # bytes vagy None
    body['rtfbody_compressed']  # bytes (LZFu-tomoritett!) vagy None -- dekompresszio kulon (compressed_rtf)
    body['body']                # bytes vagy None (plain text body)
    body['codepage']            # str, python kodlap nev (pl. "cp1250"), vagy None
"""
import struct

TNEF_SIGNATURE = 0x223E9F78
LVL_MESSAGE = 0x01
LVL_ATTACHMENT = 0x02

ATTBODY = 0x800C
ATTOEMCODEPAGE = 0x9007
ATTMAPIPROPS = 0x9003

# MAPI property tag-ek amik erdekelnek minket (properties.py-bol, tnefparse):
MAPI_BODY = 0x1000
MAPI_RTF_COMPRESSED = 0x1009
MAPI_BODY_HTML = 0x1013
MAPI_UNCOMPRESSED_BODY = 0x3FD9
MAPI_INTERNET_CODEPAGE = 0x3FDE

# MAPI property-tipusok (csak a merethez kellenek, hogy helyesen tudjunk lepni):
SZMAPI_SHORT = 0x0002
SZMAPI_INT = 0x0003
SZMAPI_FLOAT = 0x0004
SZMAPI_ERROR = 0x000A
SZMAPI_BOOLEAN = 0x000B
SZMAPI_DOUBLE = 0x0005
SZMAPI_APPTIME = 0x0007
SZMAPI_CURRENCY = 0x0006
SZMAPI_INT8BYTE = 0x0014
SZMAPI_SYSTIME = 0x0040
SZMAPI_CLSID = 0x0048
SZMAPI_STRING = 0x001E
SZMAPI_UNICODE_STRING = 0x001F
SZMAPI_OBJECT = 0x000D
SZMAPI_BINARY = 0x0102
SZMAPI_UNSPECIFIED = 0x0000
SZMAPI_NULL = 0x0001

MULTI_VALUE_FLAG = 0x1000
GUID_EXISTS_FLAG = 0x8000

_uint8 = struct.Struct('<B').unpack_from
_uint16 = struct.Struct('<H').unpack_from
_uint32 = struct.Struct('<I').unpack_from

# windows codepage szam -> python kodlap nev (a leggyakoribbak; a tobbi "cpNNNN"-kent probalkozik)
_CODEPAGE_MAP = {20127: 'ascii', 20866: 'koi8-r', 28591: 'iso-8859-1', 65001: 'utf-8'}


def _codepage_name(cp):
    if cp in _CODEPAGE_MAP:
        return _CODEPAGE_MAP[cp]
    if cp <= 1258:
        return "cp%d" % cp
    return "cp1252"  # fallback


def _fixed_size(attr_type):
    # None = valtozo hosszu (kulon kell szamolni), egyebkent bajtban a meret
    return {
        SZMAPI_SHORT: 2, SZMAPI_BOOLEAN: 2,
        SZMAPI_INT: 4, SZMAPI_FLOAT: 4, SZMAPI_ERROR: 4,
        SZMAPI_DOUBLE: 8, SZMAPI_APPTIME: 8, SZMAPI_CURRENCY: 8,
        SZMAPI_INT8BYTE: 8, SZMAPI_SYSTIME: 8,
        SZMAPI_CLSID: 16,
    }.get(attr_type)


def _skip_variable(data, offset, is_multi, attr_type, oem_codepage):
    # SZMAPI_STRING / UNICODE_STRING / OBJECT / BINARY / UNSPECIFIED
    # visszaadja: (ertekek listaja -- str ha STRING/UNICODE_STRING, egyebkent bytes --, uj offset)
    if is_multi:
        num_vals = 1
    else:
        num_vals = _uint32(data, offset)[0]
        offset += 4
    vals = []
    for _ in range(num_vals):
        length = _uint32(data, offset)[0]
        offset += 4
        pad = (-length) % 4
        item = data[offset:offset + length]
        if attr_type == SZMAPI_UNICODE_STRING:
            try: item = item.decode('utf-16')
            except Exception: pass
        elif attr_type == SZMAPI_STRING:
            try: item = item.decode(oem_codepage)
            except Exception: pass
        vals.append(item)
        offset += length + pad
    return vals, offset


def _join(values):
    if values and isinstance(values[0], str):
        return "".join(v.rstrip('\x00') for v in values)
    return b"".join(v.rstrip(b'\x00') for v in values)


def _decode_mapi_props(data, oem_codepage):
    """vegigmegy a MAPI property-listan, es kigyujti a szamunkra erdekes tageket.
    A visszaadott 'body'/'htmlbody' str, ha a property tipusa STRING/UNICODE_STRING
    volt (ekkor mar dekodolva van), egyebkent nyers bytes (ekkor a hivo fixhetul meg
    az internet_codepage alapjan, ha van ilyen property is a listaban)."""
    result = {}
    n = len(data)
    if n < 4:
        return result
    num_properties = _uint32(data, 0)[0]
    offset = 4
    for _ in range(num_properties):
        if offset + 4 > n:
            break
        attr_type = _uint16(data, offset)[0]
        offset += 2
        attr_name = _uint16(data, offset)[0]
        offset += 2

        # named (GUID-hoz kotott) property fejlec atugrasa, ha van:
        if attr_name >= GUID_EXISTS_FLAG:
            offset += 16  # guid
            kind = _uint32(data, offset)[0]
            offset += 4
            if kind == 0:
                offset += 4  # guid_prop (uint32)
            else:
                iid_len = _uint32(data, offset)[0]
                offset += 4
                pad = (-iid_len) % 4
                offset += iid_len + pad

        num_mv = None
        if MULTI_VALUE_FLAG & attr_type:
            attr_type ^= MULTI_VALUE_FLAG
            num_mv = _uint32(data, offset)[0]
            offset += 4

        fixed = _fixed_size(attr_type)
        values = []
        if fixed is not None:
            for _ in range(num_mv or 1):
                values.append(data[offset:offset + fixed])
                offset += fixed
        elif attr_type in (SZMAPI_STRING, SZMAPI_UNICODE_STRING, SZMAPI_OBJECT,
                           SZMAPI_BINARY, SZMAPI_UNSPECIFIED):
            values, offset = _skip_variable(data, offset, bool(num_mv), attr_type, oem_codepage)
        elif attr_type == SZMAPI_NULL:
            pass
        else:
            # ismeretlen tipus -> nem tudunk biztonsagosan tovabblepni, feladjuk
            return result

        # 2-byte padding parossag miatt (csak SHORT/BOOLEAN eseten, ahogy a tnefparse is csinalja)
        if (num_mv or 1) % 2 and attr_type in (SZMAPI_SHORT, SZMAPI_BOOLEAN):
            offset += 2

        if attr_name in (MAPI_BODY, MAPI_UNCOMPRESSED_BODY):
            result['body'] = _join(values)
        elif attr_name == MAPI_BODY_HTML:
            result['htmlbody'] = _join(values)
        elif attr_name == MAPI_RTF_COMPRESSED:
            result['rtfbody_compressed'] = b''.join(v.rstrip(b'\x00') for v in values)
        elif attr_name == MAPI_INTERNET_CODEPAGE and values:
            try:
                result['codepage'] = _codepage_name(struct.unpack('<I', values[0][:4])[0])
            except Exception:
                pass

    return result


def parse_tnef_body(data):
    """
    data: a teljes TNEF (winmail.dat) nyers tartalma.
    Visszaad egy dict-et: body, htmlbody (bytes), rtfbody_compressed (mindig bytes, LZFu-tomoritve), codepage (str vagy None),
    vagy None ha nem TNEF / hibas a signature.
    """
    if len(data) < 6 or _uint32(data, 0)[0] != TNEF_SIGNATURE:
        return None

    out = {'body': None, 'htmlbody': None, 'rtfbody_compressed': None, 'codepage': None}
    oem_codepage = 'cp1252'  # ATTOEMCODEPAGE hianyaban ez a TNEF-default
    offset = 6
    n = len(data)
    while offset + 11 < n:
        level = _uint8(data, offset)[0]
        name = _uint16(data, offset + 1)[0]
        length = _uint32(data, offset + 5)[0]
        obj_total = length + 11  # 9 byte fejlec + adat + 2 byte checksum
        obj_data = data[offset + 9: offset + 9 + length]

        if level == LVL_MESSAGE:
            if name == ATTOEMCODEPAGE and len(obj_data) >= 4:
                oem_codepage = _codepage_name(_uint32(obj_data, 0)[0])
            elif name == ATTMAPIPROPS:
                props = _decode_mapi_props(obj_data, oem_codepage)
                for k, v in props.items():
                    if v is not None:
                        out[k] = v
            elif name == ATTBODY and not out['body']:
                out['body'] = obj_data
        # LVL_ATTACHMENT es minden mas: nem erdekel minket, csak atugorjuk

        if obj_total <= 0:
            break  # vedelem vegtelen ciklus ellen hibas/korrupt adat eseten
        offset += obj_total

    return out


if __name__ == "__main__":
    import sys
    with open(sys.argv[1], "rb") as f:
        data = f.read()
    result = parse_tnef_body(data)
    if result is None:
        print("Nem TNEF fajl vagy hibas signature.")
    else:
        for k, v in result.items():
            if isinstance(v, bytes):
                print("%s: %d byte" % (k, len(v)))
            else:
                print("%s: %r" % (k, v))
