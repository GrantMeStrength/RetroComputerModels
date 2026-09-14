"""Keyboard layouts and source-photo regions for the two British models."""

BBC_PANEL_COLOR = (32, 30, 26)
BBC_EDITING_COLOR = (96, 94, 86)
BBC_CASE_WIDTH = .411
BBC_CAP_DEPTH = .0175
BBC_CAP_INSET_X = .0032
BBC_CAP_INSET_Y = .0024
BBC_CURSOR_LABELS = {"LEFT", "RIGHT", "UP", "DOWN"}
BBC_SHIFTED_LEGENDS = {
    "1": "!", "2": '"', "3": "#", "4": "$", "5": "%", "6": "&",
    "7": "'", "8": "(", "9": ")", "-": "=", "^": "~", "\\": "|",
    "[": "{", "_": "\u00a3", ";": "+", ":": "*", "]": "}",
    ",": "<", ".": ">", "/": "?",
}
BBC_PITCH = 4.75
BBC_F0_X = -20.7908068

BBC_ROWS = [
    (-34.397, -15.4456, ["ESCAPE", *list("1234567890"), "-", "^", "\\", "LEFT", "RIGHT"]),
    (-34.5594, -20.1058, [("TAB", 1.5), *list("QWERTYUIOP"), "@", "[", "_", "UP", "DOWN"]),
    (-34.5, -24.7686, [("CAPS\nLOCK", 1.5), *list("ASDFGHJKL"), ";", ":", "]", ("RETURN", 2.5)]),
    (-35.6356, -29.4315, ["SHIFT\nLOCK", ("SHIFT", 1.25), *list("ZXCVBNM"),
                         ",", ".", "/", ("SHIFT", 1.75), "DELETE", "COPY"]),
]


def bbc_keys():
    keys = []
    for left, y, row in BBC_ROWS:
        x = left
        for item in row:
            label, units = item if isinstance(item, tuple) else (item, 1)
            keys.append((label, x + units * 4.75 / 2, y, units * 4.75 - .55))
            x += units * 4.75
    keys += [(f"f{i}", BBC_F0_X + i * BBC_PITCH, -10.7240262, 4.2) for i in range(10)]
    keys += [("BREAK", BBC_F0_X + 10 * BBC_PITCH, -10.7240262, 4.2),
             ("CTRL", -28, -34.09, 4.2), ("SPACE", 3.875, -34.09, 42.2)]
    assert len(keys) == 74
    return keys


def rectangle(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def cpc_keys():
    keys = [("ESC", rectangle(92, 134, 130, 171))]
    for i, label in enumerate([*list("1234567890"), "-", "^"]):
        x = 132 + i * 39
        keys.append((label, rectangle(x, 134, x + 37, 171)))
    keys += [("CLR", rectangle(599, 134, 635, 171)), ("DEL", rectangle(637, 134, 693, 171)),
             ("TAB", rectangle(93, 174, 149, 210))]
    for i, label in enumerate([*list("QWERTYUIOP"), "@", "["]):
        x = 151 + i * 39
        keys.append((label, rectangle(x, 174, x + 37, 210)))
    keys += [("ENTER", [(618, 173), (694, 173), (694, 249),
                       (628, 249), (628, 212), (618, 212)]),
             ("CAPS LOCK", rectangle(92, 212, 159, 249))]
    for i, label in enumerate([*list("ASDFGHJKL"), ":", ";", "]"]):
        x = 161 + i * 39
        keys.append((label, rectangle(x, 212, x + 37, 249)))
    keys.append(("LEFT SHIFT", rectangle(92, 251, 178, 288)))
    for i, label in enumerate([*list("ZXCVBNM"), ",", ".", "/", "\\"]):
        x = 180 + i * 39
        keys.append((label, rectangle(x, 251, x + 37, 287)))
    keys += [("RIGHT SHIFT", rectangle(608, 251, 693, 287)),
             ("SPACE", rectangle(217, 290, 567, 327)),
             ("CTRL", rectangle(569, 290, 606, 326))]
    keys += [(label, rectangle(*bounds)) for label, bounds in [
        ("UP", (773, 45, 810, 81)), ("LEFT", (733, 83, 771, 120)),
        ("COPY", (773, 83, 810, 120)), ("RIGHT", (812, 83, 850, 120)),
        ("DOWN", (773, 123, 810, 159))]]
    for row, labels in enumerate((["7", "8", "9"], ["4", "5", "6"], ["1", "2", "3"], ["0", ".", "ENTER"])):
        for column, label in enumerate(labels):
            x, y = 733 + column * 39.5, 173 + row * 39
            keys.append(("NUM " + label, rectangle(x, y, x + 37, y + 36)))
    assert len(keys) == 74
    return keys


CPC_BODY_CROP = (31, 29, 1168, 355)
