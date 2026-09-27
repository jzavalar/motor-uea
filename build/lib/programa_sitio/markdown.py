"""Lectura estructural de un programa analítico en Markdown.

No interpreta el contenido: solo reconoce su forma —secciones numeradas, tablas,
listas, párrafos que empiezan con una etiqueta en negritas y bloques de datos
ocultos— para que modelo.py pueda pedir «la tabla de la sección 7 cuyas columnas son
Núm., Fecha, …» sin depender de expresiones regulares sobre todo el documento."""

import re

import yaml

from .lexico import clave

RE_ENCABEZADO = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
RE_NUMERO = re.compile(r"^(?:(\d+(?:\.\d+)*)\.?|(Anexo [A-Z])\.?)\s+(.*)$")
RE_DATOS = re.compile(r"<!--\s*fuente-datos:\s*([\w-]+)\s*\n(.*?)-->", re.S)
RE_ETIQUETA = re.compile(r"^\*\*(.+?)\*\*[ \t]*(.*)$", re.S)


class Tabla:
    def __init__(self, encabezados, filas, linea):
        self.encabezados = encabezados
        self.claves = [clave(e) for e in encabezados]
        self.filas = filas
        self.linea = linea

    def registros(self, renombrar=None):
        renombrar = renombrar or {}
        claves = [renombrar.get(c, c) for c in self.claves]
        return [dict(zip(claves, f + [""] * (len(claves) - len(f)))) for f in self.filas]

    def tiene(self, columnas):
        """¿Contiene todas estas columnas (por nombre normalizado), en este orden?"""
        buscadas = [clave(c) for c in columnas]
        pos = 0
        for b in buscadas:
            try:
                pos = self.claves.index(b, pos) + 1
            except ValueError:
                return False
        return True


class Seccion:
    def __init__(self, nivel, titulo, linea):
        self.nivel = nivel
        self.titulo_completo = titulo
        m = RE_NUMERO.match(titulo)
        if m:
            self.numero = m.group(1) or m.group(2)
            self.titulo = m.group(3).strip()
        else:
            self.numero, self.titulo = None, titulo.strip()
        self.linea = linea          # línea del encabezado (0-based)
        self.fin = None             # primera línea que ya no le pertenece
        self.hijos = []
        self.padre = None

    def __repr__(self):
        return f"<Seccion {self.numero or ''} {self.titulo!r}>"


class Documento:
    def __init__(self, texto, nombre="programa analítico"):
        self.texto = texto
        self.nombre = nombre
        self.lineas = texto.split("\n")
        self.datos = self._datos_ocultos()
        self.secciones = []
        self.raiz = Seccion(0, "(documento)", -1)
        self._leer_secciones()

    # ------------------------------------------------------------- estructura

    def _datos_ocultos(self):
        datos = {}
        self.errores_datos = []
        for m in RE_DATOS.finditer(self.texto):
            try:
                datos[m.group(1)] = yaml.safe_load(m.group(2)) or {}
            except yaml.YAMLError as e:
                self.errores_datos.append(f"el bloque oculto «fuente-datos: {m.group(1)}» "
                                          f"no es YAML válido: {e}")
        return datos

    def _leer_secciones(self):
        pila = [self.raiz]
        en_codigo = False
        for i, l in enumerate(self.lineas):
            if l.lstrip().startswith(("```", "~~~")):
                en_codigo = not en_codigo
                continue
            if en_codigo:
                continue
            m = RE_ENCABEZADO.match(l)
            if not m:
                continue
            s = Seccion(len(m.group(1)), m.group(2).replace("**", ""), i)
            while pila[-1].nivel >= s.nivel:
                pila.pop().fin = i
            s.padre = pila[-1]
            pila[-1].hijos.append(s)
            pila.append(s)
            self.secciones.append(s)
        for s in pila[1:]:
            s.fin = len(self.lineas)
        self.raiz.fin = len(self.lineas)

    def seccion(self, clave_s):
        """Por número ('5.2', 'Anexo A') o, si no hay número, por título (sin acentos
        ni mayúsculas, al principio del título)."""
        if clave_s is None:
            return self.raiz
        for s in self.secciones:
            if s.numero == clave_s:
                return s
        buscada = clave(clave_s)
        for s in self.secciones:
            if clave(s.titulo).startswith(buscada):
                return s
        return None

    def texto_de(self, s, propio=False):
        """Texto de la sección sin su encabezado. propio=True: solo hasta el primer
        subapartado."""
        ini = s.linea + 1
        fin = s.hijos[0].linea if (propio and s.hijos) else s.fin
        return "\n".join(self.lineas[ini:fin])

    def markdown_de(self, s):
        """Encabezado incluido, tal como está en la fuente."""
        return "\n".join(self.lineas[s.linea:s.fin])

    # --------------------------------------------------------------- bloques

    def tablas(self, texto, desplazamiento=0):
        tablas, lineas, i = [], texto.split("\n"), 0
        while i < len(lineas):
            l = lineas[i].strip()
            if (l.startswith("|") and i + 1 < len(lineas)
                    and re.match(r"^\|?\s*:?-{3,}", lineas[i + 1].strip())):
                enc = _celdas(l)
                filas, j = [], i + 2
                while j < len(lineas) and lineas[j].strip().startswith("|"):
                    filas.append(_celdas(lineas[j].strip()))
                    j += 1
                tablas.append(Tabla(enc, filas, desplazamiento + i))
                i = j
            else:
                i += 1
        return tablas

    def tabla(self, columnas, seccion=None):
        """Primera tabla, dentro de la sección (o en todo el documento), que tenga
        estas columnas. None si no hay."""
        s = self.seccion(seccion) if seccion else self.raiz
        if s is None:
            return None
        texto = self.texto_de(s) if s is not self.raiz else self.texto
        for t in self.tablas(texto):
            if t.tiene(columnas):
                return t
        return None


def _celdas(linea):
    linea = linea.strip()
    if linea.startswith("|"):
        linea = linea[1:]
    if linea.endswith("|"):
        linea = linea[:-1]
    # Un «|» escapado (\|) no separa celdas.
    partes = re.split(r"(?<!\\)\|", linea)
    return [p.strip().replace("\\|", "|") for p in partes]


def parrafos(texto):
    """Bloques separados por líneas en blanco (las tablas y listas quedan enteras)."""
    return [p.strip() for p in re.split(r"\n[ \t]*\n", texto) if p.strip()]


def etiquetados(texto):
    """Párrafos que empiezan con una etiqueta en negritas: «**Propósito.** texto».

    Devuelve una lista de (etiqueta, texto_del_parrafo, bloque), donde bloque es todo lo
    que sigue a la etiqueta hasta la siguiente etiqueta en negritas al inicio de
    párrafo (incluye listas y tablas intermedias)."""
    ps = parrafos(texto)
    res = []
    for i, p in enumerate(ps):
        m = RE_ETIQUETA.match(p)
        if not m or not re.search(r"[.:]$", m.group(1).strip()):
            continue
        etiqueta = m.group(1).strip().rstrip(".:").strip()
        cuerpo = m.group(2).strip()
        bloque = [cuerpo]
        for q in ps[i + 1:]:
            mq = RE_ETIQUETA.match(q)
            if (mq and re.search(r"[.:]$", mq.group(1).strip())) or RE_ENCABEZADO.match(q):
                break
            bloque.append(q)
        res.append((etiqueta, cuerpo, "\n\n".join(bloque)))
    return res


def vinetas(texto):
    return [l.strip()[2:].strip() for l in texto.split("\n")
            if re.match(r"^\s*[-*·•]\s+", l)]


def numerada(texto):
    items = []
    for l in texto.split("\n"):
        m = re.match(r"\s*\d+\.\s+(.+)$", l)
        if m:
            items.append(m.group(1).strip())
    return items


def items_parentesis(texto):
    """'(1) texto uno. (2) texto dos (insumo de P2).' -> [(texto, 'P2' | None), ...]"""
    crudos = re.findall(r"\(\d+\)\s*(.*?)(?=\s\(\d+\)|\Z)", texto, re.S)
    items = []
    for c in crudos:
        c = " ".join(c.split()).strip()
        if c.endswith("."):
            c = c[:-1]
        m = re.match(r"^(.*?)\s*\(insumo de (P\d+)\)$", c)
        items.append((m.group(1).strip(), m.group(2)) if m else (c, None))
    return items


def partir_nivel_cero(texto, separador=";"):
    """Divide por el separador solo fuera de paréntesis."""
    partes, actual, nivel = [], [], 0
    for ch in texto:
        if ch in "([":
            nivel += 1
        elif ch in ")]":
            nivel = max(0, nivel - 1)
        if ch == separador and nivel == 0:
            partes.append("".join(actual))
            actual = []
        else:
            actual.append(ch)
    partes.append("".join(actual))
    return [p.strip() for p in partes if p.strip()]


def texto_plano(celda):
    """Quita el formato Markdown de una celda: enlaces, negritas, cursivas."""
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", celda)
    t = re.sub(r"\*\*|__|(?<!\w)\*(?!\s)|(?<!\s)\*(?!\w)", "", t)
    return t.replace("\\@", "@").strip()
