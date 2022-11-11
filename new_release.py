#%%
import re 
from subprocess import Popen

with open('pyproject.toml', 'r') as f: 
    data = f.read()
result = re.search("\nversion = \"(.*)\"", data)
old_version = result.group(1)
print(f'current version: {old_version}')

Popen(
    f'bumpversion patch --allow-dirty'.split(' '), 
).wait()

with open('pyproject.toml', 'r') as f: 
    data = f.read()

import re 
result = re.search("\nversion = \"(.*)\"", data)
version = result.group(1)

Popen(
    f'git push origin {version}'.split(' '), 
).wait()

print(f'done - updated to version {version}')
