"""Minimaler PHP serialize()/unserialize()-kompatibler Codec.

Wird fuer die WordPress.org Plugin-/Theme-API gebraucht
(api.wordpress.org/plugins/info/1.0/): der Endpunkt nimmt Anfragen im
PHP-serialize-Format entgegen und liefert Antworten im selben Format - kein
JSON. Das ist auch die Art, wie WordPress selbst intern damit spricht (siehe
wp-admin/includes/plugin-install.php, plugins_api(): 'request' wird per
serialize((object) $args) gebaut, die Antwort per unserialize() gelesen).
Pythons Standardbibliothek hat dafuer keine Unterstuetzung.

Bewusst kein PyPI-Paket (z.B. phpserialize) fuer diesen einen, eng
begrenzten Anwendungsfall - das deckt exakt ab, was die Plugin-/Theme-API
tatsaechlich verwendet (Strings, Integer, Arrays, stdClass-Objekte).
"""

from typing import Any


def dumps_request(args: dict) -> bytes:
    """Serialisiert ein flaches dict als PHP-Objekt (stdClass) - exakt das
    Format, das WordPress selbst als 'request' an die Plugin-/Theme-API
    sendet."""
    body = b"".join(_dump_value(key) + _dump_value(value) for key, value in args.items())
    class_name = b"stdClass"
    return b'O:%d:"%s":%d:{%s}' % (len(class_name), class_name, len(args), body)


def _dump_value(value: Any) -> bytes:
    if isinstance(value, bool):
        return b"b:%d;" % (1 if value else 0)
    if isinstance(value, int):
        return b"i:%d;" % value
    if isinstance(value, float):
        return str(f"d:{value!r};").encode("ascii")
    if value is None:
        return b"N;"
    if isinstance(value, str):
        encoded = value.encode("utf-8")
        return b's:%d:"%s";' % (len(encoded), encoded)
    raise TypeError(f"Nicht unterstützter Typ für PHP-Serialisierung: {type(value)}")


class _Parser:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def parse(self) -> Any:
        kind = self.data[self.pos : self.pos + 1]

        if kind == b"N":
            self._expect(b"N;")
            return None
        if kind == b"b":
            self._expect(b"b:")
            val = self._read_until(b";")
            return val == b"1"
        if kind == b"i":
            self._expect(b"i:")
            return int(self._read_until(b";"))
        if kind == b"d":
            self._expect(b"d:")
            return float(self._read_until(b";"))
        if kind == b"s":
            self._expect(b"s:")
            length = int(self._read_until(b":"))
            self._expect(b'"')
            val = self.data[self.pos : self.pos + length]
            self.pos += length
            self._expect(b'"')
            self._expect(b";")
            return val.decode("utf-8", errors="replace")
        if kind in (b"a", b"O"):
            if kind == b"a":
                self._expect(b"a:")
            else:
                self._expect(b"O:")
                name_len = int(self._read_until(b":"))
                self._expect(b'"')
                self.pos += name_len  # Klassenname wird ignoriert (immer stdClass hier)
                self._expect(b'"')
                self._expect(b":")
            count = int(self._read_until(b":"))
            self._expect(b"{")
            result = {}
            for _ in range(count):
                key = self.parse()
                result[key] = self.parse()
            self._expect(b"}")
            return result

        raise ValueError(
            f"Unbekannter PHP-serialize-Typ an Position {self.pos}: {self.data[self.pos:self.pos + 20]!r}"
        )

    def _expect(self, token: bytes) -> None:
        if self.data[self.pos : self.pos + len(token)] != token:
            raise ValueError(
                f"Erwartetes Token {token!r} an Position {self.pos} nicht gefunden: "
                f"{self.data[self.pos:self.pos + 20]!r}"
            )
        self.pos += len(token)

    def _read_until(self, sep: bytes) -> bytes:
        idx = self.data.index(sep, self.pos)
        val = self.data[self.pos : idx]
        self.pos = idx + len(sep)
        return val


def loads(data: bytes) -> Any:
    """Parst PHP serialize()-Daten. PHP-Arrays UND -Objekte werden beide als
    Python-dict zurückgegeben (Arrays mit int-Keys 0..n-1 bei indizierten
    Arrays) - für die Zwecke dieses Codecs (Marketplace-API lesen) reicht
    das, eine echte Objekt/Array-Unterscheidung ist hier nicht nötig."""
    return _Parser(data).parse()
