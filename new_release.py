#%%
import re 
from subprocess import Popen

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

print('done')