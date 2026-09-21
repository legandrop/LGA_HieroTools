"""
____________________________________________________________________

  LGA_NKS_StyleUtils v1.03 | Lega

  Utilidades para estilos dinámicos de botones en paneles Hiero.
  Incluye funciones para conversión de colores, cálculo de bordes
  dinámicos y gradientes.

  Usado por runtime activo:
  - LGA_NKS_Assignee_Panel.py
  - LGA_NKS_ClipColor_Panel.py
  - LGA_NKS_Coordination_Panel.py
  - LGA_NKS_Edit_Panel.py
  - LGA_NKS_Flow_Panel.py
  - LGA_NKS_Projects_Panel.py
  - LGA_NKS_Review_Panel.py
  - LGA_NKS_ViewerTL_Panel.py

  v1.03: Suma la hoja reutilizable de botones cuyo fondo es un color de dato.
  v1.02: Los gradientes pasan a un catalogo semantico reutilizable. Suma los
         cruces Flow-Priority y Flow-Reveal del panel Flow S3.
  v1.01: Agregadas luminance(), ensure_min_luminance() y ensure_max_luminance().
         Piso y techo de luminancia para que los colores de Flow se lean tanto
         cuando van como texto sobre fondo oscuro (Projects Panel) como cuando
         van de fondo con texto claro encima (Assignee Panel, Flow Rev Panel).
  v1.00: Versión inicial
____________________________________________________________________

"""

import re


# Colores de categoria del panel Flow S3. Son informacion visual: el verde
# identifica acciones de Flow, el violeta acciones S3 y los dos gradientes
# mixtos conservan el verde para indicar que siguen perteneciendo a Flow.
GRADIENT_COLORS = {
    "gradient_magenta_violet": ("#443a91", "#543a91", "#5b3a91"),
    "gradient_flow_priority": ("#2a4d3a", "#450101"),
    "gradient_flow_reveal": ("#2a4d3a", "#1f1f1f"),
}


# Geometria y texto de los botones compactos de los paneles dockeados. Los
# colores de fondo llegan como datos de cada panel; esta caja debe quedar igual
# en Edit, Flow y ClipColor para que no parezcan interfaces distintas.
PANEL_BUTTON_TEXT_COLOR = "#d8d8d8"
PANEL_BUTTON_MIN_HEIGHT = 20
PANEL_BUTTON_RADIUS = 3


# Funciones de conversión de colores
def hex_to_rgb(hex_color):
    """Convierte color hex a RGB (0-255)"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    """Convierte RGB (0-255) a hex"""
    return '#{:02x}{:02x}{:02x}'.format(*rgb)


def rgb_to_hsv(r, g, b):
    """Convierte RGB (0-255) a HSV (0-360, 0-100, 0-100)"""
    r, g, b = r/255.0, g/255.0, b/255.0
    mx = max(r, g, b)
    mn = min(r, g, b)
    df = mx - mn

    if mx == mn:
        h = 0
    elif mx == r:
        h = (60 * ((g - b) / df) + 360) % 360
    elif mx == g:
        h = (60 * ((b - r) / df) + 120) % 360
    elif mx == b:
        h = (60 * ((r - g) / df) + 240) % 360

    if mx == 0:
        s = 0
    else:
        s = (df / mx) * 100

    v = mx * 100
    return h, s, v


def hsv_to_rgb(h, s, v):
    """Convierte HSV (0-360, 0-100, 0-100) a RGB (0-255)"""
    h, s, v = h, s/100.0, v/100.0

    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c

    if 0 <= h < 60:
        r, g, b = c, x, 0
    elif 60 <= h < 120:
        r, g, b = x, c, 0
    elif 120 <= h < 180:
        r, g, b = 0, c, x
    elif 180 <= h < 240:
        r, g, b = 0, x, c
    elif 240 <= h < 300:
        r, g, b = x, 0, c
    elif 300 <= h < 360:
        r, g, b = c, 0, x
    else:
        r, g, b = 0, 0, 0

    r = int((r + m) * 255)
    g = int((g + m) * 255)
    b = int((b + m) * 255)

    return r, g, b


# Legibilidad: piso y techo de luminancia
#
# Los colores de proyecto y de usuario salen de Flow, donde se eligen como color
# IDENTITARIO y no pensando en sobre que se van a pintar. En los paneles se usan
# de dos formas opuestas, y cada una falla por una punta distinta:
#
#   - Como COLOR DE TEXTO sobre el panel oscuro (Projects Panel): los colores
#     oscuros no se leen -> hace falta un PISO de luminancia.
#   - Como COLOR DE FONDO con texto claro encima (Assignee Panel, Flow Rev Panel):
#     los colores claros no se leen -> hace falta un TECHO.
#
# Las dos funciones son la misma operacion espejada, por eso viven juntas: si
# manana se cambia el criterio (por ejemplo pasar a contraste WCAG en vez de
# luminancia cruda), se cambia una vez y vale para los tres paneles.

# Rec. 709. Se trabaja en escala 0-255 para poder compararla de un vistazo
# contra los valores RGB del color.
LUMINANCE_R = 0.2126
LUMINANCE_G = 0.7152
LUMINANCE_B = 0.0722

# Si el color es practicamente gris no hay tono que preservar, y escalarle el
# brillo lo manda a blanco o negro puro. Por debajo de esta diferencia entre el
# canal mas alto y el mas bajo, se resuelve con un gris del limite.
UMBRAL_ACROMATICO = 8


def luminance(color):
    """Luminancia percibida (Rec. 709) de un '#RRGGBB', en escala 0-255."""
    rgb = _color_a_rgb(color)
    if rgb is None:
        return None
    r, g, b = rgb
    return LUMINANCE_R * r + LUMINANCE_G * g + LUMINANCE_B * b


def _color_a_rgb(color):
    """'#RRGGBB' -> (r, g, b), o None si el formato no sirve."""
    if not color or not isinstance(color, str):
        return None
    color = color.strip()
    if not color.startswith('#') or len(color) != 7:
        return None
    try:
        return hex_to_rgb(color)
    except ValueError:
        return None


def _gris(nivel):
    nivel = max(0, min(255, int(round(nivel))))
    return '#{0:02X}{0:02X}{0:02X}'.format(nivel)


def ensure_min_luminance(color, min_luminance):
    """
    Aclara el color hasta el piso, respetando el tono. Para TEXTO DE COLOR sobre
    fondo oscuro.

    Dos etapas, en este orden para no desaturar de mas:
      1. Sube el brillo al maximo manteniendo tono y saturacion (escala el RGB
         hasta que el canal mas alto llegue a 255). #9E3A3A -> #FF5E5E.
      2. Si con eso todavia no alcanza, recien ahi mezcla hacia blanco lo justo
         y necesario. #FF5E5E -> #FF7A7A.

    Mezclar con blanco desde el principio daria un pastel lavado (#C58989) y
    perderia la identidad del color.

    Devuelve el color sin tocar si ya cumple, o si el formato no es valido.
    """
    rgb = _color_a_rgb(color)
    if rgb is None:
        return color

    r, g, b = rgb
    if luminance(color) >= min_luminance:
        return color

    canal_max = max(r, g, b)
    if canal_max - min(r, g, b) <= UMBRAL_ACROMATICO:
        return _gris(min_luminance)

    escala = 255.0 / canal_max
    r = min(255, int(round(r * escala)))
    g = min(255, int(round(g * escala)))
    b = min(255, int(round(b * escala)))

    lum = LUMINANCE_R * r + LUMINANCE_G * g + LUMINANCE_B * b
    if lum < min_luminance:
        # La luminancia es lineal en la mezcla, asi que el factor sale directo.
        factor = (min_luminance - lum) / (255.0 - lum) if lum < 255 else 0
        factor = max(0.0, min(1.0, factor))
        r = min(255, int(round(r + (255 - r) * factor)))
        g = min(255, int(round(g + (255 - g) * factor)))
        b = min(255, int(round(b + (255 - b) * factor)))

    return '#{:02X}{:02X}{:02X}'.format(r, g, b)


def ensure_max_luminance(color, max_luminance):
    """
    Oscurece el color hasta el techo, respetando el tono. Para COLOR DE FONDO
    con texto claro encima.

    Es el espejo de ensure_min_luminance(), pero mas simple: escalar el RGB
    hacia abajo baja el brillo manteniendo tono y saturacion, y siempre alcanza
    (el limite es el negro). No hace falta una segunda etapa.

    Devuelve el color sin tocar si ya cumple, o si el formato no es valido.
    """
    rgb = _color_a_rgb(color)
    if rgb is None:
        return color

    lum = luminance(color)
    if lum <= max_luminance:
        return color

    r, g, b = rgb
    if max(r, g, b) - min(r, g, b) <= UMBRAL_ACROMATICO:
        return _gris(max_luminance)

    # La luminancia es lineal en el escalado, asi que el factor es exacto.
    factor = max_luminance / lum
    r = max(0, int(round(r * factor)))
    g = max(0, int(round(g * factor)))
    b = max(0, int(round(b * factor)))

    return '#{:02X}{:02X}{:02X}'.format(r, g, b)


# Funciones para gradientes
def extract_gradient_colors(gradient_css):
    """Extrae colores hex de una definición de gradiente CSS"""
    # Buscar patrones como stop: 0 #color, stop: 1 #color
    color_pattern = r'stop:\s*\d+\s*#([a-fA-F0-9]{6})'
    matches = re.findall(color_pattern, gradient_css)
    return ['#' + color for color in matches]


# Funciones para estilos dinámicos
def debug_color_conversion(hex_color):
    """Función de debug para verificar conversiones de color"""
    print(f"Input color: {hex_color}")
    r, g, b = hex_to_rgb(hex_color)
    print(f"RGB: ({r}, {g}, {b})")
    h, s, v = rgb_to_hsv(r, g, b)
    print(f"HSV: ({h:.2f}, {s:.2f}, {v:.2f})")

    # Aumentar value
    new_v = min(100, v + 20)
    print(f"New V: {new_v:.2f}")
    new_r, new_g, new_b = hsv_to_rgb(h, s, new_v)
    result = rgb_to_hex((new_r, new_g, new_b))
    print(f"Result color: {result}")
    return result

def calculate_dynamic_border(style):
    """
    Calcula un color de borde dinámico basado en el estilo del botón.
    Para gradientes, usa el color con mayor brillo (value).
    Para colores sólidos, aumenta el brillo manteniendo hue/saturación.
    """
    if style.startswith("gradient_"):
        # Para gradientes, extraer colores y usar el más brillante
        gradient_colors = GRADIENT_COLORS.get(style, ())

        if not gradient_colors:
            return "#616161"  # Color fallback

        # Encontrar el color con mayor value (brillo)
        max_value = 0
        brightest_color = gradient_colors[0]

        for color in gradient_colors:
            r, g, b = hex_to_rgb(color)
            h, s, v = rgb_to_hsv(r, g, b)
            if v > max_value:
                max_value = v
                brightest_color = color

        base_color = brightest_color
    else:
        # Para colores sólidos, usar el color directamente
        base_color = style

    # Convertir a HSV y aumentar el value (brillo) en un 20%
    r, g, b = hex_to_rgb(base_color)
    h, s, v = rgb_to_hsv(r, g, b)

    # Aumentar el brillo pero mantener hue y saturación
    new_v = min(100, v + 20)  # Aumentar value máximo 20 puntos

    # Convertir de vuelta a RGB y hex
    new_r, new_g, new_b = hsv_to_rgb(h, s, new_v)
    return rgb_to_hex((new_r, new_g, new_b))


def calculate_dynamic_hover(style):
    """
    Calcula colores hover dinámicos más brillantes que los bordes.
    Para gradientes, crea un gradiente más brillante.
    Para colores sólidos, color más brillante que el borde.
    """
    if style.startswith("gradient_"):
        # Para gradientes, crear versión más brillante de todo el gradiente
        base_colors = GRADIENT_COLORS.get(style)
        if not base_colors:
            return None

        hover_colors = []
        for color in base_colors:
            r, g, b = hex_to_rgb(color)
            h, s, v = rgb_to_hsv(r, g, b)
            # Aumentar brillo más que el borde (26% en lugar de 20%)
            new_v = min(100, v + 26)
            new_r, new_g, new_b = hsv_to_rgb(h, s, new_v)
            hover_colors.append(rgb_to_hex((new_r, new_g, new_b)))

        return {
            "inicio": hover_colors[0],
            "medio": hover_colors[len(hover_colors) // 2],
            "fin": hover_colors[-1],
        }

    else:
        # Para colores sólidos, hacer hover aún más brillante que el borde
        base_color = style
        r, g, b = hex_to_rgb(base_color)
        h, s, v = rgb_to_hsv(r, g, b)

        # El borde ya es +20%, el hover será +28% para ser más brillante pero no tanto
        new_v = min(100, v + 28)

        new_r, new_g, new_b = hsv_to_rgb(h, s, new_v)
        return rgb_to_hex((new_r, new_g, new_b))


def calculate_dynamic_pressed(style):
    """Oscurece un color solido para dar feedback al presionar un boton."""
    r, g, b = hex_to_rgb(style)
    h, s, v = rgb_to_hsv(r, g, b)
    new_r, new_g, new_b = hsv_to_rgb(h, s, max(0, v - 8))
    return rgb_to_hex((new_r, new_g, new_b))


def create_data_button_stylesheet(
    background_color,
):
    """
    Hoja comun para un boton cuyo fondo representa un DATO y no un rol de UI.

    Los colores de estado y de clip no pueden reemplazarse por `Style.BTN_*`:
    la informacion se perderia. La caja compacta, el contraste, el hover y el
    foco permanecen centralizados para que se lea como los demas paneles.
    """
    border_color = calculate_dynamic_border(background_color)
    hover_color = calculate_dynamic_hover(background_color)
    pressed_color = calculate_dynamic_pressed(background_color)

    return """
QPushButton {
    background-color: %(background)s;
    border: 1px solid %(border)s;
    border-radius: %(radius)dpx;
    color: %(text)s;
    min-height: %(height)dpx;
    padding: 0px;
}
QPushButton:hover { background-color: %(hover)s; }
QPushButton:pressed { background-color: %(pressed)s; }
QPushButton:focus { border: 2px solid %(hover)s; }
""" % {
        "background": background_color,
        "border": border_color,
        "radius": PANEL_BUTTON_RADIUS,
        "text": PANEL_BUTTON_TEXT_COLOR,
        "height": PANEL_BUTTON_MIN_HEIGHT,
        "hover": hover_color,
        "pressed": pressed_color,
    }


def calculate_dynamic_tooltip(style):
    """
    Calcula colores de tooltip dinámicos basados en el color del botón.
    Crea tooltips que respeten el color del botón y mantengan buena legibilidad.
    """
    if style.startswith("gradient_"):
        # Para gradientes, usar el color más brillante como base
        gradient_colors = GRADIENT_COLORS.get(
            style, GRADIENT_COLORS["gradient_magenta_violet"]
        )
        base_color = max(
            gradient_colors,
            key=lambda color: rgb_to_hsv(*hex_to_rgb(color))[2],
        )
    else:
        # Para colores sólidos, usar el color del botón
        base_color = style

    # Calcular colores del tooltip
    r, g, b = hex_to_rgb(base_color)
    h, s, v = rgb_to_hsv(r, g, b)

    # Fondo: ligeramente más oscuro que el botón para contraste
    bg_v = max(10, v - 8)  # Reducir brillo para fondo (menos oscuro)
    bg_r, bg_g, bg_b = hsv_to_rgb(h, s, bg_v)
    background_color = rgb_to_hex((bg_r, bg_g, bg_b))

    # Borde: usar el borde dinámico del botón
    border_color = calculate_dynamic_border(style)

    # Texto: blanco para máximo contraste
    text_color = "#ffffff"

    return {
        "background": background_color,
        "border": border_color,
        "text": text_color
    }


def create_tooltip_stylesheet(style):
    """
    Crea un stylesheet CSS completo para tooltip basado en el color del botón.
    """
    colors = calculate_dynamic_tooltip(style)
    return f"""
        QToolTip {{
            color: {colors['text']};
            background-color: {colors['background']};
            border: 1px solid {colors['border']};
            border-radius: 3px;
            padding: 4px;
        }}
    """


# Función para crear estilos de gradiente completos (opcional, para reutilización)
def create_gradient_style(gradient_type, include_hover=True):
    """
    Crea un estilo CSS completo para un gradiente específico.
    Útil para reutilizar en múltiples paneles.
    """
    colors = GRADIENT_COLORS.get(gradient_type)
    if not colors:
        return None

    border_color = calculate_dynamic_border(gradient_type)

    def gradient_stops(gradient_colors):
        if len(gradient_colors) == 1:
            positions = [0.0]
        else:
            positions = [
                index / float(len(gradient_colors) - 1)
                for index in range(len(gradient_colors))
            ]
        return ",\n                ".join(
            "stop: {:.3g} {}".format(position, color)
            for position, color in zip(positions, gradient_colors)
        )

    base_stops = gradient_stops(colors)

    style = f"""
        QPushButton {{
            background-color: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 0,
                {base_stops}
            );
            border: 1px solid {border_color};
            border-radius: 3px;
            color: #d8d8d8;
            padding: 0px 0px;
            min-height: 20px;
        }}
    """

    if include_hover:
        hover_map = calculate_dynamic_hover(gradient_type)
        if hover_map:
            hover_colors = []
            for color in colors:
                r, g, b = hex_to_rgb(color)
                h, s, v = rgb_to_hsv(r, g, b)
                new_r, new_g, new_b = hsv_to_rgb(h, s, min(100, v + 26))
                hover_colors.append(rgb_to_hex((new_r, new_g, new_b)))
            hover_stops = gradient_stops(hover_colors)
            style += f"""
        QPushButton:hover {{
            background-color: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 0,
                {hover_stops}
            );
        }}
            """

    # El estado pressed conserva la direccion semantica. Invertirla haria que
    # Priority dejara de anclar Flow a la izquierda durante el click.
    pressed_colors = []
    for color in colors:
        r, g, b = hex_to_rgb(color)
        h, s, v = rgb_to_hsv(r, g, b)
        new_r, new_g, new_b = hsv_to_rgb(h, s, max(0, v - 8))
        pressed_colors.append(rgb_to_hex((new_r, new_g, new_b)))
    pressed_stops = gradient_stops(pressed_colors)
    style += f"""
        QPushButton:pressed {{
            background-color: qlineargradient(
                x1: 0, y1: 1, x2: 1, y2: 0,
                {pressed_stops}
            );
        }}
    """

    return style
