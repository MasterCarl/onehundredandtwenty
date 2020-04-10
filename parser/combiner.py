import base64
import codecs
import json

import glob
import sys

lvs = {}

def load_file(filename):
    print(f"processing {filename}")
    with open(filename) as f:
        data = json.load(f)
        key: str
        for key, data in data.items():
            process_course_data(key, data)


def process_course_data(key, data):
    modules: list = data['modul']
    modules.sort()
    hashed_modules = sum([hash(m) for m in modules])  # let's ignore hash collisions
    encoded = base64.b32encode(hashed_modules.to_bytes(16, byteorder='big', signed=True))
    composite_key = key + '_' + encoded.decode() + '_' + str(data['cp'])
    composite_key = composite_key.replace(" ", "_").replace("(", "").replace(")", "").replace("=", "")
    existing = lvs.get(composite_key)
    if existing:
        # update values
        existing['dozent'].update(data['dozent'])
        assert existing['cp'] == data['cp']
        assert existing['benotet'] == data['benotet']
        check_module_consistency(existing, composite_key, data)
        existing['semester'].add(data['semester'].upper().replace("_", "/"))
    else:
        lvs[composite_key] = data
        dozent = lvs[composite_key]['dozent']
        lvs[composite_key]['dozent'] = set(dozent)
        semester = lvs[composite_key]['semester']
        lvs[composite_key]['semester'] = set()
        lvs[composite_key]['semester'].add(semester.upper().replace("_", "/"))
        lvs[composite_key]['kennung'] = list(set([name[:4] for name in modules]))


def check_module_consistency(existing, key, value):
    if existing['modul'] != value['modul']:
        print(f"Changed module values for {key}:\n"
              f"\t{', '.join(existing['semester'])}: {existing['modul']}\n"
              f"\t{value['semester']}: {value['modul']}",
              file=sys.stderr)


for filename in glob.iglob('*.json'):
    if filename[:2] in ["ws", "ss"]:
        load_file(filename)

# replace sets by lists for json encoding
for value in lvs.values():
    value['dozent'] = list(value['dozent'])
    value['semester'] = list(value['semester'])

with codecs.open("./combined.json", "w", encoding='utf-8') as f:
    f.write(json.dumps(lvs, ensure_ascii=False, indent=4))
