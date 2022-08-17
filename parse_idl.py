#%%
import json 

with open('src/driftpy/idl/clearing_house.json', 'r') as f:
    data = json.load(f)
list(data.keys())

#%%
tree = {}
def lookup_type_translation(parent, v):
    if v == 'publicKey': 
        return 'PublicKey'
    elif v in ['u64', 'u128', 'i128', 'i64', 'u32', 'i32', 'u16', 'i16', 'u8', 'i8']:
        return 'int'
    elif isinstance(v, dict): 
        if 'defined' in v: 
            tree[parent] = tree.get(parent, []) + [v['defined']]
            return v['defined']
        elif 'array' in v:
            list_type = lookup_type_translation(parent, v['array'][0]) 
            return f"list[{list_type}]"
        elif 'vec' in v:
            list_type = lookup_type_translation(parent, v['vec']) 
            return f"list[{list_type}]"
        else: 
            assert False, v
    elif v == 'bool':
        return 'bool'
    else: 
        assert False, v

tab = '    ' # tab = 4 spaces 

def generate_dataclass(account):
    dataclass = ''
    type = account['type']
    kind = type['kind']

    if kind == 'struct':
        dataclass = f"""@dataclass\nclass {account['name']}:\n"""
        for field in type['fields']:
            name = field['name']
            type = lookup_type_translation(account['name'], field['type'])
            dataclass += f"""{tab}{name}: {type}\n"""

    elif kind == 'enum':
        dataclass = f"""@_rust_enum\nclass {account['name']}:\n"""
        for v in type['variants']:
            dataclass += f"""{tab}{str.upper(v['name'])} = constructor()\n"""

    else: 
        assert False, account

    return dataclass

header = """\
from dataclasses import dataclass
from solana.publickey import PublicKey
from borsh_construct.enum import _rust_enum
from sumtypes import constructor
"""
header += '\n'

enums, structs = [], []
name2value = {}
name2kind = {}

for account in data['types'] + data['accounts']:
    dclass = generate_dataclass(account)

    kind = account['type']['kind']
    if kind == 'struct':
        structs.append(dclass)
    else:
        enums.append(dclass)
    name2value[account['name']] = dclass
    name2kind[account['name']] = kind

# enums have no dependencies so it goes at the top
for dclass in enums:
    header += f"{dclass} \n"

recorded_names = []
dclasses = []

def record_children(children):
    for child in children:
        if not child in recorded_names and name2kind[child] != 'enum':
            if child in tree: 
                record_children(tree[child])
            dclasses.append(name2value[child])
            recorded_names.append(child)

for name in tree.keys():
    children = tree[name]
    record_children(children)
    
    dclasses.append(name2value[name])
    recorded_names.append(name)
    
for dclass in dclasses:
    header += f"{dclass} \n"

with open('auto_types.py', 'w') as f: 
    f.write(header)

#%%
#%%
#%%
#%%
#%%