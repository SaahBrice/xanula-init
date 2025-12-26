#!/usr/bin/env python
"""
Compile .po to .mo files without needing external gettext tools.
Based on Python's Tools/i18n/msgfmt.py
"""
import struct
import array
import os

def generate_mo(po_file, mo_file):
    """Generate .mo file from .po file."""
    MESSAGES = {}
    
    # Add metadata entry for UTF-8 encoding (empty string key is metadata)
    MESSAGES[''] = 'Content-Type: text/plain; charset=UTF-8\n'
    
    # Read and parse .po file
    with open(po_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Simple parser for msgid/msgstr pairs
    lines = content.split('\n')
    msgid = None
    msgstr = None
    in_msgid = False
    in_msgstr = False
    current_text = []
    
    for line in lines:
        line = line.strip()
        
        if line.startswith('msgid "'):
            if msgid is not None and msgstr is not None:
                MESSAGES[msgid] = msgstr
            msgid = None
            msgstr = None
            in_msgid = True
            in_msgstr = False
            current_text = [line[7:-1]]  # Remove 'msgid "' and trailing '"'
        elif line.startswith('msgstr "'):
            if in_msgid:
                msgid = ''.join(current_text)
            in_msgid = False
            in_msgstr = True
            current_text = [line[8:-1]]  # Remove 'msgstr "' and trailing '"'
        elif line.startswith('"') and line.endswith('"'):
            current_text.append(line[1:-1])
        elif line == '' or line.startswith('#'):
            if in_msgstr:
                msgstr = ''.join(current_text)
                if msgid is not None and msgstr is not None and msgid != '':
                    MESSAGES[msgid] = msgstr
                msgid = None
                msgstr = None
            in_msgid = False
            in_msgstr = False
            current_text = []
    
    # Don't forget the last entry
    if in_msgstr:
        msgstr = ''.join(current_text)
        if msgid is not None and msgstr is not None and msgid != '':
            MESSAGES[msgid] = msgstr
    
    # Unescape common sequences
    for key in list(MESSAGES.keys()):
        MESSAGES[key] = MESSAGES[key].replace('\\n', '\n').replace('\\"', '"')
        new_key = key.replace('\\n', '\n').replace('\\"', '"')
        if new_key != key:
            MESSAGES[new_key] = MESSAGES.pop(key)
    
    # Generate .mo file
    keys = sorted(MESSAGES.keys())
    offsets = []
    ids = b''
    strs = b''
    
    for key in keys:
        offsets.append((len(ids), len(key.encode('utf-8')), len(strs), len(MESSAGES[key].encode('utf-8'))))
        ids += key.encode('utf-8') + b'\x00'
        strs += MESSAGES[key].encode('utf-8') + b'\x00'
    
    # Generate the header
    keystart = 7 * 4 + 16 * len(keys)
    valuestart = keystart + len(ids)
    
    koffsets = []
    voffsets = []
    for o1, l1, o2, l2 in offsets:
        koffsets += [l1, o1 + keystart]
        voffsets += [l2, o2 + valuestart]
    
    offsets = koffsets + voffsets
    
    # The header
    output = struct.pack(
        'Iiiiiii',
        0x950412de,        # Magic
        0,                 # Version
        len(keys),         # Number of entries
        7 * 4,             # Offset of table with original strings
        7 * 4 + len(keys) * 8,  # Offset of table with translation strings
        0,                 # Size of hashing table
        0                  # Offset of hashing table
    )
    
    output += array.array('i', offsets).tobytes()
    output += ids
    output += strs
    
    # Write output
    with open(mo_file, 'wb') as f:
        f.write(output)
    
    return len(keys)

if __name__ == '__main__':
    po_file = os.path.join('locale', 'fr', 'LC_MESSAGES', 'django.po')
    mo_file = os.path.join('locale', 'fr', 'LC_MESSAGES', 'django.mo')
    
    count = generate_mo(po_file, mo_file)
    print(f'Compiled {count} translations to {mo_file}')

