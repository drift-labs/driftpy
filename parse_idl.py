#%%
import json 
import re 

input_idl = 'src/driftpy/idl/drift.json'
output_file = 'src/driftpy/types.py'

with open(input_idl, 'r') as f:
    data = json.load(f)
list(data.keys())

#%%
def to_snake_case(v):
    snake_v = re.sub(r'(?<!^)(?=[A-Z])', '_', v).lower()
    return snake_v

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
        elif 'option' in v:
            list_type = lookup_type_translation(parent, v['option']) 
            return f"Optional[{list_type}]"
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
            name = to_snake_case(field['name'])
            type = lookup_type_translation(account['name'], field['type'])
            dataclass += f"""{tab}{name}: {type}\n"""

    elif kind == 'enum':
        dataclass = f"""@_rust_enum\nclass {account['name']}:\n"""
        for v in type['variants']:
            name = to_snake_case(v['name'])
            dataclass += f"""{tab}{str.upper(name)} = constructor()\n"""

    else: 
        assert False, account

    return dataclass

file_contents = """\
from dataclasses import dataclass
from solana.publickey import PublicKey
from borsh_construct.enum import _rust_enum
from sumtypes import constructor
from typing import Optional
"""
file_contents += '\n'

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
    file_contents += f"{dclass} \n"

recorded_names = []
def record_struct(name):
    global file_contents

    children = tree[name]
    for child in children:
        if child not in recorded_names and name2kind[child] != 'enum':
            if child in tree: 
                record_struct(child)

            file_contents += f"{name2value[child]} \n"
            recorded_names.append(child)

    file_contents += f"{name2value[name]} \n"
    recorded_names.append(name)

# tree records the structs dependencies on other structs 
# ie, tree[Market] = [..., AMM, ...] - so we want to define AMM first then Market
for name in tree.keys():
    record_struct(name)

flat_tree = []
for name in tree.keys():
    for child in tree[name]:
        flat_tree.append(child)
    flat_tree.append(name)

for name in name2value.keys():
    if name not in flat_tree and name2kind[name] == 'struct':
        # record types which dont have any dependencies 
        file_contents += f"{name2value[name]} \n"

with open(output_file, 'w') as f: 
    f.write(file_contents)

print('done! :)')